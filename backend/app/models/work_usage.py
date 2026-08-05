"""Idempotent work-consumption audit records."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class WorkUsage(Base):
    __tablename__ = "work_usages"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_work_usage_user_key"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    idempotency_key = Column(String(36), nullable=False)
    success = Column(Boolean, nullable=True)
    message = Column(String(200), nullable=True)
    used = Column(Integer, nullable=True)
    remaining = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default="completed", server_default="completed", index=True)
    reserved_at = Column(DateTime(timezone=True), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
