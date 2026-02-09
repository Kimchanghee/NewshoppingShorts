# -*- coding: utf-8 -*-
"""
Payment Error Tracker
결제 오류 추적기

결제 실패/오류를 기록하고 사용자별 통계를 관리합니다.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models.payment_error import PaymentErrorLog, UserPaymentStats

logger = logging.getLogger(__name__)


# 오류 유형 상수
class ErrorType:
    TIMEOUT = "timeout"
    VALIDATION = "validation"
    GATEWAY_ERROR = "gateway_error"
    NETWORK_ERROR = "network_error"
    AUTH_ERROR = "auth_error"
    SYSTEM_ERROR = "system_error"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


# 민감 정보 필터링 키
_SENSITIVE_KEYS = frozenset({
    "card_no", "cardno", "card_pw", "cardpw", "buyer_auth_no", "buyerauthno",
    "enc_bill", "encbill", "linkkey", "linkval", "password", "pw", "token",
    "authorization", "secret", "key",
})


def _sanitize_context(context: dict | None) -> str | None:
    """Remove sensitive data from context before storing."""
    if not context:
        return None
    
    sanitized = {}
    for key, value in context.items():
        lower_key = key.lower()
        if any(sensitive in lower_key for sensitive in _SENSITIVE_KEYS):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, str) and len(value) > 100:
            sanitized[key] = value[:100] + "..."
        else:
            sanitized[key] = value
    
    try:
        return json.dumps(sanitized, ensure_ascii=False, default=str)[:1000]
    except Exception:
        return None


def record_payment_error(
    db: Session,
    error_type: str,
    error_code: str | None = None,
    error_message: str | None = None,
    user_id: str | None = None,
    payment_id: str | None = None,
    plan_id: str | None = None,
    endpoint: str | None = None,
    context: dict | None = None,
) -> Optional[PaymentErrorLog]:
    """
    결제 오류를 기록합니다.
    
    Args:
        db: Database session
        error_type: Type of error (see ErrorType class)
        error_code: PayApp/gateway error code
        error_message: Error message (sanitized)
        user_id: User ID (if available)
        payment_id: Payment session ID (if available)
        plan_id: Plan ID (if available)
        endpoint: Failed endpoint/command
        context: Additional context (will be sanitized)
    
    Returns:
        Created PaymentErrorLog or None on failure
    """
    try:
        # Sanitize error message
        safe_message = None
        if error_message:
            safe_message = str(error_message)[:500]
            # Remove potential card numbers
            import re
            safe_message = re.sub(r'\d{13,19}', '[CARD]', safe_message)
        
        error_log = PaymentErrorLog(
            user_id=user_id,
            error_type=error_type,
            error_code=str(error_code)[:50] if error_code else None,
            error_message=safe_message,
            endpoint=str(endpoint)[:100] if endpoint else None,
            payment_id=payment_id,
            plan_id=plan_id,
            context=_sanitize_context(context),
        )
        db.add(error_log)
        db.commit()
        db.refresh(error_log)
        
        logger.info(
            f"[PaymentError] Recorded: type={error_type}, code={error_code}, "
            f"user={user_id}, payment={payment_id}"
        )
        return error_log
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"[PaymentError] Failed to record error: {e}")
        return None


def update_user_payment_stats(
    db: Session,
    user_id: str,
    success: bool,
) -> Optional[UserPaymentStats]:
    """
    사용자 결제 통계를 업데이트합니다.
    
    Args:
        db: Database session
        user_id: User ID
        success: Whether the payment succeeded
    
    Returns:
        Updated UserPaymentStats or None on failure
    """
    try:
        stats = db.query(UserPaymentStats).filter(
            UserPaymentStats.user_id == user_id
        ).with_for_update().first()
        
        now = datetime.now(timezone.utc)
        
        if not stats:
            stats = UserPaymentStats(
                user_id=user_id,
                consecutive_fail_count=0 if success else 1,
                total_fail_count=0 if success else 1,
                total_success_count=1 if success else 0,
                last_fail_at=None if success else now,
                last_success_at=now if success else None,
            )
            db.add(stats)
        else:
            if success:
                stats.consecutive_fail_count = 0
                stats.total_success_count += 1
                stats.last_success_at = now
            else:
                stats.consecutive_fail_count += 1
                stats.total_fail_count += 1
                stats.last_fail_at = now
        
        db.commit()
        db.refresh(stats)
        
        if not success and stats.consecutive_fail_count >= 3:
            logger.warning(
                f"[PaymentStats] User {user_id} has {stats.consecutive_fail_count} "
                f"consecutive payment failures"
            )
        
        return stats
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"[PaymentStats] Failed to update stats for user {user_id}: {e}")
        return None


def get_user_payment_stats(db: Session, user_id: str) -> Optional[UserPaymentStats]:
    """
    사용자 결제 통계를 조회합니다.
    
    Args:
        db: Database session
        user_id: User ID
    
    Returns:
        UserPaymentStats or None if not found
    """
    return db.query(UserPaymentStats).filter(
        UserPaymentStats.user_id == user_id
    ).first()


def get_recent_errors(
    db: Session,
    user_id: str | None = None,
    limit: int = 10,
) -> list[PaymentErrorLog]:
    """
    최근 결제 오류 목록을 조회합니다.
    
    Args:
        db: Database session
        user_id: Filter by user ID (optional)
        limit: Maximum number of results
    
    Returns:
        List of PaymentErrorLog
    """
    query = db.query(PaymentErrorLog)
    if user_id:
        query = query.filter(PaymentErrorLog.user_id == user_id)
    return query.order_by(PaymentErrorLog.created_at.desc()).limit(limit).all()


def get_error_count_by_type(
    db: Session,
    hours: int = 24,
) -> dict[str, int]:
    """
    지정된 시간 내 오류 유형별 카운트를 조회합니다.
    
    Args:
        db: Database session
        hours: Time window in hours
    
    Returns:
        Dictionary of error_type -> count
    """
    from sqlalchemy import func as sql_func
    from datetime import timedelta
    
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    results = (
        db.query(
            PaymentErrorLog.error_type,
            sql_func.count(PaymentErrorLog.id).label("count")
        )
        .filter(PaymentErrorLog.created_at >= cutoff)
        .group_by(PaymentErrorLog.error_type)
        .all()
    )
    
    return {row.error_type: row.count for row in results}
