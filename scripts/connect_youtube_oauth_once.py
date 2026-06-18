from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from managers.youtube_manager import YouTubeManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconnect YouTube OAuth once.")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()

    manager = YouTubeManager(gui=None)
    ok = manager.connect_channel(oauth_timeout_seconds=args.timeout)
    token_path = Path(manager._get_token_path())
    service_ok = manager._ensure_youtube_service()
    channel = manager.get_channel_info()
    verification = manager.get_account_verification_status()

    print(
        json.dumps(
            {
                "ok": bool(ok and service_ok),
                "connect_ok": bool(ok),
                "service_ok": bool(service_ok),
                "token_exists": token_path.exists(),
                "channel_id": channel.get("id", ""),
                "channel_name": channel.get("channel_name", ""),
                "account_email": channel.get("account_email", ""),
                "verification": verification,
                "last_error": manager.get_last_error(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    return 0 if ok and service_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
