# -*- coding: utf-8 -*-
"""
Auth duplicate-login policy tests.

Validates that stale sessions can be recovered while every fresh active
session blocks a second login, regardless of IP or legacy force flags.
"""

import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

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
os.environ.setdefault("SESSION_STALE_SECONDS", "150")

from app.models.user import User, UserType
from app.models.session import SessionModel
from app.models.payment_session import PaymentSession, PaymentStatus
from app.services.auth_service import AuthService, _is_session_stale


class _FakeQuery:
    def __init__(self, items, *, on_lock=None):
        self._items = list(items)
        self._on_lock = on_lock

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._items[0] if self._items else None

    def all(self):
        return list(self._items)

    def order_by(self, *args, **kwargs):
        return self

    def with_for_update(self):
        if self._on_lock is not None:
            self._on_lock()
        return self

    def scalar(self):
        return self._items[0] if self._items else None


class _FakeDB:
    def __init__(self, user, sessions, payments=None):
        self.user = user
        self.sessions = list(sessions)
        self.payments = list(payments or [])
        self.added = []
        self.commit_count = 0
        self.user_lock_requested = False

    def _record_user_lock(self):
        self.user_lock_requested = True

    def query(self, model):
        if str(model) == "CURRENT_TIMESTAMP":
            return _FakeQuery([datetime.now(timezone.utc)])
        if model is User:
            return _FakeQuery(
                [self.user] if self.user else [],
                on_lock=self._record_user_lock,
            )
        if model is SessionModel:
            return _FakeQuery(self.sessions)
        if model is PaymentSession:
            return _FakeQuery(self.payments)
        raise AssertionError(f"Unexpected model queried: {model}")

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, SessionModel):
            self.sessions.append(obj)

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        pass


class _AuthServiceNoRateLimit(AuthService):
    async def _check_rate_limit(self, username, ip_address):
        return {"allowed": True, "reason": None}

    def _record_login_attempt(self, username, ip_address, success):
        return None

    def apply_trial_monthly_reset(self, user):
        return None


def _make_user():
    return User(
        id=1,
        username="tester",
        password_hash="dummy_hash",
        is_active=True,
        user_type=UserType.TRIAL,
        work_count=5,
        work_used=0,
    )


def _make_session(ip: str, *, last_activity_seconds_ago: int):
    now_utc = datetime.now(timezone.utc)
    session = SessionModel(
        user_id=1,
        token_jti=f"jti-{ip}-{last_activity_seconds_ago}",
        ip_address=ip,
        expires_at=now_utc + timedelta(hours=1),
        is_active=True,
    )
    session.last_activity_at = now_utc - timedelta(seconds=last_activity_seconds_ago)
    session.created_at = now_utc - timedelta(seconds=last_activity_seconds_ago)
    return session


def _make_payment(plan_id: str = "test_3days"):
    paid_at = datetime(2026, 4, 30, 16, 11, 16, tzinfo=timezone.utc)
    payment = PaymentSession(
        user_id="1",
        payment_id=f"payment-{plan_id}",
        plan_id=plan_id,
        status=PaymentStatus.SUCCEEDED,
        amount=5000,
    )
    payment.created_at = paid_at
    payment.updated_at = paid_at
    return payment


def test_is_session_stale_uses_last_activity_threshold():
    now_utc = datetime.now(timezone.utc)
    session = SimpleNamespace(
        last_activity_at=now_utc - timedelta(seconds=40),
        created_at=now_utc - timedelta(seconds=40),
    )
    assert _is_session_stale(session, now_ref=now_utc, stale_seconds=30) is True
    assert _is_session_stale(session, now_ref=now_utc, stale_seconds=90) is False


def test_login_allows_when_existing_session_is_stale(monkeypatch):
    monkeypatch.setattr("app.services.auth_service.verify_password", lambda *_: True)
    monkeypatch.setattr(
        "app.services.auth_service.create_access_token",
        lambda user_id, ip: ("new-token", "new-jti", datetime.now(timezone.utc) + timedelta(hours=1)),
    )

    user = _make_user()
    stale_other_ip = _make_session("9.9.9.9", last_activity_seconds_ago=180)
    db = _FakeDB(user=user, sessions=[stale_other_ip])
    service = _AuthServiceNoRateLimit(db)

    result = asyncio.run(
        service.login(
            username="tester",
            password="irrelevant",
            ip_address="1.1.1.1",
            force=False,
        )
    )

    assert result.get("status") is True
    assert stale_other_ip.is_active is False


def test_login_locks_account_before_checking_active_sessions(monkeypatch):
    monkeypatch.setattr("app.services.auth_service.verify_password", lambda *_: True)
    monkeypatch.setattr(
        "app.services.auth_service.create_access_token",
        lambda user_id, ip: ("new-token", "new-jti", datetime.now(timezone.utc) + timedelta(hours=1)),
    )

    db = _FakeDB(user=_make_user(), sessions=[])
    service = _AuthServiceNoRateLimit(db)

    result = asyncio.run(
        service.login(
            username="tester",
            password="irrelevant",
            ip_address="1.1.1.1",
            force=False,
        )
    )

    assert result.get("status") is True
    assert db.user_lock_requested is True


def test_login_keeps_session_active_between_desktop_heartbeats(monkeypatch):
    monkeypatch.setattr("app.services.auth_service.verify_password", lambda *_: True)
    monkeypatch.setattr(
        "app.services.auth_service.create_access_token",
        lambda user_id, ip: ("new-token", "new-jti", datetime.now(timezone.utc) + timedelta(hours=1)),
    )

    user = _make_user()
    active_session = _make_session("2.2.2.2", last_activity_seconds_ago=45)
    db = _FakeDB(user=user, sessions=[active_session])
    service = _AuthServiceNoRateLimit(db)

    result = asyncio.run(
        service.login(
            username="tester",
            password="irrelevant",
            ip_address="1.1.1.1",
            force=False,
        )
    )

    assert result == {"status": "EU003", "message": "EU003"}
    assert active_session.is_active is True


def test_login_response_includes_latest_paid_plan(monkeypatch):
    monkeypatch.setattr("app.services.auth_service.verify_password", lambda *_: True)
    monkeypatch.setattr(
        "app.services.auth_service.create_access_token",
        lambda user_id, ip: ("new-token", "new-jti", datetime.now(timezone.utc) + timedelta(hours=1)),
    )

    user = _make_user()
    user.user_type = UserType.SUBSCRIBER
    user.work_count = -1
    user.subscription_expires_at = datetime(2026, 5, 3, 16, 11, 16, tzinfo=timezone.utc)
    db = _FakeDB(user=user, sessions=[], payments=[_make_payment("test_3days")])
    service = _AuthServiceNoRateLimit(db)

    result = asyncio.run(
        service.login(
            username="tester",
            password="irrelevant",
            ip_address="1.1.1.1",
            force=False,
        )
    )

    user_data = result["data"]["data"]
    assert user_data["plan_id"] == "test_3days"
    assert user_data["plan_name"] == "테스트 3일"
    assert user_data["last_payment_at"] == "2026-04-30T16:11:16+00:00"


def test_login_blocks_same_ip_active_session(monkeypatch):
    monkeypatch.setattr("app.services.auth_service.verify_password", lambda *_: True)
    monkeypatch.setattr(
        "app.services.auth_service.create_access_token",
        lambda user_id, ip: ("new-token", "new-jti", datetime.now(timezone.utc) + timedelta(hours=1)),
    )

    user = _make_user()
    same_ip_active = _make_session("1.1.1.1", last_activity_seconds_ago=0)
    db = _FakeDB(user=user, sessions=[same_ip_active])
    service = _AuthServiceNoRateLimit(db)

    result = asyncio.run(
        service.login(
            username="tester",
            password="irrelevant",
            ip_address="1.1.1.1",
            force=False,
        )
    )

    assert result == {"status": "EU003", "message": "EU003"}
    assert same_ip_active.is_active is True
    assert db.added == []


def test_login_blocks_other_ip_active_session(monkeypatch):
    monkeypatch.setattr("app.services.auth_service.verify_password", lambda *_: True)
    monkeypatch.setattr(
        "app.services.auth_service.create_access_token",
        lambda user_id, ip: ("new-token", "new-jti", datetime.now(timezone.utc) + timedelta(hours=1)),
    )

    user = _make_user()
    other_ip_active = _make_session("2.2.2.2", last_activity_seconds_ago=0)
    db = _FakeDB(user=user, sessions=[other_ip_active])
    service = _AuthServiceNoRateLimit(db)

    result = asyncio.run(
        service.login(
            username="tester",
            password="irrelevant",
            ip_address="1.1.1.1",
            force=False,
        )
    )

    assert result == {"status": "EU003", "message": "EU003"}
    assert other_ip_active.is_active is True
    assert db.added == []


def test_force_flag_cannot_replace_active_session(monkeypatch):
    monkeypatch.setattr("app.services.auth_service.verify_password", lambda *_: True)
    monkeypatch.setattr(
        "app.services.auth_service.create_access_token",
        lambda user_id, ip: ("new-token", "new-jti", datetime.now(timezone.utc) + timedelta(hours=1)),
    )

    user = _make_user()
    active_session = _make_session("2.2.2.2", last_activity_seconds_ago=0)
    db = _FakeDB(user=user, sessions=[active_session])
    service = _AuthServiceNoRateLimit(db)

    result = asyncio.run(
        service.login(
            username="tester",
            password="irrelevant",
            ip_address="1.1.1.1",
            force=True,
        )
    )

    assert result == {"status": "EU003", "message": "EU003"}
    assert active_session.is_active is True
    assert db.added == []
