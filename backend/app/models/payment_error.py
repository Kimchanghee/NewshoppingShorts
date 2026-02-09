# -*- coding: utf-8 -*-
"""
Payment Error Log Model
결제 오류 로그 모델

결제 실패/오류 카운팅 및 모니터링을 위한 모델
"""
from sqlalchemy import Column, Integer, String, TIMESTAMP, Index
from sqlalchemy.sql import func
from app.database import Base


class PaymentErrorLog(Base):
    """
    결제 오류 로그 모델.
    Payment error logging model for tracking and monitoring.
    
    Tracks:
    - Individual payment errors with error codes
    - Error types (timeout, validation, gateway error, etc.)
    - Failed endpoint and context
    """
    __tablename__ = "payment_error_logs"
    __table_args__ = (
        Index('ix_payment_error_logs_user_created', 'user_id', 'created_at'),
        Index('ix_payment_error_logs_error_type', 'error_type'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # 사용자 ID (nullable for anonymous/system errors)
    user_id = Column(String(100), nullable=True, index=True)
    
    # 오류 유형: timeout, validation, gateway_error, network_error, auth_error, system_error
    error_type = Column(String(50), nullable=False)
    
    # PayApp/Gateway 오류 코드 (e.g., "70020", "30051")
    error_code = Column(String(50), nullable=True)
    
    # 오류 메시지 (sanitized, no sensitive data)
    error_message = Column(String(500), nullable=True)
    
    # 실패한 엔드포인트/명령
    endpoint = Column(String(100), nullable=True)
    
    # 결제 세션 ID (if available)
    payment_id = Column(String(64), nullable=True, index=True)
    
    # 플랜 ID (if available)
    plan_id = Column(String(50), nullable=True)
    
    # 추가 컨텍스트 (JSON string, sanitized)
    context = Column(String(1000), nullable=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)


class UserPaymentStats(Base):
    """
    사용자별 결제 통계 모델.
    User-level payment statistics for monitoring consecutive failures.
    
    Used for:
    - Tracking consecutive payment failures
    - Determining if user needs intervention
    - Rate limiting abusive patterns
    """
    __tablename__ = "user_payment_stats"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # 사용자 ID (unique)
    user_id = Column(String(100), nullable=False, unique=True, index=True)
    
    # 연속 실패 횟수 (reset on success)
    consecutive_fail_count = Column(Integer, default=0, nullable=False)
    
    # 총 실패 횟수 (cumulative)
    total_fail_count = Column(Integer, default=0, nullable=False)
    
    # 총 성공 횟수 (cumulative)
    total_success_count = Column(Integer, default=0, nullable=False)
    
    # 마지막 실패 시각
    last_fail_at = Column(TIMESTAMP, nullable=True)
    
    # 마지막 성공 시각
    last_success_at = Column(TIMESTAMP, nullable=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
