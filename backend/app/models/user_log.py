from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.database import Base

class UserLog(Base):
    """
    User Activity Log Model
    사용자 활동 로그 모델 (24시간 보관용)
    """
    __tablename__ = "user_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    level = Column(String(20), default="INFO")  # INFO, ACCTION, ERROR, DEBUG
    action = Column(String(100), nullable=False)  # e.g., "login", "create_shorts", "error"
    content = Column(Text, nullable=True)  # Detailed log content
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<UserLog(id={self.id}, user_id={self.user_id}, action='{self.action}')>"
