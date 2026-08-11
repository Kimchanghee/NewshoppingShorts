"""Alembic compatibility and data-preserving rollback tests."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session


BACKEND_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("JWT_SECRET_KEY", "a" * 64)
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")


def test_postgres_migration_lock_is_transaction_scoped():
    migration_env = (BACKEND_ROOT / "migrations" / "env.py").read_text(encoding="utf-8")

    assert "pg_advisory_xact_lock" in migration_env
    assert "pg_advisory_lock(" not in migration_env
    assert "pg_advisory_unlock(" not in migration_env


def _run_alembic(database_url: str, *args: str) -> None:
    environment = dict(os.environ)
    environment.update(
        DATABASE_URL=database_url,
        JWT_SECRET_KEY="a" * 64,
    )
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_empty_database_upgrades_to_current_head(tmp_path):
    from app.database import EXPECTED_ALEMBIC_REVISION

    url = f"sqlite:///{(tmp_path / 'empty.db').as_posix()}"
    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names())

    assert {"users", "admin_sessions", "work_usages", "system_settings"} <= tables
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == EXPECTED_ALEMBIC_REVISION
            == "20260811_0006"
        )
        registration_columns = {
            column["name"] for column in inspect(connection).get_columns("registration_requests")
        }
        assert {
            "terms_accepted",
            "privacy_accepted",
            "terms_version",
            "privacy_version",
            "terms_accepted_at",
            "privacy_accepted_at",
        } <= registration_columns


def test_legacy_tables_and_rows_survive_compatibility_downgrade(tmp_path):
    url = f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(50), password_hash VARCHAR(255))"))
        connection.execute(text("CREATE TABLE registration_requests (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE billing_keys (id INTEGER PRIMARY KEY, user_id VARCHAR(100), enc_bill VARCHAR(1024))"))
        connection.execute(text("CREATE TABLE system_settings (setting_key VARCHAR(128) PRIMARY KEY, setting_value TEXT NOT NULL)"))
        connection.execute(text("INSERT INTO system_settings VALUES ('legacy', 'keep-me')"))
        connection.execute(text("CREATE TABLE user_logs (id INTEGER PRIMARY KEY, user_id INTEGER, action VARCHAR(100))"))
        connection.execute(text("INSERT INTO user_logs VALUES (1, 7, 'legacy-log')"))
        connection.execute(text("CREATE TABLE admin_sessions (session_token VARCHAR(255) PRIMARY KEY, created_at DATETIME)"))
        connection.execute(text("INSERT INTO admin_sessions VALUES ('legacy-session-token', CURRENT_TIMESTAMP)"))
        connection.execute(text("CREATE INDEX ix_admin_sessions_expires_at ON admin_sessions(created_at)"))

    _run_alembic(url, "upgrade", "head")

    admin_columns = {column["name"] for column in inspect(engine).get_columns("admin_sessions")}
    assert {
        "id",
        "token_hash",
        "created_ip",
        "is_active",
        "created_at",
        "last_used_at",
        "expires_at",
        "revoked_at",
    } <= admin_columns
    with engine.connect() as connection:
        system_setting_columns = {
            column["name"]
            for column in inspect(connection).get_columns("system_settings")
        }
        assert "updated_at" in system_setting_columns
        assert connection.execute(text("SELECT COUNT(*) FROM admin_sessions")).scalar_one() == 0
        assert connection.execute(
            text("SELECT session_token FROM admin_sessions_legacy_20260805")
        ).scalar_one() == "legacy-session-token"

    _run_alembic(url, "downgrade", "base")

    with engine.connect() as connection:
        assert connection.execute(text("SELECT setting_value FROM system_settings WHERE setting_key='legacy'")).scalar_one() == "keep-me"
        assert connection.execute(text("SELECT action FROM user_logs WHERE id=1")).scalar_one() == "legacy-log"
        assert connection.execute(
            text("SELECT session_token FROM admin_sessions_legacy_20260805")
        ).scalar_one() == "legacy-session-token"


def test_smoke_account_cleanup_requires_exact_id_and_username(tmp_path):
    url = f"sqlite:///{(tmp_path / 'cleanup.db').as_posix()}"
    _run_alembic(url, "upgrade", "20260808_0004")

    from app.models.computer_use_job import ComputerUseJob
    from app.models.login_attempt import LoginAttempt
    from app.models.registration_request import RegistrationRequest, RequestStatus
    from app.models.user import User
    from app.models.user_log import UserLog

    engine = create_engine(url)
    with Session(engine) as session:
        disposable = User(
            id=28,
            username="ui_full_1786295998_4c6d80",
            password_hash="hash",
            is_active=True,
        )
        preserved = User(
            id=29,
            username="ui_full_1786295998_other",
            password_hash="hash",
            is_active=True,
        )
        session.add_all([disposable, preserved])
        session.flush()
        session.add_all(
            [
                RegistrationRequest(
                    name="Disposable QA",
                    username=disposable.username,
                    password_hash="hash",
                    contact="01092754320",
                    status=RequestStatus.APPROVED,
                ),
                UserLog(user_id=disposable.id, action="login", content="test"),
                LoginAttempt(
                    username=disposable.username,
                    ip_address="127.0.0.1",
                    success=True,
                ),
                ComputerUseJob(
                    job_id="cleanup-job",
                    user_id=disposable.id,
                    scope="all",
                    prompt="test",
                ),
            ]
        )
        session.commit()

    _run_alembic(url, "upgrade", "head")

    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT COUNT(*) FROM users WHERE id=28")
        ).scalar_one() == 0
        assert connection.execute(
            text("SELECT COUNT(*) FROM registration_requests WHERE username=:username"),
            {"username": "ui_full_1786295998_4c6d80"},
        ).scalar_one() == 0
        assert connection.execute(
            text("SELECT COUNT(*) FROM login_attempts WHERE username=:username"),
            {"username": "ui_full_1786295998_4c6d80"},
        ).scalar_one() == 0
        assert connection.execute(
            text("SELECT COUNT(*) FROM user_logs WHERE user_id=28")
        ).scalar_one() == 0
        assert connection.execute(
            text("SELECT COUNT(*) FROM computer_use_jobs WHERE user_id=28")
        ).scalar_one() == 0
        assert connection.execute(
            text("SELECT username FROM users WHERE id=29")
        ).scalar_one() == "ui_full_1786295998_other"
