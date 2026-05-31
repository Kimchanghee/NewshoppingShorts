"""Install requirements + zendriver directly into the user's Python 3.12
(no venv, since `python3.12 -m venv` failed with SIGABRT).

Then exec main.py using python3.12.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
REQUIREMENTS = PROJECT_DIR / "requirements.txt"
MAIN_PY = PROJECT_DIR / "main.py"
PY312 = Path.home() / "Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12"

assert PY312.exists()


def step(msg: str):
    print(f"\n=== {msg} ===")
    sys.stdout.flush()


step(f"Probe python3.12 ({PY312})")
v = subprocess.run([str(PY312), "--version"], capture_output=True, text=True)
print("--version:", v.stdout.strip(), v.stderr.strip())
print("returncode:", v.returncode)

step("Bootstrap pip")
subprocess.check_call([str(PY312), "-m", "ensurepip", "--upgrade"])

step("Upgrade pip")
subprocess.check_call([str(PY312), "-m", "pip", "install", "--upgrade", "pip"])

step("Install requirements.txt")
subprocess.check_call([str(PY312), "-m", "pip", "install", "-r", str(REQUIREMENTS)])

step("Install zendriver")
subprocess.check_call([str(PY312), "-m", "pip", "install", "zendriver"])

step("Sanity import")
subprocess.check_call([str(PY312), "-c", "import PyQt6, zendriver; print('imports OK')"])

step(f"Launching main.py with {PY312}")
os.execv(str(PY312), [str(PY312), str(MAIN_PY)])
