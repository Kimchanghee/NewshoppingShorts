"""Download and verify immutable Faster-Whisper release assets."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.release_assets import (  # noqa: E402
    WHISPER_MODEL_ASSETS,
    verify_whisper_model_assets,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def download_and_bundle_models(
    *,
    project_root: Path = PROJECT_ROOT,
    verify_only: bool = False,
) -> bool:
    bundled_root = project_root / "faster_whisper_models"
    bundled_root.mkdir(parents=True, exist_ok=True)

    if not verify_only:
        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            logger.error("huggingface-hub is required to download release models")
            return False

        for model_name, identity in WHISPER_MODEL_ASSETS.items():
            expected_files = identity["files"]
            assert isinstance(expected_files, dict)
            logger.info(
                "Downloading %s from %s@%s",
                model_name,
                identity["repo_id"],
                identity["revision"],
            )
            try:
                snapshot_download(
                    repo_id=str(identity["repo_id"]),
                    revision=str(identity["revision"]),
                    allow_patterns=list(expected_files),
                    local_dir=str(bundled_root / model_name),
                )
            except Exception as exc:
                logger.error("Pinned %s model download failed: %s", model_name, exc)
                return False

    try:
        projection = verify_whisper_model_assets(bundled_root)
    except (OSError, ValueError) as exc:
        logger.error("%s", exc)
        return False
    logger.info("Verified immutable Whisper assets: %s", projection)
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify existing model files without network access.",
    )
    args = parser.parse_args()
    return 0 if download_and_bundle_models(verify_only=args.verify_only) else 1


if __name__ == "__main__":
    raise SystemExit(main())
