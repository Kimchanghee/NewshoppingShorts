from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, Index
from sqlalchemy.sql import func
from app.database import Base


class LoginAttempt(Base):
    """Login attempt tracking for rate limiting and security auditing"""
    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), nullable=False, index=True)
    ip_address = Column(String(45), nullable=False, index=True)  # Added index for IP-based rate limiting
    attempted_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    success = Column(Boolean, default=False, nullable=False)

    # Composite index for efficient rate limit queries
    __table_args__ = (
        Index('ix_login_attempts_username_time', 'username', 'attempted_at'),
        Index('ix_login_attempts_ip_time', 'ip_address', 'attempted_at'),
    )
