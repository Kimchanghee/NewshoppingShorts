# -*- coding: utf-8 -*-
"""
User activity log retention configuration tests.
"""

import os
import sys
import importlib
from pathlib import Path


# Add backend root to path
backend_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_root))


# Minimal env for settings/database import paths
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "127.0.0.1")
os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("JWT_SECRET_KEY", "a" * 64)
os.environ.setdefault("ADMIN_API_KEY", "b" * 64)
os.environ.setdefault("SSMAKER_API_KEY", "c" * 32)
os.environ.setdefault(
    "BILLING_KEY_ENCRYPTION_KEY",
    "uKVciQZlzUKtZPwuiKHl3wVCJJhQrWL6TqrFRClcEOI=",
)


def _reload_logs_router(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    import app.routers.logs as logs_router

    return importlib.reload(logs_router)


def test_user_log_retention_default_is_7_days(monkeypatch):
    monkeypatch.delenv("USER_LOG_RETENTION_DAYS", raising=False)
    logs_router = _reload_logs_router(monkeypatch)
    assert logs_router._LOG_RETENTION_DAYS == 7


def test_user_log_retention_uses_env_value(monkeypatch):
    logs_router = _reload_logs_router(monkeypatch, USER_LOG_RETENTION_DAYS="10")
    assert logs_router._LOG_RETENTION_DAYS == 10


def test_user_log_retention_invalid_env_falls_back_to_default(monkeypatch):
    logs_router = _reload_logs_router(monkeypatch, USER_LOG_RETENTION_DAYS="not-a-number")
    assert logs_router._LOG_RETENTION_DAYS == 7
