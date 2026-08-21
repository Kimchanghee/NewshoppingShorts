"""Build provenance helpers shared by release scripts and contract tests.

The manifest is evidence about a build, not its trust root.  CI supplies the
expected commit, ref, run and package target independently and publication is
allowed only when those values agree with the checked-out repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import subprocess
from typing import Mapping, Sequence

from utils.url_security import (
    COUPANG_PARTNER_LINK_CONTRACT_ID,
    COUPANG_PARTNER_LINK_CONTRACT_SCHEMA_VERSION,
)
from utils.release_assets import sha256_file, verify_whisper_model_assets


BUILD_MANIFEST_SCHEMA_VERSION = 1
EXPECTED_BUILD_ENV_NAMES = (
    "SSMAKER_EXPECTED_COMMIT_SHA",
    "SSMAKER_EXPECTED_REF",
    "SSMAKER_EXPECTED_RUN_ID",
    "SSMAKER_PACKAGE_TARGET",
)
PACKAGE_TARGETS = frozenset({"installer", "msix"})
_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_INSTALLER_TAG_RE = re.compile(r"^refs/tags/v(?P<version>[0-9]+\.[0-9]+\.[0-9]+)$")
_STORE_TAG_RE = re.compile(r"^refs/tags/store-v(?P<version>[0-9]+\.[0-9]+\.[0-9]+)$")


class BuildMetadataError(RuntimeError):
    """Raised when CI provenance is absent, malformed, or contradictory."""


@dataclass(frozen=True)
class GitState:
    commit_sha: str
    current_ref: str
    clean_tree: bool
    tracked_status: tuple[str, ...]


def _git(project_root: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise BuildMetadataError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout.strip() if completed.returncode == 0 else ""


def read_git_state(project_root: Path) -> GitState:
    """Read HEAD and tracked status without inspecting or changing untracked files."""

    root = project_root.resolve()
    commit_sha = _git(root, "rev-parse", "HEAD").lower()
    if not _FULL_SHA_RE.fullmatch(commit_sha):
        raise BuildMetadataError(f"git HEAD is not a full commit SHA: {commit_sha!r}")
    current_ref = _git(root, "symbolic-ref", "-q", "HEAD", check=False) or "DETACHED"
    status_text = _git(
        root,
        "status",
        "--porcelain=v1",
        "--untracked-files=no",
    )
    tracked_status = tuple(line for line in status_text.splitlines() if line)
    return GitState(
        commit_sha=commit_sha,
        current_ref=current_ref,
        clean_tree=not tracked_status,
        tracked_status=tracked_status,
    )


def _clean_env(env: Mapping[str, str], name: str) -> str:
    return str(env.get(name, "") or "").strip()


def _is_ci(env: Mapping[str, str]) -> bool:
    return _clean_env(env, "CI").lower() in {"1", "true", "yes"} or _clean_env(
        env, "GITHUB_ACTIONS"
    ).lower() in {"1", "true", "yes"}


def _expected_ref_matches_head(project_root: Path, expected_ref: str, head: str) -> bool:
    if not expected_ref:
        return False
    resolved = _git(project_root, "rev-parse", f"{expected_ref}^{{commit}}", check=False).lower()
    return resolved == head


def _publication_ref_matches(target: str, ref: str, version: str) -> bool:
    pattern = _INSTALLER_TAG_RE if target == "installer" else _STORE_TAG_RE
    match = pattern.fullmatch(ref)
    return bool(match and match.group("version") == version)


def _capture_release_asset_tree(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def create_build_manifest(
    *,
    project_root: Path,
    version: str,
    build_number: str | int,
    env: Mapping[str, str] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Create a fail-closed build provenance manifest.

    Missing expected values are permitted only outside CI.  Such local builds
    are useful as candidates but can never authorize publication.
    """

    environment = os.environ if env is None else env
    root = project_root.resolve()
    git_state = read_git_state(root)
    expected = {name: _clean_env(environment, name) for name in EXPECTED_BUILD_ENV_NAMES}
    missing = [name for name, value in expected.items() if not value]
    ci = _is_ci(environment)
    if ci and missing:
        raise BuildMetadataError(
            "CI build provenance requires all external trust inputs; missing: "
            + ", ".join(missing)
        )

    expected_sha = expected["SSMAKER_EXPECTED_COMMIT_SHA"].lower()
    expected_ref = expected["SSMAKER_EXPECTED_REF"]
    expected_run_id = expected["SSMAKER_EXPECTED_RUN_ID"]
    package_target = expected["SSMAKER_PACKAGE_TARGET"].lower() or "installer"
    if package_target not in PACKAGE_TARGETS:
        raise BuildMetadataError(
            f"SSMAKER_PACKAGE_TARGET must be one of {sorted(PACKAGE_TARGETS)}; got {package_target!r}"
        )
    if expected_sha and not _FULL_SHA_RE.fullmatch(expected_sha):
        raise BuildMetadataError("SSMAKER_EXPECTED_COMMIT_SHA must be a full 40-character SHA")
    if expected_run_id and not expected_run_id.isdecimal():
        raise BuildMetadataError("SSMAKER_EXPECTED_RUN_ID must contain decimal digits only")

    checks = {
        "ci_environment": ci,
        "external_trust_complete": not missing,
        "commit_matches": bool(expected_sha and expected_sha == git_state.commit_sha),
        "ref_matches": bool(
            expected_ref
            and _expected_ref_matches_head(root, expected_ref, git_state.commit_sha)
        ),
        "run_id_valid": bool(expected_run_id and expected_run_id.isdecimal()),
        "package_target_valid": package_target in PACKAGE_TARGETS,
        "publication_ref_matches": _publication_ref_matches(
            package_target, expected_ref, str(version)
        ),
        "clean_tree": git_state.clean_tree,
    }
    if ci:
        identity_failures = [
            name
            for name in (
                "commit_matches",
                "ref_matches",
                "run_id_valid",
                "package_target_valid",
            )
            if not checks[name]
        ]
        if identity_failures:
            raise BuildMetadataError(
                "CI external build identity does not match the checked-out source: "
                + ", ".join(identity_failures)
            )
    publication_allowed = all(checks.values())
    denial_reasons = [name for name, passed in checks.items() if not passed]
    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    generated_utc = timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        whisper_assets: dict[str, object] = verify_whisper_model_assets(
            root / "faster_whisper_models"
        )
    except (OSError, ValueError) as exc:
        whisper_assets = {"verified": False, "error": str(exc), "models": {}}
    tesseract_files = _capture_release_asset_tree(
        root / "build_staging" / "tesseract"
    )

    return {
        "schema_version": BUILD_MANIFEST_SCHEMA_VERSION,
        "version": str(version),
        "build_number": str(build_number),
        "commit_sha": git_state.commit_sha,
        "commit_short_sha": git_state.commit_sha[:12],
        "ref": expected_ref or git_state.current_ref,
        "package_target": package_target,
        "url_contract_id": COUPANG_PARTNER_LINK_CONTRACT_ID,
        "url_contract_schema_version": COUPANG_PARTNER_LINK_CONTRACT_SCHEMA_VERSION,
        "whisper_assets": whisper_assets,
        "tesseract_assets": {
            "source_package": (
                "tesseract 5.5.0.20241111 nupkg "
                "sha256:56659a4c01e6ea75a0b710ba7e8bb16e9cc6675978d2861323751812aeea6183"
            ),
            "files": tesseract_files,
        },
        "ci_run_id": expected_run_id or None,
        "generated_at_utc": generated_utc,
        "clean_tree": git_state.clean_tree,
        "tracked_status": list(git_state.tracked_status),
        "ci": ci,
        "external_trust": {
            "commit_sha": expected_sha or None,
            "ref": expected_ref or None,
            "run_id": expected_run_id or None,
            "package_target": expected["SSMAKER_PACKAGE_TARGET"] or None,
        },
        "checks": checks,
        "publication_allowed": publication_allowed,
        "publication_denial_reasons": denial_reasons,
    }


def validate_manifest_identity(
    manifest: Mapping[str, object],
    *,
    expected_commit_sha: str,
    expected_ref: str,
    expected_run_id: str,
    expected_package_target: str,
    require_publication: bool = False,
) -> None:
    """Validate a manifest against values supplied across an external boundary."""

    expected_pairs: Sequence[tuple[str, object]] = (
        ("commit_sha", expected_commit_sha.lower()),
        ("ref", expected_ref),
        ("ci_run_id", expected_run_id),
        ("package_target", expected_package_target.lower()),
    )
    mismatches = [
        f"{key}: expected={expected!r} actual={manifest.get(key)!r}"
        for key, expected in expected_pairs
        if manifest.get(key) != expected
    ]
    if manifest.get("url_contract_id") != COUPANG_PARTNER_LINK_CONTRACT_ID:
        mismatches.append("url_contract_id does not match the source contract")
    if manifest.get("url_contract_schema_version") != COUPANG_PARTNER_LINK_CONTRACT_SCHEMA_VERSION:
        mismatches.append("url_contract_schema_version does not match the source contract")
    if require_publication and manifest.get("publication_allowed") is not True:
        mismatches.append("publication_allowed is not true")
    if mismatches:
        raise BuildMetadataError("Build manifest identity mismatch: " + "; ".join(mismatches))
