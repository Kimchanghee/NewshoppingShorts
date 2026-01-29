"""
Registration Request Router
회원가입 요청 라우터

사용자 회원가입 요청 및 관리자 승인 API

Security:
- Admin endpoints require X-Admin-API-Key header
- Rate limiting on all endpoints
- Transaction rollback handling
- User enumeration prevention
"""
import logging
from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request, Query
from slowapi import Limiter
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from passlib.context import CryptContext

from app.database import get_db
from app.dependencies import verify_admin_api_key
from app.models.registration_request import RegistrationRequest, RequestStatus
from app.models.user import User
from app.schemas.registration import (
    RegistrationRequestCreate,
    RegistrationRequestResponse,
    RegistrationRequestList,
    ApproveRequest,
    RejectRequest,
    RegistrationResponse,
    RequestStatusEnum,
)

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_client_ip(request: Request) -> str:
    """Extract client IP from request"""
    if request.client:
        return request.client.host
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return "unknown"


# Rate limiter
limiter = Limiter(key_func=get_client_ip)

router = APIRouter(prefix="/user", tags=["registration"])


@router.post("/register/request", response_model=RegistrationResponse)
@limiter.limit("5/hour")
async def submit_registration_request(
    request: Request,
    data: RegistrationRequestCreate,
    db: Session = Depends(get_db)
):
    """
    회원가입 요청 제출
    Submit a registration request

    Rate limited to 5 requests per hour per IP to prevent abuse.
    IP당 시간당 5회로 제한하여 남용 방지.
    """
    logger.info(f"Registration request received: username={data.username}, name={data.name}")
    try:
        # Check if username already exists in users table
        existing_user = db.query(User).filter(User.username == data.username).first()
        if existing_user:
            return RegistrationResponse(
                success=False,
                message="이미 사용 중인 아이디입니다."
            )

        # Check if there's already a request with same username
        existing_request = db.query(RegistrationRequest).filter(
            RegistrationRequest.username == data.username
        ).first()
        if existing_request:
            # Get status as string for reliable comparison
            status_str = existing_request.status.value if hasattr(existing_request.status, 'value') else str(existing_request.status)
            logger.info(f"Found existing request: username={data.username}, status={status_str}")

            if status_str == "pending":
                return RegistrationResponse(
                    success=False,
                    message="이미 승인 대기 중인 요청이 있습니다."
                )
            elif status_str == "approved":
                return RegistrationResponse(
                    success=False,
                    message="이미 승인된 계정입니다. 로그인해 주세요."
                )
            elif status_str == "rejected":
                # 거부된 요청은 삭제하고 새로 생성 허용
                logger.info(f"Deleting rejected request for re-registration: {data.username}")
                db.delete(existing_request)
                db.flush()

        # Hash the password
        password_hash = pwd_context.hash(data.password)

        # Create registration request
        registration_request = RegistrationRequest(
            name=data.name,
            username=data.username,
            password_hash=password_hash,
            contact=data.contact,
            status=RequestStatus.PENDING
        )

        db.add(registration_request)
        db.commit()
        db.refresh(registration_request)

        logger.info(f"Registration request created: id={registration_request.id}")

        return RegistrationResponse(
            success=True,
            message="회원가입 요청이 접수되었습니다. 관리자 승인 후 로그인이 가능합니다.",
            data={"request_id": registration_request.id}
        )

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during registration request: {e}", exc_info=True)
        # 에러 메시지에 실제 에러 힌트 포함 (디버깅용)
        error_hint = str(e)[:200] if str(e) else "Unknown DB error"
        return RegistrationResponse(
            success=False,
            message=f"서버 오류가 발생했습니다. [{error_hint}]"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during registration request: {e}", exc_info=True)
        return RegistrationResponse(
            success=False,
            message=f"예기치 않은 오류가 발생했습니다. [{str(e)[:100]}]"
        )


@router.get("/register/requests", response_model=RegistrationRequestList)
@limiter.limit("100/hour")
async def list_registration_requests(
    request: Request,
    status: Optional[RequestStatusEnum] = Query(None, description="필터할 상태"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key)
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
    requests = query.order_by(RegistrationRequest.created_at.desc()).offset(offset).limit(page_size).all()

    return RegistrationRequestList(
        requests=[RegistrationRequestResponse.model_validate(r) for r in requests],
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("/register/approve", response_model=RegistrationResponse)
@limiter.limit("50/hour")
async def approve_registration(
    request: Request,
    data: ApproveRequest,
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key)
):
    """
    회원가입 요청 승인 (관리자용)
    Approve registration request (for admin)

    Requires X-Admin-API-Key header.
    """
    logger.info(f"Approve request received: request_id={data.request_id}, days={data.subscription_days}, work_count={data.work_count}")
    try:
        # Find the registration request
        reg_request = db.query(RegistrationRequest).filter(
            RegistrationRequest.id == data.request_id
        ).first()
        logger.info(f"Registration request found: {reg_request is not None}")

        if not reg_request:
            return RegistrationResponse(
                success=False,
                message="요청을 찾을 수 없습니다."
            )

        if reg_request.status != RequestStatus.PENDING:
            return RegistrationResponse(
                success=False,
                message=f"이미 처리된 요청입니다. (상태: {reg_request.status.value})"
            )

        # Check if username is still available
        existing_user = db.query(User).filter(User.username == reg_request.username).first()
        if existing_user:
            reg_request.status = RequestStatus.REJECTED
            reg_request.reviewed_at = datetime.utcnow()
            reg_request.rejection_reason = "아이디가 이미 사용 중입니다."
            db.commit()
            return RegistrationResponse(
                success=False,
                message="아이디가 이미 사용 중입니다."
            )

        # Create the user
        subscription_expires_at = datetime.utcnow() + timedelta(days=data.subscription_days)
        logger.info(f"Creating user: username={reg_request.username}, expires={subscription_expires_at}, work_count={data.work_count}")

        new_user = User(
            username=reg_request.username,
            password_hash=reg_request.password_hash,
            subscription_expires_at=subscription_expires_at,
            is_active=True,
            work_count=data.work_count,  # -1 = 무제한
            work_used=0
        )

        db.add(new_user)
        logger.info(f"User added to session, committing...")

        # Update registration request status
        reg_request.status = RequestStatus.APPROVED
        reg_request.reviewed_at = datetime.utcnow()

        db.commit()

        logger.info(f"Registration approved: user_id={new_user.id}, username={new_user.username}")

        work_count_str = "무제한" if data.work_count == -1 else f"{data.work_count}회"
        return RegistrationResponse(
            success=True,
            message=f"회원가입이 승인되었습니다. (구독: {data.subscription_days}일, 작업: {work_count_str})",
            data={
                "user_id": new_user.id,
                "username": new_user.username,
                "subscription_expires_at": subscription_expires_at.isoformat(),
                "work_count": data.work_count
            }
        )

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during approval: {e}", exc_info=True)
        return RegistrationResponse(
            success=False,
            message=f"승인 처리 중 오류가 발생했습니다: {str(e)[:100]}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during approval: {e}", exc_info=True)
        return RegistrationResponse(
            success=False,
            message=f"승인 처리 중 예기치 않은 오류: {str(e)[:100]}"
        )


@router.post("/register/reject", response_model=RegistrationResponse)
@limiter.limit("50/hour")
async def reject_registration(
    request: Request,
    data: RejectRequest,
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key)
):
    """
    회원가입 요청 거부 (관리자용)
    Reject registration request (for admin)

    Requires X-Admin-API-Key header.
    """
    try:
        # Find the registration request
        reg_request = db.query(RegistrationRequest).filter(
            RegistrationRequest.id == data.request_id
        ).first()

        if not reg_request:
            return RegistrationResponse(
                success=False,
                message="요청을 찾을 수 없습니다."
            )

        if reg_request.status != RequestStatus.PENDING:
            return RegistrationResponse(
                success=False,
                message=f"이미 처리된 요청입니다. (상태: {reg_request.status.value})"
            )

        # Update registration request status
        reg_request.status = RequestStatus.REJECTED
        reg_request.reviewed_at = datetime.utcnow()
        reg_request.rejection_reason = data.reason

        db.commit()

        logger.info(f"Registration rejected: request_id={reg_request.id}")

        return RegistrationResponse(
            success=True,
            message="회원가입 요청이 거부되었습니다.",
            data={"request_id": reg_request.id}
        )

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during rejection: {e}")
        return RegistrationResponse(
            success=False,
            message="거부 처리 중 오류가 발생했습니다."
        )


@router.get("/register/status/{username}", response_model=RegistrationResponse)
@limiter.limit("10/minute")
async def check_registration_status(
    request: Request,
    username: str,
    contact: str = Query(..., min_length=4, description="연락처 뒤 4자리 (본인 확인용)"),
    db: Session = Depends(get_db)
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
            success=False,
            message="해당 정보와 일치하는 가입 요청이 없습니다."
        )

    # Sanitize username
    username_clean = username.lower().strip()

    reg_request = db.query(RegistrationRequest).filter(
        RegistrationRequest.username == username_clean
    ).order_by(RegistrationRequest.created_at.desc()).first()

    # Always return the same message format to prevent enumeration
    if not reg_request:
        return RegistrationResponse(
            success=False,
            message="해당 정보와 일치하는 가입 요청이 없습니다."
        )

    # Verify contact (last 4 digits)
    stored_contact = reg_request.contact.replace("-", "").replace(" ", "")
    input_contact = contact.replace("-", "").replace(" ", "")

    if not stored_contact.endswith(input_contact[-4:]):
        # Return same message to prevent enumeration
        return RegistrationResponse(
            success=False,
            message="해당 정보와 일치하는 가입 요청이 없습니다."
        )

    status_messages = {
        RequestStatus.PENDING: "승인 대기 중입니다.",
        RequestStatus.APPROVED: "승인이 완료되었습니다. 로그인해 주세요.",
        RequestStatus.REJECTED: f"요청이 거부되었습니다. 사유: {reg_request.rejection_reason or '미기재'}"
    }

    return RegistrationResponse(
        success=True,
        message=status_messages.get(reg_request.status, "알 수 없는 상태"),
        data={
            "status": reg_request.status.value,
            "created_at": reg_request.created_at.isoformat() if reg_request.created_at else None,
            "reviewed_at": reg_request.reviewed_at.isoformat() if reg_request.reviewed_at else None
        }
    )
