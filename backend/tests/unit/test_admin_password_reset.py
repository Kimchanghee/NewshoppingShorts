# -*- coding: utf-8 -*-
"""Administrator password-reset security regressions."""

import asyncio
import importlib.util
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


backend_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_root))

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

try:
    import slowapi  # noqa: F401
except ModuleNotFoundError:
    slowapi_stub = types.ModuleType("slowapi")
    slowapi_stub.__path__ = []
    errors_stub = types.ModuleType("slowapi.errors")

    class RateLimitExceeded(Exception):
        pass

    errors_stub.RateLimitExceeded = RateLimitExceeded
    slowapi_stub.errors = errors_stub

    class _DummyLimiter:
        def __init__(self, *args, **kwargs):
            pass

        def limit(self, *args, **kwargs):
            def _decorator(func):
                return func

            return _decorator

    slowapi_stub.Limiter = _DummyLimiter
    sys.modules["slowapi"] = slowapi_stub
    sys.modules["slowapi.errors"] = errors_stub

from app.database import Base  # noqa: E402
from app.models.login_attempt import LoginAttempt  # noqa: E402
from app.models.session import SessionModel  # noqa: E402
from app.models.user import ProgramType, User  # noqa: E402
from app.models.user_log import UserLog  # noqa: E402
from app.utils.password import hash_password, verify_password  # noqa: E402


_admin_spec = importlib.util.spec_from_file_location(
    "test_admin_password_reset_router_module",
    backend_root / "app" / "routers" / "admin.py",
)
_admin_module = importlib.util.module_from_spec(_admin_spec)
assert _admin_spec and _admin_spec.loader
_admin_spec.loader.exec_module(_admin_module)


def _database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _reset(db, user_id: int, **overrides):
    payload = {
        "username_confirmation": "reset_me",
        "program_type": "ssmaker",
        "new_password": "FreshPassword123",
    }
    payload.update(overrides)
    reset_user_password = _admin_module.reset_user_password
    while hasattr(reset_user_password, "__wrapped__"):
        reset_user_password = reset_user_password.__wrapped__
    return asyncio.run(
        reset_user_password(
            request=None,
            user_id=user_id,
            data=_admin_module.ResetUserPasswordRequest(**payload),
            db=db,
            _admin=True,
        )
    )


def test_password_reset_replaces_hash_revokes_sessions_and_writes_safe_audit():
    db = _database()
    old_password = "OldPassword123"
    user = User(
        username="reset_me",
        password_hash=hash_password(old_password),
        is_active=True,
        program_type=ProgramType.SSMAKER,
    )
    other = User(
        username="keep_me",
        password_hash=hash_password(old_password),
        is_active=True,
        program_type=ProgramType.SSMAKER,
    )
    db.add_all([user, other])
    db.flush()
    expires_at = datetime.now(timezone.utc) + timedelta(days=1)
    db.add_all(
        [
            SessionModel(
                user_id=user.id,
                program_type="ssmaker",
                token_jti="active-reset-session",
                ip_address="127.0.0.1",
                expires_at=expires_at,
                is_active=True,
            ),
            SessionModel(
                user_id=user.id,
                program_type="ssmaker",
                token_jti="inactive-reset-session",
                ip_address="127.0.0.1",
                expires_at=expires_at,
                is_active=False,
            ),
            SessionModel(
                user_id=other.id,
                program_type="ssmaker",
                token_jti="other-session",
                ip_address="127.0.0.1",
                expires_at=expires_at,
                is_active=True,
            ),
        ]
    )
    db.add_all(
        [
            LoginAttempt(
                username=user.username,
                ip_address="127.0.0.1",
                success=False,
                program_type="ssmaker",
            ),
            LoginAttempt(
                username=other.username,
                ip_address="127.0.0.2",
                success=False,
                program_type="ssmaker",
            ),
        ]
    )
    db.commit()

    result = _reset(db, user.id)
    db.refresh(user)

    assert result.success is True
    assert result.data == {
        "user_id": user.id,
        "sessions_revoked": 1,
        "login_attempts_cleared": 1,
    }
    assert verify_password("FreshPassword123", user.password_hash) is True
    assert verify_password(old_password, user.password_hash) is False
    assert (
        db.query(SessionModel)
        .filter(SessionModel.user_id == user.id, SessionModel.is_active.is_(True))
        .count()
        == 0
    )
    assert (
        db.query(SessionModel)
        .filter(SessionModel.user_id == other.id, SessionModel.is_active.is_(True))
        .count()
        == 1
    )
    assert (
        db.query(LoginAttempt)
        .filter(LoginAttempt.username == user.username)
        .count()
        == 0
    )
    assert (
        db.query(LoginAttempt)
        .filter(LoginAttempt.username == other.username)
        .count()
        == 1
    )
    audit = (
        db.query(UserLog)
        .filter(UserLog.user_id == user.id, UserLog.action == "admin_password_reset")
        .one()
    )
    assert audit.level == "WARNING"
    assert "sessions_revoked=1" in audit.content
    assert "login_attempts_cleared=1" in audit.content
    assert "FreshPassword123" not in audit.content
    assert user.password_hash not in audit.content
    assert "password" not in str(result.data).lower()
    db.close()


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"username_confirmation": "someone_else"}, "사용자명이 일치하지 않습니다."),
        ({"program_type": "stmaker"}, "프로그램이 일치하지 않습니다."),
    ],
)
def test_password_reset_rejects_wrong_account_confirmation(overrides, message):
    db = _database()
    original_hash = hash_password("OldPassword123")
    user = User(
        username="reset_me",
        password_hash=original_hash,
        is_active=True,
        program_type=ProgramType.SSMAKER,
    )
    db.add(user)
    db.commit()

    result = _reset(db, user.id, **overrides)
    db.refresh(user)

    assert result.success is False
    assert result.message == message
    assert user.password_hash == original_hash
    assert db.query(UserLog).count() == 0
    db.close()


@pytest.mark.parametrize("password", ["short1", "onlyletters", "12345678"])
def test_password_reset_schema_enforces_shared_password_policy(password):
    with pytest.raises(ValidationError):
        _admin_module.ResetUserPasswordRequest(
            username_confirmation="reset_me",
            program_type="ssmaker",
            new_password=password,
        )
