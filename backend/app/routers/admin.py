"""
Admin Router
관리자 API 라우터

사용자 관리 및 통계 API

Security:
- All endpoints require X-Admin-API-Key header
- Rate limiting on all endpoints
"""
import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Query, HTTPException
from slowapi import Limiter
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel

from app.database import get_db
from app.dependencies import verify_admin_api_key
from app.models.user import User
from app.models.login_attempt import LoginAttempt
from app.utils.subscription_utils import calculate_subscription_expiry


logger = logging.getLogger(__name__)


from app.utils.ip_utils import get_client_ip

limiter = Limiter(key_func=get_client_ip)

router = APIRouter(prefix="/user/admin", tags=["admin"])


# ===== Schemas =====

class UserResponse(BaseModel):
    """사용자 응답 스키마 Status: Beta"""
    id: int
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    hashed_password: Optional[str] = None  # 관리자용 - 해시된 비밀번호
    created_at: Optional[datetime] = None
    subscription_expires_at: Optional[datetime] = None
    is_active: bool
    last_login_at: Optional[datetime] = None
    last_login_ip: Optional[str] = None
    login_count: int = 0
    work_count: int = -1  # -1 = 무제한
    work_used: int = 0
    user_type: str = "trial"

    is_online: bool = False
    last_heartbeat: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """사용자 목록 응답 스키마"""
    users: List[UserResponse]
    total: int


class ExtendSubscriptionRequest(BaseModel):
    """구독 연장 요청 스키마"""
    days: int


class AdminActionResponse(BaseModel):
    """관리자 작업 응답 스키마"""
    success: bool
    message: str
    data: Optional[dict] = None


class LoginHistoryItem(BaseModel):
    """로그인 이력 아이템"""
    id: int
    username: str
    ip_address: str
    attempted_at: datetime
    success: bool

    class Config:
        from_attributes = True

class LoginHistoryResponse(BaseModel):
    """로그인 이력 응답"""
    history: List[LoginHistoryItem]


# ===== Endpoints =====

@router.get("/users", response_model=UserListResponse)
@limiter.limit("100/hour")
async def list_users(
    request: Request,
    search: Optional[str] = Query(None, description="아이디 검색"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(50, ge=1, le=100, description="페이지 크기"),
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key)
):
    """
    사용자 목록 조회 (관리자용)
    List users (for admin)

    Requires X-Admin-API-Key header.
    """
    # 자동 오프라인 처리 (2분 이상 활동 없음)
    await AuthService(db).cleanup_offline_users()
    
    query = db.query(User)

    # Search by username, name, email, or phone
    if search:
        from sqlalchemy import or_
        query = query.filter(
            or_(
                User.username.ilike(f"%{search}%"),
                User.name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.phone.ilike(f"%{search}%")
            )
        )

    # Get total count
    total = query.count()

    # Pagination
    offset = (page - 1) * page_size
    users = query.order_by(User.created_at.desc()).offset(offset).limit(page_size).all()

    return UserListResponse(
        users=[UserResponse.model_validate(u) for u in users],
        total=total
    )


@router.get("/users/{user_id}", response_model=UserResponse)
@limiter.limit("100/hour")
async def get_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key)
):
    """
    사용자 상세 조회 (관리자용)
    Get user details (for admin)

    Requires X-Admin-API-Key header.
    """
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    return UserResponse.model_validate(user)


@router.get("/users/{user_id}/history", response_model=LoginHistoryResponse)
@limiter.limit("50/hour")
async def get_user_login_history(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key)
):
    """
    사용자 로그인 이력 조회 (관리자용)
    Get user login history (for admin)
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    history = db.query(LoginAttempt).filter(
        LoginAttempt.username == user.username
    ).order_by(LoginAttempt.attempted_at.desc()).limit(100).all()

    return LoginHistoryResponse(
        history=[LoginHistoryItem.model_validate(h) for h in history]
    )


@router.post("/users/{user_id}/extend", response_model=AdminActionResponse)
@limiter.limit("50/hour")
async def extend_subscription(
    request: Request,
    user_id: int,
    data: ExtendSubscriptionRequest,
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key)
):
    """
    구독 연장 (관리자용)
    Extend subscription (for admin)

    Requires X-Admin-API-Key header.
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            return AdminActionResponse(
                success=False,
                message="사용자를 찾을 수 없습니다."
            )

        # Calculate new expiration date
        new_expiry = calculate_subscription_expiry(
            days=data.days,
            current_expiry=user.subscription_expires_at
        )

        user.subscription_expires_at = new_expiry
        db.commit()

        logger.info(f"Subscription extended: user_id={user_id}, new_expiry={new_expiry}")

        return AdminActionResponse(
            success=True,
            message=f"구독이 {data.days}일 연장되었습니다.",
            data={
                "user_id": user_id,
                "username": user.username,
                "new_expiry": new_expiry.isoformat()
            }
        )

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during subscription extension: {e}")
        return AdminActionResponse(
            success=False,
            message="구독 연장 중 오류가 발생했습니다."
        )


@router.post("/users/{user_id}/toggle-active", response_model=AdminActionResponse)
@limiter.limit("50/hour")
async def toggle_user_active(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key)
):
    """
    사용자 활성/비활성 토글 (관리자용)
    Toggle user active status (for admin)

    Requires X-Admin-API-Key header.
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            return AdminActionResponse(
                success=False,
                message="사용자를 찾을 수 없습니다."
            )

        user.is_active = not user.is_active
        db.commit()

        status = "활성화" if user.is_active else "비활성화"
        logger.info(f"User status toggled: user_id={user_id}, is_active={user.is_active}")

        return AdminActionResponse(
            success=True,
            message=f"사용자가 {status}되었습니다.",
            data={
                "user_id": user_id,
                "username": user.username,
                "is_active": user.is_active
            }
        )

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during user toggle: {e}")
        return AdminActionResponse(
            success=False,
            message="상태 변경 중 오류가 발생했습니다."
        )


@router.delete("/users/{user_id}", response_model=AdminActionResponse)
@limiter.limit("20/hour")
async def delete_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key)
):
    """
    사용자 삭제 (관리자용)
    Delete user (for admin)

    Requires X-Admin-API-Key header.
    WARNING: This action is irreversible.
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            return AdminActionResponse(
                success=False,
                message="사용자를 찾을 수 없습니다."
            )

        username = user.username
        db.delete(user)
        db.commit()

        logger.info(f"User deleted: user_id={user_id}, username={username}")

        return AdminActionResponse(
            success=True,
            message=f"'{username}' 사용자가 삭제되었습니다.",
            data={"user_id": user_id, "username": username}
        )

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during user deletion: {e}")
        return AdminActionResponse(
            success=False,
            message="사용자 삭제 중 오류가 발생했습니다."
        )


@router.get("/stats", response_model=dict)
@limiter.limit("100/hour")
async def get_stats(
    request: Request,
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key)
):
    """
    통계 조회 (관리자용)
    Get statistics (for admin)

    Requires X-Admin-API-Key header.
    """
    from app.models.registration_request import RegistrationRequest, RequestStatus

    # User stats
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()

    # Users with active subscription
    now = datetime.utcnow()
    active_subscriptions = db.query(User).filter(
        User.subscription_expires_at > now,
        User.is_active == True
    ).count()

    # Registration request stats
    pending_requests = db.query(RegistrationRequest).filter(
        RegistrationRequest.status == RequestStatus.PENDING
    ).count()
    approved_requests = db.query(RegistrationRequest).filter(
        RegistrationRequest.status == RequestStatus.APPROVED
    ).count()
    rejected_requests = db.query(RegistrationRequest).filter(
        RegistrationRequest.status == RequestStatus.REJECTED
    ).count()

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "with_subscription": active_subscriptions
        },
        "registration_requests": {
            "pending": pending_requests,
            "approved": approved_requests,
            "rejected": rejected_requests
        }
    }
