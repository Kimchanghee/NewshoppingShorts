# -*- coding: utf-8 -*-
"""
Tests for Payment Error Tracking and Subscription Management
결제 오류 추적 및 구독 관리 테스트
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.utils.payment_error_tracker import (
    record_payment_error,
    update_user_payment_stats,
    get_user_payment_stats,
    get_recent_errors,
    get_error_count_by_type,
    ErrorType,
    _sanitize_context,
)
from app.utils.subscription_manager import (
    check_subscription_expiry,
    get_effective_user_type,
    expire_subscription,
    get_expiring_soon_users,
    get_users_needing_expiry_notification,
    get_subscription_summary,
    FREE_USER_WORK_LIMIT,
)
from app.models.payment_error import PaymentErrorLog, UserPaymentStats
from app.models.user import User, UserType


class TestPaymentErrorTracker:
    """결제 오류 추적기 테스트"""

    def test_sanitize_context_removes_sensitive_keys(self):
        """민감 정보가 제거되는지 확인"""
        context = {
            "card_no": "1234567890123456",
            "linkkey": "secret123",
            "user_id": "user123",
            "plan_id": "pro_1month",
        }
        result = _sanitize_context(context)
        assert result is not None
        assert "[REDACTED]" in result
        assert "1234567890123456" not in result
        assert "secret123" not in result
        assert "user123" in result
        assert "pro_1month" in result

    def test_sanitize_context_truncates_long_values(self):
        """긴 값이 잘리는지 확인"""
        context = {
            "long_value": "x" * 200,
        }
        result = _sanitize_context(context)
        assert result is not None
        assert len(result) <= 1000

    def test_sanitize_context_handles_none(self):
        """None 처리 확인"""
        assert _sanitize_context(None) is None
        assert _sanitize_context({}) is None

    def test_error_type_constants(self):
        """오류 유형 상수 확인"""
        assert ErrorType.TIMEOUT == "timeout"
        assert ErrorType.VALIDATION == "validation"
        assert ErrorType.GATEWAY_ERROR == "gateway_error"
        assert ErrorType.NETWORK_ERROR == "network_error"
        assert ErrorType.AUTH_ERROR == "auth_error"
        assert ErrorType.SYSTEM_ERROR == "system_error"
        assert ErrorType.EXPIRED == "expired"
        assert ErrorType.CANCELLED == "cancelled"


class TestSubscriptionManager:
    """구독 관리자 테스트"""

    def test_check_subscription_expiry_not_subscriber(self):
        """비구독자의 만료 확인"""
        user = MagicMock()
        user.user_type = UserType.TRIAL
        
        is_expired, days = check_subscription_expiry(user)
        assert is_expired is False
        assert days == 0

    def test_check_subscription_expiry_no_expiry_date(self):
        """만료일 없는 구독자"""
        user = MagicMock()
        user.user_type = UserType.SUBSCRIBER
        user.subscription_expires_at = None
        
        is_expired, days = check_subscription_expiry(user)
        assert is_expired is True
        assert days == -999

    def test_check_subscription_expiry_future(self):
        """미래 만료일"""
        user = MagicMock()
        user.user_type = UserType.SUBSCRIBER
        user.subscription_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        
        is_expired, days = check_subscription_expiry(user)
        assert is_expired is False
        assert 29 <= days <= 30

    def test_check_subscription_expiry_past(self):
        """과거 만료일"""
        user = MagicMock()
        user.user_type = UserType.SUBSCRIBER
        user.subscription_expires_at = datetime.now(timezone.utc) - timedelta(days=5)
        
        is_expired, days = check_subscription_expiry(user)
        assert is_expired is True
        assert days < 0

    def test_get_effective_user_type_free_user(self):
        """무료 사용자의 유효 타입"""
        user = MagicMock()
        user.user_type = UserType.TRIAL
        
        effective = get_effective_user_type(user)
        assert effective == UserType.TRIAL

    def test_get_effective_user_type_active_subscriber(self):
        """활성 구독자의 유효 타입"""
        user = MagicMock()
        user.user_type = UserType.SUBSCRIBER
        user.subscription_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        
        effective = get_effective_user_type(user)
        assert effective == UserType.SUBSCRIBER

    def test_get_effective_user_type_expired_subscriber(self):
        """만료된 구독자의 유효 타입"""
        user = MagicMock()
        user.user_type = UserType.SUBSCRIBER
        user.subscription_expires_at = datetime.now(timezone.utc) - timedelta(days=5)
        
        effective = get_effective_user_type(user)
        assert effective == UserType.TRIAL

    def test_free_user_work_limit_constant(self):
        """무료 사용자 작업 한도 상수"""
        assert FREE_USER_WORK_LIMIT == 5


class TestSubscriptionExpiry:
    """구독 만료 처리 테스트"""

    def test_expire_subscription_success(self):
        """구독 만료 성공"""
        db = MagicMock()
        user = MagicMock()
        user.id = "test_user"
        user.user_type = UserType.SUBSCRIBER
        
        result = expire_subscription(db, user, reason="test")
        
        assert result is True
        assert user.user_type == UserType.TRIAL
        assert user.work_count == FREE_USER_WORK_LIMIT
        db.commit.assert_called_once()

    def test_expire_subscription_db_error(self):
        """DB 오류 시 롤백"""
        from sqlalchemy.exc import SQLAlchemyError
        
        db = MagicMock()
        db.commit.side_effect = SQLAlchemyError("DB Error")
        user = MagicMock()
        user.id = "test_user"
        user.user_type = UserType.SUBSCRIBER
        
        result = expire_subscription(db, user, reason="test")
        
        assert result is False
        db.rollback.assert_called_once()


class TestPaymentWebhookIntegration:
    """결제 웹훅 통합 테스트"""

    def test_cancelled_payment_updates_stats(self):
        """취소된 결제가 통계를 업데이트하는지 확인"""
        # Mock DB session
        db = MagicMock()
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = None
        
        # This would normally be tested via API call
        # Here we just verify the function signature
        from app.utils.payment_error_tracker import update_user_payment_stats
        
        # Simulate a failed payment stats update
        stats = update_user_payment_stats(db, "test_user", success=False)
        # Should create new stats entry
        db.add.assert_called()


class TestPaymentErrorLogging:
    """결제 오류 로깅 테스트"""

    def test_record_payment_error_sanitizes_card_number(self):
        """카드 번호가 마스킹되는지 확인"""
        db = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        
        error_log = record_payment_error(
            db=db,
            error_type=ErrorType.GATEWAY_ERROR,
            error_message="Card 1234567890123456 declined",
            user_id="test_user",
            endpoint="test_endpoint",
        )
        
        # Verify db.add was called
        db.add.assert_called_once()
        
        # The actual PaymentErrorLog instance should have masked card number
        call_args = db.add.call_args[0][0]
        if hasattr(call_args, 'error_message') and call_args.error_message:
            assert "1234567890123456" not in call_args.error_message


class TestAdminEndpoints:
    """관리자 API 엔드포인트 테스트"""

    def test_subscription_summary_structure(self):
        """구독 요약 구조 확인"""
        db = MagicMock()
        user = MagicMock()
        user.id = "test_user"
        user.user_type = UserType.SUBSCRIBER
        user.subscription_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        user.work_count = -1
        user.work_used = 5
        
        db.query.return_value.filter.return_value.first.return_value = user
        db.query.return_value.filter.return_value.all.return_value = []
        
        summary = get_subscription_summary(db, "test_user")
        
        assert "user_id" in summary
        assert "effective_user_type" in summary
        assert "is_expired" in summary
        assert "days_remaining" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
