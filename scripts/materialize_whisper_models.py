"""Materialize only verified, immutable Faster-Whisper snapshot artifacts."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.whisper_model_catalog import (  # noqa: E402
    WHISPER_MODEL_CATALOG,
    validate_model_directory,
)


def _snapshot_dir(model_name: str, size_dir: Path) -> Path:
    model = WHISPER_MODEL_CATALOG[model_name]
    repo_cache_name = "models--" + str(model["repo_id"]).replace("/", "--")
    return size_dir / repo_cache_name / "snapshots" / str(model["revision"])


def materialize_models(root: Path) -> int:
    if not root.is_dir():
        raise ValueError(f"missing Whisper model root: {root}")
    actual_models = {path.name for path in root.iterdir() if path.is_dir()}
    unexpected = actual_models - set(WHISPER_MODEL_CATALOG)
    if unexpected:
        raise ValueError(f"unexpected Whisper model directories: {sorted(unexpected)}")

    changed = 0
    for model_name, model in WHISPER_MODEL_CATALOG.items():
        size_dir = root / model_name
        files = model["files"]
        assert isinstance(files, dict)
        repo_cache_name = "models--" + str(model["repo_id"]).replace("/", "--")
        unexpected_entries = {
            entry.name for entry in size_dir.iterdir()
            # .locks/CACHEDIR.TAG are Hugging Face cache bookkeeping and are
            # never copied or included by the PyInstaller model-file allowlist.
            if entry.name not in set(files) | {repo_cache_name, ".locks", "CACHEDIR.TAG"}
        }
        if unexpected_entries:
            raise ValueError(
                f"{model_name}: unexpected entries in materialization source: "
                f"{sorted(unexpected_entries)}"
            )
        snapshot = _snapshot_dir(model_name, size_dir)
        validate_model_directory(model_name, snapshot)

        with tempfile.TemporaryDirectory(prefix=f"whisper-{model_name}-", dir=size_dir) as temp:
            verified_copy = Path(temp)
            for filename in files:
                shutil.copy2(snapshot / filename, verified_copy / filename)
            validate_model_directory(model_name, verified_copy)
            for filename in files:
                os.replace(verified_copy / filename, size_dir / filename)
                changed += 1
        print(f"[materialize] verified {model_name}@{model['revision']}")
    return changed


def main() -> int:
    count = materialize_models(PROJECT_ROOT / "faster_whisper_models")
    print(f"[materialize] done: {count} files updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
