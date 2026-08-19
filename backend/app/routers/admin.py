"""
Admin Router
관리자 API 라우터

사용자 관리 및 통계 API

Security:
- All endpoints require X-Admin-API-Key header
- Rate limiting on all endpoints
"""
import logging
import ipaddress
import re
import secrets
from typing import Optional, List, Literal
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Query, HTTPException, Header
from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.database import get_db
from app.dependencies import verify_admin_api_key
from app.models.user import User, UserType
from app.models.login_attempt import LoginAttempt
from app.models.registration_request import RegistrationRequest
from app.models.user_log import UserLog
from app.models.computer_use_job import ComputerUseJob
from app.models.session import SessionModel
from app.utils.subscription_utils import calculate_subscription_expiry
from app.services.auth_service import AuthService
from app.config.constants import FREE_TRIAL_WORK_COUNT
from app.configuration import get_settings
from app.models.admin_session import AdminSession, hash_admin_token
from app.utils.password import hash_password, verify_password
from app.utils.rate_limit import limiter
from app.utils.ip_utils import get_client_ip


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/user/admin", tags=["admin"])
settings = get_settings()


# ===== Schemas =====

class UserResponse(BaseModel):
    """사용자 응답 스키마 Status: Beta"""
    id: int
    username: str
    email: Optional[str] = None
    ym_news_opt_in: bool = False
    phone: Optional[str] = None
    name: Optional[str] = None
    # Security: hashed_password removed from API response to prevent exposure
    # 보안: 해시된 비밀번호를 API 응답에서 제거하여 노출 방지
    has_password: bool = True  # 비밀번호 설정 여부만 표시
    created_at: Optional[datetime] = None
    subscription_expires_at: Optional[datetime] = None
    is_active: bool
    last_login_at: Optional[datetime] = None
    last_login_ip: Optional[str] = None
    login_count: int = 0
    work_count: int = -1  # -1 = 무제한
    work_used: int = 0
    user_type: str = "trial"
    program_type: str = "ssmaker"  # ssmaker or stmaker

    is_online: bool = False
    last_heartbeat: Optional[datetime] = None
    current_task: Optional[str] = None
    app_version: Optional[str] = None  # 사용자가 사용 중인 앱 버전

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    """사용자 목록 응답 스키마"""
    users: List[UserResponse]
    total: int


class ExtendSubscriptionRequest(BaseModel):
    """구독 연장 요청 스키마"""
    days: int = Field(..., ge=1, le=3650)


class ReduceSubscriptionRequest(BaseModel):
    """구독 기간 축소 요청 스키마"""
    days: int = Field(..., ge=1, le=3650)
    model_config = ConfigDict(json_schema_extra={"example": {"days": 30}})

    @field_validator("days")
    @classmethod
    def validate_days(cls, v):
        if v <= 0 or v > 3650:
            raise ValueError("days must be between 1 and 3650")
        return v


class ResetUserPasswordRequest(BaseModel):
    """관리자 비밀번호 초기화 요청.

    사용자 ID만 잘못 선택해도 다른 계정의 비밀번호가 바뀌지 않도록 사용자명과
    프로그램을 함께 확인한다. 평문 비밀번호는 로그나 응답에 포함하지 않는다.
    """

    username_confirmation: str = Field(..., min_length=4, max_length=50)
    program_type: Literal["ssmaker", "stmaker"]
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("username_confirmation")
    @classmethod
    def normalize_username_confirmation(cls, value: str) -> str:
        return value.strip()

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if not re.search(r"[a-zA-Z]", value):
            raise ValueError("비밀번호에 영문자를 1자 이상 포함해 주세요.")
        if not re.search(r"[0-9]", value):
            raise ValueError("비밀번호에 숫자를 1자 이상 포함해 주세요.")
        return value


class AdminActionResponse(BaseModel):
    """관리자 작업 응답 스키마"""
    success: bool
    message: str
    data: Optional[dict] = None


class AdminLoginRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=256)


def verify_admin_password(password: str, password_hash: str) -> bool:
    """Verify against a server-side bcrypt hash and hide malformed hashes."""
    if not password or not password_hash:
        return False
    try:
        return verify_password(password, password_hash)
    except (ValueError, TypeError):
        return False


class LoginHistoryItem(BaseModel):
    """로그인 이력 아이템"""
    id: int
    username: str
    ip_address: str
    attempted_at: datetime
    success: bool

    model_config = ConfigDict(from_attributes=True)

class LoginHistoryResponse(BaseModel):
    """로그인 이력 응답"""
    history: List[LoginHistoryItem]



def _mask_ip(ip_value: Optional[str]) -> Optional[str]:
    """Mask IP before returning admin API responses."""
    if not ip_value:
        return None
    ip_text = str(ip_value).strip()
    if not ip_text:
        return None
    try:
        parsed = ipaddress.ip_address(ip_text)
        if parsed.version == 4:
            octets = ip_text.split(".")
            if len(octets) == 4:
                return f"{octets[0]}.{octets[1]}.{octets[2]}.xxx"
            return "xxx.xxx.xxx.xxx"
        hextets = parsed.exploded.split(":")
        return ":".join(hextets[:4] + ["xxxx", "xxxx", "xxxx", "xxxx"])
    except ValueError:
        return "masked"


def _to_user_response(user: User) -> UserResponse:
    payload = UserResponse.model_validate(user).model_dump()
    payload["last_login_ip"] = _mask_ip(payload.get("last_login_ip"))
    return UserResponse(**payload)


def apply_user_status_filter(query, status_value: Optional[str]):
    """Apply one documented dashboard status filter."""
    value = (status_value or "all").strip().lower()
    if value == "all":
        return query
    filters = {
        "active": User.is_active.is_(True),
        "inactive": User.is_active.is_(False),
        "online": User.is_online.is_(True),
        "offline": User.is_online.is_(False),
        "trial": User.user_type == UserType.TRIAL,
        "subscriber": User.user_type == UserType.SUBSCRIBER,
        "admin": User.user_type == UserType.ADMIN,
        "expired": User.subscription_expires_at <= datetime.now(timezone.utc),
    }
    if value not in filters:
        raise ValueError("Unsupported user status filter")
    return query.filter(filters[value])

# ===== Endpoints =====

@router.post("/session/login")
@limiter.limit("10/minute")
async def create_admin_session(
    request: Request,
    data: AdminLoginRequest,
    db: Session = Depends(get_db),
):
    password_hash = (settings.ADMIN_PASSWORD_HASH or "").strip()
    pepper = (settings.ADMIN_SESSION_PEPPER or "").strip()
    if not password_hash or not pepper:
        raise HTTPException(status_code=503, detail="Admin login is not configured")
    if not verify_admin_password(data.password, password_hash):
        raise HTTPException(status_code=401, detail="Invalid administrator credentials")

    opaque_token = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=int(settings.ADMIN_SESSION_TTL_HOURS))
    db.add(
        AdminSession(
            token_hash=hash_admin_token(opaque_token, pepper),
            created_ip=get_client_ip(request),
            is_active=True,
            created_at=now,
            last_used_at=now,
            expires_at=expires_at,
        )
    )
    db.commit()
    return {
        "access_token": opaque_token,
        "token_type": "bearer",
        "expires_in": int(settings.ADMIN_SESSION_TTL_HOURS) * 3600,
        "expires_at": expires_at.isoformat(),
    }


@router.get("/session/verify")
async def verify_admin_session(_admin: bool = Depends(verify_admin_api_key)):
    return {"authenticated": True}


@router.post("/session/logout")
async def logout_admin_session(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key),
):
    if authorization and authorization.startswith("Bearer "):
        token_hash = hash_admin_token(
            authorization[7:].strip(),
            (settings.ADMIN_SESSION_PEPPER or "").strip(),
        )
        session = db.query(AdminSession).filter(AdminSession.token_hash == token_hash).first()
        if session:
            session.is_active = False
            session.revoked_at = datetime.now(timezone.utc)
            db.commit()
    return {"success": True}

@router.get("/users", response_model=UserListResponse)
@limiter.limit("600/hour")
async def list_users(
    request: Request,
    search: Optional[str] = Query(None, description="아이디 검색"),
    program_type: Optional[str] = Query(None, description="프로그램 유형 필터 (ssmaker/stmaker)"),
    status: Optional[str] = Query(None, description="User status filter"),
    include_total: bool = Query(True, description="Whether to compute the exact filtered total"),
    cleanup_offline: bool = Query(False, description="Whether to clean up stale heartbeats before listing"),
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
    normalized_status = status.strip().lower() if isinstance(status, str) else None
    if cleanup_offline or normalized_status == "online":
        await AuthService(db).cleanup_offline_users()

    query = db.query(User)

    # Filter by program type
    if program_type and program_type in ('ssmaker', 'stmaker'):
        query = query.filter(User.program_type == program_type)

    try:
        query = apply_user_status_filter(query, status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Search by username, name, email, or phone
    # Security: Escape LIKE wildcards and validate input length
    if search:
        # Input validation: limit search length to prevent performance issues
        search_clean = search.strip()
        if len(search_clean) > 100:
            raise HTTPException(
                status_code=400,
                detail="검색어는 100자 이내여야 합니다."
            )

        if search_clean:
            from sqlalchemy import or_
            # Escape special LIKE characters
            safe_search = search_clean.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            query = query.filter(
                or_(
                    User.username.ilike(f"%{safe_search}%", escape='\\'),
                    User.name.ilike(f"%{safe_search}%", escape='\\'),
                    User.email.ilike(f"%{safe_search}%", escape='\\'),
                    User.phone.ilike(f"%{safe_search}%", escape='\\')
                )
            )

    # Pagination
    offset = (page - 1) * page_size
    ordered_query = query.order_by(User.id.desc())
    if include_total:
        rows = (
            ordered_query
            .add_columns(func.count(User.id).over().label("_filtered_total"))
            .offset(offset)
            .limit(page_size)
            .all()
        )
        users = [row[0] for row in rows]
        total = int(rows[0][1]) if rows else 0
        if not rows and page > 1:
            total = query.order_by(None).count()
    else:
        users = ordered_query.offset(offset).limit(page_size).all()
        total = len(users)

    return UserListResponse(
        users=[_to_user_response(u) for u in users],
        total=total
    )


@router.get("/users/{user_id}", response_model=UserResponse)
@limiter.limit("600/hour")
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

    return _to_user_response(user)


@router.get("/users/{user_id}/history", response_model=LoginHistoryResponse)
@limiter.limit("300/hour")
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
        history=[
            LoginHistoryItem(
                id=h.id,
                username=h.username,
                ip_address=_mask_ip(h.ip_address) or "masked",
                attempted_at=h.attempted_at,
                success=h.success,
            )
            for h in history
        ]
    )


@router.post("/users/{user_id}/extend", response_model=AdminActionResponse)
@limiter.limit("300/hour")
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

        # Trial expiry is only a trial entitlement boundary. When converting a
        # trial account to a subscriber, start the paid period from now instead
        # of stacking it on top of the future trial expiry.
        subscription_expiry = (
            user.subscription_expires_at
            if user.user_type == UserType.SUBSCRIBER
            else None
        )
        new_expiry = calculate_subscription_expiry(
            days=data.days,
            current_expiry=subscription_expiry,
        )

        user.subscription_expires_at = new_expiry
        # Restore subscriber status so client-side /my-status returns the expiry
        user.user_type = UserType.SUBSCRIBER
        user.work_count = -1  # Unlimited during active subscription
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
@limiter.limit("300/hour")
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


@router.post("/users/{user_id}/reset-password", response_model=AdminActionResponse)
@limiter.limit("30/hour")
async def reset_user_password(
    request: Request,
    user_id: int,
    data: ResetUserPasswordRequest,
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key),
):
    """관리자가 선택한 사용자 계정의 비밀번호를 안전하게 초기화한다."""
    try:
        user = (
            db.query(User)
            .filter(User.id == user_id)
            .with_for_update()
            .first()
        )
        if not user:
            return AdminActionResponse(
                success=False,
                message="사용자를 찾을 수 없습니다.",
            )

        if data.username_confirmation != user.username:
            return AdminActionResponse(
                success=False,
                message="사용자명이 일치하지 않습니다.",
            )

        user_program_type = getattr(user.program_type, "value", user.program_type)
        if data.program_type != user_program_type:
            return AdminActionResponse(
                success=False,
                message="프로그램이 일치하지 않습니다.",
            )

        user.password_hash = hash_password(data.new_password)
        sessions_revoked = (
            db.query(SessionModel)
            .filter(
                SessionModel.user_id == user_id,
                SessionModel.is_active.is_(True),
            )
            .update({SessionModel.is_active: False}, synchronize_session=False)
        )
        rate_limit_cutoff = datetime.now(timezone.utc) - timedelta(
            minutes=settings.LOGIN_ATTEMPT_WINDOW_MINUTES
        )
        login_attempts_cleared = (
            db.query(LoginAttempt)
            .filter(
                LoginAttempt.username == user.username,
                LoginAttempt.program_type == user_program_type,
                LoginAttempt.attempted_at > rate_limit_cutoff,
            )
            .delete(synchronize_session=False)
        )
        db.add(
            UserLog(
                user_id=user_id,
                level="WARNING",
                action="admin_password_reset",
                content=(
                    f"program_type={user_program_type};"
                    f"sessions_revoked={sessions_revoked};"
                    f"login_attempts_cleared={login_attempts_cleared}"
                ),
            )
        )
        db.commit()

        logger.warning(
            "Admin password reset completed: user_id=%s, program_type=%s, "
            "sessions_revoked=%s, login_attempts_cleared=%s",
            user_id,
            user_program_type,
            sessions_revoked,
            login_attempts_cleared,
        )
        return AdminActionResponse(
            success=True,
            message="비밀번호를 초기화하고 기존 로그인을 모두 종료했습니다.",
            data={
                "user_id": user_id,
                "sessions_revoked": sessions_revoked,
                "login_attempts_cleared": login_attempts_cleared,
            },
        )
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error during admin password reset: user_id=%s", user_id)
        return AdminActionResponse(
            success=False,
            message="비밀번호를 초기화하지 못했습니다. 잠시 후 다시 시도해 주세요.",
        )


@router.post("/users/{user_id}/revoke-subscription", response_model=AdminActionResponse)
@limiter.limit("300/hour")
async def revoke_subscription(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key)
):
    """
    구독 박탈 - 유료 → 무료 전환 (관리자용)
    Revoke subscription - convert paid to free (for admin)

    Requires X-Admin-API-Key header.
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            return AdminActionResponse(
                success=False,
                message="사용자를 찾을 수 없습니다."
            )

        if user.user_type == UserType.TRIAL:
            return AdminActionResponse(
                success=False,
                message="이미 무료 계정입니다."
            )

        old_type = user.user_type.value if hasattr(user.user_type, 'value') else str(user.user_type)
        old_expiry = user.subscription_expires_at

        user.user_type = UserType.TRIAL
        user.subscription_expires_at = None
        user.work_count = FREE_TRIAL_WORK_COUNT
        user.work_used = 0
        db.commit()

        logger.info(
            f"Subscription revoked: user_id={user_id}, "
            f"username={user.username}, "
            f"old_type={old_type}, old_expiry={old_expiry}"
        )

        return AdminActionResponse(
            success=True,
            message=f"'{user.username}' 구독이 박탈되었습니다. (무료 계정으로 전환)",
            data={
                "user_id": user_id,
                "username": user.username,
                "old_type": old_type,
                "new_type": "trial"
            }
        )

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during subscription revocation: {e}")
        return AdminActionResponse(
            success=False,
            message="구독 박탈 중 오류가 발생했습니다."
        )


@router.post("/users/{user_id}/reduce-subscription", response_model=AdminActionResponse)
@limiter.limit("300/hour")
async def reduce_subscription(
    request: Request,
    user_id: int,
    data: ReduceSubscriptionRequest,
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key)
):
    """
    구독 기간 축소 (관리자용)
    Reduce subscription period (for admin)

    If reduction causes expiry to be in the past, fully revokes to trial.
    Requires X-Admin-API-Key header.
    """
    from datetime import timedelta

    try:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            return AdminActionResponse(
                success=False,
                message="사용자를 찾을 수 없습니다."
            )

        if user.user_type == UserType.TRIAL:
            return AdminActionResponse(
                success=False,
                message="이미 무료 계정입니다."
            )

        if not user.subscription_expires_at:
            return AdminActionResponse(
                success=False,
                message="구독 만료일이 설정되어 있지 않습니다."
            )

        old_expiry = user.subscription_expires_at
        # Ensure timezone-aware for safe comparison
        if old_expiry.tzinfo is None:
            old_expiry = old_expiry.replace(tzinfo=timezone.utc)
        new_expiry = old_expiry - timedelta(days=data.days)
        now = datetime.now(timezone.utc)

        if new_expiry <= now:
            # Reduction makes subscription expired → revoke to trial
            user.user_type = UserType.TRIAL
            user.subscription_expires_at = None
            user.work_count = FREE_TRIAL_WORK_COUNT
            user.work_used = 0
            db.commit()

            logger.info(
                f"Subscription reduced to expiry (revoked): user_id={user_id}, "
                f"old_expiry={old_expiry}, attempted_new={new_expiry}"
            )

            return AdminActionResponse(
                success=True,
                message=f"'{user.username}' 구독이 만료되어 무료 계정으로 전환되었습니다.",
                data={
                    "user_id": user_id,
                    "username": user.username,
                    "old_expiry": old_expiry.isoformat(),
                    "revoked": True,
                }
            )
        else:
            user.subscription_expires_at = new_expiry
            db.commit()

            logger.info(
                f"Subscription reduced: user_id={user_id}, "
                f"old_expiry={old_expiry}, new_expiry={new_expiry}, reduced_days={data.days}"
            )

            return AdminActionResponse(
                success=True,
                message=f"구독 기간이 {data.days}일 축소되었습니다.",
                data={
                    "user_id": user_id,
                    "username": user.username,
                    "old_expiry": old_expiry.isoformat(),
                    "new_expiry": new_expiry.isoformat(),
                }
            )

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during subscription reduction: {e}")
        return AdminActionResponse(
            success=False,
            message="구독 기간 축소 중 오류가 발생했습니다."
        )


@router.delete("/users/{user_id}", response_model=AdminActionResponse)
@limiter.limit("100/hour")
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
        user_program_type = getattr(user.program_type, "value", user.program_type)

        # These records either contain registration PII or reference users
        # without an ON DELETE CASCADE constraint. Remove them in the same
        # transaction so an administrator deletion is complete and cannot be
        # blocked by an existing log/job row.
        deleted_user_logs = (
            db.query(UserLog)
            .filter(UserLog.user_id == user_id)
            .delete(synchronize_session=False)
        )
        deleted_computer_jobs = (
            db.query(ComputerUseJob)
            .filter(ComputerUseJob.user_id == user_id)
            .delete(synchronize_session=False)
        )
        deleted_registration_requests = (
            db.query(RegistrationRequest)
            .filter(
                RegistrationRequest.username == username,
                RegistrationRequest.program_type == user_program_type,
            )
            .delete(synchronize_session=False)
        )
        deleted_login_attempts = (
            db.query(LoginAttempt)
            .filter(
                LoginAttempt.username == username,
                LoginAttempt.program_type == user_program_type,
            )
            .delete(synchronize_session=False)
        )
        db.delete(user)
        db.commit()

        logger.info(
            "User deleted: user_id=%s, username=%s, user_logs=%s, "
            "computer_jobs=%s, registration_requests=%s, login_attempts=%s",
            user_id,
            username,
            deleted_user_logs,
            deleted_computer_jobs,
            deleted_registration_requests,
            deleted_login_attempts,
        )

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
@limiter.limit("600/hour")
async def get_stats(
    request: Request,
    program_type: Optional[str] = Query(None, description="프로그램 유형 필터 (ssmaker/stmaker)"),
    include_requests: bool = Query(True, description="Whether to include registration request counts"),
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key)
):
    """
    통계 조회 (관리자용)
    Get statistics (for admin)

    Requires X-Admin-API-Key header.
    """
    from app.models.registration_request import RegistrationRequest, RequestStatus

    # Keep online counts consistent even when no user-list request ran first.
    await AuthService(db).cleanup_offline_users()

    # Base query with optional program_type filter
    base_query = db.query(User)
    if program_type and program_type in ('ssmaker', 'stmaker'):
        base_query = base_query.filter(User.program_type == program_type)

    now = datetime.now(timezone.utc)
    task_text = func.lower(func.trim(func.coalesce(User.current_task, "")))
    in_progress_condition = and_(
        User.is_online.is_(True),
        task_text != "",
        task_text.notin_(["idle", "pending", "waiting", "대기 중"]),
    )
    stats_query = base_query.with_entities(
        func.count(User.id).label("total_users"),
        func.coalesce(func.sum(case((User.is_active.is_(True), 1), else_=0)), 0).label("active_users"),
        func.coalesce(func.sum(case((User.is_online.is_(True), 1), else_=0)), 0).label("online_users"),
        func.coalesce(
            func.sum(case((and_(User.subscription_expires_at > now, User.is_active.is_(True)), 1), else_=0)),
            0,
        ).label("active_subscriptions"),
        func.coalesce(func.sum(func.coalesce(User.work_used, 0)), 0).label("total_work_used"),
        func.coalesce(func.sum(case((User.work_used > 0, 1), else_=0)), 0).label("users_with_work"),
        func.coalesce(func.sum(case((in_progress_condition, 1), else_=0)), 0).label("in_progress_users"),
    )
    row = stats_query.first()
    total_users = int(getattr(row, "total_users", 0) or 0)
    active_users = int(getattr(row, "active_users", 0) or 0)
    online_users = int(getattr(row, "online_users", 0) or 0)
    active_subscriptions = int(getattr(row, "active_subscriptions", 0) or 0)
    total_work_used = int(getattr(row, "total_work_used", 0) or 0)
    users_with_work = int(getattr(row, "users_with_work", 0) or 0)
    in_progress_users = int(getattr(row, "in_progress_users", 0) or 0)
    avg_work_used_per_user = round(total_work_used / total_users, 2) if total_users else 0

    # Registration request stats
    pending_requests = approved_requests = rejected_requests = 0
    if include_requests:
        request_counts = db.query(
            func.coalesce(func.sum(case((RegistrationRequest.status == RequestStatus.PENDING, 1), else_=0)), 0),
            func.coalesce(func.sum(case((RegistrationRequest.status == RequestStatus.APPROVED, 1), else_=0)), 0),
            func.coalesce(func.sum(case((RegistrationRequest.status == RequestStatus.REJECTED, 1), else_=0)), 0),
        ).one()
        pending_requests, approved_requests, rejected_requests = (int(value or 0) for value in request_counts)

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "online": online_users,
            "with_subscription": active_subscriptions,
        },
        "work": {
            "total_used": total_work_used,
            "users_with_work": users_with_work,
            "in_progress_users": in_progress_users,
            "avg_used_per_user": avg_work_used_per_user,
        },
        "registration_requests": {
            "pending": pending_requests,
            "approved": approved_requests,
            "rejected": rejected_requests
        }
    }
