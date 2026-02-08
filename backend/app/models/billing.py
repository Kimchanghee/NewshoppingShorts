# -*- coding: utf-8 -*-
"""
Billing Models
빌링 모델

카드 빌링키 및 정기결제 구독 관리를 위한 모델
Models for card billing key management and recurring subscription management.
"""
from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, Enum as SQLEnum, UniqueConstraint
from sqlalchemy.sql import func
import enum
from app.database import Base


class SubscriptionStatus(str, enum.Enum):
    """Recurring subscription status enumeration / 정기결제 상태"""
    ACTIVE = "active"
    STOPPED = "stopped"
    CANCELLED = "cancelled"


class BillingKey(Base):
    """
    Card billing key model for saved card payments.
    저장된 카드 결제를 위한 빌링키 모델.

    PayApp billRegist API 호출 시 반환되는 encBill(암호화된 빌링키)을 저장.
    """
    __tablename__ = "billing_keys"
    __table_args__ = (
        UniqueConstraint('user_id', 'enc_bill', name='uq_user_enc_bill'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # 사용자 ID (User reference)
    user_id = Column(String(100), nullable=False, index=True)

    # PayApp 암호화 빌링키 (encrypted billing key from PayApp)
    # Encrypted at app layer (Fernet) before DB storage.
    enc_bill = Column(String(1024), nullable=False)

    # 마스킹된 카드번호 (e.g. "4518****")
    card_no_masked = Column(String(20), nullable=True)

    # 카드사 이름 (e.g. "[신한]")
    card_name = Column(String(50), nullable=True)

    # 활성 여부 (soft delete)
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())


class RecurringSubscription(Base):
    """
    Recurring subscription model for PayApp rebill management.
    PayApp 정기결제(rebill) 관리를 위한 구독 모델.
    """
    __tablename__ = "recurring_subscriptions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # 사용자 ID (User reference)
    user_id = Column(String(100), nullable=False, index=True)

    # PayApp 정기결제 번호 (rebill number from PayApp)
    rebill_no = Column(String(50), nullable=False, unique=True)

    # 구독 플랜 ID
    plan_id = Column(String(50), nullable=False)

    # 결제 금액 (KRW)
    amount = Column(Integer, nullable=False)

    # 결제 주기 타입 (Month/Week/Day)
    cycle_type = Column(String(20), nullable=False)

    # 결제 주기 값 (일자, e.g. 1~31, 90=말일)
    cycle_value = Column(Integer, nullable=True)

    # 만료일 (yyyy-mm-dd)
    expire_date = Column(String(20), nullable=True)

    # 구독 상태 (active/stopped/cancelled)
    status = Column(
        SQLEnum(SubscriptionStatus, values_callable=lambda x: [e.value for e in x]),
        default=SubscriptionStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
