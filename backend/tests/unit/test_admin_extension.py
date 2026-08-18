import asyncio
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.pop("DATABASE_URL", None)
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "127.0.0.1")
os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("JWT_SECRET_KEY", "a" * 64)
os.environ.setdefault("ADMIN_API_KEY", "b" * 64)

from app.database import Base
from app.models.user import User, UserType
from app.routers.admin import ExtendSubscriptionRequest, extend_subscription


def _call_extend(db, user_id: int, days: int):
    route = extend_subscription
    while hasattr(route, "__wrapped__"):
        route = route.__wrapped__
    return asyncio.run(route(
        request=None,
        user_id=user_id,
        data=ExtendSubscriptionRequest(days=days),
        db=db,
        _admin=True,
    ))


def test_extending_trial_starts_subscription_from_now():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
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
    result = _call_extend(db, trial.id, 30)
    after = datetime.now(timezone.utc)
    db.refresh(trial)
    actual_expiry = trial.subscription_expires_at.replace(tzinfo=timezone.utc)

    assert result.success is True
    assert trial.user_type == UserType.SUBSCRIBER
    assert before + timedelta(days=30) <= actual_expiry <= after + timedelta(days=30)
    db.close()


def test_extending_subscriber_keeps_remaining_paid_time():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
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

    result = _call_extend(db, subscriber.id, 30)
    db.refresh(subscriber)

    assert result.success is True
    assert subscriber.subscription_expires_at.replace(tzinfo=timezone.utc) == current_expiry + timedelta(days=30)
    db.close()
