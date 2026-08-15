"""Download the exact Faster-Whisper artifacts approved for release builds."""

from __future__ import annotations

import logging
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def download_and_bundle_models(root: Path | None = None) -> bool:
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        logger.error("huggingface_hub is required to download Faster-Whisper models")
        return False

    bundled_root = root or PROJECT_ROOT / "faster_whisper_models"
    bundled_root.mkdir(parents=True, exist_ok=True)
    try:
        for model_name, model in WHISPER_MODEL_CATALOG.items():
            files = model["files"]
            assert isinstance(files, dict)
            logger.info("Downloading %s@%s", model["repo_id"], model["revision"])
            size_dir = bundled_root / model_name
            size_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="verified-download-", dir=size_dir) as temp:
                staged = Path(temp) / "snapshot"
                snapshot_download(
                    repo_id=str(model["repo_id"]),
                    revision=str(model["revision"]),
                    local_dir=staged,
                    allow_patterns=sorted(files),
                )
                shutil.rmtree(staged / ".cache", ignore_errors=True)
                validate_model_directory(model_name, staged)
                repo_cache_name = "models--" + str(model["repo_id"]).replace("/", "--")
                snapshot = size_dir / repo_cache_name / "snapshots" / str(model["revision"])
                if snapshot.exists():
                    shutil.rmtree(snapshot)
                snapshot.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(staged, snapshot)
            validate_model_directory(model_name, snapshot)
            logger.info("Verified %s at %s", model_name, snapshot)
    except Exception:
        logger.exception("Pinned Faster-Whisper artifact download/verification failed")
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(0 if download_and_bundle_models() else 1)
