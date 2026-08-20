"""Run the fail-closed backend steps required before a Vercel web build."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

def _is_preview_deployment() -> bool:
    return os.environ.get("VERCEL_ENV", "").strip().lower() == "preview"


def _load_backend_steps():
    from scripts.apply_account_recovery import main as apply_account_recovery
    from scripts.verify_deployment_env import main as verify_deployment_env

    return apply_account_recovery, verify_deployment_env


def main() -> int:
    if _is_preview_deployment():
        print(
            "Vercel preview detected: skipping backend preflight, migrations, "
            "and account recovery."
        )
        return 0

    apply_account_recovery, verify_deployment_env = _load_backend_steps()
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
