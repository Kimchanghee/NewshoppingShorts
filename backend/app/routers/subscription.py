"""
Subscription Request Router
구독 신청 라우터

체험판 사용자의 구독 신청 및 관리자 승인 API

Security:
- User endpoints require valid JWT token
- Admin endpoints require X-Admin-API-Key header
- Rate limiting on all endpoints
"""
import logging
from typing import Optional
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Query, Header
from slowapi import Limiter
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db
from app.dependencies import verify_admin_api_key
from app.models.subscription_request import SubscriptionRequest, SubscriptionRequestStatus
from app.models.user import User, UserType
from app.schemas.subscription import (
    SubscriptionRequestCreate,
    SubscriptionRequestResponse,
    SubscriptionRequestList,
    ApproveSubscriptionRequest,
    RejectSubscriptionRequest,
    SubscriptionResponse,
    SubscriptionStatusResponse,
    SubscriptionRequestStatusEnum,
)
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)


# Use the secure get_client_ip from ip_utils for consistent IP extraction
# 보안: IP 스푸핑 방지를 위해 통일된 get_client_ip 사용
from app.utils.ip_utils import get_client_ip


# Rate limiter
limiter = Limiter(key_func=get_client_ip)

router = APIRouter(prefix="/user/subscription", tags=["subscription"])


@router.post("/request", response_model=SubscriptionResponse)
@limiter.limit("5/hour")
async def submit_subscription_request(
    request: Request,
    data: SubscriptionRequestCreate,
    user_id: int = Header(..., alias="X-User-ID", description="User ID"),
    token: str = Header(..., alias="Authorization", description="Bearer token"),
    db: Session = Depends(get_db)
):
    """
    구독 신청 제출 (체험판 사용자용)
    Submit subscription request (for trial users)

    Requires valid JWT token via Authorization header.
    """
    # Remove "Bearer " prefix if present
    if token.startswith("Bearer "):
        token = token[7:]

    logger.info(f"Subscription request received: user_id={user_id}")

    try:
        # Verify user and token
        service = AuthService(db)
        session_result = await service.check_session(
            user_id=str(user_id), token=token, ip_address=get_client_ip(request)
        )
        if not session_result.get("status"):
            return SubscriptionResponse(
                success=False,
                message="유효하지 않은 세션입니다. 다시 로그인해 주세요."
            )

        # Check if user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return SubscriptionResponse(
                success=False,
                message="사용자를 찾을 수 없습니다."
            )

        # Check if user is already a subscriber
        if user.work_count == -1:
            return SubscriptionResponse(
                success=False,
                message="이미 무제한 구독 중입니다."
            )

        # Check if there's already a pending request
        existing_request = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.user_id == user_id,
            SubscriptionRequest.status == SubscriptionRequestStatus.PENDING
        ).first()
        if existing_request:
            return SubscriptionResponse(
                success=False,
                message="이미 대기 중인 구독 신청이 있습니다.",
                data={"request_id": existing_request.id}
            )

        # Create subscription request
        subscription_request = SubscriptionRequest(
            user_id=user_id,
            message=data.message,
            status=SubscriptionRequestStatus.PENDING
        )

        db.add(subscription_request)
        db.commit()
        db.refresh(subscription_request)

        logger.info(f"Subscription request created: id={subscription_request.id}, user_id={user_id}")

        return SubscriptionResponse(
            success=True,
            message="구독 신청이 접수되었습니다. 관리자 승인 후 적용됩니다.",
            data={"request_id": subscription_request.id}
        )

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during subscription request: {e}", exc_info=True)
        return SubscriptionResponse(
            success=False,
            message="서버 오류가 발생했습니다."
        )


@router.get("/my-status", response_model=SubscriptionStatusResponse)
@limiter.limit("60/minute")
async def get_my_subscription_status(
    request: Request,
    user_id: int = Header(..., alias="X-User-ID", description="User ID"),
    token: str = Header(..., alias="Authorization", description="Bearer token"),
    db: Session = Depends(get_db)
):
    """
    내 구독 상태 조회
    Get my subscription status
    """
    # Remove "Bearer " prefix if present
    if token.startswith("Bearer "):
        token = token[7:]

    try:
        # Verify user and token
        service = AuthService(db)
        session_result = await service.check_session(
            user_id=str(user_id), token=token, ip_address=get_client_ip(request)
        )
        if not session_result.get("status"):
            return SubscriptionStatusResponse(
                success=False,
                is_trial=True,
                work_count=0,
                work_used=0,
                remaining=0,
                can_work=False
            )

        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return SubscriptionStatusResponse(
                success=False,
                is_trial=True,
                work_count=0,
                work_used=0,
                remaining=0,
                can_work=False
            )

        # Calculate remaining
        is_unlimited = user.work_count == -1
        remaining = -1 if is_unlimited else max(0, user.work_count - user.work_used)
        can_work = is_unlimited or remaining > 0

        # Check for pending subscription request
        pending_request = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.user_id == user_id,
            SubscriptionRequest.status == SubscriptionRequestStatus.PENDING
        ).first()

        # Determine if trial user
        user_type_value = user.user_type.value if hasattr(user.user_type, 'value') else str(user.user_type)
        is_trial = user_type_value == "trial" or (user.work_count > 0 and user.work_count != -1)

        return SubscriptionStatusResponse(
            success=True,
            is_trial=is_trial,
            work_count=user.work_count,
            work_used=user.work_used,
            remaining=remaining,
            can_work=can_work,
            subscription_expires_at=user.subscription_expires_at.isoformat() if user.subscription_expires_at else None,
            has_pending_request=pending_request is not None
        )

    except Exception as e:
        logger.error(f"Error getting subscription status: {e}", exc_info=True)
        return SubscriptionStatusResponse(
            success=False,
            is_trial=True,
            work_count=0,
            work_used=0,
            remaining=0,
            can_work=False
        )


@router.get("/requests", response_model=SubscriptionRequestList)
@limiter.limit("100/hour")
async def list_subscription_requests(
    request: Request,
    status: Optional[SubscriptionRequestStatusEnum] = Query(None, description="필터할 상태"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key)
):
    """
    구독 신청 목록 조회 (관리자용)
    List subscription requests (for admin)

    Requires X-Admin-API-Key header.
    """
    query = db.query(SubscriptionRequest)

    # Filter by status if provided
    if status:
        query = query.filter(SubscriptionRequest.status == status.value)

    # Get total count
    total = query.count()

    # Pagination with user info
    offset = (page - 1) * page_size
    # Join with User to get username efficiently
    results = (
        query.join(User, SubscriptionRequest.user_id == User.id)
        .order_by(SubscriptionRequest.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .with_entities(SubscriptionRequest, User.username)
        .all()
    )

    # Build response
    response_list = []
    for req, username in results:
        response_list.append(SubscriptionRequestResponse(
            id=req.id,
            user_id=req.user_id,
            username=username if username else "Unknown",
            status=SubscriptionRequestStatusEnum(req.status.value),
            requested_work_count=req.requested_work_count,
            message=req.message,
            admin_response=req.admin_response,
            created_at=req.created_at,
            reviewed_at=req.reviewed_at
        ))

    return SubscriptionRequestList(
        requests=response_list,
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("/approve", response_model=SubscriptionResponse)
@limiter.limit("50/hour")
async def approve_subscription(
    request: Request,
    data: ApproveSubscriptionRequest,
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key)
):
    """
    구독 신청 승인 (관리자용)
    Approve subscription request (for admin)

    Requires X-Admin-API-Key header.
    """
    logger.info(f"Approve subscription request: request_id={data.request_id}, work_count={data.work_count}")

    try:
        # Find the subscription request
        sub_request = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.id == data.request_id
        ).first()

        if not sub_request:
            return SubscriptionResponse(
                success=False,
                message="구독 신청을 찾을 수 없습니다."
            )

        if sub_request.status != SubscriptionRequestStatus.PENDING:
            return SubscriptionResponse(
                success=False,
                message=f"이미 처리된 신청입니다. (상태: {sub_request.status.value})"
            )

        # Find the user
        user = db.query(User).filter(User.id == sub_request.user_id).first()
        if not user:
            return SubscriptionResponse(
                success=False,
                message="사용자를 찾을 수 없습니다."
            )

        # Update user subscription
        user.work_count = data.work_count
        user.work_used = 0  # Reset work used
        user.subscription_expires_at = datetime.now(timezone.utc) + timedelta(days=data.subscription_days)
        user.user_type = UserType.SUBSCRIBER

        # Update subscription request
        sub_request.status = SubscriptionRequestStatus.APPROVED
        sub_request.reviewed_at = datetime.now(timezone.utc)
        sub_request.admin_response = data.admin_response

        db.commit()

        logger.info(f"Subscription approved: user_id={user.id}, work_count={data.work_count}")

        work_count_str = "무제한" if data.work_count == -1 else f"{data.work_count}회"
        return SubscriptionResponse(
            success=True,
            message=f"구독이 승인되었습니다. (작업: {work_count_str}, 기간: {data.subscription_days}일)",
            data={
                "user_id": user.id,
                "username": user.username,
                "work_count": data.work_count,
                "subscription_days": data.subscription_days
            }
        )

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during approval: {e}", exc_info=True)
        return SubscriptionResponse(
            success=False,
            message="승인 처리 중 오류가 발생했습니다."
        )


@router.post("/reject", response_model=SubscriptionResponse)
@limiter.limit("50/hour")
async def reject_subscription(
    request: Request,
    data: RejectSubscriptionRequest,
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key)
):
    """
    구독 신청 거절 (관리자용)
    Reject subscription request (for admin)

    Requires X-Admin-API-Key header.
    """
    try:
        # Find the subscription request
        sub_request = db.query(SubscriptionRequest).filter(
            SubscriptionRequest.id == data.request_id
        ).first()

        if not sub_request:
            return SubscriptionResponse(
                success=False,
                message="구독 신청을 찾을 수 없습니다."
            )

        if sub_request.status != SubscriptionRequestStatus.PENDING:
            return SubscriptionResponse(
                success=False,
                message=f"이미 처리된 신청입니다. (상태: {sub_request.status.value})"
            )

        # Update subscription request
        sub_request.status = SubscriptionRequestStatus.REJECTED
        sub_request.reviewed_at = datetime.now(timezone.utc)
        sub_request.admin_response = data.admin_response

        db.commit()

        logger.info(f"Subscription rejected: request_id={sub_request.id}")

        return SubscriptionResponse(
            success=True,
            message="구독 신청이 거절되었습니다.",
            data={"request_id": sub_request.id}
        )

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during rejection: {e}", exc_info=True)
        return SubscriptionResponse(
            success=False,
            message="거절 처리 중 오류가 발생했습니다."
        )


@router.get("/stats")
@limiter.limit("100/hour")
async def get_subscription_stats(
    request: Request,
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key)
):
    """
    구독 신청 통계 (관리자용)
    Get subscription request statistics (for admin)
    """
    pending_count = db.query(SubscriptionRequest).filter(
        SubscriptionRequest.status == SubscriptionRequestStatus.PENDING
    ).count()

    approved_count = db.query(SubscriptionRequest).filter(
        SubscriptionRequest.status == SubscriptionRequestStatus.APPROVED
    ).count()

    rejected_count = db.query(SubscriptionRequest).filter(
        SubscriptionRequest.status == SubscriptionRequestStatus.REJECTED
    ).count()

    return {
        "pending": pending_count,
        "approved": approved_count,
        "rejected": rejected_count,
        "total": pending_count + approved_count + rejected_count
    }
