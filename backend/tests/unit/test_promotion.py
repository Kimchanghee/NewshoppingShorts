# -*- coding: utf-8 -*-
from datetime import datetime, timezone

from app.utils.promotion import (
    PROMOTION_BONUS_DAYS,
    build_promotion_payload,
    get_new_subscriber_promotion_days,
    get_promotion_status,
)


def test_promotion_is_active_during_kst_window():
    now = datetime(2026, 4, 30, 1, 0, 0, tzinfo=timezone.utc)  # 10:00 KST
    assert get_promotion_status(now) == "active"


def test_promotion_closes_after_may_14_kst():
    now = datetime(2026, 5, 14, 15, 0, 0, tzinfo=timezone.utc)  # May 15 00:00 KST
    assert get_promotion_status(now) == "closed"


def test_new_free_user_gets_bonus_days_once_inside_window():
    created_at = datetime(2026, 4, 30, 2, 0, 0, tzinfo=timezone.utc)
    now = datetime(2026, 5, 1, 2, 0, 0, tzinfo=timezone.utc)
    assert (
        get_new_subscriber_promotion_days(created_at, was_free=True, now=now)
        == PROMOTION_BONUS_DAYS
    )


def test_existing_or_old_user_does_not_get_bonus():
    now = datetime(2026, 5, 1, 2, 0, 0, tzinfo=timezone.utc)
    old_created_at = datetime(2026, 4, 29, 14, 59, 59, tzinfo=timezone.utc)

    assert get_new_subscriber_promotion_days(old_created_at, was_free=True, now=now) == 0
    assert (
        get_new_subscriber_promotion_days(
            datetime(2026, 4, 30, 2, 0, 0, tzinfo=timezone.utc),
            was_free=False,
            now=now,
        )
        == 0
    )


def test_promotion_payload_marks_eligibility():
    created_at = datetime(2026, 5, 1, 2, 0, 0, tzinfo=timezone.utc)
    now = datetime(2026, 5, 2, 2, 0, 0, tzinfo=timezone.utc)
    payload = build_promotion_payload(created_at, was_free=True, now=now)

    assert payload["status"] == "active"
    assert payload["eligible"] is True
    assert payload["bonus_days"] == PROMOTION_BONUS_DAYS
