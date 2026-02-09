# -*- coding: utf-8 -*-
"""
Admin stats aggregation tests.
"""

import os
import sys
import asyncio
import types
import importlib.util
from pathlib import Path
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# Add backend root to path
backend_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_root))

# Minimal env for settings initialization during imports
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

from app.database import Base
from app.models.user import User, UserType
from app.models.registration_request import RegistrationRequest, RequestStatus


# Test environment may not have slowapi installed; provide a minimal stub.
if "slowapi" not in sys.modules:
    slowapi_stub = types.ModuleType("slowapi")

    class _DummyLimiter:
        def __init__(self, *args, **kwargs):
            pass

        def limit(self, *args, **kwargs):
            def _decorator(func):
                return func

            return _decorator

    slowapi_stub.Limiter = _DummyLimiter
    sys.modules["slowapi"] = slowapi_stub


_admin_spec = importlib.util.spec_from_file_location(
    "test_admin_router_module",
    backend_root / "app" / "routers" / "admin.py",
)
_admin_module = importlib.util.module_from_spec(_admin_spec)
assert _admin_spec and _admin_spec.loader
_admin_spec.loader.exec_module(_admin_module)
get_stats = _admin_module.get_stats


def test_admin_stats_includes_work_aggregates():
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    now = datetime.now(timezone.utc)

    db.add_all(
        [
            User(
                username="u1",
                password_hash="hash",
                is_active=True,
                is_online=True,
                current_task="processing",
                user_type=UserType.SUBSCRIBER,
                work_count=-1,
                work_used=10,
                subscription_expires_at=now + timedelta(days=30),
            ),
            User(
                username="u2",
                password_hash="hash",
                is_active=True,
                is_online=False,
                current_task=None,
                user_type=UserType.TRIAL,
                work_count=5,
                work_used=3,
            ),
            User(
                username="u3",
                password_hash="hash",
                is_active=False,
                is_online=True,
                current_task="대기 중",
                user_type=UserType.TRIAL,
                work_count=5,
                work_used=0,
            ),
        ]
    )

    db.add_all(
        [
            RegistrationRequest(
                name="pending",
                username="r_pending",
                password_hash="hash",
                contact="01012341234",
                status=RequestStatus.PENDING,
            ),
            RegistrationRequest(
                name="approved",
                username="r_approved",
                password_hash="hash",
                contact="01022341234",
                status=RequestStatus.APPROVED,
            ),
            RegistrationRequest(
                name="rejected",
                username="r_rejected",
                password_hash="hash",
                contact="01032341234",
                status=RequestStatus.REJECTED,
            ),
        ]
    )
    db.commit()

    stats = asyncio.run(get_stats(request=None, db=db, _admin=True))

    assert stats["users"]["total"] == 3
    assert stats["users"]["active"] == 2
    assert stats["users"]["online"] == 2
    assert stats["users"]["with_subscription"] == 1

    assert stats["work"]["total_used"] == 13
    assert stats["work"]["users_with_work"] == 2
    assert stats["work"]["in_progress_users"] == 1
    assert stats["work"]["avg_used_per_user"] == 4.33

    assert stats["registration_requests"]["pending"] == 1
    assert stats["registration_requests"]["approved"] == 1
    assert stats["registration_requests"]["rejected"] == 1

    db.close()
