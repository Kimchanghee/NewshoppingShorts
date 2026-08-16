# -*- coding: utf-8 -*-
"""Administrator user-deletion regression tests."""

import asyncio
import importlib.util
import os
import sys
import types
from pathlib import Path

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

from app.database import Base
from app.models.computer_use_job import ComputerUseJob
from app.models.login_attempt import LoginAttempt
from app.models.registration_request import RegistrationRequest, RequestStatus
from app.models.user import ProgramType, User
from app.models.user_log import UserLog


_admin_spec = importlib.util.spec_from_file_location(
    "test_admin_delete_router_module",
    backend_root / "app" / "routers" / "admin.py",
)
_admin_module = importlib.util.module_from_spec(_admin_spec)
assert _admin_spec and _admin_spec.loader
_admin_spec.loader.exec_module(_admin_module)


def test_delete_user_removes_non_cascading_and_registration_records():
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    user = User(
        username="delete_me",
        password_hash="hash",
        is_active=True,
        program_type=ProgramType.SSMAKER,
    )
    other_program_user = User(
        username="delete_me",
        password_hash="hash",
        is_active=True,
        program_type=ProgramType.STMAKER,
    )
    db.add_all([user, other_program_user])
    db.flush()
    db.add_all(
        [
            RegistrationRequest(
                name="Delete Me",
                username=user.username,
                password_hash="hash",
                contact="01012341234",
                status=RequestStatus.APPROVED,
                program_type="ssmaker",
            ),
            RegistrationRequest(
                name="Keep Other Program",
                username=user.username,
                password_hash="hash",
                contact="01099998888",
                status=RequestStatus.APPROVED,
                program_type="stmaker",
            ),
            UserLog(user_id=user.id, action="login", content="test"),
            LoginAttempt(
                username=user.username,
                ip_address="127.0.0.1",
                success=True,
                program_type="ssmaker",
            ),
            LoginAttempt(
                username=user.username,
                ip_address="127.0.0.2",
                success=True,
                program_type="stmaker",
            ),
            ComputerUseJob(
                job_id="delete-job",
                user_id=user.id,
                scope="all",
                prompt="test",
            ),
        ]
    )
    db.commit()
    user_id = user.id

    delete_user = _admin_module.delete_user
    while hasattr(delete_user, "__wrapped__"):
        delete_user = delete_user.__wrapped__
    result = asyncio.run(
        delete_user(request=None, user_id=user_id, db=db, _admin=True)
    )

    assert result.success is True
    assert db.query(User).filter(User.id == user_id).first() is None
    assert db.query(UserLog).filter(UserLog.user_id == user_id).count() == 0
    assert (
        db.query(ComputerUseJob).filter(ComputerUseJob.user_id == user_id).count()
        == 0
    )
    assert (
        db.query(RegistrationRequest)
        .filter(
            RegistrationRequest.username == "delete_me",
            RegistrationRequest.program_type == "ssmaker",
        )
        .count()
        == 0
    )
    assert (
        db.query(LoginAttempt)
        .filter(
            LoginAttempt.username == "delete_me",
            LoginAttempt.program_type == "ssmaker",
        )
        .count()
        == 0
    )
    assert (
        db.query(RegistrationRequest)
        .filter(
            RegistrationRequest.username == "delete_me",
            RegistrationRequest.program_type == "stmaker",
        )
        .count()
        == 1
    )
    assert (
        db.query(LoginAttempt)
        .filter(
            LoginAttempt.username == "delete_me",
            LoginAttempt.program_type == "stmaker",
        )
        .count()
        == 1
    )

    db.close()
