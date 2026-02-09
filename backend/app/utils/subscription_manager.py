# -*- coding: utf-8 -*-
"""
Subscription Manager
구독 관리자

구독 만료 처리, 상태 전환, 알림 등을 관리합니다.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models.user import User, UserType
from app.models.billing import RecurringSubscription, SubscriptionStatus
from app.utils.subscription_utils import _utcnow, _ensure_aware

logger = logging.getLogger(__name__)


# 무료 사용자 기본 작업 한도
FREE_USER_WORK_LIMIT = 5


def check_subscription_expiry(user: User) -> tuple[bool, int]:
    """
    사용자 구독 만료 여부를 확인합니다.
    
    Args:
        user: User model instance
    
    Returns:
        Tuple of (is_expired, days_remaining)
        - is_expired: True if subscription has expired
        - days_remaining: Days until expiry (negative if expired)
    """
    if user.user_type != UserType.SUBSCRIBER:
        return False, 0
    
    if not user.subscription_expires_at:
        return True, -999
    
    now = _utcnow()
    expires_at = _ensure_aware(user.subscription_expires_at)
    delta = expires_at - now
    days_remaining = delta.days
    
    return days_remaining < 0, days_remaining


def get_effective_user_type(user: User) -> UserType:
    """
    사용자의 실제 유효 타입을 반환합니다.
    만료된 SUBSCRIBER는 FREE로 반환됩니다.
    
    Args:
        user: User model instance
    
    Returns:
        Effective UserType
    """
    if user.user_type == UserType.SUBSCRIBER:
        is_expired, _ = check_subscription_expiry(user)
        if is_expired:
            return UserType.FREE
    return user.user_type


def expire_subscription(db: Session, user: User, reason: str = "expiry") -> bool:
    """
    사용자 구독을 만료 처리합니다 (유료 → 무료 전환).
    
    Args:
        db: Database session
        user: User model instance
        reason: Reason for expiration
    
    Returns:
        True on success, False on failure
    """
    try:
        prev_type = user.user_type
        user.user_type = UserType.FREE
        user.work_count = FREE_USER_WORK_LIMIT
        # work_used는 유지 (다음 달 초기화는 별도 로직)
        
        db.commit()
        
        logger.info(
            f"[SubscriptionManager] Expired subscription: user={user.id}, "
            f"prev_type={prev_type.value}, reason={reason}"
        )
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"[SubscriptionManager] Failed to expire subscription: {e}")
        return False


def process_expired_subscriptions(db: Session) -> tuple[int, int]:
    """
    만료된 모든 구독을 처리합니다 (배치 작업용).
    
    Args:
        db: Database session
    
    Returns:
        Tuple of (processed_count, failed_count)
    """
    now = _utcnow()
    
    try:
        expired_users = db.query(User).filter(
            User.user_type == UserType.SUBSCRIBER,
            User.subscription_expires_at < now,
        ).all()
        
        processed = 0
        failed = 0
        
        for user in expired_users:
            if expire_subscription(db, user, "batch_expiry"):
                processed += 1
            else:
                failed += 1
        
        logger.info(
            f"[SubscriptionManager] Batch expiry completed: "
            f"processed={processed}, failed={failed}"
        )
        return processed, failed
    except SQLAlchemyError as e:
        logger.error(f"[SubscriptionManager] Batch expiry failed: {e}")
        return 0, 0


def get_expiring_soon_users(db: Session, days: int = 7) -> list[User]:
    """
    곧 만료될 구독 사용자 목록을 조회합니다.
    
    Args:
        db: Database session
        days: Days threshold (default 7 days)
    
    Returns:
        List of User instances with expiring subscriptions
    """
    now = _utcnow()
    threshold = now + timedelta(days=days)
    
    return db.query(User).filter(
        User.user_type == UserType.SUBSCRIBER,
        User.subscription_expires_at > now,
        User.subscription_expires_at <= threshold,
    ).all()


def get_users_needing_expiry_notification(
    db: Session,
    days_before: list[int] = None,
) -> dict[int, list[User]]:
    """
    만료 알림이 필요한 사용자를 일수별로 그룹화하여 반환합니다.
    
    Args:
        db: Database session
        days_before: Days before expiry to notify (default [7, 3, 1])
    
    Returns:
        Dictionary of days -> list of users
    """
    if days_before is None:
        days_before = [7, 3, 1]
    
    now = _utcnow()
    result: dict[int, list[User]] = {}
    
    for days in days_before:
        target_date_start = now + timedelta(days=days)
        target_date_end = now + timedelta(days=days + 1)
        
        users = db.query(User).filter(
            User.user_type == UserType.SUBSCRIBER,
            User.subscription_expires_at >= target_date_start,
            User.subscription_expires_at < target_date_end,
        ).all()
        
        if users:
            result[days] = users
    
    return result


def cancel_recurring_subscription_on_expiry(
    db: Session,
    user_id: str,
) -> bool:
    """
    구독 만료 시 정기결제도 함께 취소합니다.
    
    Args:
        db: Database session
        user_id: User ID
    
    Returns:
        True if any subscriptions were cancelled
    """
    try:
        active_subs = db.query(RecurringSubscription).filter(
            RecurringSubscription.user_id == user_id,
            RecurringSubscription.status == SubscriptionStatus.ACTIVE,
        ).all()
        
        if not active_subs:
            return False
        
        for sub in active_subs:
            sub.status = SubscriptionStatus.CANCELLED
        
        db.commit()
        
        logger.info(
            f"[SubscriptionManager] Cancelled {len(active_subs)} recurring subscriptions "
            f"on expiry for user={user_id}"
        )
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"[SubscriptionManager] Failed to cancel recurring subscriptions: {e}")
        return False


def get_subscription_summary(db: Session, user_id: str) -> dict:
    """
    사용자 구독 요약 정보를 반환합니다.
    
    Args:
        db: Database session
        user_id: User ID
    
    Returns:
        Dictionary with subscription summary
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "User not found"}
    
    is_expired, days_remaining = check_subscription_expiry(user)
    effective_type = get_effective_user_type(user)
    
    # 정기결제 현황
    recurring_subs = db.query(RecurringSubscription).filter(
        RecurringSubscription.user_id == user_id,
    ).all()
    
    active_recurring = [s for s in recurring_subs if s.status == SubscriptionStatus.ACTIVE]
    
    return {
        "user_id": user_id,
        "stored_user_type": user.user_type.value if user.user_type else None,
        "effective_user_type": effective_type.value if effective_type else None,
        "subscription_expires_at": (
            user.subscription_expires_at.isoformat() 
            if user.subscription_expires_at else None
        ),
        "is_expired": is_expired,
        "days_remaining": days_remaining,
        "work_count": user.work_count,
        "work_used": user.work_used,
        "recurring_subscriptions": len(recurring_subs),
        "active_recurring_subscriptions": len(active_recurring),
    }
