"""Generate the build_manifest.json bundled into every Windows package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.build_metadata import BuildMetadataError, create_build_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--version-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    version_payload = json.loads(args.version_json.read_text(encoding="utf-8"))
    try:
        manifest = create_build_manifest(
            project_root=args.project_root,
            version=version_payload["version"],
            build_number=version_payload["build_number"],
        )
    except (BuildMetadataError, KeyError, ValueError) as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Generated build manifest: {args.output}")
    print(f"Publication allowed: {str(manifest['publication_allowed']).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
