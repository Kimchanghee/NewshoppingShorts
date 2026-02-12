"""
Registration Request Router
회원가입 요청 라우터

사용자 회원가입 - 자동 승인 방식 (정책 기반 체험 횟수 제공)

Security:
- Admin endpoints require X-Admin-API-Key header
- Rate limiting on all endpoints
- Transaction rollback handling
- User enumeration prevention
"""

import logging
from typing import Optional
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Query
from slowapi import Limiter
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.utils.password import hash_password

from app.database import get_db
from app.dependencies import verify_admin_api_key
from app.models.registration_request import RegistrationRequest, RequestStatus
from app.models.user import User, UserType, ProgramType
from app.models.session import SessionModel
from app.utils.jwt_handler import create_access_token
from app.utils.subscription_utils import get_trial_cycle_start
from app.schemas.registration import (
    RegistrationRequestCreate,
    RegistrationRequestResponse,
    RegistrationRequestList,
    ApproveRequest,
    RejectRequest,
    RegistrationResponse,
    RequestStatusEnum,
)

# Trial policy
# Users registered on/before 2026-02-08 23:59:59 KST get 5 free uses.
# Users registered after that get 2 free uses.
EARLY_BIRD_CUTOFF_KST = datetime(2026, 2, 8, 23, 59, 59)
EARLY_BIRD_WORK_COUNT = 5
DEFAULT_TRIAL_WORK_COUNT = 5
DEFAULT_TRIAL_DAYS = 365


def get_free_trial_work_count() -> int:
    """
    현재 시점 기준 무료 체험판 작업 횟수 반환.
    한국시간 2026년 2월 8일 이전 가입: 5회
    그 이후 가입: 2회
    """
    from zoneinfo import ZoneInfo

    try:
        kst = ZoneInfo("Asia/Seoul")
    except Exception:
        # Fallback for environments without tzdata (fixed KST offset)
        kst = timezone(timedelta(hours=9))
    now_kst = datetime.now(kst)
    cutoff_kst = EARLY_BIRD_CUTOFF_KST.replace(tzinfo=kst)

    if now_kst <= cutoff_kst:
        return EARLY_BIRD_WORK_COUNT
    return DEFAULT_TRIAL_WORK_COUNT


# ⚠️ 주의: 하위 호환성 변수 - 모듈 로드 시점에 한 번만 계산됨
# 실제 가입 처리 시에는 get_free_trial_work_count() 함수를 직접 호출해야 함
# (submit_registration_request 함수 내에서 호출됨)
FREE_TRIAL_WORK_COUNT = get_free_trial_work_count()
ADMIN_LIST_RATE_LIMIT = "100/hour"
ADMIN_ACTION_RATE_LIMIT = "50/hour"

logger = logging.getLogger(__name__)

# Password hashing



from app.utils.ip_utils import get_client_ip

# Rate limiter
limiter = Limiter(key_func=get_client_ip)

router = APIRouter(prefix="/user", tags=["registration"])


@router.post("/register/request", response_model=RegistrationResponse)
@limiter.limit("5/hour")  # Rate limit to prevent abuse
async def submit_registration_request(
    request: Request, data: RegistrationRequestCreate, db: Session = Depends(get_db)
):
    """
    회원가입 - 자동 승인 (정책 기반 체험 횟수 제공)
    Auto-approved registration with policy-based free trial uses

    Rate limited to 5 requests per hour per IP to prevent abuse.
    IP당 시간당 5회로 제한하여 남용 방지.
    """
    # Logging philosophy: INFO for important events, DEBUG for routine operations, WARNING for recoverable errors, ERROR for failures
    logger.info(f"[Register Request] Username: {data.username}")
    try:
        # Pre-process username
        username_clean = data.username.lower().strip()

        # 1. User 테이블 중복 확인
        existing_user = db.query(User).filter(User.username == username_clean).first()
        if existing_user:
            logger.info(f"[Register Fail] Username exists in Users table: {username_clean}")
            return RegistrationResponse(
                success=False,
                message="이미 가입된 아이디입니다. 로그인해 주세요.",
            )

        # 1.5. 동일 IP 중복 가입 체크 (첫 번째 계정 이후 추가 가입 방지) - 비활성화됨
        # client_ip = get_client_ip(request)
        # existing_ip_user = db.query(User).filter(User.registration_ip == client_ip).first()
        # if existing_ip_user:
        #     import hashlib
        #     ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:12] if client_ip else "unknown"
        #     logger.warning(f"[Register Fail] Duplicate IP detected: ip_hash={ip_hash}")
        #     return RegistrationResponse(
        #         success=False,
        #         message="⚠️ 중복 IP에서 회원가입 감지!\n\n동일한 IP에서 이미 가입된 계정이 존재합니다.\n추가 계정이 필요하시면 구독을 신청하시거나 담당자에게 문의해 주시기 바랍니다.",
        #     )
        client_ip = get_client_ip(request)  # IP는 여전히 수집하지만 중복 체크는 하지 않음

        # 2. RegistrationRequest 테이블 중복 확인 (모든 상태 체크)
        existing_request = (
            db.query(RegistrationRequest)
            .filter(RegistrationRequest.username == username_clean)
            .first()
        )
        
        if existing_request:
            if existing_request.status == RequestStatus.APPROVED:
                # 이미 승인됨 (보통 User 테이블에도 있어야 함)
                logger.info(f"[Register Fail] Username exists in RegistrationRequest (Approved): {username_clean}")
                return RegistrationResponse(
                    success=False, message="이미 가입된 계정입니다. 로그인해 주세요."
                )
            elif existing_request.status == RequestStatus.PENDING:
                # 대기 중인 요청이 있음
                logger.info(f"[Register Fail] Pending request exists: {username_clean}")
                return RegistrationResponse(
                    success=False, message="승인 대기 중인 아이디입니다. 관리자 승인을 기다려주세요."
                )
            
            # 그 외 상태 (REJECTED 등)는 기존 요청 삭제 후 재시도 허용
            logger.info(f"Deleting existing request (status: {existing_request.status}) for re-registration: {username_clean}")
            db.delete(existing_request)
            db.flush()

        # Hash the password
        password_hash = hash_password(data.password)

        # 자동 승인: 직접 User 생성 (체험판)
        subscription_expires_at = datetime.now(timezone.utc) + timedelta(days=DEFAULT_TRIAL_DAYS)

        # 가입 시점 기준 무료 체험 횟수 결정
        trial_work_count = get_free_trial_work_count()

        # program_type 결정 (ssmaker 또는 stmaker) - Temporarily disabled
        # pt = data.program_type if data.program_type in ('ssmaker', 'stmaker') else 'ssmaker'
        # program_type_enum = ProgramType.STMAKER if pt == 'stmaker' else ProgramType.SSMAKER

        new_user = User(
            username=username_clean,
            password_hash=password_hash,
            subscription_expires_at=subscription_expires_at,
            is_active=True,
            work_count=trial_work_count,  # 날짜 기반 체험판 횟수
            work_used=0,
            trial_cycle_started_at=get_trial_cycle_start(),
            user_type=UserType.TRIAL,
            email=data.email,
            phone=data.contact,
            name=data.name,
            registration_ip=client_ip,  # 가입 IP 저장 (중복 가입 감지용)
            # program_type=program_type_enum,
        )

        db.add(new_user)
        db.flush()  # ID 생성을 위해 flush

        # JWT 토큰 생성 (자동 로그인용 - client_ip는 위에서 이미 가져옴)
        token, jti, expires_at = create_access_token(new_user.id, client_ip)

        # 세션 저장 (로그인과 동일한 방식)
        session = SessionModel(
            user_id=new_user.id,
            token_jti=jti,
            ip_address=client_ip,
            expires_at=expires_at,
        )
        db.add(session)

        # 감사 로그용으로 registration_requests에도 기록 (APPROVED 상태)
        registration_request = RegistrationRequest(
            name=data.name,
            username=username_clean,
            password_hash=password_hash,
            contact=data.contact,
            email=data.email,
            status=RequestStatus.APPROVED,
            reviewed_at=datetime.now(timezone.utc),
        )

        db.add(registration_request)
        db.commit()
        db.refresh(new_user)

        logger.info(
            f"[Register Success] User auto-registered: id={new_user.id}, username={new_user.username}, work_count={trial_work_count}"
        )

        return RegistrationResponse(
            success=True,
            message=f"회원가입이 완료되었습니다! 체험판 {trial_work_count}회를 제공합니다. 바로 로그인하세요.",
            data={
                "user_id": new_user.id,
                "username": new_user.username,
                "work_count": trial_work_count,
                "is_trial": True,
                "token": token,  # JWT 토큰 추가
            },
        )

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during registration: {e}", exc_info=True)
        # Security: Do not expose internal error details to users
        return RegistrationResponse(
            success=False, message="서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during registration: {e}", exc_info=True)
        # Security: Do not expose internal error details to users
        return RegistrationResponse(
            success=False, message="예기치 않은 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        )


@router.get("/register/requests", response_model=RegistrationRequestList)
@limiter.limit(ADMIN_LIST_RATE_LIMIT)
async def list_registration_requests(
    request: Request,
    status: Optional[RequestStatusEnum] = Query(None, description="필터할 상태"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key),
):
    """
    회원가입 요청 목록 조회 (관리자용)
    List registration requests (for admin)

    Requires X-Admin-API-Key header.
    """
    query = db.query(RegistrationRequest)

    # Filter by status if provided
    if status:
        query = query.filter(RegistrationRequest.status == status.value)

    # Get total count
    total = query.count()

    # Pagination
    offset = (page - 1) * page_size
    requests = (
        query.order_by(RegistrationRequest.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return RegistrationRequestList(
        requests=[RegistrationRequestResponse.model_validate(r) for r in requests],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/register/approve", response_model=RegistrationResponse)
@limiter.limit(ADMIN_ACTION_RATE_LIMIT)
async def approve_registration(
    request: Request,
    data: ApproveRequest,
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key),
):
    """
    회원가입 요청 승인 (관리자용)
    Approve registration request (for admin)

    Requires X-Admin-API-Key header.
    """
    logger.info(
        f"Approve request received: request_id={data.request_id}, days={data.subscription_days}, work_count={data.work_count}"
    )
    try:
        # Find the registration request
        reg_request = (
            db.query(RegistrationRequest)
            .filter(RegistrationRequest.id == data.request_id)
            .first()
        )
        logger.info(f"Registration request found: {reg_request is not None}")

        if not reg_request:
            return RegistrationResponse(
                success=False, message="요청을 찾을 수 없습니다."
            )

        if reg_request.status != RequestStatus.PENDING:
            return RegistrationResponse(
                success=False,
                message=f"이미 처리된 요청입니다. (상태: {reg_request.status.value})",
            )

        # Check if username is still available
        existing_user = (
            db.query(User).filter(User.username == reg_request.username).first()
        )
        if existing_user:
            reg_request.status = RequestStatus.REJECTED
            reg_request.reviewed_at = datetime.now(timezone.utc)
            reg_request.rejection_reason = "아이디가 이미 사용 중입니다."
            db.commit()
            return RegistrationResponse(
                success=False, message="아이디가 이미 사용 중입니다."
            )

        # Create the user
        subscription_expires_at = datetime.now(timezone.utc) + timedelta(
            days=data.subscription_days
        )
        logger.info(
            f"Creating user: username={reg_request.username}, expires={subscription_expires_at}, work_count={data.work_count}"
        )

        new_user = User(
            username=reg_request.username,
            password_hash=reg_request.password_hash,
            subscription_expires_at=subscription_expires_at,
            is_active=True,
            work_count=data.work_count,  # -1 = 무제한
            work_used=0,
            trial_cycle_started_at=get_trial_cycle_start(),
            user_type=UserType.SUBSCRIBER if data.work_count == -1 else UserType.TRIAL,
            email=reg_request.email,
            phone=reg_request.contact,
            name=reg_request.name,
        )

        db.add(new_user)
        logger.info(f"User added to session, committing...")

        # Update registration request status
        reg_request.status = RequestStatus.APPROVED
        reg_request.reviewed_at = datetime.now(timezone.utc)

        db.commit()

        logger.info(
            f"Registration approved: user_id={new_user.id}, username={new_user.username}"
        )

        work_count_str = "무제한" if data.work_count == -1 else f"{data.work_count}회"
        return RegistrationResponse(
            success=True,
            message=f"회원가입이 승인되었습니다. (구독: {data.subscription_days}일, 작업: {work_count_str})",
            data={
                "user_id": new_user.id,
                "username": new_user.username,
                "subscription_expires_at": subscription_expires_at.isoformat(),
                "work_count": data.work_count,
            },
        )

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during approval: {e}", exc_info=True)
        # Security: Do not expose internal error details to users
        return RegistrationResponse(
            success=False, message="승인 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during approval: {e}", exc_info=True)
        # Security: Do not expose internal error details to users
        return RegistrationResponse(
            success=False, message="승인 처리 중 예기치 않은 오류가 발생했습니다."
        )


@router.post("/register/reject", response_model=RegistrationResponse)
@limiter.limit(ADMIN_ACTION_RATE_LIMIT)
async def reject_registration(
    request: Request,
    data: RejectRequest,
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key),
):
    """
    회원가입 요청 거부 (관리자용)
    Reject registration request (for admin)

    Requires X-Admin-API-Key header.
    """
    try:
        # Find the registration request
        reg_request = (
            db.query(RegistrationRequest)
            .filter(RegistrationRequest.id == data.request_id)
            .first()
        )

        if not reg_request:
            return RegistrationResponse(
                success=False, message="요청을 찾을 수 없습니다."
            )

        if reg_request.status != RequestStatus.PENDING:
            return RegistrationResponse(
                success=False,
                message=f"이미 처리된 요청입니다. (상태: {reg_request.status.value})",
            )

        # Update registration request status
        reg_request.status = RequestStatus.REJECTED
        reg_request.reviewed_at = datetime.now(timezone.utc)
        reg_request.rejection_reason = data.reason

        db.commit()

        logger.info(f"Registration rejected: request_id={reg_request.id}")

        return RegistrationResponse(
            success=True,
            message="회원가입 요청이 거부되었습니다.",
            data={"request_id": reg_request.id},
        )

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during rejection: {e}")
        return RegistrationResponse(
            success=False, message="거부 처리 중 오류가 발생했습니다."
        )


@router.get("/register/status/{username}", response_model=RegistrationResponse)
@limiter.limit("10/minute")
async def check_registration_status(
    request: Request,
    username: str,
    contact: str = Query(
        ..., min_length=4, description="연락처 뒤 4자리 (본인 확인용)"
    ),
    db: Session = Depends(get_db),
):
    """
    회원가입 요청 상태 확인
    Check registration request status

    본인 확인을 위해 연락처 뒤 4자리를 함께 입력해야 합니다.
    Requires last 4 digits of contact for verification.
    """
    # Validate username format
    if not username or len(username) < 4:
        return RegistrationResponse(
            success=False, message="해당 정보와 일치하는 가입 요청이 없습니다."
        )

    # Sanitize username
    username_clean = username.lower().strip()

    reg_request = (
        db.query(RegistrationRequest)
        .filter(RegistrationRequest.username == username_clean)
        .order_by(RegistrationRequest.created_at.desc())
        .first()
    )

    # Always return the same message format to prevent enumeration
    if not reg_request:
        return RegistrationResponse(
            success=False, message="해당 정보와 일치하는 가입 요청이 없습니다."
        )

    # Verify contact (last 4 digits) - with input validation
    if not contact or len(contact.strip()) < 4:
        return RegistrationResponse(
            success=False, message="해당 정보와 일치하는 가입 요청이 없습니다."
        )

    stored_contact = reg_request.contact.replace("-", "").replace(" ", "").strip()
    input_contact = contact.replace("-", "").replace(" ", "").strip()

    # Ensure input_contact has at least 4 characters for slicing
    if len(input_contact) < 4:
        return RegistrationResponse(
            success=False, message="해당 정보와 일치하는 가입 요청이 없습니다."
        )

    if not stored_contact.endswith(input_contact[-4:]):
        # Return same message to prevent enumeration
        return RegistrationResponse(
            success=False, message="해당 정보와 일치하는 가입 요청이 없습니다."
        )

    status_messages = {
        RequestStatus.PENDING: "승인 대기 중입니다.",
        RequestStatus.APPROVED: "승인이 완료되었습니다. 로그인해 주세요.",
        RequestStatus.REJECTED: f"요청이 거부되었습니다. 사유: {reg_request.rejection_reason or '미기재'}",
    }

    return RegistrationResponse(
        success=True,
        message=status_messages.get(reg_request.status, "알 수 없는 상태"),
        data={
            "status": reg_request.status.value,
            "created_at": reg_request.created_at.isoformat()
            if reg_request.created_at
            else None,
            "reviewed_at": reg_request.reviewed_at.isoformat()
            if reg_request.reviewed_at
            else None,
        },
    )

