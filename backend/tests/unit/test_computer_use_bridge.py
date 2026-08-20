# -*- coding: utf-8 -*-
"""Unit tests for computer-use bridge entitlement helper."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

# Ensure config validation can load in test runtime.
os.environ.setdefault("DB_USER", "test_user")
os.environ.setdefault("DB_PASSWORD", "test_password")
os.environ.setdefault("JWT_SECRET_KEY", "0123456789abcdef0123456789abcdef")

from app.models.user import User, UserType  # noqa: E402
from app.routers import computer_use  # noqa: E402
from app.routers.computer_use import (  # noqa: E402
    ComputerUseJobCreate,
    is_paid_entitled_user,
    resolve_computer_use_prompt,
)


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


def test_server_template_resolution_returns_id_and_keeps_freeform_disabled(monkeypatch):
    prompt = "Server-owned Computer Use instruction that must never be persisted."
    monkeypatch.setattr(
        computer_use.settings,
        "COMPUTER_USE_PROMPT_TEMPLATES_JSON",
        '{"setup_target_test": "' + prompt + '"}',
    )
    monkeypatch.setattr(
        computer_use.settings,
        "COMPUTER_USE_ALLOW_FREEFORM_PROMPTS",
        True,
    )

    template_id, resolved = resolve_computer_use_prompt(
        ComputerUseJobCreate(template_id="setup_target_test")
    )
    assert template_id == "setup_target_test"
    assert resolved == prompt

    with pytest.raises(HTTPException, match="permitted server template"):
        resolve_computer_use_prompt(
            ComputerUseJobCreate(prompt="This freeform prompt must not reach the database.")
        )
