"""Install Python 3.12 from the downloaded .pkg without using the GUI installer.

Tries two paths:
  1. `installer -pkg ... -target CurrentUserHomeDirectory` (no sudo, user-only)
  2. If that fails, falls back to GUI installer via `open -W <pkg>`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PKG = Path.home() / "Downloads" / "python-3.12.10-macos11.pkg"

assert PKG.exists(), f"pkg missing at {PKG}"

print(f"[install] Installing {PKG.name}")
print("[install] Trying user-only install (no sudo) ...")
result = subprocess.run(
    ["installer", "-pkg", str(PKG), "-target", "CurrentUserHomeDirectory"],
    capture_output=True, text=True,
)
print(result.stdout)
print(result.stderr)
print(f"[install] user-only exit={result.returncode}")

if result.returncode == 0:
    print("[install] User-only install succeeded.")
    sys.exit(0)

print("\n[install] User-only install failed. Falling back to GUI installer.")
print("[install] The macOS Installer app will open. Click through the prompts.")
print("[install] You'll be asked for your admin password near the end.")

# `open -W` waits until the installer app exits, so this script blocks until
# the user finishes (or cancels) the install.
result = subprocess.run(
    ["open", "-W", "-a", "Installer", str(PKG)],
    capture_output=True, text=True,
)
print(result.stdout)
print(result.stderr)
print(f"[install] GUI installer exit={result.returncode}")

# Verify python3.12 ended up at the standard location
target = Path("/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12")
if target.exists():
    print(f"[install] OK — python3.12 at {target}")
else:
    user_target = Path.home() / "Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12"
    if user_target.exists():
        print(f"[install] OK — python3.12 (user) at {user_target}")
    else:
        print("[install] python3.12 not found at expected paths after install.")
        sys.exit(1)
