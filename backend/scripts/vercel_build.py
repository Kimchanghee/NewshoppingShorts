"""Run the fail-closed backend steps required before a Vercel web build."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from scripts.apply_account_recovery import main as apply_account_recovery  # noqa: E402
from scripts.verify_deployment_env import main as verify_deployment_env  # noqa: E402


def main() -> int:
    if verify_deployment_env() != 0:
        return 1

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        check=True,
        env=os.environ.copy(),
    )
    return apply_account_recovery()


if __name__ == "__main__":
    raise SystemExit(main())
