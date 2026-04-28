"""Wipe the old Python 3.9 venv, recreate it with Python 3.12, install all
deps + zendriver, then exec main.py.

Run from VS Code (Run button) once after Python 3.12 is installed at:
  ~/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
VENV_DIR = PROJECT_DIR / ".venv"
REQUIREMENTS = PROJECT_DIR / "requirements.txt"
MAIN_PY = PROJECT_DIR / "main.py"
PY312 = Path("/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12")

assert PY312.exists(), f"Python 3.12 missing at {PY312}"

VENV_PY = VENV_DIR / "bin" / "python"


def step(msg: str):
    print(f"\n=== {msg} ===")


step(f"Removing old venv at {VENV_DIR}")
if VENV_DIR.exists():
    shutil.rmtree(VENV_DIR)
print("[ok] removed")

step(f"Creating new venv with {PY312}")
subprocess.check_call([str(PY312), "-m", "venv", str(VENV_DIR)])
print(f"[ok] venv created — {VENV_PY}")

step("Upgrading pip")
subprocess.check_call([str(VENV_PY), "-m", "pip", "install", "--upgrade", "pip"])

step("Installing requirements.txt")
subprocess.check_call([str(VENV_PY), "-m", "pip", "install", "-r", str(REQUIREMENTS)])

step("Installing zendriver (Mode 3 dependency)")
subprocess.check_call([str(VENV_PY), "-m", "pip", "install", "zendriver"])

step("Sanity import checks")
subprocess.check_call([
    str(VENV_PY), "-c",
    "import PyQt6; import zendriver; print('imports OK')",
])

step(f"Launching main.py with {VENV_PY}")
os.execv(str(VENV_PY), [str(VENV_PY), str(MAIN_PY)])
