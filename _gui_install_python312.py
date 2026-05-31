
"""Launch the Python 3.12 GUI installer. User needs to click through it and
enter admin password when prompted. Script waits until Installer exits, then
verifies /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 exists.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PKG = Path.home() / "Downloads" / "python-3.12.10-macos11.pkg"
SYSTEM_PY312 = Path("/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12")

print(f"[install] Opening GUI installer: {PKG}")
print("[install] Please click Continue → Continue → Continue → Install,")
print("[install] then enter your Mac admin password when prompted.")
print("[install] This script will wait until the installer window closes.")

# `open -W` blocks until the Installer app quits. The installer shows the
# password prompt modally, so macOS itself handles that part.
proc = subprocess.run(["open", "-W", "-a", "Installer", str(PKG)])
print(f"\n[install] Installer exited with code {proc.returncode}")

if SYSTEM_PY312.exists():
    print(f"[install] SUCCESS — system Python 3.12 at {SYSTEM_PY312}")
    # Probe it
    r = subprocess.run([str(SYSTEM_PY312), "--version"], capture_output=True, text=True)
    print(f"[install] {r.stdout.strip()}")
else:
    print("[install] FAILED — python3.12 not found at /Library/Frameworks/...")
    print("[install] Did you cancel the installer?")
    sys.exit(1)
