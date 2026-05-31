#!/usr/bin/env python3
"""
One-time 1688 login helper.

Why this exists
---------------
The automated sourcing pipeline (core/sourcing/pipeline.py) drives 1688 with a
persistent zendriver Chrome profile, but 1688 search is login / anti-bot walled:
without a logged-in session it returns 0 results, which is why 1688 historically
produced no sourced videos. The app had no way to log into 1688, so the pipeline
now *skips* 1688 entirely unless a login exists.

What this does
--------------
Opens the SAME persistent browser profile the pipeline uses, navigates to the
1688 sign-in page, and waits for you to log in. Your session then persists in
that profile, so every future automated run can use 1688. As a backup it also
copies the 1688 cookies into settings (the pipeline bridges those in as well).

Usage
-----
    python scripts/login_1688.py
    # or double-click login_1688.command on macOS
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Allow running from anywhere: make the project root importable.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

LOGIN_URL = "https://login.1688.com/member/signin.htm"


def _resolve_profile() -> str:
    """Match the pipeline's profile resolution exactly so the login lands in the
    browser profile the automated sourcing actually uses."""
    default_profile = os.path.join(str(Path.home()), ".ssmaker", "zendriver_profile")
    profile = os.getenv("SSMAKER_ZENDRIVER_PROFILE", default_profile)
    os.makedirs(profile, exist_ok=True)
    return profile


def _resolve_chrome():
    """Probe common Chrome/Chromium/Edge locations (macOS Chrome isn't on PATH)."""
    candidates = []
    if sys.platform == "darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ]
    elif sys.platform.startswith("linux"):
        candidates = [
            "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium", "/usr/bin/chromium-browser", "/snap/bin/chromium",
        ]
    elif sys.platform.startswith("win"):
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
    return next((p for p in candidates if os.path.isfile(p)), None)


async def _run() -> int:
    try:
        import zendriver as zd
    except Exception as exc:
        print(f"[오류] zendriver 가 설치되어 있지 않습니다: {exc}")
        print("      pip install -r requirements.txt 후 다시 시도하세요.")
        return 2

    profile = _resolve_profile()
    print("=" * 60)
    print(" 1688 로그인 도우미")
    print("=" * 60)
    print(f" 사용 프로필: {profile}")
    print(" 잠시 후 Chrome 창이 열립니다. 1688에 로그인해주세요.")
    print("=" * 60)

    kwargs = {
        "headless": False,
        "user_data_dir": profile,
        "browser_args": [
            "--window-size=1280,900",
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ],
        "browser_connection_timeout": 1.5,
        "browser_connection_max_tries": 30,
    }
    chrome = _resolve_chrome()
    if chrome:
        kwargs["browser_executable_path"] = chrome

    browser = None
    try:
        browser = await zd.start(**kwargs)
    except Exception as exc:
        print(f"[오류] 브라우저를 시작할 수 없습니다: {exc}")
        return 2

    try:
        tab = await browser.get(LOGIN_URL)
        try:
            await tab.sleep(2)
        except Exception:
            pass

        print("\n👉 열린 Chrome 창에서 1688 로그인을 완료하세요.")
        print("   완료한 뒤, 이 터미널로 돌아와 Enter 키를 누르세요...")
        try:
            await asyncio.get_running_loop().run_in_executor(None, input)
        except (EOFError, KeyboardInterrupt):
            pass

        # Verify we left the login page.
        current = ""
        try:
            current = str(await tab.evaluate("location.href") or "")
        except Exception:
            current = ""
        if "login" in current.lower() or "signin" in current.lower():
            print("\n⚠️  아직 로그인 페이지로 보입니다. 로그인이 완료되지 않았을 수 있어요.")
            print("    그래도 세션은 프로필에 저장됩니다. 동작하지 않으면 다시 실행해주세요.")
        else:
            print("\n✅ 로그인 감지됨.")

        # Backup path: copy 1688-domain cookies into settings. The pipeline's
        # _start_browser bridges these into its zendriver session too, so 1688
        # works even if the persistent profile is ever reset.
        saved = 0
        try:
            cookies = await browser.cookies.get_all()
            jar = {}
            for c in cookies:
                dom = str(getattr(c, "domain", "") or "")
                if "1688.com" in dom:
                    name = getattr(c, "name", None)
                    val = getattr(c, "value", None)
                    if name:
                        jar[str(name)] = str(val if val is not None else "")
            if jar:
                from managers.settings_manager import get_settings_manager
                get_settings_manager().set_1688_cookies(jar)
                saved = len(jar)
        except Exception as exc:
            print(f"   (쿠키 백업 저장은 건너뜀: {exc})")
        if saved:
            print(f"✅ 1688 쿠키 {saved}개를 설정에 백업했습니다.")

        print("\n🎉 완료! 이제 자동 소싱에서 1688이 동작합니다.")
        print("   (쿠키가 없으면 자동 스킵되던 1688이, 이제 로그인 세션으로 실행됩니다.)")
        return 0
    finally:
        if browser is not None:
            try:
                await browser.stop()
            except Exception:
                pass


def main() -> int:
    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
