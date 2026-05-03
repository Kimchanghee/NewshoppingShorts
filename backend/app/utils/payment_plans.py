"""Shared payment plan catalog."""
from __future__ import annotations


PLAN_PRICES = {
    "trial": 0,
    "test_3days": 5000,
    "test_7days": 49000,
    "pro_1month": 149000,
    "pro_6months": 759900,
    "pro_12months": 1251600,
}

PLAN_DAYS = {
    "test_3days": 3,
    "test_7days": 7,
    "pro_1month": 30,
    "pro_6months": 180,
    "pro_12months": 365,
}

PLAN_NAMES = {
    "test_3days": "테스트 3일",
    "test_7days": "1주 테스트 상품",
    "pro_1month": "프로 1개월",
    "pro_6months": "프로 6개월",
    "pro_12months": "프로 12개월",
}

FIXED_TEST_PLAN_IDS = {"test_3days", "test_7days"}
PROMOTION_EXCLUDED_PLAN_IDS = set(FIXED_TEST_PLAN_IDS)
SELLABLE_PLAN_IDS = {"test_7days", "pro_1month", "pro_6months", "pro_12months"}


def get_plan_name(plan_id: str | None) -> str | None:
    if not plan_id:
        return None
    return PLAN_NAMES.get(plan_id)


def get_plan_days(plan_id: str | None) -> int | None:
    if not plan_id:
        return None
    return PLAN_DAYS.get(plan_id)


def is_sellable_plan(plan_id: str | None) -> bool:
    return bool(plan_id and plan_id in SELLABLE_PLAN_IDS)


def get_sellable_plan_price(plan_id: str | None) -> int | None:
    if not is_sellable_plan(plan_id):
        return None
    amount = PLAN_PRICES.get(plan_id)
    if amount is None or amount <= 0:
        return None
    return amount


def should_extend_from_current_expiry(plan_id: str | None, was_free: bool) -> bool:
    """Return whether a successful payment should extend from existing expiry.

    Free/trial accounts often carry a trial validity date. That date must not be
    used as the base for a paid entitlement, otherwise a short test purchase can
    appear as a year-long subscription. Test plans are intentionally fixed
    windows, so they start from payment completion.
    """
    if was_free:
        return False
    if plan_id in FIXED_TEST_PLAN_IDS:
        return False
    return True
