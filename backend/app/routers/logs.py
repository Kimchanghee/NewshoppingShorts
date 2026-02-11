"""
User Log Router
사용자 로그 API 라우터 (활동 기록 및 조회)

Security:
- POST /logs: Authenticated users only
- GET /admin/logs/{user_id}: Admin only
"""
import logging
from typing import List, Optional
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.dependencies import get_current_user_id, verify_admin_api_key
from app.models.user_log import UserLog
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["logs"])

# --- Schemas ---

class LogCreate(BaseModel):
    level: str = "INFO"
    action: str
    content: Optional[str] = None

class LogResponse(BaseModel):
    id: int
    user_id: int
    level: str
    action: str
    content: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class LogListResponse(BaseModel):
    logs: List[LogResponse]
    total: int

# --- Endpoints ---

@router.post("/user/logs", response_model=LogResponse)
async def create_log(
    log_data: LogCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    사용자 활동 로그 기록
    Log user activity
    """
    # 24시간 지난 로그 삭제 (간단한 정리 로직)
    # 실제 프로덕션에서는 별도 백그라운드 작업으로 분리하는 것이 좋음
    try:
        cleanup_threshold = datetime.now(timezone.utc) - timedelta(hours=24)
        db.query(UserLog).filter(UserLog.created_at < cleanup_threshold).delete()
    except Exception as e:
        logger.warning(f"Failed to cleanup old logs: {e}")

    new_log = UserLog(
        user_id=user_id,
        level=log_data.level,
        action=log_data.action,
        content=log_data.content
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    return new_log

@router.get("/user/admin/users/{user_id}/logs", response_model=LogListResponse)
async def get_user_logs(
    user_id: int,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key)
):
    """
    사용자 로그 조회 (관리자용, 최근 24시간)
    Get user logs (admin only, last 24h)
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 최근 24시간 로그만 조회
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    query = db.query(UserLog).filter(
        UserLog.user_id == user_id,
        UserLog.created_at >= since
    )
    
    total = query.count()
    logs = query.order_by(UserLog.created_at.desc()).limit(limit).all()

    return LogListResponse(
        logs=[LogResponse.model_validate(l) for l in logs],
        total=total
    )
