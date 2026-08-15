"""Immutable Faster-Whisper artifacts included in release builds."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Mapping

_COMMIT_RE = re.compile(r"[0-9a-f]{40}")
_FILENAMES = {"model.bin", "config.json", "tokenizer.json", "vocabulary.txt"}

WHISPER_MODEL_CATALOG: Mapping[str, Mapping[str, object]] = {
    "tiny": {
        "repo_id": "Systran/faster-whisper-tiny",
        "revision": "d90ca5fe260221311c53c58e660288d3deb8d356",
        "files": {
            "config.json": (2249, "a73a28cdfe1c43ccc7202fa333d1f89c202477271407ae9a7f19afa52039cac8"),
            "model.bin": (75538270, "dcb76c6586fc06cbdac6dd21f14cfd129cc4cdd9dce19bf4ffa62e59cbe6e6d1"),
            "tokenizer.json": (2203239, "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab"),
            "vocabulary.txt": (459861, "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913"),
        },
    },
    "base": {
        "repo_id": "Systran/faster-whisper-base",
        "revision": "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66",
        "files": {
            "config.json": (2309, "56a6d8110d311f19c8f0471e562832c7527f146b567275bfca59fcf7c184da9a"),
            "model.bin": (145217532, "d01c3014881c9c6f3133c182f3d2887eb6ca1c789a7538c5c007196857a0a6a9"),
            "tokenizer.json": (2203239, "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab"),
            "vocabulary.txt": (459861, "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913"),
        },
    },
}


def validate_catalog(catalog: Mapping[str, Mapping[str, object]] = WHISPER_MODEL_CATALOG) -> None:
    """Reject incomplete catalogs and mutable Hugging Face revisions."""
    if set(catalog) != {"tiny", "base"}:
        raise ValueError("Whisper catalog must contain exactly tiny and base")
    for model_name, model in catalog.items():
        revision = model.get("revision")
        if not isinstance(revision, str) or _COMMIT_RE.fullmatch(revision) is None:
            raise ValueError(f"{model_name}: revision must be an immutable 40-character commit SHA")
        if model.get("repo_id") != f"Systran/faster-whisper-{model_name}":
            raise ValueError(f"{model_name}: unexpected Hugging Face repository")
        files = model.get("files")
        if not isinstance(files, dict) or set(files) != _FILENAMES:
            raise ValueError(f"{model_name}: artifact manifest is incomplete or unexpected")
        for filename, artifact in files.items():
            if (not isinstance(artifact, tuple) or len(artifact) != 2
                    or not isinstance(artifact[0], int) or artifact[0] <= 0
                    or not isinstance(artifact[1], str)
                    or re.fullmatch(r"[0-9a-f]{64}", artifact[1]) is None):
                raise ValueError(f"{model_name}/{filename}: invalid size/SHA-256 pin")


def validate_model_directory(model_name: str, directory: Path) -> None:
    """Verify an artifact directory exactly matches its pinned manifest."""
    validate_catalog()
    if model_name not in WHISPER_MODEL_CATALOG:
        raise ValueError(f"Unknown Whisper model: {model_name}")
    files = WHISPER_MODEL_CATALOG[model_name]["files"]
    assert isinstance(files, dict)
    if not directory.is_dir():
        raise ValueError(f"{model_name}: artifact directory is missing: {directory}")
    actual_names = {entry.name for entry in directory.iterdir()}
    if actual_names != set(files):
        missing = sorted(set(files) - actual_names)
        unexpected = sorted(actual_names - set(files))
        raise ValueError(f"{model_name}: artifact set mismatch; missing={missing}, unexpected={unexpected}")
    validate_materialized_model_files(model_name, directory)


def validate_materialized_model_files(model_name: str, directory: Path) -> None:
    """Verify the allowlisted flat files while ignoring cache bookkeeping."""
    validate_catalog()
    if model_name not in WHISPER_MODEL_CATALOG:
        raise ValueError(f"Unknown Whisper model: {model_name}")
    files = WHISPER_MODEL_CATALOG[model_name]["files"]
    assert isinstance(files, dict)
    if not directory.is_dir():
        raise ValueError(f"{model_name}: artifact directory is missing: {directory}")
    for filename, (expected_size, expected_hash) in files.items():
        path = directory / filename
        if not path.is_file():
            raise ValueError(f"{model_name}/{filename}: not a file")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        actual_size = path.stat().st_size
        actual_hash = digest.hexdigest()
        if actual_size != expected_size or actual_hash != expected_hash:
            raise ValueError(
                f"{model_name}/{filename}: integrity mismatch "
                f"(size={actual_size}, sha256={actual_hash})"
            )


validate_catalog()
