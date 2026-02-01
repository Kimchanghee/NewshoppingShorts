"""
Registration Request Model
회원가입 요청 모델

사용자의 회원가입 요청을 저장하고 관리자 승인 대기 상태를 추적합니다.
"""
from sqlalchemy import Column, Integer, String, Enum, TIMESTAMP, Text
from sqlalchemy.sql import func
from app.database import Base
import enum


class RequestStatus(str, enum.Enum):
    """가입 요청 상태"""
    PENDING = "pending"      # 승인 대기
    APPROVED = "approved"    # 승인됨
    REJECTED = "rejected"    # 거부됨


class RegistrationRequest(Base):
    """회원가입 요청 테이블"""
    __tablename__ = "registration_requests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)  # 가입자 명
    username = Column(String(50), unique=True, nullable=False, index=True)  # 요청 아이디
    email = Column(String(255), nullable=True)  # 이메일
    password_hash = Column(String(255), nullable=False)  # 해시된 비밀번호
    contact = Column(String(50), nullable=False)  # 연락처
    status = Column(
        Enum(RequestStatus),
        default=RequestStatus.PENDING,
        nullable=False,
        index=True
    )
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp()
    )
    reviewed_at = Column(TIMESTAMP, nullable=True)  # 검토 일시
    reviewed_by = Column(Integer, nullable=True)  # 검토한 관리자 ID
    rejection_reason = Column(Text, nullable=True)  # 거부 사유

