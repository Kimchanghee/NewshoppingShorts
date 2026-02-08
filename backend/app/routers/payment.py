# -*- coding: utf-8 -*-
"""
Payment Router
결제 라우터

결제 세션 생성 및 상태 조회 API + PayApp 가상계좌 연동

Security:
- Rate limiting on all endpoints
- User authentication required for mock endpoints
- PayApp webhook validates linkkey/linkval
"""
import logging
import os
import secrets
from typing import Optional
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs

import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException, Request, Query, Header
from fastapi.responses import PlainTextResponse
from slowapi import Limiter
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.utils.ip_utils import get_client_ip
from app.utils.subscription_utils import calculate_subscription_expiry, _ensure_aware
from app.utils.jwt_handler import decode_access_token
from app.dependencies import verify_admin_api_key
from app.models.payment_session import PaymentSession, PaymentStatus, PaymentStatusHistory
from app.models.session import SessionModel
from app.models.user import User, UserType

logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_client_ip)

router = APIRouter(prefix="/payments", tags=["payment"])

# Plan pricing (KRW)
PLAN_PRICES = {
    "trial": 0,
    "pro_1month": 190000,
    "pro_6months": 969000,
    "pro_12months": 1596000,
}

# Plan durations (days)
PLAN_DAYS = {
    "pro_1month": 30,
    "pro_6months": 180,
    "pro_12months": 365,
}

# PayApp Configuration (from environment)
# IMPORTANT: Never ship real PayApp credentials in the repository defaults.
# Configure these via environment variables / secrets manager in production.
PAYAPP_USERID = os.getenv("PAYAPP_USERID", "")
PAYAPP_LINKKEY = os.getenv("PAYAPP_LINKKEY", "")
PAYAPP_LINKVAL = os.getenv("PAYAPP_LINKVAL", "")
_PAYAPP_API_URL_RAW = os.getenv("PAYAPP_API_URL", "https://api.payapp.kr/oapi/apiLoad.html")
# SSRF prevention: only allow known PayApp domain
from urllib.parse import urlparse as _urlparse
_parsed = _urlparse(_PAYAPP_API_URL_RAW)
if _parsed.hostname not in ("api.payapp.kr",):
    logger.error(f"[SSRF] Blocked untrusted PAYAPP_API_URL domain: {_parsed.hostname}")
    PAYAPP_API_URL = "https://api.payapp.kr/oapi/apiLoad.html"
else:
    PAYAPP_API_URL = _PAYAPP_API_URL_RAW


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


def _record_status_change(db: Session, payment_id: str, prev: str | None, new: str, source: str):
    """결제 상태 변경 이력 기록"""
    try:
        history = PaymentStatusHistory(
            payment_id=payment_id,
            previous_status=prev,
            new_status=new,
            source=source,
        )
        db.add(history)
    except Exception as e:
        logger.warning(f"[Payment] Failed to record status history: {e}")


def _get_payment_session(db: Session, payment_id: str) -> Optional[PaymentSession]:
    """Retrieve payment session from database."""
    return db.query(PaymentSession).filter(PaymentSession.payment_id == payment_id).first()


def _validate_authenticated_user(db: Session, user_id: str, authorization: str) -> None:
    """Validate Authorization token/session and ensure it belongs to user_id."""
    token = authorization[7:] if authorization.startswith("Bearer ") else authorization
    if not token:
        raise HTTPException(status_code=401, detail="Missing auth token")

    try:
        payload = decode_access_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail="Invalid auth token") from e

    token_user_id = payload.get("sub")
    jti = payload.get("jti")
    if str(token_user_id) != str(user_id):
        raise HTTPException(status_code=403, detail="Token/user mismatch")
    if not jti:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    active_session = (
        db.query(SessionModel)
        .filter(
            SessionModel.token_jti == jti,
            SessionModel.is_active == True,
            SessionModel.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )
    if not active_session:
        raise HTTPException(status_code=401, detail="Session expired or revoked")


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
    - pro_1month: 프로 1개월
    - pro_6months: 프로 6개월
    - pro_12months: 프로 12개월
    """
    logger.info(f"[Payment] Create request: plan={data.plan_id}, user={data.user_id}")

    # Generate unique payment ID
    payment_id = secrets.token_urlsafe(32)

    # Calculate expiration (30 minutes)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

    # Get plan price and validate
    amount = PLAN_PRICES.get(data.plan_id)
    if amount is None:
        raise HTTPException(status_code=400, detail=f"Invalid plan_id: {data.plan_id}")

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
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat()
        )

    # Check if session has expired (use timezone-aware comparison)
    if session.status == PaymentStatus.PENDING and session.expires_at:
        expires_at_aware = _ensure_aware(session.expires_at)
        if datetime.now(timezone.utc) > expires_at_aware:
            session.status = PaymentStatus.EXPIRED
            db.commit()

    return PaymentStatusResponse(
        payment_id=session.payment_id,
        status=session.status.value,
        plan_id=session.plan_id,
        user_id=session.user_id,
        created_at=session.created_at.isoformat() if session.created_at else datetime.now(timezone.utc).isoformat(),
        updated_at=session.updated_at.isoformat() if session.updated_at else datetime.now(timezone.utc).isoformat()
    )


@router.post("/webhook")
@limiter.limit("100/minute")
async def payment_webhook(
    request: Request,
    db: Session = Depends(get_db),
    _admin: bool = Depends(verify_admin_api_key)
):
    """
    결제 웹훅 엔드포인트 (Admin 인증 필요)
    Payment webhook endpoint (requires Admin API key)

    Security: Admin API key required to prevent unauthorized subscription activation.
    보안: 무단 구독 활성화를 방지하기 위해 Admin API 키가 필요합니다.
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
            # Idempotency check - if already completed, skip
            if session.status == PaymentStatus.SUCCEEDED:
                logger.info(f"[Payment] Payment already completed (idempotent): {payment_id}")
                return {"success": True, "payment_id": payment_id, "note": "already_completed"}

            prev = session.status.value if session.status else None
            session.status = mapped_status
            # Store gateway reference if provided
            if payload.get("gateway_reference"):
                session.gateway_reference = payload.get("gateway_reference")
            _record_status_change(db, payment_id, prev, mapped_status.value, "webhook")
            db.commit()
            logger.info(f"[Payment] Status updated: {payment_id} -> {mapped_status.value}")

            # 결제 완료 시 구독 활성화
            if mapped_status == PaymentStatus.SUCCEEDED and session.user_id:
                _activate_subscription(db, session.user_id, session.plan_id)

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

        # Activate subscription after marking payment complete
        if session.user_id:
            _activate_subscription(db, session.user_id, session.plan_id)

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


# ─────────────────────────────────────────────
# PayApp 가상계좌 결제 연동
# ─────────────────────────────────────────────

class PayAppCreateRequest(BaseModel):
    """PayApp 결제 생성 요청"""
    user_id: str
    phone: str  # 수신자 전화번호 (PayApp 필수)
    plan_id: str = "pro_1month"  # Added: which plan to purchase


class PayAppCreateResponse(BaseModel):
    """PayApp 결제 생성 응답"""
    success: bool
    payment_id: str = ""
    payurl: str = ""
    mul_no: str = ""
    message: str = ""


def _activate_subscription(db: Session, user_id: str, plan_id: str) -> None:
    """결제 완료 후 사용자 구독 활성화"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"[Payment] User not found for subscription activation: {user_id}")
            return

        # Fail closed: unknown plan_id must never activate subscription.
        plan_days = PLAN_DAYS.get(plan_id)
        if plan_days is None:
            logger.error(f"[Payment] Unknown plan_id for activation: user={user_id}, plan={plan_id}")
            return

        # Calculate new expiry date, extending from current expiry if it exists
        current_expiry = user.subscription_expires_at
        new_expiry = calculate_subscription_expiry(plan_days, current_expiry)

        user.user_type = UserType.SUBSCRIBER
        user.subscription_expires_at = new_expiry
        user.work_count = -1  # 무제한
        user.work_used = 0
        db.commit()
        logger.info(
            f"[Payment] Subscription activated: user={user_id}, plan={plan_id}, "
            f"days={plan_days}, expires_at={user.subscription_expires_at}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"[Payment] Failed to activate subscription: {e}", exc_info=True)


@router.post("/payapp/create", response_model=PayAppCreateResponse)
@limiter.limit("10/minute")
async def create_payapp_payment(
    request: Request,
    data: PayAppCreateRequest,
    x_user_id: str = Header(..., alias="X-User-ID"),
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db)
):
    """
    PayApp 가상계좌 결제 요청 생성
    Creates a PayApp virtual account payment request

    Security:
    - Requires Authorization + X-User-ID headers
    - Header user must match body user_id
    """
    _validate_authenticated_user(db, str(x_user_id), authorization)
    if str(data.user_id) != str(x_user_id):
        logger.warning(
            f"[PayApp] Body/header user mismatch: body_user={data.user_id}, header_user={x_user_id}"
        )
        raise HTTPException(status_code=403, detail="User mismatch")

    user_id = str(x_user_id)
    masked_phone = data.phone[:3] + "****" + data.phone[-4:] if len(data.phone) > 7 else "***"
    logger.info(f"[PayApp] Create request: user={user_id}, phone={masked_phone}")

    if not PAYAPP_USERID:
        logger.error("[PayApp] PAYAPP_USERID not configured")
        return PayAppCreateResponse(
            success=False, message="결제 설정이 완료되지 않았습니다."
        )

    # Create local payment session first
    local_payment_id = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

    # Determine feedbackurl (backend webhook URL)
    # Prefer explicit env var for production, but fall back to request base URL for local/dev.
    base_url = os.getenv("PAYMENT_API_BASE_URL", "").rstrip("/")
    if not base_url:
        base_url = str(request.base_url).rstrip("/")
    feedback_url = f"{base_url}/payments/payapp/webhook"

    # Get plan info
    plan_price = PLAN_PRICES.get(data.plan_id)
    if plan_price is None or plan_price <= 0:
        return PayAppCreateResponse(success=False, message=f"유효하지 않은 플랜입니다: {data.plan_id}")

    plan_names = {
        "pro_1month": "프로 구독 (1개월)",
        "pro_6months": "프로 구독 (6개월)",
        "pro_12months": "프로 구독 (12개월)",
    }
    good_name = f"쇼핑숏폼메이커 {plan_names.get(data.plan_id, '프로 구독')}"

    # Call PayApp API with dynamic plan_id
    payapp_params = {
        "cmd": "payrequest",
        "userid": PAYAPP_USERID,
        "goodname": good_name,
        "price": str(plan_price),
        "recvphone": data.phone.replace("-", ""),
        "openpaytype": "vbank",
        "smsuse": "n",
        "feedbackurl": feedback_url,
        "var1": local_payment_id,
        "var2": user_id,
        "checkretry": "y",
    }

    try:
        resp = http_requests.post(PAYAPP_API_URL, data=payapp_params, timeout=30)
        result = {k: v[0] for k, v in parse_qs(resp.text).items()}

        if result.get("state") == "1":
            mul_no = result.get("mul_no", "")
            payurl = result.get("payurl", "")

            # Save payment session to DB with dynamic plan_id
            session = PaymentSession(
                payment_id=local_payment_id,
                plan_id=data.plan_id,
                user_id=user_id,
                status=PaymentStatus.PENDING,
                amount=plan_price,
                gateway_reference=mul_no,
                expires_at=expires_at,
            )
            db.add(session)
            db.commit()

            logger.info(f"[PayApp] Payment created: mul_no={mul_no}, payurl={payurl}")
            return PayAppCreateResponse(
                success=True,
                payment_id=local_payment_id,
                payurl=payurl,
                mul_no=mul_no,
            )
        else:
            error_msg = result.get("errorMessage", "알 수 없는 오류")
            logger.warning(f"[PayApp] API error: {error_msg}")
            return PayAppCreateResponse(success=False, message=f"결제 요청 실패: {error_msg}")

    except http_requests.exceptions.Timeout:
        logger.error("[PayApp] API request timed out")
        return PayAppCreateResponse(success=False, message="결제 서버 연결 시간 초과")
    except Exception as e:
        logger.error(f"[PayApp] API request failed: {e}", exc_info=True)
        return PayAppCreateResponse(success=False, message="결제 요청 처리 중 오류가 발생했습니다.")


@router.post("/payapp/webhook")
@limiter.limit("100/minute")
async def payapp_webhook(request: Request, db: Session = Depends(get_db)):
    """
    PayApp 웹훅 (feedbackurl)
    PayApp에서 결제 상태 변경 시 호출됨

    Security: linkkey/linkval 검증으로 정상 호출 확인
    Response: "SUCCESS" (plain text) - PayApp 요구사항
    """
    try:
        form_data = await request.form()
        pay_state = form_data.get("pay_state", "")
        mul_no = form_data.get("mul_no", "")
        price = form_data.get("price", "")
        recv_linkkey = form_data.get("linkkey", "")
        recv_linkval = form_data.get("linkval", "")
        local_payment_id = form_data.get("var1", "")
        user_id = form_data.get("var2", "")

        logger.info(
            f"[PayApp Webhook] pay_state={pay_state}, mul_no={mul_no}, "
            f"price={price}, var1={local_payment_id}, var2={user_id}"
        )

        # 인증 검증
        if not PAYAPP_LINKKEY or not PAYAPP_LINKVAL:
            logger.error("[PayApp Webhook] PAYAPP_LINKKEY/LINKVAL not configured")
            return PlainTextResponse("FAIL")

        if not secrets.compare_digest(str(recv_linkkey), PAYAPP_LINKKEY):
            logger.warning("[PayApp Webhook] Invalid linkkey")
            return PlainTextResponse("FAIL")

        if not secrets.compare_digest(str(recv_linkval), PAYAPP_LINKVAL):
            logger.warning("[PayApp Webhook] Invalid linkval")
            return PlainTextResponse("FAIL")

        # DB에서 결제 세션 조회
        session = _get_payment_session(db, local_payment_id) if local_payment_id else None

        # 금액 검증 - Verify price matches the session's plan
        if session and price:
            expected_price = str(session.amount)
            if price != expected_price:
                logger.warning(f"[PayApp Webhook] Price mismatch: expected={expected_price}, got={price}")
                return PlainTextResponse("FAIL")

        if pay_state == "4":
            # 결제 완료
            logger.info(f"[PayApp Webhook] Payment completed: mul_no={mul_no}")
            if session:
                # Idempotency check - if already completed, skip
                if session.status == PaymentStatus.SUCCEEDED:
                    logger.info(f"[PayApp Webhook] Payment already completed (idempotent): {local_payment_id}")
                    return PlainTextResponse("SUCCESS")

                prev = session.status.value if session.status else None
                session.status = PaymentStatus.SUCCEEDED
                session.gateway_reference = mul_no
                _record_status_change(db, local_payment_id, prev, "succeeded", "payapp_webhook")
                db.commit()

                # 구독 활성화 - 신뢰할 수 있는 session.user_id 사용 (form data가 아닌 DB 값)
                if session.user_id:
                    _activate_subscription(db, session.user_id, session.plan_id)

        elif pay_state == "10":
            # 가상계좌 입금 대기
            logger.info(f"[PayApp Webhook] Virtual account pending: mul_no={mul_no}")
            vbank = form_data.get("vbank", "")
            vbankno = form_data.get("vbankno", "")
            masked_vbankno = vbankno[:4] + "****" if len(vbankno) > 4 else "****"
            logger.info(f"[PayApp Webhook] VBank: {vbank} {masked_vbankno}")

        elif pay_state in ("8", "32"):
            # 요청 취소
            logger.info(f"[PayApp Webhook] Payment request cancelled: mul_no={mul_no}")
            if session:
                prev = session.status.value if session.status else None
                session.status = PaymentStatus.CANCELLED
                _record_status_change(db, local_payment_id, prev, "cancelled", "payapp_webhook")
                db.commit()

        elif pay_state in ("9", "64"):
            # 승인 취소
            logger.info(f"[PayApp Webhook] Payment approval cancelled: mul_no={mul_no}")
            if session:
                prev = session.status.value if session.status else None
                session.status = PaymentStatus.CANCELLED
                _record_status_change(db, local_payment_id, prev, "cancelled", "payapp_webhook")
                db.commit()

        elif pay_state == "1":
            # 결제 요청 (초기 상태)
            logger.info(f"[PayApp Webhook] Payment requested: mul_no={mul_no}")

        return PlainTextResponse("SUCCESS")

    except Exception as e:
        logger.error(f"[PayApp Webhook] Error: {e}", exc_info=True)
        return PlainTextResponse("FAIL")
