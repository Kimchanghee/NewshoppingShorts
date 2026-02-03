# -*- coding: utf-8 -*-
"""
Payment Router
결제 라우터

결제 세션 생성 및 상태 조회 API

Security:
- Rate limiting on all endpoints
- User authentication required for mock endpoints
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
from app.dependencies import verify_admin_api_key
from app.models.payment_session import PaymentSession, PaymentStatus

logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_client_ip)

router = APIRouter(prefix="/payments", tags=["payment"])

# Plan pricing (KRW)
PLAN_PRICES = {
    "trial": 0,
    "monthly": 9900,
    "yearly": 86400,
}


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


def _get_payment_session(db: Session, payment_id: str) -> Optional[PaymentSession]:
    """Retrieve payment session from database."""
    return db.query(PaymentSession).filter(PaymentSession.payment_id == payment_id).first()


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

    # Generate unique payment ID
    payment_id = secrets.token_urlsafe(32)

    # Calculate expiration (30 minutes)
    expires_at = datetime.utcnow() + timedelta(minutes=30)

    # Get plan price
    amount = PLAN_PRICES.get(data.plan_id, 0)

    # Create payment session in database
    session = PaymentSession(
        payment_id=payment_id,
        plan_id=data.plan_id,
        user_id=data.user_id,
        status=PaymentStatus.PENDING,
        amount=amount,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Generate checkout URL (mock - should be real payment gateway URL)
    # 실제 결제 게이트웨이 URL로 교체 필요 (예: 토스페이먼츠, 카카오페이 등)
    checkout_url = f"http://localhost:8000/static/mock_payment.html?payment_id={payment_id}&plan={data.plan_id}"

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
    - succeeded: 결제 완료
    - failed: 결제 실패
    - cancelled: 결제 취소
    - expired: 만료됨
    """
    logger.info(f"[Payment] Status check: {payment_id}")

    session = _get_payment_session(db, payment_id)

    if not session:
        logger.warning(f"[Payment] Session not found: {payment_id}")
        # Return a default response for unknown payment
        return PaymentStatusResponse(
            payment_id=payment_id,
            status="not_found",
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat()
        )

    # Check if session has expired
    if session.status == PaymentStatus.PENDING and session.expires_at:
        if datetime.utcnow() > session.expires_at:
            session.status = PaymentStatus.EXPIRED
            db.commit()

    return PaymentStatusResponse(
        payment_id=session.payment_id,
        status=session.status.value,
        plan_id=session.plan_id,
        user_id=session.user_id,
        created_at=session.created_at.isoformat() if session.created_at else datetime.utcnow().isoformat(),
        updated_at=session.updated_at.isoformat() if session.updated_at else datetime.utcnow().isoformat()
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

        # Map status string to enum
        status_map = {
            "paid": PaymentStatus.SUCCEEDED,
            "success": PaymentStatus.SUCCEEDED,
            "succeeded": PaymentStatus.SUCCEEDED,
            "failed": PaymentStatus.FAILED,
            "canceled": PaymentStatus.CANCELLED,
            "cancelled": PaymentStatus.CANCELLED,
        }
        mapped_status = status_map.get(new_status.lower())
        if not mapped_status:
            logger.warning(f"[Payment] Unknown status: {new_status}")
            return {"success": False, "message": f"Unknown status: {new_status}"}

        # Update session status in database
        session = _get_payment_session(db, payment_id)
        if session:
            session.status = mapped_status
            # Store gateway reference if provided
            if payload.get("gateway_reference"):
                session.gateway_reference = payload.get("gateway_reference")
            db.commit()
            logger.info(f"[Payment] Status updated: {payment_id} -> {mapped_status.value}")

            # TODO: Update user subscription in database
            # if mapped_status == PaymentStatus.SUCCEEDED and session.user_id:
            #     # Update user subscription
            #     pass

            return {"success": True, "payment_id": payment_id}
        else:
            logger.warning(f"[Payment] Session not found for webhook: {payment_id}")
            return {"success": False, "message": "Payment not found"}

    except Exception as e:
        logger.error(f"[Payment] Webhook error: {e}", exc_info=True)
        return {"success": False, "message": "Internal error"}


@router.post("/mock/complete/{payment_id}")
@limiter.limit("20/minute")
async def mock_complete_payment(
    request: Request,
    payment_id: str,
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key)
):
    """
    Mock: 테스트용 결제 완료 처리 (Admin 전용)
    Mock: Complete payment for testing (Admin only)

    Requires X-Admin-API-Key header for security.
    """
    logger.info(f"[Payment] Mock complete (admin): {payment_id}")

    session = _get_payment_session(db, payment_id)
    if session:
        session.status = PaymentStatus.SUCCEEDED
        db.commit()
        return {"success": True, "message": "Payment completed (mock)"}

    return {"success": False, "message": "Payment not found"}


@router.post("/mock/cancel/{payment_id}")
@limiter.limit("20/minute")
async def mock_cancel_payment(
    request: Request,
    payment_id: str,
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key)
):
    """
    Mock: 테스트용 결제 취소 처리 (Admin 전용)
    Mock: Cancel payment for testing (Admin only)

    Requires X-Admin-API-Key header for security.
    """
    logger.info(f"[Payment] Mock cancel (admin): {payment_id}")

    session = _get_payment_session(db, payment_id)
    if session:
        session.status = PaymentStatus.CANCELLED
        db.commit()
        return {"success": True, "message": "Payment cancelled (mock)"}

    return {"success": False, "message": "Payment not found"}
