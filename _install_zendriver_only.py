"""Minimal installer: try zendriver versions compatible with the project venv.

If the venv is Python 3.9, zendriver >= 0.3 won't install (requires 3.10+).
We probe older versions and stop at the first one that works.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
VENV_PY = PROJECT_DIR / ".venv" / "bin" / "python"

assert VENV_PY.exists(), f"venv python missing at {VENV_PY}"

print(f"[install] Using {VENV_PY}")

# Probe the venv's Python version.
ver = subprocess.check_output([str(VENV_PY), "--version"], text=True).strip()
print(f"[install] venv version: {ver}")

CANDIDATES = [
    "zendriver",            # latest (needs Py >= 3.10)
    "zendriver<0.3",        # earlier versions before the 3.10 bump
    "zendriver<0.2",
    "zendriver<0.1",
]

for spec in CANDIDATES:
    print(f"\n[install] Trying: pip install '{spec}'")
    r = subprocess.run(
        [str(VENV_PY), "-m", "pip", "install", spec],
        check=False, capture_output=True, text=True,
    )
    print(r.stdout[-1500:] if r.stdout else "")
    if r.returncode != 0:
        print(r.stderr[-1000:] if r.stderr else "")
        print(f"[install] FAIL ({spec}) exit={r.returncode}")
        continue
    # Verify import works
    check = subprocess.run(
        [str(VENV_PY), "-c", "import zendriver, sys; print('zendriver', getattr(zendriver, '__version__', '?'))"],
        check=False, capture_output=True, text=True,
    )
    if check.returncode == 0:
        print(f"[install] SUCCESS: {check.stdout.strip()}")
        sys.exit(0)
    else:
        print(f"[install] Import check failed: {check.stderr}")

print("[install] ALL candidates failed. Need Python >= 3.10 for zendriver.")
sys.exit(1)
