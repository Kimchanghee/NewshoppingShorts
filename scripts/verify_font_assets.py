#!/usr/bin/env python3
"""Verify bundled fonts against the canonical catalog."""

from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.font_catalog import (  # noqa: E402
    DEFAULT_FONTS_DIR,
    DEFAULT_LICENSES_DIR,
    FONT_CHOICES,
    LICENSE_NOTICES,
    FontAsset,
)


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from(">H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def _table(data: bytes, tag: bytes) -> bytes:
    if len(data) < 12:
        raise ValueError("truncated sfnt header")
    table_count = _u16(data, 4)
    if 12 + table_count * 16 > len(data):
        raise ValueError("truncated sfnt table directory")
    for index in range(table_count):
        record = 12 + index * 16
        if data[record : record + 4] != tag:
            continue
        offset = _u32(data, record + 8)
        length = _u32(data, record + 12)
        if offset + length > len(data):
            raise ValueError(f"truncated {tag.decode('ascii')} table")
        return data[offset : offset + length]
    raise ValueError(f"missing {tag.decode('ascii')} table")


def _decode_name(platform_id: int, raw: bytes) -> str:
    try:
        if platform_id in (0, 3):
            return raw.decode("utf-16-be").replace("\x00", "").strip()
        if platform_id == 1:
            return raw.decode("mac_roman").strip()
        return raw.decode("utf-8").strip()
    except (UnicodeDecodeError, LookupError):
        return ""


def _font_names(data: bytes) -> tuple[set[str], set[str]]:
    table = _table(data, b"name")
    if len(table) < 6:
        raise ValueError("truncated name table")
    count = _u16(table, 2)
    strings_offset = _u16(table, 4)
    families: set[str] = set()
    styles: set[str] = set()
    for index in range(count):
        record = 6 + index * 12
        if record + 12 > len(table):
            raise ValueError("truncated name record")
        platform_id = _u16(table, record)
        name_id = _u16(table, record + 6)
        length = _u16(table, record + 8)
        offset = strings_offset + _u16(table, record + 10)
        if offset + length > len(table):
            continue
        value = _decode_name(platform_id, table[offset : offset + length])
        if value and name_id in (1, 16):
            families.add(value)
        elif value and name_id in (2, 17):
            styles.add(value)
    return families, styles


def _format4_has(subtable: bytes, codepoint: int) -> bool:
    if codepoint > 0xFFFF or len(subtable) < 16:
        return False
    seg_count = _u16(subtable, 6) // 2
    end_offset = 14
    start_offset = end_offset + 2 * seg_count + 2
    delta_offset = start_offset + 2 * seg_count
    range_offset = delta_offset + 2 * seg_count
    if range_offset + 2 * seg_count > len(subtable):
        return False
    for index in range(seg_count):
        start = _u16(subtable, start_offset + 2 * index)
        end = _u16(subtable, end_offset + 2 * index)
        if not start <= codepoint <= end:
            continue
        delta = _u16(subtable, delta_offset + 2 * index)
        range_value_offset = range_offset + 2 * index
        glyph_range = _u16(subtable, range_value_offset)
        if glyph_range == 0:
            return ((codepoint + delta) & 0xFFFF) != 0
        glyph_offset = range_value_offset + glyph_range + 2 * (codepoint - start)
        if glyph_offset + 2 > len(subtable):
            return False
        glyph = _u16(subtable, glyph_offset)
        return glyph != 0 and ((glyph + delta) & 0xFFFF) != 0
    return False


def _format12_has(subtable: bytes, codepoint: int) -> bool:
    if len(subtable) < 16:
        return False
    group_count = _u32(subtable, 12)
    if 16 + group_count * 12 > len(subtable):
        return False
    for index in range(group_count):
        offset = 16 + index * 12
        start = _u32(subtable, offset)
        end = _u32(subtable, offset + 4)
        if start <= codepoint <= end:
            glyph = _u32(subtable, offset + 8) + codepoint - start
            return glyph != 0
        if codepoint < start:
            return False
    return False


def _font_has_codepoint(data: bytes, codepoint: int) -> bool:
    table = _table(data, b"cmap")
    if len(table) < 4:
        raise ValueError("truncated cmap table")
    count = _u16(table, 2)
    for index in range(count):
        record = 4 + index * 8
        if record + 8 > len(table):
            raise ValueError("truncated cmap record")
        platform_id = _u16(table, record)
        encoding_id = _u16(table, record + 2)
        if platform_id != 0 and not (platform_id == 3 and encoding_id in (1, 10)):
            continue
        offset = _u32(table, record + 4)
        if offset + 2 > len(table):
            continue
        subtable = table[offset:]
        font_format = _u16(subtable, 0)
        if font_format == 4 and _format4_has(subtable, codepoint):
            return True
        if font_format == 12 and _format12_has(subtable, codepoint):
            return True
    return False


def verify_font_file(path: str | Path, asset: FontAsset) -> list[str]:
    """Return human-readable integrity errors for one decoded TTF."""
    path = Path(path)
    if not path.is_file():
        return [f"missing font: {path}"]
    data = path.read_bytes()
    errors: list[str] = []
    if len(data) != asset.size:
        errors.append(f"{path.name}: size {len(data)} != {asset.size}")
    digest = hashlib.sha256(data).hexdigest()
    if digest != asset.sha256:
        errors.append(f"{path.name}: sha256 {digest} != {asset.sha256}")

    try:
        families, styles = _font_names(data)
        if asset.family not in families:
            errors.append(
                f"{path.name}: family {sorted(families)!r} does not contain {asset.family!r}"
            )
        if asset.style not in styles:
            errors.append(
                f"{path.name}: style {sorted(styles)!r} does not contain {asset.style!r}"
            )
        missing = [
            f"U+{codepoint:04X}"
            for codepoint in asset.hangul_codepoints
            if not _font_has_codepoint(data, codepoint)
        ]
        if missing:
            errors.append(f"{path.name}: missing Hangul glyphs {', '.join(missing)}")
    except (IndexError, struct.error, ValueError) as exc:
        errors.append(f"{path.name}: invalid font metadata ({exc})")
    return errors


def verify_font_directory(
    fonts_dir: str | Path = DEFAULT_FONTS_DIR,
    licenses_dir: str | Path = DEFAULT_LICENSES_DIR,
) -> list[str]:
    """Verify all catalog assets and every catalog-required license notice."""
    fonts_dir = Path(fonts_dir)
    licenses_dir = Path(licenses_dir)
    errors: list[str] = []
    for choice in FONT_CHOICES:
        errors.extend(verify_font_file(fonts_dir / choice.asset.filename, choice.asset))

    required_notices = {
        filename for choice in FONT_CHOICES for filename in choice.license_files
    }
    for filename in sorted(required_notices):
        path = licenses_dir / filename
        notice = LICENSE_NOTICES.get(filename)
        if notice is None:
            errors.append(f"catalog has no integrity pin for license notice: {filename}")
            continue
        if not path.is_file():
            errors.append(f"missing license notice: {path}")
            continue
        data = path.read_bytes()
        if len(data) != notice.size:
            errors.append(f"{filename}: size {len(data)} != {notice.size}")
        digest = hashlib.sha256(data).hexdigest()
        if digest != notice.sha256:
            errors.append(f"{filename}: sha256 {digest} != {notice.sha256}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fonts-dir", type=Path, default=DEFAULT_FONTS_DIR)
    parser.add_argument("--licenses-dir", type=Path, default=DEFAULT_LICENSES_DIR)
    args = parser.parse_args(argv)

    errors = verify_font_directory(args.fonts_dir, args.licenses_dir)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Verified {len(FONT_CHOICES)} font assets in {args.fonts_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
