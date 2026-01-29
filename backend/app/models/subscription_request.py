"""
Subscription Request Model
구독 신청 모델

체험판 사용자가 구독을 신청할 때 사용
"""
from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
import enum
from app.database import Base


class SubscriptionRequestStatus(enum.Enum):
    """Subscription request status enumeration"""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SubscriptionRequest(Base):
    __tablename__ = "subscription_requests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(
        SQLEnum(SubscriptionRequestStatus, values_callable=lambda x: [e.value for e in x]),
        default=SubscriptionRequestStatus.PENDING,
        nullable=False,
        index=True
    )
    # 요청한 작업 횟수 (참고용)
    requested_work_count = Column(Integer, default=100, nullable=False)
    # 사용자 메시지
    message = Column(Text, nullable=True)
    # 관리자 응답
    admin_response = Column(Text, nullable=True)
    # 생성/검토 시간
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    reviewed_at = Column(TIMESTAMP, nullable=True)
    reviewed_by = Column(Integer, nullable=True)
