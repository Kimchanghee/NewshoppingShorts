from __future__ import annotations

import os
import subprocess
import time
from urllib.parse import urlencode
from typing import Any, Dict

import requests
from utils.logging_config import get_logger

logger = get_logger(__name__)


ADMIN_URL = "https://linktr.ee/admin/links"
DEFAULT_LINKTREE_PROFILE_URL = "https://linktr.ee/studio.idol"
DEFAULT_TIMEOUT_SECONDS = 90


def _bool_env(name: str, default: bool = False) -> bool:
    raw = str(os.environ.get(name, "") or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def browser_publish_enabled() -> bool:
    return _bool_env("SSMAKER_LINKTREE_BROWSER_PUBLISH", False)


def close_tab_after_verify_enabled() -> bool:
    return _bool_env("SSMAKER_LINKTREE_CLOSE_TAB_AFTER_VERIFY", True)


def _open_browser_url(url: str) -> None:
    if os.name == "nt":
        try:
            subprocess.Popen(
                ["chrome.exe", "--new-window", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            os.startfile(url)  # type: ignore[attr-defined]
        return
    import webbrowser

    webbrowser.open(url)


def _close_linktree_browser_window() -> Dict[str, Any]:
    if os.name != "nt" or not close_tab_after_verify_enabled():
        return {"attempted": False, "closed": False}

    command = r"""
$shell = New-Object -ComObject WScript.Shell
$titles = @(
  'Linktree',
  'linktr.ee',
  'Linktree Admin'
)
foreach ($title in $titles) {
  if ($shell.AppActivate($title)) {
    Start-Sleep -Milliseconds 350
    $shell.SendKeys('%{F4}')
    Start-Sleep -Milliseconds 350
    exit 0
  }
}
exit 2
"""
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-WindowStyle",
                "Hidden",
                "-Command",
                command,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
        return {
            "attempted": True,
            "closed": completed.returncode == 0,
            "returncode": completed.returncode,
        }
    except Exception as exc:
        logger.warning("[Linktree] Browser cleanup failed: %s", exc)
        return {"attempted": True, "closed": False, "error": str(exc)}


def _build_create_link_url(title: str, url: str) -> str:
    params = urlencode(
        {
            "action": "create-link",
            "title": title,
            "url": url,
            "active": "true",
            "utm_source": "url",
            "utm_channel": "ssmaker",
        }
    )
    return f"{ADMIN_URL}?{params}"


def _verify_public_card(number: str, purchase_url: str, *, profile_url: str) -> Dict[str, Any]:
    try:
        response = requests.get(
            profile_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
                ),
            },
            timeout=30,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc), "status_code": 0}
    text = response.text
    marker_ok = True if not number else number in text
    return {
        "ok": response.status_code == 200 and marker_ok and purchase_url in text,
        "status_code": response.status_code,
        "has_number": marker_ok,
        "has_purchase_url": purchase_url in text,
    }


def publish_link_via_visible_browser(
    *,
    title: str,
    url: str,
    number: str,
    profile_url: str = "",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Publish a Linktree card through the logged-in visible Chrome session.

    Linktree does not expose a broadly available write API. This fallback uses
    Linktree Admin's authenticated create-link deep link in the user's logged-in
    Chrome session. It is meant for the local full-automation workstation, not
    for headless servers.
    """
    if not browser_publish_enabled():
        return {
            "ok": False,
            "method": "browser_disabled",
            "blocking_reason": "Linktree browser publish fallback is disabled.",
        }

    target_url = str(url or "").strip()
    target_title = str(title or "").strip() or "Shopping Shorts Link"
    if not target_url:
        return {
            "ok": False,
            "method": "browser",
            "blocking_reason": "Linktree browser publish target URL is empty.",
        }

    profile = str(profile_url or "").strip() or DEFAULT_LINKTREE_PROFILE_URL
    existing_check = _verify_public_card(str(number or "").strip(), target_url, profile_url=profile)
    if existing_check.get("ok"):
        return {
            "ok": True,
            "method": "browser_existing",
            "profile_url": profile,
            "public_verification": existing_check,
            "blocking_reason": "",
        }

    started = time.time()
    opened_browser = False
    result: Dict[str, Any]
    try:
        _open_browser_url(_build_create_link_url(target_title, target_url))
        opened_browser = True

        public_check: Dict[str, Any] = {}
        while time.time() - started < timeout_seconds:
            public_check = _verify_public_card(number, target_url, profile_url=profile)
            if public_check.get("ok"):
                result = {
                    "ok": True,
                    "method": "browser_deeplink",
                    "profile_url": profile,
                    "public_verification": public_check,
                    "blocking_reason": "",
                }
                break
            time.sleep(5)
        else:
            result = {
                "ok": False,
                "method": "browser_deeplink",
                "profile_url": profile,
                "public_verification": public_check,
                "blocking_reason": (
                    "Linktree create-link deep link opened, but the public page did not verify before timeout. "
                    "Confirm Chrome is logged in to the expected Linktree account."
                ),
            }
    except Exception as exc:
        logger.warning("[Linktree] Browser publish failed: %s", exc)
        result = {
            "ok": False,
            "method": "browser_deeplink",
            "profile_url": profile,
            "blocking_reason": str(exc),
        }
    if opened_browser:
        result["browser_cleanup"] = _close_linktree_browser_window()
    return result
