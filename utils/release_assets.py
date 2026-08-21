"""Immutable third-party model identities used by Windows release builds."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Mapping


WHISPER_MODEL_ASSETS: Mapping[str, Mapping[str, object]] = {
    "tiny": {
        "repo_id": "Systran/faster-whisper-tiny",
        "revision": "d90ca5fe260221311c53c58e660288d3deb8d356",
        "files": {
            "model.bin": "dcb76c6586fc06cbdac6dd21f14cfd129cc4cdd9dce19bf4ffa62e59cbe6e6d1",
            "config.json": "a73a28cdfe1c43ccc7202fa333d1f89c202477271407ae9a7f19afa52039cac8",
            "tokenizer.json": "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab",
            "vocabulary.txt": "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913",
        },
    },
    "base": {
        "repo_id": "Systran/faster-whisper-base",
        "revision": "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66",
        "files": {
            "model.bin": "d01c3014881c9c6f3133c182f3d2887eb6ca1c789a7538c5c007196857a0a6a9",
            "config.json": "56a6d8110d311f19c8f0471e562832c7527f146b567275bfca59fcf7c184da9a",
            "tokenizer.json": "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab",
            "vocabulary.txt": "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913",
        },
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_whisper_model_assets(root: Path) -> dict[str, object]:
    """Verify every bundled model file and return its manifest projection."""

    verified_models: dict[str, object] = {}
    failures: list[str] = []
    for model_name, identity in WHISPER_MODEL_ASSETS.items():
        model_dir = root / model_name
        expected_files = identity["files"]
        assert isinstance(expected_files, Mapping)
        file_hashes: dict[str, str] = {}
        for filename, expected_hash in expected_files.items():
            path = model_dir / str(filename)
            if not path.is_file():
                failures.append(f"{model_name}/{filename}: missing")
                continue
            actual_hash = sha256_file(path)
            file_hashes[str(filename)] = actual_hash
            if actual_hash != expected_hash:
                failures.append(
                    f"{model_name}/{filename}: expected {expected_hash}, got {actual_hash}"
                )
        verified_models[model_name] = {
            "repo_id": identity["repo_id"],
            "revision": identity["revision"],
            "files": file_hashes,
        }
    if failures:
        raise ValueError("Whisper release asset verification failed: " + "; ".join(failures))
    return {"verified": True, "models": verified_models}
