# -*- coding: utf-8 -*-
"""
Payment Session Model
결제 세션 모델

결제 세션을 데이터베이스에 저장하여 서버 재시작 시에도 세션 유지
"""
from sqlalchemy import Column, Integer, String, TIMESTAMP, Enum as SQLEnum
from sqlalchemy.sql import func
import enum
from app.database import Base


class PaymentStatus(enum.Enum):
    """Payment status enumeration"""
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PaymentSession(Base):
    """
    Payment session model for tracking payment status.
    결제 상태 추적을 위한 결제 세션 모델.
    """
    __tablename__ = "payment_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Unique payment identifier (token)
    payment_id = Column(String(64), unique=True, nullable=False, index=True)

    # Plan being purchased
    plan_id = Column(String(50), nullable=False)

    # User making the payment (optional for guest checkout)
    user_id = Column(String(100), nullable=True, index=True)

    # Current status
    status = Column(
        SQLEnum(PaymentStatus, values_callable=lambda x: [e.value for e in x]),
        default=PaymentStatus.PENDING,
        nullable=False,
        index=True
    )

    # External payment gateway reference (if any)
    gateway_reference = Column(String(255), nullable=True)

    # Amount in KRW (for audit trail)
    amount = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    expires_at = Column(TIMESTAMP, nullable=True)
