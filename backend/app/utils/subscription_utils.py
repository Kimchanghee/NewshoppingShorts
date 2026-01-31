"""
Subscription Utility Functions
구독 관련 유틸리티 함수
"""
from datetime import datetime, timedelta
from typing import Optional


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
        New expiration datetime (UTC)
    """
    now = datetime.utcnow()

    if current_expiry and current_expiry > now:
        # Extend from current expiry
        return current_expiry + timedelta(days=days)
    else:
        # Extend from now
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

    return expiry_date > datetime.utcnow()


def days_until_expiry(expiry_date: Optional[datetime]) -> int:
    """
    Calculate days until subscription expires.

    Args:
        expiry_date: Subscription expiration date

    Returns:
        Days until expiry (negative if already expired)
    """
    if not expiry_date:
        return -999  # Sentinel value

    delta = expiry_date - datetime.utcnow()
    return delta.days
