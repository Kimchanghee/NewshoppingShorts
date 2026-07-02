from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from utils.secrets_manager import SecretsManager


CONFIRM_FLAG = "--yes-delete-gemini-api-keys"


def clear_all_gemini_keys(*, confirmed: bool = False) -> int:
    if not confirmed:
        print(
            "Refusing to delete Gemini API keys. "
            f"Re-run with {CONFIRM_FLAG} only when you intentionally want to wipe them."
        )
        return 2

    print("Clearing all Gemini API keys from SecretsManager...")
    for i in range(1, 11):
        key_name = f"gemini_api_{i}"
        deleted = SecretsManager.delete_api_key(key_name)
        if deleted:
            print(f"Deleted {key_name}")

    config.GEMINI_API_KEYS = {}
    print("Clear complete.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Clear all stored Gemini API keys.")
    parser.add_argument(CONFIRM_FLAG, action="store_true")
    args = parser.parse_args()
    return clear_all_gemini_keys(confirmed=getattr(args, CONFIRM_FLAG.lstrip("-").replace("-", "_")))


if __name__ == "__main__":
    raise SystemExit(main())
