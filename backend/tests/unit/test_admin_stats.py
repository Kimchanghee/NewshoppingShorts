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

from sqlalchemy import create_engine, event
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
try:
    import slowapi  # noqa: F401
except ModuleNotFoundError:
    slowapi_stub = types.ModuleType("slowapi")
    slowapi_stub.__path__ = []  # mark as package so `slowapi.errors` can be imported

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


_admin_spec = importlib.util.spec_from_file_location(
    "test_admin_router_module",
    backend_root / "app" / "routers" / "admin.py",
)
_admin_module = importlib.util.module_from_spec(_admin_spec)
assert _admin_spec and _admin_spec.loader
_admin_spec.loader.exec_module(_admin_module)
get_stats = _admin_module.get_stats
list_users = _admin_module.list_users
extend_subscription = _admin_module.extend_subscription


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
                last_heartbeat=now,
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
                last_heartbeat=now - timedelta(minutes=5),
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

    # The router is rate-limited via slowapi, which wraps the endpoint and
    # requires a real starlette Request instance. For unit testing we call the
    # underlying function directly.
    fn = get_stats
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    stats = asyncio.run(fn(request=None, db=db, _admin=True))

    assert stats["users"]["total"] == 3
    assert stats["users"]["active"] == 2
    assert stats["users"]["online"] == 1
    assert stats["users"]["with_subscription"] == 1

    assert stats["work"]["total_used"] == 13
    assert stats["work"]["users_with_work"] == 2
    assert stats["work"]["in_progress_users"] == 1
    assert stats["work"]["avg_used_per_user"] == 4.33

    assert stats["registration_requests"]["pending"] == 1
    assert stats["registration_requests"]["approved"] == 1
    assert stats["registration_requests"]["rejected"] == 1

    db.close()


def test_admin_stats_can_skip_registration_request_queries():
    engine = create_engine("sqlite:///:memory:")
    statements = []
    event.listen(
        engine,
        "before_cursor_execute",
        lambda _conn, _cursor, statement, _parameters, _context, _executemany: statements.append(statement),
    )
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    db.add(User(username="fast", password_hash="hash", is_active=True, work_used=2))
    db.commit()
    statements.clear()

    fn = get_stats
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    stats = asyncio.run(fn(request=None, include_requests=False, db=db, _admin=True))

    assert stats["users"]["total"] == 1
    assert stats["work"]["total_used"] == 2
    assert stats["registration_requests"] == {
        "pending": 0,
        "approved": 0,
        "rejected": 0,
    }
    assert len([statement for statement in statements if statement.lstrip().upper().startswith("SELECT")]) == 1

    db.close()


def test_admin_user_list_gets_page_and_total_in_one_select():
    engine = create_engine("sqlite:///:memory:")
    statements = []
    event.listen(
        engine,
        "before_cursor_execute",
        lambda _conn, _cursor, statement, _parameters, _context, _executemany: statements.append(statement),
    )
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    db.add_all([
        User(username=f"user-{index}", password_hash="hash", is_active=True)
        for index in range(3)
    ])
    db.commit()
    statements.clear()

    fn = list_users
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    result = asyncio.run(fn(
        request=None,
        search=None,
        program_type=None,
        status=None,
        include_total=True,
        cleanup_offline=False,
        page=1,
        page_size=2,
        db=db,
        _admin=True,
    ))

    assert len(result.users) == 2
    assert result.total == 3
    assert len([statement for statement in statements if statement.lstrip().upper().startswith("SELECT")]) == 1

    db.close()


def test_extending_trial_starts_subscription_from_now():
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    trial = User(
        username="trial-extension",
        password_hash="hash",
        is_active=True,
        user_type=UserType.TRIAL,
        work_count=5,
        subscription_expires_at=datetime.now(timezone.utc) + timedelta(days=365),
    )
    db.add(trial)
    db.commit()

    before = datetime.now(timezone.utc)
    fn = extend_subscription
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    result = asyncio.run(fn(
        request=None,
        user_id=trial.id,
        data=_admin_module.ExtendSubscriptionRequest(days=30),
        db=db,
        _admin=True,
    ))
    after = datetime.now(timezone.utc)
    db.refresh(trial)

    assert result.success is True
    assert trial.user_type == UserType.SUBSCRIBER
    assert before + timedelta(days=30) <= trial.subscription_expires_at.replace(tzinfo=timezone.utc)
    assert trial.subscription_expires_at.replace(tzinfo=timezone.utc) <= after + timedelta(days=30)
    db.close()


def test_extending_subscriber_keeps_remaining_paid_time():
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    current_expiry = datetime.now(timezone.utc) + timedelta(days=10)
    subscriber = User(
        username="subscriber-extension",
        password_hash="hash",
        is_active=True,
        user_type=UserType.SUBSCRIBER,
        work_count=-1,
        subscription_expires_at=current_expiry,
    )
    db.add(subscriber)
    db.commit()

    fn = extend_subscription
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    result = asyncio.run(fn(
        request=None,
        user_id=subscriber.id,
        data=_admin_module.ExtendSubscriptionRequest(days=30),
        db=db,
        _admin=True,
    ))
    db.refresh(subscriber)

    assert result.success is True
    assert subscriber.subscription_expires_at.replace(tzinfo=timezone.utc) == current_expiry + timedelta(days=30)
    db.close()
