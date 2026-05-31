"""One-shot installer for missing runtime deps discovered at runtime."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
VENV_PY = PROJECT_DIR / ".venv" / "bin" / "python"

# Packages we've seen missing during actual runs.
MISSING = [
    "zendriver",
]


def main():
    py = str(VENV_PY) if VENV_PY.exists() else sys.executable
    print(f"[install] Using python: {py}")
    for pkg in MISSING:
        print(f"[install] pip install {pkg} ...")
        subprocess.check_call([py, "-m", "pip", "install", pkg])
    print("[install] Done.")


if __name__ == "__main__":
    main()
