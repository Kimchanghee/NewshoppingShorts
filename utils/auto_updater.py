# -*- coding: utf-8 -*-
"""
Auto Updater Module
앱 버전 확인, 안전한 다운로드 및 설치 실행을 담당합니다.
업데이트 메타데이터와 파일 해시, Windows 서명을 검증합니다.
"""

import os
import sys
import json
import re
import time
import shutil
import hashlib
import tempfile
import threading
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Callable, Tuple

from urllib.parse import unquote, urlparse

import requests
from utils.logging_config import get_logger
from utils.windows_package import is_msix_package
from utils.authenticode import (
    configured_transition_bridge_version,
    expected_public_signer_thumbprints,
    is_legacy_bridge_version,
    verify_authenticode,
)

logger = get_logger(__name__)

# 현재 앱 버전(배포 시 version.json이 우선)
CURRENT_VERSION = "1.5.65"

# 버전 확인 API 기본 주소
_DEFAULT_UPDATE_BASE_URL = (
    os.getenv("PAYMENT_API_BASE_URL", "").strip()
    or os.getenv("API_SERVER_URL", "").strip()
    or "https://newshopping-shorts-auth.vercel.app"
).rstrip("/")
UPDATE_CHECK_URL = os.getenv(
    "UPDATE_CHECK_URL",
    f"{_DEFAULT_UPDATE_BASE_URL}/app/version",
)
GITHUB_RELEASE_API_URL = os.getenv(
    "GITHUB_RELEASE_API_URL",
    "https://api.github.com/repos/Kimchanghee/NewshoppingShorts/releases/latest",
)

# Allowed domains for update downloads (security: prevent redirect to malicious hosts)
_ALLOWED_DOWNLOAD_DOMAINS: frozenset[str] = frozenset({
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "storage.googleapis.com",
    "project-user-dashboard-api.vercel.app",
    "newshopping-shorts-auth.vercel.app",
    "ssmaker-auth-api-1049571775048.us-central1.run.app",
})
MAX_UPDATE_DOWNLOAD_BYTES = 512 * 1024 * 1024


def _is_allowed_update_download_url(download_url: str) -> bool:
    try:
        parsed = urlparse(str(download_url or "").strip())
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and parsed.hostname.lower() in _ALLOWED_DOWNLOAD_DOMAINS
        and not parsed.username
        and not parsed.password
        and port in (None, 443)
    )


def _validate_update_redirect_chain(response: requests.Response) -> bool:
    """Require the initial response and every redirect destination to stay trusted."""
    visited = [getattr(item, "url", "") for item in getattr(response, "history", ())]
    visited.append(getattr(response, "url", ""))
    return bool(visited) and all(_is_allowed_update_download_url(url) for url in visited)


def _safe_update_filename(download_url: str) -> str | None:
    """Return a simple installer filename, rejecting encoded traversal and separators."""
    raw_name = urlparse(download_url).path.rsplit("/", 1)[-1]
    filename = unquote(raw_name)
    if (
        not filename
        or filename in {".", ".."}
        or "/" in filename
        or "\\" in filename
        or not re.fullmatch(r"[A-Za-z0-9._-]{1,180}", filename)
        or Path(filename).suffix.lower() not in {".exe", ".zip", ".msi"}
    ):
        return None
    return filename

def _verify_authenticode_signature(
    file_path: str,
    thumbprints: str,
    *,
    artifact_version: str | None = None,
    allow_legacy_integrity_bridge: bool = False,
) -> tuple[bool, str]:
    """Apply the central Authenticode policy to a downloaded installer."""
    if sys.platform != "win32":
        return True, "signature check skipped on non-windows"
    if not file_path or not os.path.exists(file_path):
        return False, "file not found"

    verification = verify_authenticode(
        file_path,
        expected_thumbprints=expected_public_signer_thumbprints(thumbprints),
        artifact_version=artifact_version,
        allow_legacy_integrity_bridge=allow_legacy_integrity_bridge,
        transition_bridge_version=configured_transition_bridge_version(),
    )
    return verification.accepted_for_update, verification.reason


def get_current_version() -> str:
    """Return the current version from version.json or the built-in fallback."""
    version_file = get_version_file_path()
    if version_file and version_file.exists():
        try:
            with open(version_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("version", CURRENT_VERSION)
        except Exception:
            pass
    
    return CURRENT_VERSION


def get_version_file_path() -> Optional[Path]:
    """
    Locate version.json in an installed or source checkout.

    A frozen build first checks beside the executable, then the PyInstaller
    bundle directory. Source runs use the repository root.
    """
    if getattr(sys, 'frozen', False):
        # Installed version.json beside the executable.
        exe_dir = Path(sys.executable).parent
        exe_version = exe_dir / "version.json"
        if exe_version.exists():
            return exe_version

        # Bundled version.json inside a one-file PyInstaller extraction.
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            bundled_version = Path(meipass) / "version.json"
            if bundled_version.exists():
                return bundled_version

        return exe_version  # Stable path; get_current_version supplies fallback.
    else:
        # Source checkout.
        base_path = Path(__file__).parent.parent
        return base_path / "version.json"


def parse_version(version_str: str) -> Tuple[int, int, int]:
    """Parse a version such as ``1.0.0`` into a three-integer tuple."""
    try:
        parts = version_str.strip().split('.')
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except (ValueError, IndexError):
        logger.warning(f"Failed to parse version: {version_str}")
        return (0, 0, 0)


def compare_versions(current: str, latest: str) -> int:
    """
    Compare semantic versions.

    Returns -1 when an update is available, 0 when equal, and 1 when the
    current version is newer.
    """
    current_tuple = parse_version(current)
    latest_tuple = parse_version(latest)
    
    if current_tuple < latest_tuple:
        return -1
    elif current_tuple > latest_tuple:
        return 1
    else:
        return 0


class UpdateChecker:
    """Check update metadata and download verified installer packages."""
    
    def __init__(
        self,
        check_url: str = UPDATE_CHECK_URL,
        timeout: int = 10
    ):
        """Initialize with the update API URL and request timeout in seconds."""
        self.check_url = check_url
        self.timeout = timeout
        self.current_version = get_current_version()
        self._update_info: Optional[Dict[str, Any]] = None

    @staticmethod
    def _extract_sha256(text: str) -> str:
        match = re.search(r"\b([a-fA-F0-9]{64})\b", str(text or ""))
        return match.group(1).lower() if match else ""

    def _query_github_latest_release(self) -> Optional[Dict[str, Any]]:
        if not GITHUB_RELEASE_API_URL:
            return None
        try:
            response = requests.get(
                GITHUB_RELEASE_API_URL,
                timeout=self.timeout,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": f"SSMaker/{self.current_version}",
                },
            )
            if response.status_code != 200:
                logger.warning("GitHub release fallback returned HTTP %s", response.status_code)
                return None

            data = response.json()
            latest_version = str(data.get("tag_name", "")).strip().lstrip("vV")
            if not latest_version:
                return None

            result = {
                "update_available": False,
                "current_version": self.current_version,
                "latest_version": latest_version,
                "download_url": None,
                "release_notes": data.get("body", ""),
                "is_mandatory": False,
                "error": None,
            }
            if compare_versions(self.current_version, latest_version) >= 0:
                return result

            assets = data.get("assets", []) or []
            preferred_name = f"ssmaker_setup_v{latest_version}.exe"
            installer_asset = next(
                (
                    asset
                    for asset in assets
                    if str(asset.get("name", "")).lower() == preferred_name
                ),
                None,
            )
            if installer_asset is None:
                installer_asset = next(
                    (
                        asset
                        for asset in assets
                        if str(asset.get("name", "")).lower().endswith(".exe")
                    ),
                    None,
                )
            if installer_asset is None:
                result["error"] = "Missing installer asset in GitHub release"
                return result

            download_url = installer_asset.get("browser_download_url")
            digest = str(installer_asset.get("digest", "")).strip()
            file_hash = digest.split(":", 1)[1].strip() if digest.lower().startswith("sha256:") else ""
            if not file_hash:
                file_hash = self._extract_sha256(data.get("body", ""))

            result["download_url"] = download_url
            result["file_hash"] = file_hash
            if download_url and file_hash:
                result["update_available"] = True
            else:
                result["error"] = "GitHub release metadata is incomplete"
            return result
        except Exception as e:
            logger.warning("GitHub release fallback failed: %s", e)
            return None

    def _prefer_github_if_newer(self, result: Dict[str, Any]) -> Dict[str, Any]:
        github_result = self._query_github_latest_release()
        if not github_result:
            return result

        current_latest = str(result.get("latest_version") or "0.0.0")
        github_latest = str(github_result.get("latest_version") or "0.0.0")
        try:
            github_is_newer = compare_versions(current_latest, github_latest) < 0
        except Exception:
            github_is_newer = current_latest < github_latest

        if github_result.get("update_available") and (
            not result.get("update_available") or github_is_newer
        ):
            return github_result
        if github_is_newer and not result.get("update_available"):
            result["latest_version"] = github_latest
            result["release_notes"] = github_result.get("release_notes")
        return result
        
    def check_for_updates(self) -> Dict[str, Any]:
        """
        Check the configured endpoint and return normalized update metadata.

        The result contains:
            {
                "update_available": bool,
                "current_version": str,
                "latest_version": str,
                "download_url": str (optional),
                "release_notes": str (optional),
                "is_mandatory": bool,
                "error": str (optional)
            }
        """
        result = {
            "update_available": False,
            "current_version": self.current_version,
            "latest_version": self.current_version,
            "download_url": None,
            "release_notes": None,
            "is_mandatory": False,
            "error": None
        }

        if is_msix_package():
            logger.info("Microsoft Store package detected; updates are managed by the Store")
            self._update_info = result
            return result
        
        try:
            logger.info(f"Checking for updates at: {self.check_url}")
            
            response = requests.get(
                self.check_url,
                timeout=self.timeout,
                headers={"User-Agent": f"SSMaker/{self.current_version}"}
            )
            
            if response.status_code == 200:
                data = response.json()
                
                latest_version = data.get("version", self.current_version)
                result["latest_version"] = latest_version
                result["download_url"] = data.get("download_url")
                result["release_notes"] = data.get("release_notes", "")
                result["is_mandatory"] = data.get("is_mandatory", False)
                result["file_hash"] = data.get("file_hash")  # SHA256 hash for integrity verification
                
                comparison = compare_versions(self.current_version, latest_version)
                if comparison < 0:
                    if not result["download_url"]:
                        result["error"] = "Missing download_url in update metadata"
                        logger.error("Update metadata missing download_url")
                    elif not result["file_hash"]:
                        result["error"] = "Missing file_hash in update metadata"
                        logger.error("Update metadata missing file_hash; refusing unsafe update")
                    else:
                        # Validate download URL domain before accepting update
                        dl_parsed = urlparse(result["download_url"])
                        if dl_parsed.scheme != "https" or dl_parsed.hostname not in _ALLOWED_DOWNLOAD_DOMAINS:
                            result["error"] = f"Untrusted download domain: {dl_parsed.hostname}"
                            logger.error(f"[Security] Rejecting update from untrusted domain: {dl_parsed.hostname}")
                        else:
                            result["update_available"] = True
                            logger.info(f"Update available: {self.current_version} -> {latest_version}")
                else:
                    logger.info(f"No update needed. Current: {self.current_version}, Latest: {latest_version}")
            elif response.status_code == 404:
                # Some backend deployments do not include update API routes.
                # This is not a connectivity failure; just skip update flow.
                logger.info("Update endpoint not available (404). Skipping update check.")
            else:
                result["error"] = f"HTTP {response.status_code}"
                logger.warning(f"Update check failed: HTTP {response.status_code}")
                
        except requests.exceptions.Timeout:
            result["error"] = "요청 시간이 초과되었습니다."
            logger.warning("Update check timeout")
        except requests.exceptions.ConnectionError:
            result["error"] = "업데이트 서버에 연결할 수 없습니다."
            logger.warning("Update check connection error")
        except json.JSONDecodeError:
            result["error"] = "업데이트 서버 응답을 해석할 수 없습니다."
            logger.warning("Update check JSON parse error")
        except Exception as e:
            result["error"] = f"알 수 없는 오류: {str(e)[:50]}"
            logger.exception(f"Update check error: {e}")
        
        result = self._prefer_github_if_newer(result)
        self._update_info = result
        return result
    
    def download_update(
        self,
        download_url: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Optional[Path]:
        """
        Download and verify an update package.

        ``progress_callback`` receives downloaded and total byte counts.
        Returns the local file path, or ``None`` when validation fails.
        """
        if is_msix_package():
            logger.info("Ignoring legacy installer download in Microsoft Store package")
            return None
        if not download_url:
            logger.error("Download URL is empty")
            return None

        if not _is_allowed_update_download_url(download_url):
            logger.error("[Security] Rejecting untrusted update URL: %s", download_url)
            return None
        filename = _safe_update_filename(download_url)
        if filename is None:
            logger.error("[Security] Rejecting unsafe update filename from URL: %s", download_url)
            return None

        try:
            logger.info(f"Downloading update from: {download_url}")
            
            # Download to a temporary directory.
            temp_dir = Path(tempfile.gettempdir()) / "ssmaker_update"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Determine target filename.
            download_path = (temp_dir / filename).resolve()
            if download_path.parent != temp_dir.resolve():
                raise ValueError("Update download destination escapes temporary directory")
            
            # Stream download for stable memory usage.
            with requests.get(
                download_url,
                stream=True,
                timeout=60,
                headers={"User-Agent": f"SSMaker/{self.current_version}"},
            ) as response:
                response.raise_for_status()
                if not _validate_update_redirect_chain(response):
                    raise ValueError("Update redirect chain contains an untrusted URL")

                raw_length = response.headers.get("content-length")
                try:
                    total_size = int(raw_length) if raw_length is not None else 0
                except (TypeError, ValueError) as exc:
                    raise ValueError("Invalid update Content-Length") from exc
                if total_size < 0 or total_size > MAX_UPDATE_DOWNLOAD_BYTES:
                    raise ValueError("Update Content-Length exceeds download limit")
                downloaded_size = 0

                with open(download_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            downloaded_size += len(chunk)
                            if downloaded_size > MAX_UPDATE_DOWNLOAD_BYTES:
                                raise ValueError("Update download exceeds byte limit")
                            f.write(chunk)
                            if progress_callback and total_size > 0:
                                progress_callback(downloaded_size, total_size)
            
            logger.info(f"Download complete: {download_path}")

            # Verify file integrity with SHA256 hash
            expected_hash = self._update_info.get("file_hash") if self._update_info else None
            if expected_hash:
                sha256 = hashlib.sha256()
                with open(download_path, "rb") as f:
                    for block in iter(lambda: f.read(8192), b""):
                        sha256.update(block)
                actual_hash = sha256.hexdigest()
                if actual_hash.lower() != expected_hash.lower():
                    logger.error(f"Hash mismatch! Expected: {expected_hash[:16]}..., Got: {actual_hash[:16]}...")
                    download_path.unlink(missing_ok=True)
                    return None
                logger.info("File integrity verified (SHA256)")
            else:
                logger.error("No file_hash provided by server - refusing to install update")
                download_path.unlink(missing_ok=True)
                return None

            if sys.platform == "win32":
                artifact_version = str(
                    (self._update_info or {}).get("latest_version") or ""
                ).strip().lstrip("vV")
                ok, reason = _verify_authenticode_signature(
                    str(download_path),
                    os.getenv("UPDATE_SIGNER_THUMBPRINTS", ""),
                    artifact_version=artifact_version,
                    allow_legacy_integrity_bridge=is_legacy_bridge_version(
                        artifact_version,
                        transition_bridge_version=configured_transition_bridge_version(),
                    ),
                )
                if not ok:
                    logger.error("Installer signature verification failed: %s", reason)
                    download_path.unlink(missing_ok=True)
                    return None
                logger.info("Installer Authenticode signature verified")

            return download_path
            
        except Exception as e:
            logger.exception(f"Download failed: {e}")
            if "download_path" in locals():
                download_path.unlink(missing_ok=True)
            return None
    
    def install_update(self, installer_path: Path) -> bool:
        """
        Launch a verified Inno Setup installer in silent mode.

        When this returns ``True``, the caller must exit so the installer can
        replace application files and restart the app.
        """
        if is_msix_package():
            logger.info("Ignoring legacy installer launch in Microsoft Store package")
            return False
        if not installer_path or not installer_path.exists():
            logger.error("Installer file not found")
            return False

        try:
            logger.info(f"Installing update (silent): {installer_path}")

            if sys.platform == "win32":
                # Inno Setup silent install flags: suppress UI/prompts, close
                # the running app, and skip the initial confirmation prompt.
                subprocess.Popen(
                    [
                        str(installer_path),
                        "/VERYSILENT",
                        "/SUPPRESSMSGBOXES",
                        "/CLOSEAPPLICATIONS",
                        "/SP-",
                    ],
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
                logger.info("Installer launched. App should exit now for update to proceed.")
                return True
            else:
                logger.warning("Auto-install not supported on this platform")
                return False

        except Exception as e:
            logger.exception(f"Install failed: {e}")
            return False


class UpdateCheckerAsync:
    """Run update checks on a background thread."""
    
    def __init__(self):
        self._checker = UpdateChecker()
        self._result: Optional[Dict[str, Any]] = None
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[Dict[str, Any]], None]] = None
    
    def check_async(
        self,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> None:
        """Start a check and invoke ``callback`` with the result when done."""
        self._callback = callback
        self._thread = threading.Thread(target=self._check_worker, daemon=True)
        self._thread.start()
    
    def _check_worker(self):
        """Background worker entry point."""
        self._result = self._checker.check_for_updates()
        if self._callback:
            self._callback(self._result)
    
    def get_result(self) -> Optional[Dict[str, Any]]:
        """Return the most recent result, if available."""
        return self._result
    
    def is_checking(self) -> bool:
        """Return whether a background check is still running."""
        return self._thread is not None and self._thread.is_alive()


# Process-wide singleton.
_update_checker: Optional[UpdateCheckerAsync] = None


def get_update_checker() -> UpdateCheckerAsync:
    """Return the process-wide asynchronous update checker."""
    global _update_checker
    if _update_checker is None:
        _update_checker = UpdateCheckerAsync()
    return _update_checker


def check_for_updates_on_startup(
    callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> None:
    """Start the non-blocking application-startup update check."""
    checker = get_update_checker()
    checker.check_async(callback)
