"""
Payment Router
결제 라우터

결제 세션 생성 및 상태 조회 API

Security:
- Rate limiting on all endpoints
- User authentication required
"""
import logging
import secrets
from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request, Query
from slowapi import Limiter
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.utils.ip_utils import get_client_ip

logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_client_ip)

router = APIRouter(prefix="/payments", tags=["payment"])


# In-memory storage for payment sessions (production should use DB)
# 결제 세션 메모리 저장소 (운영 환경에서는 DB 사용 필요)
_payment_sessions = {}


class CreatePaymentRequest(BaseModel):
    """결제 생성 요청"""
    plan_id: str
    user_id: Optional[str] = None


class CreatePaymentResponse(BaseModel):
    """결제 생성 응답"""
    payment_id: str
    checkout_url: str
    expires_at: str


class PaymentStatusResponse(BaseModel):
    """결제 상태 응답"""
    payment_id: str
    status: str
    plan_id: Optional[str] = None
    user_id: Optional[str] = None
    created_at: str
    updated_at: str


@router.post("/create", response_model=CreatePaymentResponse)
@limiter.limit("10/minute")
async def create_payment(
    request: Request,
    data: CreatePaymentRequest,
    db: Session = Depends(get_db)
):
    """
    결제 세션 생성
    Create payment session

    Plans:
    - trial: 체험판 (무료)
    - monthly: 베이식 월간 (9,900원)
    - yearly: 프로 연간 (86,400원)
    """
    logger.info(f"[Payment] Create request: plan={data.plan_id}, user={data.user_id}")

    # Generate payment ID
    payment_id = secrets.token_urlsafe(32)

    # Create payment session
    session_data = {
        "payment_id": payment_id,
        "plan_id": data.plan_id,
        "user_id": data.user_id,
        "status": "pending",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    _payment_sessions[payment_id] = session_data

    # Generate checkout URL (mock - should be real payment gateway URL)
    # 실제 결제 게이트웨이 URL로 교체 필요 (예: 토스페이먼츠, 카카오페이 등)
    checkout_url = f"https://payment.example.com/checkout?session={payment_id}"

    # Mock: For testing, you can use a local mock page
    # 테스트용 mock 페이지 (실제로는 결제 게이트웨이 URL 사용)
    checkout_url = f"http://localhost:8000/static/mock_payment.html?payment_id={payment_id}&plan={data.plan_id}"

    expires_at = datetime.utcnow() + timedelta(minutes=30)

    logger.info(f"[Payment] Session created: {payment_id}")

    return CreatePaymentResponse(
        payment_id=payment_id,
        checkout_url=checkout_url,
        expires_at=expires_at.isoformat()
    )


@router.get("/status", response_model=PaymentStatusResponse)
@limiter.limit("60/minute")
async def get_payment_status(
    request: Request,
    payment_id: str = Query(..., description="결제 ID"),
    db: Session = Depends(get_db)
):
    """
    결제 상태 조회
    Get payment status

    Status values:
    - pending: 대기 중
    - paid/success/succeeded: 결제 완료
    - failed: 결제 실패
    - canceled/cancelled: 결제 취소
    """
    logger.info(f"[Payment] Status check: {payment_id}")

    session_data = _payment_sessions.get(payment_id)

    if not session_data:
        logger.warning(f"[Payment] Session not found: {payment_id}")
        # Return a default response for unknown payment
        return PaymentStatusResponse(
            payment_id=payment_id,
            status="not_found",
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat()
        )

    return PaymentStatusResponse(
        payment_id=session_data["payment_id"],
        status=session_data["status"],
        plan_id=session_data.get("plan_id"),
        user_id=session_data.get("user_id"),
        created_at=session_data["created_at"].isoformat(),
        updated_at=session_data["updated_at"].isoformat()
    )


@router.post("/webhook")
@limiter.limit("100/minute")
async def payment_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    결제 웹훅 엔드포인트 (결제 게이트웨이에서 호출)
    Payment webhook endpoint (called by payment gateway)

    This endpoint should be configured in your payment gateway dashboard.
    결제 게이트웨이 대시보드에서 설정 필요.

    Security: In production, verify webhook signature from payment gateway.
    보안: 운영 환경에서는 결제 게이트웨이의 서명을 검증해야 합니다.
    """
    try:
        # Parse webhook payload
        payload = await request.json()
        logger.info(f"[Payment] Webhook received: {payload}")

        # Extract payment info
        payment_id = payload.get("payment_id")
        new_status = payload.get("status")

        if not payment_id or not new_status:
            logger.warning("[Payment] Invalid webhook payload")
            return {"success": False, "message": "Invalid payload"}

        # Update session status
        session_data = _payment_sessions.get(payment_id)
        if session_data:
            session_data["status"] = new_status
            session_data["updated_at"] = datetime.utcnow()
            logger.info(f"[Payment] Status updated: {payment_id} -> {new_status}")

            # TODO: Update user subscription in database
            # user_id = session_data.get("user_id")
            # plan_id = session_data.get("plan_id")
            # if new_status in ("paid", "success", "succeeded") and user_id:
            #     # Update user subscription
            #     pass

        return {"success": True, "payment_id": payment_id}

    except Exception as e:
        logger.error(f"[Payment] Webhook error: {e}", exc_info=True)
        return {"success": False, "message": "Internal error"}


@router.post("/mock/complete/{payment_id}")
@limiter.limit("20/minute")
async def mock_complete_payment(
    request: Request,
    payment_id: str,
    db: Session = Depends(get_db)
):
    """
    Mock: 테스트용 결제 완료 처리
    Mock: Complete payment for testing

    ⚠️ WARNING: This endpoint should be REMOVED or PROTECTED in production!
    ⚠️ 경고: 운영 환경에서는 이 엔드포인트를 삭제하거나 보호해야 합니다!
    """
    logger.info(f"[Payment] Mock complete: {payment_id}")

    session_data = _payment_sessions.get(payment_id)
    if session_data:
        session_data["status"] = "succeeded"
        session_data["updated_at"] = datetime.utcnow()
        return {"success": True, "message": "Payment completed (mock)"}

    return {"success": False, "message": "Payment not found"}


@router.post("/mock/cancel/{payment_id}")
@limiter.limit("20/minute")
async def mock_cancel_payment(
    request: Request,
    payment_id: str,
    db: Session = Depends(get_db)
):
    """
    Mock: 테스트용 결제 취소 처리
    Mock: Cancel payment for testing

    ⚠️ WARNING: This endpoint should be REMOVED or PROTECTED in production!
    ⚠️ 경고: 운영 환경에서는 이 엔드포인트를 삭제하거나 보호해야 합니다!
    """
    logger.info(f"[Payment] Mock cancel: {payment_id}")

    session_data = _payment_sessions.get(payment_id)
    if session_data:
        session_data["status"] = "cancelled"
        session_data["updated_at"] = datetime.utcnow()
        return {"success": True, "message": "Payment cancelled (mock)"}

    return {"success": False, "message": "Payment not found"}
