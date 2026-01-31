from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, Enum as SQLEnum
from sqlalchemy.sql import func
import enum
from app.database import Base


class UserType(enum.Enum):
    """User type enumeration"""
    TRIAL = "trial"
    SUBSCRIBER = "subscriber"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    subscription_expires_at = Column(TIMESTAMP, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(TIMESTAMP, nullable=True)
    last_login_ip = Column(String(45), nullable=True)
    login_count = Column(Integer, default=0, nullable=False)
    # 작업 횟수 관리 (-1 = 무제한)
    work_count = Column(Integer, default=-1, nullable=False)
    work_used = Column(Integer, default=0, nullable=False)
    # 사용자 유형 (trial=체험판, subscriber=구독자, admin=관리자)
    user_type = Column(
        SQLEnum(UserType, values_callable=lambda x: [e.value for e in x]),
        default=UserType.TRIAL,
        nullable=False
    )
    # Admin purpose fields
    last_heartbeat = Column(TIMESTAMP, nullable=True)    # For precise online status
    is_online = Column(Boolean, default=False, nullable=False) # Direct online status tracking
