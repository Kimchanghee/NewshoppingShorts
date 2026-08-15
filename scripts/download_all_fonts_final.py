#!/usr/bin/env python3
"""Synchronize the exact font assets declared in ``config.font_catalog``."""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
import tempfile
import urllib.request
from urllib.parse import urljoin, urlparse
import zipfile
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.font_catalog import (  # noqa: E402
    BROWSER_USER_AGENT,
    DEFAULT_FONTS_DIR,
    DEFAULT_LICENSES_DIR,
    FONT_CHOICES,
    FontAsset,
)
from scripts.verify_font_assets import (  # noqa: E402
    verify_font_directory,
    verify_font_file,
)


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

_FONT_REDIRECT_HOSTS = {
    "github.com": frozenset({
        "github.com",
        "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
    }),
    "gongu.copyright.or.kr": frozenset({
        "gongu.copyright.or.kr",
        "www.copyright.or.kr",
    }),
}


def _approved_download_hosts(url: str) -> frozenset[str]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"font source has an invalid port: {url}") from exc
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username
        or parsed.password
        or port not in (None, 443)
    ):
        raise ValueError(f"font source must be an absolute HTTPS URL: {url}")
    return _FONT_REDIRECT_HOSTS.get(host, frozenset({host}))


def _validate_download_url(url: str, approved_hosts: frozenset[str]) -> None:
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"font redirect destination has an invalid port: {url}") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.hostname.lower() not in approved_hosts
        or parsed.username
        or parsed.password
        or port not in (None, 443)
    ):
        raise ValueError(f"font redirect destination is not approved: {url}")


class _ApprovedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, approved_hosts: frozenset[str]):
        self._approved_hosts = approved_hosts
        super().__init__()

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        destination = urljoin(req.full_url, newurl)
        _validate_download_url(destination, self._approved_hosts)
        return super().redirect_request(req, fp, code, msg, headers, destination)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_download(path: Path, size: int, sha256: str, label: str) -> None:
    actual_size = path.stat().st_size
    if actual_size != size:
        raise ValueError(f"{label}: size {actual_size} != {size}")
    actual_hash = _sha256(path)
    if actual_hash != sha256:
        raise ValueError(f"{label}: sha256 {actual_hash} != {sha256}")


def _download(
    url: str,
    directory: Path,
    *,
    browser_user_agent: bool,
    max_bytes: int,
) -> Path:
    approved_hosts = _approved_download_hosts(url)
    _validate_download_url(url, approved_hosts)
    fd, raw_path = tempfile.mkstemp(prefix=".font-download-", dir=directory)
    os.close(fd)
    path = Path(raw_path)
    headers = {
        "User-Agent": BROWSER_USER_AGENT if browser_user_agent else "SSMaker-Font-Sync/1.0",
        "Accept": "*/*",
    }
    request = urllib.request.Request(url, headers=headers)
    try:
        opener = urllib.request.build_opener(_ApprovedRedirectHandler(approved_hosts))
        with opener.open(request, timeout=90) as response, path.open("wb") as target:
            _validate_download_url(response.geturl(), approved_hosts)
            status = getattr(response, "status", 200)
            if status != 200:
                raise OSError(f"HTTP {status} for {url}")
            wire_limit = max_bytes + max(65_536, max_bytes // 100)
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    declared_length = int(content_length)
                except ValueError:
                    declared_length = None
                if declared_length is not None and declared_length > wire_limit:
                    raise ValueError(
                        f"response Content-Length {declared_length} exceeds {wire_limit}"
                    )

            encoding = response.headers.get("Content-Encoding", "").lower().strip()
            decoder = zlib.decompressobj(16 + zlib.MAX_WBITS) if encoding == "gzip" else None
            wire_size = 0
            decoded_size = 0
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                wire_size += len(chunk)
                if wire_size > wire_limit:
                    raise ValueError(f"wire response exceeds {wire_limit} bytes")
                payload = (
                    decoder.decompress(chunk, max_bytes - decoded_size + 1)
                    if decoder is not None
                    else chunk
                )
                decoded_size += len(payload)
                if decoded_size > max_bytes or (
                    decoder is not None and decoder.unconsumed_tail
                ):
                    raise ValueError(f"decoded response exceeds {max_bytes} bytes")
                target.write(payload)
            if decoder is not None:
                payload = decoder.flush(max_bytes - decoded_size + 1)
                decoded_size += len(payload)
                if decoded_size > max_bytes:
                    raise ValueError(f"decoded response exceeds {max_bytes} bytes")
                target.write(payload)
                if not decoder.eof:
                    raise ValueError("incomplete gzip response")
            target.flush()
            os.fsync(target.fileno())
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _decoded_bytes(asset: FontAsset, fonts_dir: Path) -> bytes:
    if asset.archive is None:
        assert asset.url is not None
        download = _download(
            asset.url,
            fonts_dir,
            browser_user_agent=asset.browser_user_agent,
            max_bytes=asset.size,
        )
        try:
            return download.read_bytes()
        finally:
            download.unlink(missing_ok=True)

    archive = asset.archive
    download = _download(
        archive.url,
        fonts_dir,
        browser_user_agent=False,
        max_bytes=archive.size,
    )
    try:
        _assert_download(download, archive.size, archive.sha256, archive.url)
        with zipfile.ZipFile(download) as bundle:
            try:
                member = bundle.getinfo(archive.member)
            except KeyError as exc:
                raise ValueError(
                    f"{asset.filename}: archive member missing: {archive.member}"
                ) from exc
            if member.is_dir():
                raise ValueError(f"{asset.filename}: archive member is a directory")
            if member.file_size != asset.size:
                raise ValueError(
                    f"{asset.filename}: archive member size {member.file_size} != {asset.size}"
                )
            extracted = bytearray()
            with bundle.open(member, "r") as source:
                while True:
                    chunk = source.read(min(1024 * 1024, asset.size - len(extracted) + 1))
                    if not chunk:
                        break
                    extracted.extend(chunk)
                    if len(extracted) > asset.size:
                        raise ValueError(
                            f"{asset.filename}: extracted archive member exceeds {asset.size} bytes"
                        )
            if len(extracted) != asset.size:
                raise ValueError(
                    f"{asset.filename}: extracted size {len(extracted)} != {asset.size}"
                )
            return bytes(extracted)
    finally:
        download.unlink(missing_ok=True)


def _atomic_install(asset: FontAsset, data: bytes, fonts_dir: Path) -> None:
    fd, raw_path = tempfile.mkstemp(
        prefix=f".{asset.filename}.", suffix=".tmp", dir=fonts_dir
    )
    candidate = Path(raw_path)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        errors = verify_font_file(candidate, asset)
        if errors:
            raise ValueError("; ".join(errors))
        os.replace(candidate, fonts_dir / asset.filename)
    finally:
        candidate.unlink(missing_ok=True)


def sync_font(asset: FontAsset, fonts_dir: Path) -> bool:
    """Validate an existing file; download and atomically replace only if needed."""
    target = fonts_dir / asset.filename
    errors = verify_font_file(target, asset)
    if not errors:
        logger.info("[VERIFIED] %s", asset.filename)
        return True

    logger.info("[SYNC] %s (%s)", asset.filename, "; ".join(errors))
    try:
        _atomic_install(asset, _decoded_bytes(asset, fonts_dir), fonts_dir)
    except Exception as exc:
        logger.error("[FAILED] %s: %s", asset.filename, exc)
        return False
    logger.info("[INSTALLED] %s", asset.filename)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fonts-dir", type=Path, default=DEFAULT_FONTS_DIR)
    parser.add_argument("--licenses-dir", type=Path, default=DEFAULT_LICENSES_DIR)
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate only; do not download or replace files",
    )
    args = parser.parse_args(argv)
    args.fonts_dir.mkdir(parents=True, exist_ok=True)

    sync_ok = True
    if not args.check:
        for choice in FONT_CHOICES:
            sync_ok = sync_font(choice.asset, args.fonts_dir) and sync_ok

    errors = verify_font_directory(args.fonts_dir, args.licenses_dir)
    for error in errors:
        logger.error("[VERIFY] %s", error)
    if not sync_ok or errors:
        return 1
    logger.info("Verified all %d catalog fonts and required notices", len(FONT_CHOICES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
