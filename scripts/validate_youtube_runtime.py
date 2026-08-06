"""Validate source-build YouTube OAuth dependencies and offline runtime data."""

from __future__ import annotations

import argparse
import json
import sys
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


ROOT = Path(__file__).resolve().parents[1]
YOUTUBE_DISTRIBUTIONS = {
    canonicalize_name(name)
    for name in (
        "google-api-python-client",
        "google-api-core",
        "google-genai",
        "google-auth",
        "google-auth-oauthlib",
        "google-auth-httplib2",
        "httplib2",
        "requests-oauthlib",
        "oauthlib",
        "requests",
        "httpx",
        "keyring",
    )
}


def validate_requirement_versions(requirements_path: Path) -> dict[str, object]:
    """Check that the build interpreter satisfies committed OAuth requirements."""
    checked: dict[str, str] = {}
    errors: list[str] = []
    declared: set[str] = set()

    for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        requirement = Requirement(line)
        name = canonicalize_name(requirement.name)
        if name not in YOUTUBE_DISTRIBUTIONS:
            continue
        if requirement.marker and not requirement.marker.evaluate():
            continue

        declared.add(name)
        try:
            installed = metadata.version(requirement.name)
        except metadata.PackageNotFoundError:
            errors.append(f"{requirement.name} is not installed")
            continue
        checked[requirement.name] = installed
        if requirement.specifier and not requirement.specifier.contains(installed, prereleases=True):
            errors.append(
                f"{requirement.name}=={installed} does not satisfy {requirement.specifier}"
            )

    undeclared = sorted(YOUTUBE_DISTRIBUTIONS - declared)
    if undeclared:
        errors.append("requirements.txt is missing explicit dependencies: " + ", ".join(undeclared))
    return {"ok": not errors, "versions": checked, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requirements", type=Path, default=ROOT / "requirements.txt")
    args = parser.parse_args()

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from managers.youtube_manager import get_youtube_runtime_diagnostics

    version_report = validate_requirement_versions(args.requirements)
    runtime_report = get_youtube_runtime_diagnostics()
    report = {
        "ok": bool(version_report["ok"] and runtime_report.get("ok")),
        "requirements": version_report,
        "runtime": runtime_report,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
