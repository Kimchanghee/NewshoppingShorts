"""Fail a backend deployment before migrations when security settings are absent.

Only variable names and validation reasons are printed. Secret values are never
included in output, so this check is safe to run in hosted build logs.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping


def _clean(value: str | None) -> str:
    cleaned = (value or "").strip()
    return "" if cleaned in {'""', "''"} else cleaned


def deployment_env_errors(env: Mapping[str, str]) -> list[str]:
    errors: list[str] = []
    database_url = _clean(env.get("DATABASE_URL")) or _clean(env.get("POSTGRES_URL"))
    legacy_database = bool(
        _clean(env.get("DB_USER"))
        and _clean(env.get("DB_PASSWORD"))
    )
    if _clean(env.get("VERCEL")) and not database_url:
        errors.append("DATABASE_URL is required for the Vercel PostgreSQL runtime")
    elif not database_url and not legacy_database:
        errors.append("DATABASE_URL (or DB_USER and DB_PASSWORD) is missing")

    minimum_lengths = {
        "JWT_SECRET_KEY": 32,
        "ADMIN_API_KEY": 32,
        "ADMIN_SESSION_PEPPER": 32,
        "APP_VERSION_UPDATE_API_KEY": 32,
        "BILLING_KEY_ENCRYPTION_KEY": 32,
    }
    for name, minimum in minimum_lengths.items():
        if len(_clean(env.get(name))) < minimum:
            errors.append(f"{name} must contain at least {minimum} characters")

    admin_hash = _clean(env.get("ADMIN_PASSWORD_HASH"))
    if not admin_hash.startswith(("$2a$", "$2b$", "$2y$")):
        errors.append("ADMIN_PASSWORD_HASH must contain a bcrypt hash")
    return errors


def main() -> int:
    errors = deployment_env_errors(os.environ)
    if not errors:
        print("Deployment environment preflight passed.")
        return 0

    print("Deployment blocked: required backend environment is incomplete.", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    print("No deployment or database migration was started.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
