"""Generate the Windows version resource consumed by PyInstaller."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _numeric_version(version: str, build_number: str | int) -> tuple[int, int, int, int]:
    parts = [int(part) for part in str(version).split(".")]
    if len(parts) != 3 or any(part < 0 or part > 65535 for part in parts):
        raise ValueError("version must contain three numeric components")
    build = int(build_number)
    if build < 0 or build > 65535:
        raise ValueError("build_number must be between 0 and 65535")
    return parts[0], parts[1], parts[2], build


def build_version_resource(version: str, build_number: str | int) -> str:
    file_version = _numeric_version(version, build_number)
    tuple_text = ", ".join(str(part) for part in file_version)
    file_version_text = ".".join(str(part) for part in file_version)
    return f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({tuple_text}),
    prodvers=({tuple_text}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '041204B0',
        [
          StringStruct('CompanyName', 'SSMaker'),
          StringStruct('FileDescription', 'SSMaker 쇼핑 숏폼 자동 제작'),
          StringStruct('FileVersion', '{file_version_text}'),
          StringStruct('InternalName', 'ssmaker'),
          StringStruct('LegalCopyright', 'Copyright (c) SSMaker'),
          StringStruct('OriginalFilename', 'ssmaker.exe'),
          StringStruct('ProductName', 'SSMaker'),
          StringStruct('ProductVersion', '{version}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1042, 1200])])
  ]
)
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.version_json.read_text(encoding="utf-8"))
    rendered = build_version_resource(payload["version"], payload["build_number"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"Generated Windows version resource: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
