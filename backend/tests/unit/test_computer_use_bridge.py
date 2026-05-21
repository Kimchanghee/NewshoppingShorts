# -*- coding: utf-8 -*-
"""Unit tests for computer-use bridge entitlement helper."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

# Ensure config validation can load in test runtime.
os.environ.setdefault("DB_USER", "test_user")
os.environ.setdefault("DB_PASSWORD", "test_password")
os.environ.setdefault("JWT_SECRET_KEY", "0123456789abcdef0123456789abcdef")

from app.models.user import User, UserType  # noqa: E402
from app.routers.computer_use import is_paid_entitled_user  # noqa: E402


def _build_user(user_type: UserType, *, expiry=None, work_count: int = 0) -> User:
    user = User()
    user.user_type = user_type
    user.subscription_expires_at = expiry
    user.work_count = work_count
    return user


def test_paid_entitlement_admin_is_true():
    user = _build_user(UserType.ADMIN)
    assert is_paid_entitled_user(user) is True


def test_paid_entitlement_subscriber_with_valid_expiry_is_true():
    expiry = datetime.now(timezone.utc) + timedelta(days=1)
    user = _build_user(UserType.SUBSCRIBER, expiry=expiry)
    assert is_paid_entitled_user(user) is True


def test_paid_entitlement_subscriber_with_expired_expiry_is_false():
    expiry = datetime.now(timezone.utc) - timedelta(days=1)
    user = _build_user(UserType.SUBSCRIBER, expiry=expiry)
    assert is_paid_entitled_user(user) is False


def test_paid_entitlement_trial_is_false():
    user = _build_user(UserType.TRIAL, work_count=5)
    assert is_paid_entitled_user(user) is False

