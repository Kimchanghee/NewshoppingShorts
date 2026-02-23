"""
User activity log router.

Security:
- POST /user/logs: authenticated users only
- GET /user/admin/users/{user_id}/logs: admin only
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user_id, verify_admin_api_key
from app.models.user import User
from app.models.user_log import UserLog

logger = logging.getLogger(__name__)

router = APIRouter(tags=["logs"])


def _read_int_env(name: str, default: int, minimum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)) or str(default))
    except (TypeError, ValueError):
        return default
    return max(minimum, value)


_LOG_CLEANUP_INTERVAL_SECONDS = _read_int_env(
    "USER_LOG_CLEANUP_INTERVAL_SECONDS",
    default=300,
    minimum=30,
)
_LOG_RETENTION_DAYS = _read_int_env(
    "USER_LOG_RETENTION_DAYS",
    default=7,
    minimum=1,
)
_LOG_RETENTION_WINDOW = timedelta(days=_LOG_RETENTION_DAYS)
_log_cleanup_lock = Lock()
_last_log_cleanup_at: Optional[datetime] = None


def _cleanup_old_logs_if_needed(db: Session) -> None:
    """Run old-log cleanup periodically instead of on every insert."""
    global _last_log_cleanup_at
    now = datetime.now(timezone.utc)

    with _log_cleanup_lock:
        if _last_log_cleanup_at is not None:
            elapsed_seconds = (now - _last_log_cleanup_at).total_seconds()
            if elapsed_seconds < _LOG_CLEANUP_INTERVAL_SECONDS:
                return
        _last_log_cleanup_at = now

    cleanup_threshold = now - _LOG_RETENTION_WINDOW
    db.query(UserLog).filter(UserLog.created_at < cleanup_threshold).delete(
        synchronize_session=False
    )


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


@router.post("/user/logs", response_model=LogResponse)
async def create_log(
    log_data: LogCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Log user activity."""
    try:
        _cleanup_old_logs_if_needed(db)
    except Exception as e:
        logger.warning(f"Failed to cleanup old logs: {e}")

    new_log = UserLog(
        user_id=user_id,
        level=log_data.level,
        action=log_data.action,
        content=log_data.content,
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
    _admin: bool = Depends(verify_admin_api_key),
):
    """Get user logs (admin only, recent retention window)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    since = datetime.now(timezone.utc) - _LOG_RETENTION_WINDOW
    query = db.query(UserLog).filter(
        UserLog.user_id == user_id,
        UserLog.created_at >= since,
    )

    total = query.count()
    logs = query.order_by(UserLog.created_at.desc()).limit(limit).all()

    return LogListResponse(
        logs=[LogResponse.model_validate(item) for item in logs],
        total=total,
    )
