"""Security contracts for the bundled Faster-Whisper model artifacts."""

from pathlib import Path

import pytest

from config.whisper_model_catalog import (
    WHISPER_MODEL_CATALOG,
    validate_catalog,
    validate_model_directory,
)


ROOT = Path(__file__).resolve().parents[2]


def test_catalog_uses_official_repositories_and_immutable_commits():
    validate_catalog()
    assert WHISPER_MODEL_CATALOG["tiny"]["repo_id"] == "Systran/faster-whisper-tiny"
    assert WHISPER_MODEL_CATALOG["tiny"]["revision"] == "d90ca5fe260221311c53c58e660288d3deb8d356"
    assert WHISPER_MODEL_CATALOG["base"]["repo_id"] == "Systran/faster-whisper-base"
    assert WHISPER_MODEL_CATALOG["base"]["revision"] == "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66"


def test_catalog_rejects_mutable_revision():
    catalog = {name: dict(model) for name, model in WHISPER_MODEL_CATALOG.items()}
    catalog["tiny"]["revision"] = "main"
    with pytest.raises(ValueError, match="immutable 40-character commit SHA"):
        validate_catalog(catalog)


def _write_manifest_names(directory: Path, model_name: str) -> None:
    files = WHISPER_MODEL_CATALOG[model_name]["files"]
    assert isinstance(files, dict)
    for filename in files:
        (directory / filename).write_bytes(b"")


def test_verification_rejects_missing_file(tmp_path):
    _write_manifest_names(tmp_path, "tiny")
    (tmp_path / "model.bin").unlink()
    with pytest.raises(ValueError, match="artifact set mismatch"):
        validate_model_directory("tiny", tmp_path)


def test_verification_rejects_tampered_file(tmp_path):
    _write_manifest_names(tmp_path, "tiny")
    (tmp_path / "config.json").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="integrity mismatch"):
        validate_model_directory("tiny", tmp_path)


def test_verification_rejects_unexpected_file(tmp_path):
    _write_manifest_names(tmp_path, "tiny")
    (tmp_path / "README.md").write_text("not bundled", encoding="utf-8")
    with pytest.raises(ValueError, match=r"unexpected=\['README.md'\]"):
        validate_model_directory("tiny", tmp_path)


def test_download_and_materialization_never_use_mutable_aliases():
    downloader = (ROOT / "scripts" / "download_whisper_models.py").read_text(encoding="utf-8")
    materializer = (ROOT / "scripts" / "materialize_whisper_models.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "build-and-deploy.yml").read_text(
        encoding="utf-8"
    )
    spec = (ROOT / "ssmaker.spec").read_text(encoding="utf-8-sig")
    assert 'revision=str(model["revision"])' in downloader
    assert "allow_patterns=sorted(files)" in downloader
    assert "WhisperModel(" not in downloader
    assert '"main"' not in downloader
    assert "stat().st_mtime" not in materializer
    assert "validate_model_directory(model_name, snapshot)" in materializer
    whisper_step = workflow.split("- name: Download Whisper models", 1)[1].split(
        "- name:", 1
    )[0]
    assert "python scripts/download_whisper_models.py" in whisper_step
    assert "continue-on-error" not in whisper_step
    assert "WHISPER_MODEL_CATALOG.items()" in spec
    assert "validate_materialized_model_files(model_name, Path(size_dir))" in spec
