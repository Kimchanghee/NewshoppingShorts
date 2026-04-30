"""Shared payment plan catalog."""
from __future__ import annotations


PLAN_PRICES = {
    "trial": 0,
    "test_3days": 5000,
    "pro_1month": 190000,
    "pro_6months": 969000,
    "pro_12months": 1596000,
}

PLAN_DAYS = {
    "test_3days": 3,
    "pro_1month": 30,
    "pro_6months": 180,
    "pro_12months": 365,
}

PLAN_NAMES = {
    "test_3days": "테스트 3일",
    "pro_1month": "프로 1개월",
    "pro_6months": "프로 6개월",
    "pro_12months": "프로 12개월",
}

PROMOTION_EXCLUDED_PLAN_IDS = {"test_3days"}


def get_plan_name(plan_id: str | None) -> str | None:
    if not plan_id:
        return None
    return PLAN_NAMES.get(plan_id)


def get_plan_days(plan_id: str | None) -> int | None:
    if not plan_id:
        return None
    return PLAN_DAYS.get(plan_id)


def should_extend_from_current_expiry(plan_id: str | None, was_free: bool) -> bool:
    """Return whether a successful payment should extend from existing expiry.

    Free/trial accounts often carry a trial validity date. That date must not be
    used as the base for a paid entitlement, otherwise a 3-day test purchase can
    appear as a year-long subscription. The 3-day test plan is also intentionally
    a short fixed window, so it starts from payment completion.
    """
    if was_free:
        return False
    if plan_id == "test_3days":
        return False
    return True
