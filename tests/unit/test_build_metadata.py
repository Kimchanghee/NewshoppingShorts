from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess

import pytest

from utils.build_metadata import BuildMetadataError, create_build_manifest


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


@pytest.fixture
def repository(tmp_path: Path) -> tuple[Path, str]:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "build-test@example.invalid")
    _git(tmp_path, "config", "user.name", "Build Test")
    (tmp_path / "tracked.txt").write_text("clean\n", encoding="utf-8")
    _git(tmp_path, "add", "tracked.txt")
    _git(tmp_path, "commit", "-q", "-m", "initial")
    return tmp_path, _git(tmp_path, "rev-parse", "HEAD")


def _ci_env(sha: str, ref: str, target: str = "installer") -> dict[str, str]:
    return {
        "CI": "true",
        "SSMAKER_EXPECTED_COMMIT_SHA": sha,
        "SSMAKER_EXPECTED_REF": ref,
        "SSMAKER_EXPECTED_RUN_ID": "123456789",
        "SSMAKER_PACKAGE_TARGET": target,
    }


def test_local_candidate_records_clean_tree_but_cannot_publish(repository):
    root, sha = repository
    (root / "untracked-user-file.txt").write_text("preserve me", encoding="utf-8")

    manifest = create_build_manifest(
        project_root=root,
        version="1.5.72",
        build_number="139",
        env={},
        generated_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
    )

    assert manifest["commit_sha"] == sha
    assert manifest["clean_tree"] is True
    assert manifest["publication_allowed"] is False
    assert manifest["external_trust"]["commit_sha"] is None
    assert (root / "untracked-user-file.txt").is_file()


def test_tracked_change_closes_publication_without_touching_it(repository):
    root, sha = repository
    _git(root, "tag", "v1.5.72")
    (root / "tracked.txt").write_text("dirty\n", encoding="utf-8")

    manifest = create_build_manifest(
        project_root=root,
        version="1.5.72",
        build_number=139,
        env=_ci_env(sha, "refs/tags/v1.5.72"),
    )

    assert manifest["clean_tree"] is False
    assert manifest["publication_allowed"] is False
    assert manifest["tracked_status"]
    assert (root / "tracked.txt").read_text(encoding="utf-8") == "dirty\n"


def test_ci_requires_all_four_external_trust_values(repository):
    root, _sha = repository

    with pytest.raises(BuildMetadataError, match="all external trust inputs"):
        create_build_manifest(
            project_root=root,
            version="1.5.72",
            build_number=139,
            env={"CI": "true", "SSMAKER_PACKAGE_TARGET": "installer"},
        )


def test_ci_rejects_commit_identity_mismatch(repository):
    root, _sha = repository
    _git(root, "tag", "v1.5.72")

    with pytest.raises(BuildMetadataError, match="commit_matches"):
        create_build_manifest(
            project_root=root,
            version="1.5.72",
            build_number=139,
            env=_ci_env("a" * 40, "refs/tags/v1.5.72"),
        )


def test_direct_publication_requires_exact_immutable_version_tag(repository):
    root, sha = repository
    _git(root, "tag", "v1.5.72")

    manifest = create_build_manifest(
        project_root=root,
        version="1.5.72",
        build_number=139,
        env=_ci_env(sha, "refs/tags/v1.5.72"),
    )

    assert manifest["publication_allowed"] is True
    assert manifest["checks"]["publication_ref_matches"] is True


def test_store_publication_is_tag_only_and_dispatch_branch_is_candidate(repository):
    root, sha = repository
    _git(root, "tag", "store-v1.5.72")
    branch_ref = _git(root, "symbolic-ref", "HEAD")
    tag_manifest = create_build_manifest(
        project_root=root,
        version="1.5.72",
        build_number=139,
        env=_ci_env(sha, "refs/tags/store-v1.5.72", "msix"),
    )
    branch_manifest = create_build_manifest(
        project_root=root,
        version="1.5.72",
        build_number=139,
        env=_ci_env(sha, branch_ref, "msix"),
    )

    assert tag_manifest["publication_allowed"] is True
    assert branch_manifest["publication_allowed"] is False
