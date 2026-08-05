# -*- coding: utf-8 -*-
"""Focused regression tests for backend security hardening."""

from __future__ import annotations

import os
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("JWT_SECRET_KEY", "a" * 64)
os.environ.setdefault("ADMIN_API_KEY", "b" * 64)
os.environ.setdefault("ADMIN_SESSION_PEPPER", "c" * 64)

from app.models.admin_session import hash_admin_token
from app.routers.admin import verify_admin_password
from app.utils.password import hash_password
from app.models.work_usage import WorkUsage
from app.schemas.auth import UseWorkV2Request
from app.routers.admin import apply_user_status_filter
from app.scheduler.computer_use_worker import build_worker_env
from app.models.system_setting import SystemSetting
from app.routers.admin import ExtendSubscriptionRequest
from app.database import Base
from app.models.session import SessionModel
from app.models.user import User, UserType
from app.services.auth_service import AuthService
from app.utils.jwt_handler import create_access_token


def test_admin_session_token_hash_is_peppered_and_deterministic():
    token = "opaque-secret-token"
    digest = hash_admin_token(token, "server-only-pepper")

    assert token not in digest
    assert len(digest) == 64
    assert digest == hash_admin_token(token, "server-only-pepper")
    assert digest != hash_admin_token(token, "different-pepper")


def test_admin_password_verification_uses_bcrypt_hash_only():
    password_hash = hash_password("correct horse battery staple")

    assert verify_admin_password("correct horse battery staple", password_hash)
    assert not verify_admin_password("wrong password", password_hash)


def test_all_rate_limited_routers_share_one_limiter():
    from app.routers import admin, auth, computer_use, payment, registration, subscription

    assert admin.limiter is auth.limiter
    assert computer_use.limiter is auth.limiter
    assert payment.limiter is auth.limiter
    assert registration.limiter is auth.limiter
    assert subscription.limiter is auth.limiter


def test_work_usage_has_user_scoped_idempotency_constraint():
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in WorkUsage.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }

    assert ("user_id", "idempotency_key") in unique_columns
    assert len(str(uuid4())) == 36


def test_use_work_v2_requires_uuid_idempotency_key():
    request = UseWorkV2Request(user_id="7", idempotency_key=str(uuid4()))
    assert str(request.idempotency_key)


def test_admin_status_filter_rejects_unknown_value():
    import pytest

    with pytest.raises(ValueError):
        apply_user_status_filter(object(), "not-a-real-status")


def test_computer_use_worker_environment_drops_application_secrets():
    env = build_worker_env({
        "PATH": "safe-path",
        "SYSTEMROOT": "C:/Windows",
        "JWT_SECRET_KEY": "must-not-leak",
        "DATABASE_URL": "must-not-leak",
    })

    assert env["PATH"] == "safe-path"
    assert "JWT_SECRET_KEY" not in env
    assert "DATABASE_URL" not in env


def test_system_setting_is_portable_orm_model():
    assert SystemSetting.__table__.primary_key.columns.keys() == ["setting_key"]
    assert "setting_value" in SystemSetting.__table__.columns


def test_admin_subscription_extension_is_bounded():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ExtendSubscriptionRequest(days=0)
    with pytest.raises(ValidationError):
        ExtendSubscriptionRequest(days=3651)


def test_use_work_v2_replay_does_not_increment_twice():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    user = User(
        username="idempotent-user",
        password_hash="hash",
        user_type=UserType.TRIAL,
        work_count=2,
        work_used=0,
        subscription_expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token, jti, expires_at = create_access_token(user.id, "127.0.0.1")
    db.add(SessionModel(
        user_id=user.id,
        token_jti=jti,
        ip_address="127.0.0.1",
        expires_at=expires_at,
        is_active=True,
    ))
    db.commit()
    key = str(uuid4())

    first = asyncio.run(AuthService(db).use_work_v2(str(user.id), token, key))
    second = asyncio.run(AuthService(db).use_work_v2(str(user.id), token, key))

    db.refresh(user)
    assert first["success"] is True, first
    assert second["idempotent_replay"] is True
    assert user.work_used == 1
    db.close()


def test_work_v3_reserve_finalize_release_and_expiry_recovery():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    user = User(
        username="reservation-user",
        password_hash="hash",
        user_type=UserType.TRIAL,
        work_count=2,
        work_used=0,
        subscription_expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token, jti, expires_at = create_access_token(user.id, "127.0.0.1")
    db.add(SessionModel(
        user_id=user.id,
        token_jti=jti,
        ip_address="127.0.0.1",
        expires_at=expires_at,
        is_active=True,
    ))
    db.commit()
    service = AuthService(db)

    released_key = str(uuid4())
    reserved = asyncio.run(service.reserve_work_v3(str(user.id), token, released_key))
    db.refresh(user)
    assert reserved["reservation_status"] == "reserved"
    assert user.work_used == 0
    released = asyncio.run(service.release_work_v3(str(user.id), token, released_key))
    db.refresh(user)
    assert released["reservation_status"] == "released"
    assert user.work_used == 0

    completed_key = str(uuid4())
    asyncio.run(service.reserve_work_v3(str(user.id), token, completed_key))
    completed = asyncio.run(service.finalize_work_v3(str(user.id), token, completed_key))
    replay = asyncio.run(service.finalize_work_v3(str(user.id), token, completed_key))
    db.refresh(user)
    assert completed["reservation_status"] == "completed"
    assert replay["idempotent_replay"] is True
    assert user.work_used == 1

    expired_key = str(uuid4())
    asyncio.run(service.reserve_work_v3(str(user.id), token, expired_key))
    usage = db.query(WorkUsage).filter(WorkUsage.idempotency_key == expired_key).one()
    usage.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    next_key = str(uuid4())
    recovered = asyncio.run(service.reserve_work_v3(str(user.id), token, next_key))
    db.refresh(usage)
    assert recovered["reservation_status"] == "reserved"
    assert usage.status == "expired"

    asyncio.run(service.release_work_v3(str(user.id), token, next_key))
    recovered_finalize = asyncio.run(
        service.finalize_work_v3(str(user.id), token, expired_key)
    )
    db.refresh(user)
    assert recovered_finalize["reservation_status"] == "completed"
    assert user.work_used == 2
    db.close()
