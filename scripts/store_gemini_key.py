#!/usr/bin/env python3
"""Store a Gemini API key in SecretsManager without printing the key."""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from utils.secrets_manager import SecretsManager


GEMINI_KEY_RE = re.compile(r"^AIza[A-Za-z0-9_-]{35,96}$")
# New 2026 Gemini "Auth key" format (AI Studio now issues AQ.* by default).
GEMINI_AUTH_KEY_RE = re.compile(r"^AQ\.[A-Za-z0-9_.\-]{16,200}$")


def main() -> int:
    key = sys.stdin.read().strip()
    if not key:
        print("ERROR: no key received on stdin")
        return 1
    if not (GEMINI_KEY_RE.match(key) or GEMINI_AUTH_KEY_RE.match(key)):
        print("ERROR: key format does not look like a Gemini API key")
        return 2

    ok_primary = SecretsManager.store_api_key("gemini_api_1", key)
    ok_legacy = SecretsManager.store_api_key("gemini", key)
    if not ok_primary:
        print("ERROR: failed to store Gemini key")
        return 3

    suffix = key[-4:]
    print(f"OK: Gemini key stored as gemini_api_1 (ending ...{suffix})")
    if not ok_legacy:
        print("WARN: legacy alias gemini was not updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
