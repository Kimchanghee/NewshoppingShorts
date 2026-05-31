"""
Limited-time subscription promotion policy.

The promotion is intentionally evaluated at activation time so it can expire
without a scheduler or manual cleanup. Dates are business-time in Korea.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo


try:
    PROMOTION_TIMEZONE = ZoneInfo("Asia/Seoul")
except Exception:
    PROMOTION_TIMEZONE = timezone(timedelta(hours=9))


PROMOTION_ID = "spring-2026-new-subscriber-extra-month"
PROMOTION_TITLE = "신규 구독 1개월 추가 제공 이벤트"
PROMOTION_START_KST = datetime(2026, 4, 30, 0, 0, 0, tzinfo=PROMOTION_TIMEZONE)
PROMOTION_END_EXCLUSIVE_KST = datetime(2026, 5, 15, 0, 0, 0, tzinfo=PROMOTION_TIMEZONE)
PROMOTION_PERIOD_LABEL = "2026.04.30 - 2026.05.14"
PROMOTION_BONUS_DAYS = 30
PROMOTION_BONUS_MONTHS = 1


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _to_kst(dt: datetime) -> datetime:
    return _ensure_aware_utc(dt).astimezone(PROMOTION_TIMEZONE)


def get_promotion_status(now: Optional[datetime] = None) -> str:
    """Return upcoming, active, or closed for the promotion window."""
    local_now = _to_kst(now or _now_utc())
    if local_now < PROMOTION_START_KST:
        return "upcoming"
    if local_now < PROMOTION_END_EXCLUSIVE_KST:
        return "active"
    return "closed"


def is_promotion_active(now: Optional[datetime] = None) -> bool:
    return get_promotion_status(now) == "active"


def is_new_user_in_promotion_window(
    user_created_at: Optional[datetime],
    now: Optional[datetime] = None,
) -> bool:
    if user_created_at is None:
        return False
    local_created_at = _to_kst(user_created_at)
    return (
        is_promotion_active(now)
        and PROMOTION_START_KST <= local_created_at < PROMOTION_END_EXCLUSIVE_KST
    )


def get_new_subscriber_promotion_days(
    user_created_at: Optional[datetime],
    *,
    was_free: bool,
    now: Optional[datetime] = None,
) -> int:
    """
    Return bonus days for a first paid conversion during the promotion.

    Existing subscribers/admins and users created outside the promotion window
    are never eligible, which prevents repeated bonuses on renewals.
    """
    if not was_free:
        return 0
    if not is_new_user_in_promotion_window(user_created_at, now):
        return 0
    return PROMOTION_BONUS_DAYS


def build_promotion_payload(
    user_created_at: Optional[datetime] = None,
    *,
    was_free: bool = False,
    now: Optional[datetime] = None,
) -> dict:
    status = get_promotion_status(now)
    eligible = get_new_subscriber_promotion_days(
        user_created_at,
        was_free=was_free,
        now=now,
    ) > 0
    if status == "active":
        message = "신규 가입 후 이벤트 기간 내 구독 확정 시 1개월이 자동 추가됩니다."
    elif status == "closed":
        message = "이벤트가 마감되어 신규 구독 추가 1개월 혜택은 더 이상 적용되지 않습니다."
    else:
        message = "이벤트 시작 전입니다."

    return {
        "id": PROMOTION_ID,
        "title": PROMOTION_TITLE,
        "status": status,
        "period_label": PROMOTION_PERIOD_LABEL,
        "starts_at": PROMOTION_START_KST.isoformat(),
        "ends_at": (PROMOTION_END_EXCLUSIVE_KST - timedelta(seconds=1)).isoformat(),
        "bonus_days": PROMOTION_BONUS_DAYS,
        "bonus_months": PROMOTION_BONUS_MONTHS,
        "eligible": eligible,
        "message": message,
    }
