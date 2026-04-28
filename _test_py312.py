"""Probe what's wrong with python3.12."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PY312 = Path.home() / "Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12"

print(f"PY312 exists: {PY312.exists()}")
print(f"PY312 path: {PY312}")

# Probe 1: --version
r = subprocess.run([str(PY312), "--version"], capture_output=True, text=True)
print(f"\n[--version] exit={r.returncode}")
print("stdout:", r.stdout)
print("stderr:", r.stderr)

# Probe 2: -c "print('hi')"
r = subprocess.run([str(PY312), "-c", "print('hello from py312')"],
                   capture_output=True, text=True)
print(f"\n[-c print] exit={r.returncode}")
print("stdout:", r.stdout)
print("stderr:", r.stderr)

# Probe 3: -m venv to /tmp/probe_venv
import shutil
TMP = Path("/tmp/_probe_venv_312")
if TMP.exists():
    shutil.rmtree(TMP)
r = subprocess.run([str(PY312), "-m", "venv", str(TMP)],
                   capture_output=True, text=True)
print(f"\n[-m venv /tmp/_probe_venv_312] exit={r.returncode}")
print("stdout:", r.stdout[-1500:])
print("stderr:", r.stderr[-1500:])

# Probe 4: ls files at PY312 dir
print("\n[install dir contents]")
for p in (PY312.parent.parent).rglob("*"):
    if p.is_file():
        try:
            rel = p.relative_to(PY312.parent.parent)
        except ValueError:
            rel = p
        if str(rel).startswith("bin/") or "lib/python3.12" in str(rel)[:30]:
            print(rel)
            if str(rel).startswith("bin/python3"):
                pass
        if "Resources" in str(rel) and "Info.plist" in str(rel):
            print(rel)
