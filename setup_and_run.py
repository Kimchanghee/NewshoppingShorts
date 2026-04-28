"""Bootstrap installer / launcher for Shopping Shorts Maker.

Run this from VS Code (Run button) to:
  1. Create .venv in the project folder (if missing)
  2. Install requirements.txt into it (only if .venv was just created)
  3. Re-exec main.py using the venv's python

Set FORCE_REINSTALL=1 in the env to force pip install even if venv exists.
"""
from __future__ import annotations

import os
import sys
import subprocess
import venv
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
VENV_DIR = PROJECT_DIR / ".venv"
REQUIREMENTS = PROJECT_DIR / "requirements.txt"
MAIN_PY = PROJECT_DIR / "main.py"


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def ensure_venv() -> bool:
    """Return True if the venv was freshly created this run."""
    if VENV_DIR.exists() and venv_python().exists():
        print(f"[setup] venv already exists: {VENV_DIR}")
        return False
    print(f"[setup] Creating venv at {VENV_DIR} ...")
    builder = venv.EnvBuilder(with_pip=True, upgrade_deps=False)
    builder.create(str(VENV_DIR))
    print("[setup] venv created.")
    return True


def install_requirements():
    py = str(venv_python())
    print(f"[setup] Upgrading pip in {py} ...")
    subprocess.check_call([py, "-m", "pip", "install", "--upgrade", "pip"])
    if not REQUIREMENTS.exists():
        print("[setup] WARN: requirements.txt not found — skipping.")
        return
    print(f"[setup] pip install -r {REQUIREMENTS} (can take several minutes)...")
    subprocess.check_call([py, "-m", "pip", "install", "-r", str(REQUIREMENTS)])
    print("[setup] All requirements installed.")


# Packages needed at runtime but not in requirements.txt (discovered from actual runs).
EXTRA_RUNTIME_PACKAGES = [
    "zendriver",   # used by core.sourcing.pipeline for headless browser scraping
]


def ensure_extra_packages():
    """Install runtime packages we've seen missing, even when skipping full reinstall."""
    py = str(venv_python())
    for pkg in EXTRA_RUNTIME_PACKAGES:
        # Use `pip install` which is idempotent (no-op if already up-to-date).
        print(f"[setup] Ensuring {pkg} is installed ...")
        try:
            subprocess.check_call([py, "-m", "pip", "install", "--quiet", pkg])
        except subprocess.CalledProcessError as e:
            print(f"[setup] WARN: failed to install {pkg}: {e}")


def run_main():
    py = str(venv_python())
    print(f"[setup] Launching: {py} {MAIN_PY}")
    # os.execv replaces the current process so the PyQt window owns this terminal.
    os.execv(py, [py, str(MAIN_PY)])


def main():
    print("=" * 60)
    print("Shopping Shorts Maker - bootstrap setup")
    print(f"Project: {PROJECT_DIR}")
    print(f"Host python: {sys.executable} ({sys.version.split()[0]})")
    print("=" * 60)
    try:
        freshly_created = ensure_venv()
        if freshly_created or os.environ.get("FORCE_REINSTALL") == "1":
            install_requirements()
        else:
            print("[setup] Skipping requirements install (set FORCE_REINSTALL=1 to force).")
        # Always top-up extra runtime packages (zendriver, etc.) — cheap if already installed.
        ensure_extra_packages()
    except subprocess.CalledProcessError as e:
        print(f"[setup] FAILED during install: {e}")
        sys.exit(e.returncode)
    run_main()


if __name__ == "__main__":
    main()
