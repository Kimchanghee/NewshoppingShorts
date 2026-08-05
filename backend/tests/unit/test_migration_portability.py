"""Alembic compatibility and data-preserving rollback tests."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


BACKEND_ROOT = Path(__file__).resolve().parents[2]


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
    url = f"sqlite:///{(tmp_path / 'empty.db').as_posix()}"
    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names())

    assert {"users", "admin_sessions", "work_usages", "system_settings"} <= tables
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "20260805_0003"


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
        connection.execute(text("CREATE TABLE admin_sessions (id INTEGER PRIMARY KEY, session_token VARCHAR(255), created_at DATETIME)"))
        connection.execute(text("INSERT INTO admin_sessions VALUES (5, 'legacy-session-token', CURRENT_TIMESTAMP)"))

    _run_alembic(url, "upgrade", "head")

    admin_columns = {column["name"] for column in inspect(engine).get_columns("admin_sessions")}
    assert {
        "session_token",
        "token_hash",
        "created_ip",
        "is_active",
        "created_at",
        "last_used_at",
        "expires_at",
        "revoked_at",
    } <= admin_columns
    with engine.connect() as connection:
        session = connection.execute(
            text(
                "SELECT session_token, token_hash, is_active, expires_at, revoked_at "
                "FROM admin_sessions WHERE id=5"
            )
        ).mappings().one()
        assert session["session_token"] == "legacy-session-token"
        assert len(session["token_hash"]) == 64
        assert not session["is_active"]
        assert session["expires_at"] is not None
        assert session["revoked_at"] is not None

    _run_alembic(url, "downgrade", "base")

    with engine.connect() as connection:
        assert connection.execute(text("SELECT setting_value FROM system_settings WHERE setting_key='legacy'")).scalar_one() == "keep-me"
        assert connection.execute(text("SELECT action FROM user_logs WHERE id=1")).scalar_one() == "legacy-log"
