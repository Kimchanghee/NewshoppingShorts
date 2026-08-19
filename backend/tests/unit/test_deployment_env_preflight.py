"""Deployment environment preflight regressions."""

import importlib.util
from pathlib import Path


script_path = Path(__file__).parents[2] / "scripts" / "verify_deployment_env.py"
spec = importlib.util.spec_from_file_location("verify_deployment_env", script_path)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def _valid_env():
    return {
        "DATABASE_URL": "postgresql://example.invalid/database",
        "JWT_SECRET_KEY": "j" * 32,
        "ADMIN_API_KEY": "a" * 32,
        "ADMIN_PASSWORD_HASH": "$2b$12$" + "x" * 53,
        "ADMIN_SESSION_PEPPER": "p" * 32,
        "APP_VERSION_UPDATE_API_KEY": "u" * 32,
        "BILLING_KEY_ENCRYPTION_KEY": "b" * 44,
    }


def test_complete_environment_passes_without_exposing_values():
    env = _valid_env()
    assert module.deployment_env_errors(env) == []


def test_blank_or_encoded_empty_secrets_block_deployment_by_name_only():
    env = _valid_env()
    env["DATABASE_URL"] = '""'
    env["JWT_SECRET_KEY"] = ""
    errors = module.deployment_env_errors(env)

    assert any("DATABASE_URL" in error for error in errors)
    assert any("JWT_SECRET_KEY" in error for error in errors)
    assert "postgresql://example.invalid/database" not in str(errors)


def test_legacy_database_credentials_are_supported():
    env = _valid_env()
    env.pop("DATABASE_URL")
    env["DB_USER"] = "service"
    env["DB_PASSWORD"] = "secret"
    assert module.deployment_env_errors(env) == []


def test_vercel_requires_postgres_url_instead_of_unbundled_legacy_driver():
    env = _valid_env()
    env.pop("DATABASE_URL")
    env["DB_USER"] = "service"
    env["DB_PASSWORD"] = "secret"
    env["VERCEL"] = "1"
    assert module.deployment_env_errors(env) == [
        "DATABASE_URL is required for the Vercel PostgreSQL runtime"
    ]
