"""Minimal zendriver test — figure out what kwargs / setup actually works."""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import traceback
from pathlib import Path


PY312 = Path("/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12")
VENV_PY = Path(__file__).resolve().parent / ".venv" / "bin" / "python"

# If we're running under the system /usr/bin/python3, re-exec with venv python.
if "venv" not in sys.executable and VENV_PY.exists():
    os.execv(str(VENV_PY), [str(VENV_PY), __file__])


CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
USER_DATA = os.path.join(tempfile.gettempdir(), "ssmaker_zendriver_test_profile")
os.makedirs(USER_DATA, exist_ok=True)


async def trial(name: str, **kwargs):
    import zendriver as zd
    print(f"\n--- {name} ---")
    print("kwargs:", {k: v for k, v in kwargs.items() if k != "browser_args"})
    print("browser_args:", kwargs.get("browser_args"))
    try:
        browser = await zd.start(**kwargs)
        print("OK browser started, opening tab")
        page = await browser.get("https://example.com")
        await asyncio.sleep(1)
        print("Page title:", (await page.evaluate("document.title")) if hasattr(page, "evaluate") else "?")
        await browser.stop()
        print(f"--- {name}: SUCCESS ---")
        return True
    except Exception as e:
        traceback.print_exc()
        print(f"--- {name}: FAIL: {e} ---")
        return False


async def main():
    base = {
        "headless": False,
        "browser_args": [
            "--window-size=1400,900",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
        "browser_executable_path": CHROME_PATH,
        "user_data_dir": USER_DATA,
    }

    if await trial("with --no-sandbox in args", **base):
        return

    base2 = dict(base)
    base2["headless"] = True
    if await trial("headless=True", **base2):
        return

    base3 = {
        "headless": True,
        "browser_executable_path": CHROME_PATH,
    }
    if await trial("headless minimal", **base3):
        return

    print("\nAll trials failed. Inspect zendriver version / Chrome version.")
    import zendriver
    print("zendriver:", getattr(zendriver, "__version__", "?"))
    import subprocess
    r = subprocess.run([CHROME_PATH, "--version"], capture_output=True, text=True)
    print("Chrome:", r.stdout.strip())


if __name__ == "__main__":
    asyncio.run(main())
