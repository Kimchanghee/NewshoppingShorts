"""
Subscription Utility Functions
구독 관련 유틸리티 함수
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo


try:
    TRIAL_RESET_TIMEZONE = ZoneInfo("Asia/Seoul")
except Exception:
    # Fallback for environments without tzdata (fixed KST offset)
    TRIAL_RESET_TIMEZONE = timezone(timedelta(hours=9))


def _utcnow() -> datetime:
    """Timezone-aware UTC now."""
    return datetime.now(timezone.utc)


def _ensure_aware(dt: datetime) -> datetime:
    """naive datetime을 UTC aware로 변환."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def calculate_subscription_expiry(
    days: int,
    current_expiry: Optional[datetime] = None
) -> datetime:
    """
    Calculate new subscription expiry date.

    If current_expiry exists and is in the future, extends from that date.
    Otherwise, extends from now.

    Args:
        days: Number of days to add
        current_expiry: Current expiration date (optional)

    Returns:
        New expiration datetime (UTC, timezone-aware)
    """
    now = _utcnow()

    if current_expiry:
        current_expiry = _ensure_aware(current_expiry)
        if current_expiry > now:
            return current_expiry + timedelta(days=days)

    return now + timedelta(days=days)


def is_subscription_active(expiry_date: Optional[datetime]) -> bool:
    """
    Check if subscription is currently active.

    Args:
        expiry_date: Subscription expiration date

    Returns:
        True if subscription is active
    """
    if not expiry_date:
        return False

    return _ensure_aware(expiry_date) > _utcnow()


def days_until_expiry(expiry_date: Optional[datetime]) -> int:
    """
    Calculate days until subscription expires.

    Args:
        expiry_date: Subscription expiration date

    Returns:
        Days until expiry (negative if already expired)
    """
    if not expiry_date:
        return -999

    delta = _ensure_aware(expiry_date) - _utcnow()
    return delta.days


def get_trial_cycle_start(reference_dt: Optional[datetime] = None) -> datetime:
    """
    Return trial monthly cycle start as UTC datetime.

    Cycle boundary uses Asia/Seoul month start (00:00 on day 1).
    """
    base = _ensure_aware(reference_dt) if reference_dt else _utcnow()
    local = base.astimezone(TRIAL_RESET_TIMEZONE)
    local_cycle_start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return local_cycle_start.astimezone(timezone.utc)


def is_new_trial_cycle(stored_cycle_start: Optional[datetime], now: Optional[datetime] = None) -> bool:
    """
    Check whether stored trial cycle start is older than current cycle start.
    """
    if stored_cycle_start is None:
        return False
    current_cycle_start = get_trial_cycle_start(now)
    return _ensure_aware(stored_cycle_start) < current_cycle_start
