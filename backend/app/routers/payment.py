# -*- coding: utf-8 -*-
"""
Payment Router
寃곗젣 ?쇱슦??
寃곗젣 ?몄뀡 ?앹꽦 諛??곹깭 議고쉶 API + PayApp 媛?곴퀎醫??곕룞

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
from pydantic import BaseModel, Field, field_validator
import re

from app.database import get_db
from app.utils.ip_utils import get_client_ip
from app.utils.subscription_utils import calculate_subscription_expiry, _ensure_aware
from app.utils.jwt_handler import decode_access_token
from app.utils.billing_crypto import (
    decrypt_billing_key,
    encrypt_billing_key,
    has_encryption_key,
    is_encrypted,
)
from app.dependencies import verify_admin_api_key
from app.models.payment_session import PaymentSession, PaymentStatus, PaymentStatusHistory
from app.models.session import SessionModel
from app.models.user import User, UserType
from app.models.billing import BillingKey, RecurringSubscription, SubscriptionStatus

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

# Plan display names (?뚮옖 ?쒖떆 ?대쫫)
PLAN_NAMES = {
    "pro_1month": "?꾨줈 援щ룆 (1媛쒖썡)",
    "pro_6months": "?꾨줈 援щ룆 (6媛쒖썡)",
    "pro_12months": "?꾨줈 援щ룆 (12媛쒖썡)",
}

# ?ъ슜?먮떦 理쒕? 移대뱶 ?깅줉 ??(Maximum cards per user)
MAX_CARDS_PER_USER = 5

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
if _parsed.scheme != "https" or _parsed.hostname not in ("api.payapp.kr",):
    logger.error(f"[SSRF] Blocked untrusted PAYAPP_API_URL domain: {_parsed.hostname}")
    PAYAPP_API_URL = "https://api.payapp.kr/oapi/apiLoad.html"
else:
    PAYAPP_API_URL = _PAYAPP_API_URL_RAW

# PayApp callback state compatibility:
# Different sections/examples in PayApp docs mention slightly different cancel codes.
# Keep this superset to avoid missing legitimate cancellation callbacks.
_PAYAPP_SUCCESS_STATE = "4"
_PAYAPP_CANCEL_STATES = frozenset({"8", "9", "16", "31", "32", "64"})

_TERMINAL_PAYMENT_STATUSES = frozenset(
    {
        PaymentStatus.SUCCEEDED,
        PaymentStatus.CANCELLED,
        PaymentStatus.FAILED,
        PaymentStatus.EXPIRED,
    }
)


def _can_transition_payment_status(
    current: PaymentStatus | None, new: PaymentStatus
) -> bool:
    """Allow only valid payment status transitions."""
    if current is None:
        return True
    if current == new:
        return True
    if current in _TERMINAL_PAYMENT_STATUSES:
        return False
    if current == PaymentStatus.PENDING:
        return new in _TERMINAL_PAYMENT_STATUSES
    return False


def _build_not_found_status_response(payment_id: str) -> "PaymentStatusResponse":
    now_iso = datetime.now(timezone.utc).isoformat()
    return PaymentStatusResponse(
        payment_id=payment_id,
        status="not_found",
        created_at=now_iso,
        updated_at=now_iso,
    )


def _parse_int_value(value: str | None) -> Optional[int]:
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    if not value.isdigit():
        return None
    return int(value)


def _force_masked_card_number(value: str | None, fallback_mask: str) -> str:
    """
    Never trust upstream masking format.
    Always return a local masked form (first4 + **** + last4) when possible.
    """
    raw = (value or "").strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 8:
        return f"{digits[:4]}****{digits[-4:]}"
    return fallback_mask


def _resolve_payment_base_url(request: Request) -> str:
    """
    Resolve public backend base URL used in feedbackurl.

    Security:
    - Production requires explicit PAYMENT_API_BASE_URL.
    - Dynamic host-based fallback is allowed only for local development.
    """
    configured = os.getenv("PAYMENT_API_BASE_URL", "").strip().rstrip("/")
    if configured:
        parsed = _urlparse(configured)
        if not parsed.scheme or not parsed.hostname:
            raise RuntimeError("Invalid PAYMENT_API_BASE_URL")
        if parsed.scheme != "https" and parsed.hostname not in ("localhost", "127.0.0.1"):
            raise RuntimeError("PAYMENT_API_BASE_URL must use HTTPS")
        return configured

    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        raise RuntimeError("PAYMENT_API_BASE_URL must be configured in production")

    dynamic_base = str(request.base_url).rstrip("/")
    parsed_dynamic = _urlparse(dynamic_base)
    if parsed_dynamic.hostname not in ("localhost", "127.0.0.1", "testserver"):
        raise RuntimeError("Refusing dynamic payment base URL for non-local host")
    return dynamic_base


def _decrypt_enc_bill_or_raise(raw_enc_bill: str) -> str:
    try:
        return decrypt_billing_key(raw_enc_bill)
    except RuntimeError as e:
        logger.error(f"[PayApp Card] Failed to decrypt billing key: {e}")
        raise HTTPException(status_code=500, detail="Stored billing key is invalid") from e


class CreatePaymentRequest(BaseModel):
    """寃곗젣 ?앹꽦 ?붿껌"""
    plan_id: str
    user_id: Optional[str] = None


class CreatePaymentResponse(BaseModel):
    """寃곗젣 ?앹꽦 ?묐떟"""
    payment_id: str
    checkout_url: str
    expires_at: str


class PaymentStatusResponse(BaseModel):
    """寃곗젣 ?곹깭 ?묐떟"""
    payment_id: str
    status: str
    plan_id: Optional[str] = None
    user_id: Optional[str] = None
    created_at: str
    updated_at: str


def _record_status_change(db: Session, payment_id: str, prev: str | None, new: str, source: str):
    """寃곗젣 ?곹깭 蹂寃??대젰 湲곕줉"""
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
    x_user_id: str = Header(..., alias="X-User-ID"),
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db)
):
    """
    寃곗젣 ?몄뀡 ?앹꽦
    Create payment session

    Plans:
    - pro_1month: ?꾨줈 1媛쒖썡
    - pro_6months: ?꾨줈 6媛쒖썡
    - pro_12months: ?꾨줈 12媛쒖썡

    Security:
    - Requires Authorization + X-User-ID headers
    - Header user must match optional body user_id
    """
    _validate_authenticated_user(db, str(x_user_id), authorization)
    if data.user_id is not None and str(data.user_id) != str(x_user_id):
        raise HTTPException(status_code=403, detail="User mismatch")

    user_id = str(x_user_id)
    logger.info(f"[Payment] Create request: plan={data.plan_id}, user={user_id}")

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
        user_id=user_id,
        status=PaymentStatus.PENDING,
        amount=amount,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Generate checkout URL (mock - should be real payment gateway URL)
    # ?ㅼ젣 寃곗젣 寃뚯씠?몄썾??URL濡?援먯껜 ?꾩슂 (?? ?좎뒪?섏씠癒쇱툩, 移댁뭅?ㅽ럹????
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
    payment_id: str = Query(..., description="寃곗젣 ID"),
    x_user_id: str = Header(..., alias="X-User-ID"),
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db)
):
    """
    寃곗젣 ?곹깭 議고쉶
    Get payment status

    Status values:
    - pending: ?湲?以?    - succeeded: 寃곗젣 ?꾨즺
    - failed: 寃곗젣 ?ㅽ뙣
    - cancelled: 寃곗젣 痍⑥냼
    - expired: 留뚮즺??    """
    _validate_authenticated_user(db, str(x_user_id), authorization)
    logger.info(f"[Payment] Status check: {payment_id}")

    session = _get_payment_session(db, payment_id)

    if not session:
        logger.warning(f"[Payment] Session not found: {payment_id}")
        return _build_not_found_status_response(payment_id)

    # Hide payment existence across accounts (prevents payment_id enumeration).
    if str(session.user_id) != str(x_user_id):
        logger.warning(
            f"[Payment] Status access denied: payment={payment_id}, user={x_user_id}"
        )
        return _build_not_found_status_response(payment_id)

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
    寃곗젣 ?뱁썒 ?붾뱶?ъ씤??(Admin ?몄쬆 ?꾩슂)
    Payment webhook endpoint (requires Admin API key)

    Security: Admin API key required to prevent unauthorized subscription activation.
    蹂댁븞: 臾대떒 援щ룆 ?쒖꽦?붾? 諛⑹??섍린 ?꾪빐 Admin API ?ㅺ? ?꾩슂?⑸땲??
    """
    try:
        # Parse webhook payload
        payload = await request.json()
        safe_fields = {k: payload.get(k) for k in ("payment_id", "status") if k in payload}
        logger.info(f"[Payment] Webhook received: {safe_fields}")

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

        # Update session status in database (row locking for concurrent webhook protection)
        session = (
            db.query(PaymentSession)
            .filter(PaymentSession.payment_id == payment_id)
            .with_for_update()
            .first()
        )
        if session:
            # Idempotency check - if already completed, skip
            if session.status == PaymentStatus.SUCCEEDED:
                logger.info(f"[Payment] Payment already completed (idempotent): {payment_id}")
                return {"success": True, "payment_id": payment_id, "note": "already_completed"}

            if not _can_transition_payment_status(session.status, mapped_status):
                logger.warning(
                    f"[Payment] Invalid status transition ignored: payment={payment_id}, "
                    f"current={session.status.value if session.status else None}, new={mapped_status.value}"
                )
                return {"success": True, "payment_id": payment_id, "note": "invalid_transition_ignored"}

            prev = session.status.value if session.status else None
            session.status = mapped_status
            # Store gateway reference if provided
            if payload.get("gateway_reference"):
                session.gateway_reference = payload.get("gateway_reference")
            _record_status_change(db, payment_id, prev, mapped_status.value, "webhook")
            db.commit()
            logger.info(f"[Payment] Status updated: {payment_id} -> {mapped_status.value}")

            # Activate subscription only on successful payment status.
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
    Mock: ?뚯뒪?몄슜 寃곗젣 ?꾨즺 泥섎━ (Admin ?꾩슜)
    Mock: Complete payment for testing (Admin only)

    Requires X-Admin-API-Key header for security.
    """
    logger.info(f"[Payment] Mock complete (admin): {payment_id}")

    session = (
        db.query(PaymentSession)
        .filter(PaymentSession.payment_id == payment_id)
        .with_for_update()
        .first()
    )
    if session:
        # Idempotency check
        if session.status == PaymentStatus.SUCCEEDED:
            return {"success": True, "message": "Payment already completed", "note": "already_completed"}

        if not _can_transition_payment_status(session.status, PaymentStatus.SUCCEEDED):
            return {"success": True, "message": "Invalid transition ignored", "note": "invalid_transition_ignored"}

        prev = session.status.value if session.status else None
        session.status = PaymentStatus.SUCCEEDED
        _record_status_change(db, payment_id, prev, PaymentStatus.SUCCEEDED.value, "admin")
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
    Mock: ?뚯뒪?몄슜 寃곗젣 痍⑥냼 泥섎━ (Admin ?꾩슜)
    Mock: Cancel payment for testing (Admin only)

    Requires X-Admin-API-Key header for security.
    """
    logger.info(f"[Payment] Mock cancel (admin): {payment_id}")

    session = (
        db.query(PaymentSession)
        .filter(PaymentSession.payment_id == payment_id)
        .with_for_update()
        .first()
    )
    if session:
        if session.status == PaymentStatus.CANCELLED:
            return {"success": True, "message": "Payment already cancelled", "note": "already_cancelled"}

        if not _can_transition_payment_status(session.status, PaymentStatus.CANCELLED):
            return {"success": True, "message": "Invalid transition ignored", "note": "invalid_transition_ignored"}

        prev = session.status.value if session.status else None
        session.status = PaymentStatus.CANCELLED
        _record_status_change(db, payment_id, prev, PaymentStatus.CANCELLED.value, "admin")
        db.commit()
        return {"success": True, "message": "Payment cancelled (mock)"}

    return {"success": False, "message": "Payment not found"}


# ?????????????????????????????????????????????
# PayApp 媛?곴퀎醫?寃곗젣 ?곕룞
# ?????????????????????????????????????????????

class PayAppCreateRequest(BaseModel):
    """PayApp 寃곗젣 ?앹꽦 ?붿껌"""
    user_id: str
    phone: str  # ?섏떊???꾪솕踰덊샇 (PayApp ?꾩닔)
    plan_id: str = "pro_1month"  # Added: which plan to purchase
    payment_type: str = "vbank"  # 寃곗젣 ?섎떒: "vbank" (媛?곴퀎醫? ?먮뒗 "card" (移대뱶)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        v = v.replace("-", "").strip()
        if not re.match(r'^01[016789]\d{7,8}$', v):
            raise ValueError("?좏슚???대??곕쾲?몃? ?낅젰?댁＜?몄슂")
        return v


class PayAppCreateResponse(BaseModel):
    """PayApp 寃곗젣 ?앹꽦 ?묐떟"""
    success: bool
    payment_id: str = ""
    payurl: str = ""
    mul_no: str = ""
    message: str = ""


def _activate_subscription(db: Session, user_id: str, plan_id: str) -> None:
    """Activate subscription entitlement after successful payment."""
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
        user.work_count = -1  # 臾댁젣??        user.work_used = 0
        db.commit()
        logger.info(
            f"[Payment] Subscription activated: user={user_id}, plan={plan_id}, "
            f"days={plan_days}, expires_at={user.subscription_expires_at}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"[Payment] Failed to activate subscription: {e}", exc_info=True)


def _call_payapp_api(params: dict) -> dict:
    """
    PayApp API ?몄텧 ?ы띁
    Centralized helper for calling the PayApp API.

    Sends POST to PAYAPP_API_URL, parses the URL-encoded response,
    and returns a flat dict. Raises RuntimeError on timeout/network failure.
    """
    try:
        resp = http_requests.post(
            PAYAPP_API_URL,
            data=params,
            timeout=30,
            allow_redirects=False,
        )
        resp.raise_for_status()
        result = {k: v[0] for k, v in parse_qs(resp.text, keep_blank_values=True).items()}
        if "state" not in result:
            safe_keys = ",".join(sorted(result.keys()))[:120]
            logger.warning(
                f"[PayApp] API response missing state (keys={safe_keys or 'none'})"
            )
        return result
    except http_requests.exceptions.Timeout:
        logger.error("[PayApp] API request timed out")
        raise RuntimeError("寃곗젣 ?쒕쾭 ?곌껐 ?쒓컙 珥덇낵")
    except Exception as e:
        logger.error(f"[PayApp] API request failed: {e}", exc_info=True)
        raise RuntimeError("寃곗젣 ?붿껌 泥섎━ 以??ㅻ쪟媛 諛쒖깮?덉뒿?덈떎.")


# Allowed payment types for PayApp 寃곗젣 ?붿껌
_ALLOWED_PAYMENT_TYPES = {"vbank", "card"}


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
    PayApp 寃곗젣 ?붿껌 ?앹꽦 (媛?곴퀎醫??먮뒗 移대뱶)
    Creates a PayApp payment request (virtual account or card)

    Security:
    - Requires Authorization + X-User-ID headers
    - Header user must match body user_id
    - payment_type must be "vbank" or "card"
    """
    _validate_authenticated_user(db, str(x_user_id), authorization)
    if str(data.user_id) != str(x_user_id):
        logger.warning(
            f"[PayApp] Body/header user mismatch: body_user={data.user_id}, header_user={x_user_id}"
        )
        raise HTTPException(status_code=403, detail="User mismatch")

    # 寃곗젣 ?섎떒 寃利?(Validate payment type)
    if data.payment_type not in _ALLOWED_PAYMENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid payment_type: {data.payment_type}. Allowed: {', '.join(_ALLOWED_PAYMENT_TYPES)}"
        )

    user_id = str(x_user_id)
    masked_phone = data.phone[:3] + "****" + data.phone[-4:] if len(data.phone) > 7 else "***"
    logger.info(f"[PayApp] Create request: user={user_id}, phone={masked_phone}, type={data.payment_type}")

    if not PAYAPP_USERID:
        logger.error("[PayApp] PAYAPP_USERID not configured")
        return PayAppCreateResponse(
            success=False, message="寃곗젣 ?ㅼ젙???꾨즺?섏? ?딆븯?듬땲??"
        )

    # Create local payment session first
    local_payment_id = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

    # Determine feedbackurl (backend webhook URL).
    # Production must use explicit PAYMENT_API_BASE_URL.
    try:
        feedback_url = _get_feedback_url(request)
    except RuntimeError as e:
        logger.error(f"[PayApp] Invalid feedback URL configuration: {e}")
        return PayAppCreateResponse(success=False, message="결제 서버 설정 오류")

    # Get plan info
    plan_price = PLAN_PRICES.get(data.plan_id)
    if plan_price is None or plan_price <= 0:
        return PayAppCreateResponse(success=False, message=f"?좏슚?섏? ?딆? ?뚮옖?낅땲?? {data.plan_id}")

    good_name = f"?쇳븨?륂뤌硫붿씠而?{PLAN_NAMES.get(data.plan_id, '?꾨줈 援щ룆')}"

    # Call PayApp API with dynamic plan_id and payment_type
    payapp_params = {
        "cmd": "payrequest",
        "userid": PAYAPP_USERID,
        "goodname": good_name,
        "price": str(plan_price),
        "recvphone": data.phone.replace("-", ""),
        "openpaytype": data.payment_type,
        "smsuse": "n",
        "feedbackurl": feedback_url,
        "var1": local_payment_id,
        "var2": user_id,
        "checkretry": "y",
    }

    try:
        result = _call_payapp_api(payapp_params)

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
            error_msg = result.get("errorMessage", "?????녿뒗 ?ㅻ쪟")
            logger.warning(f"[PayApp] API error: {error_msg}")
            return PayAppCreateResponse(success=False, message="寃곗젣 ?붿껌???ㅽ뙣?덉뒿?덈떎. ?ㅼ떆 ?쒕룄?댁＜?몄슂.")

    except RuntimeError as e:
        return PayAppCreateResponse(success=False, message=str(e))
    except Exception as e:
        logger.error(f"[PayApp] Unexpected error: {e}", exc_info=True)
        return PayAppCreateResponse(success=False, message="寃곗젣 ?붿껌 泥섎━ 以??ㅻ쪟媛 諛쒖깮?덉뒿?덈떎.")


@router.post("/payapp/webhook")
@limiter.limit("100/minute")
async def payapp_webhook(request: Request, db: Session = Depends(get_db)):
    """
    PayApp webhook endpoint (feedbackurl).
    Security: validates linkkey/linkval and enforces strict session ownership checks.
    Response: "SUCCESS" (plain text) per PayApp requirement.
    """
    try:
        form_data = await request.form()
        pay_state = str(form_data.get("pay_state", "")).strip()
        mul_no = str(form_data.get("mul_no", "")).strip()
        price = form_data.get("price", "")
        recv_linkkey = form_data.get("linkkey", "")
        recv_linkval = form_data.get("linkval", "")
        local_payment_id = str(form_data.get("var1", "")).strip()
        user_id = str(form_data.get("var2", "")).strip()

        logger.info(
            f"[PayApp Webhook] pay_state={pay_state}, mul_no={mul_no}, "
            f"price={price}, var1={local_payment_id}, var2={user_id}"
        )

        if not PAYAPP_LINKKEY or not PAYAPP_LINKVAL:
            logger.error("[PayApp Webhook] PAYAPP_LINKKEY/LINKVAL not configured")
            return PlainTextResponse("FAIL")

        if not secrets.compare_digest(str(recv_linkkey), PAYAPP_LINKKEY):
            logger.warning("[PayApp Webhook] Invalid linkkey")
            return PlainTextResponse("FAIL")

        if not secrets.compare_digest(str(recv_linkval), PAYAPP_LINKVAL):
            logger.warning("[PayApp Webhook] Invalid linkval")
            return PlainTextResponse("FAIL")

        if not local_payment_id:
            logger.warning("[PayApp Webhook] Missing var1(local payment id)")
            return PlainTextResponse("FAIL")

        session = (
            db.query(PaymentSession)
            .filter(PaymentSession.payment_id == local_payment_id)
            .with_for_update()
            .first()
        )
        if not session:
            logger.warning(f"[PayApp Webhook] Session not found: {local_payment_id}")
            return PlainTextResponse("FAIL")

        if user_id and str(session.user_id) != user_id:
            logger.warning(
                f"[PayApp Webhook] user mismatch: session_user={session.user_id}, webhook_user={user_id}"
            )
            return PlainTextResponse("FAIL")

        if session.gateway_reference and mul_no and session.gateway_reference != mul_no:
            logger.warning(
                f"[PayApp Webhook] gateway reference mismatch: "
                f"expected={session.gateway_reference}, got={mul_no}"
            )
            return PlainTextResponse("FAIL")

        # Expired pending sessions should not accept completion events.
        if session.status == PaymentStatus.PENDING and session.expires_at:
            expires_at_aware = _ensure_aware(session.expires_at)
            if datetime.now(timezone.utc) > expires_at_aware:
                prev = session.status.value if session.status else None
                session.status = PaymentStatus.EXPIRED
                _record_status_change(db, local_payment_id, prev, "expired", "payapp_webhook")
                db.commit()
                logger.warning(f"[PayApp Webhook] expired payment ignored: {local_payment_id}")
                return PlainTextResponse("FAIL")

        if price not in (None, ""):
            received_price = _parse_int_value(str(price))
            if received_price is None or session.amount is None or received_price != int(session.amount):
                logger.warning(
                    f"[PayApp Webhook] price mismatch: expected={session.amount}, got={price}"
                )
                return PlainTextResponse("FAIL")

        if pay_state == "10":
            logger.info(f"[PayApp Webhook] Virtual account pending: mul_no={mul_no}")
            vbank = form_data.get("vbank", "")
            vbankno = form_data.get("vbankno", "")
            masked_vbankno = vbankno[:4] + "****" if len(vbankno) > 4 else "****"
            logger.info(f"[PayApp Webhook] VBank: {vbank} {masked_vbankno}")
            return PlainTextResponse("SUCCESS")

        if pay_state == "1":
            logger.info(f"[PayApp Webhook] Payment requested: mul_no={mul_no}")
            return PlainTextResponse("SUCCESS")

        mapped_status: PaymentStatus | None = None
        if pay_state == _PAYAPP_SUCCESS_STATE:
            mapped_status = PaymentStatus.SUCCEEDED
        elif pay_state in _PAYAPP_CANCEL_STATES:
            mapped_status = PaymentStatus.CANCELLED

        if mapped_status is None:
            logger.info(f"[PayApp Webhook] Ignored unknown pay_state={pay_state}")
            return PlainTextResponse("SUCCESS")

        if not _can_transition_payment_status(session.status, mapped_status):
            logger.warning(
                f"[PayApp Webhook] Invalid transition ignored: payment={local_payment_id}, "
                f"current={session.status.value if session.status else None}, new={mapped_status.value}"
            )
            return PlainTextResponse("SUCCESS")

        prev = session.status.value if session.status else None
        session.status = mapped_status
        if mul_no:
            session.gateway_reference = mul_no
        _record_status_change(db, local_payment_id, prev, mapped_status.value, "payapp_webhook")
        db.commit()

        if mapped_status == PaymentStatus.SUCCEEDED and session.user_id:
            _activate_subscription(db, session.user_id, session.plan_id)

        return PlainTextResponse("SUCCESS")

    except Exception as e:
        logger.error(f"[PayApp Webhook] Error: {e}", exc_info=True)
        return PlainTextResponse("FAIL")


# --- Pydantic Request/Response Models ---

class CardRegisterRequest(BaseModel):
    """Card registration request (issue billing key)."""
    user_id: str
    card_no: str = Field(..., min_length=13, max_length=19)
    exp_month: str = Field(..., min_length=2, max_length=2)
    exp_year: str = Field(..., min_length=2, max_length=2)
    buyer_auth_no: str = Field(..., min_length=6, max_length=10)
    card_pw: str = Field(..., min_length=2, max_length=2)
    buyer_phone: str = Field(..., min_length=10, max_length=15)
    buyer_name: str = Field(..., min_length=1, max_length=50)

    @field_validator("card_no")
    @classmethod
    def validate_card_no(cls, v):
        v = v.strip()
        if not v.isdigit() or len(v) < 13 or len(v) > 19:
            raise ValueError("card_no must be 13-19 digits")
        return v

    @field_validator("exp_month")
    @classmethod
    def validate_exp_month(cls, v):
        if not v.isdigit() or int(v) < 1 or int(v) > 12:
            raise ValueError("exp_month must be between 01 and 12")
        return v.zfill(2)

    @field_validator("exp_year")
    @classmethod
    def validate_exp_year(cls, v):
        if not v.isdigit() or len(v) != 2:
            raise ValueError("exp_year must be 2 digits")
        return v

    @field_validator("buyer_auth_no")
    @classmethod
    def validate_buyer_auth_no(cls, v):
        v = v.strip()
        if not v.isdigit() or len(v) not in (6, 10):
            raise ValueError("?앸뀈?붿씪(6?먮━) ?먮뒗 ?ъ뾽?먮쾲??10?먮━)瑜??낅젰?댁＜?몄슂")
        return v

    @field_validator("card_pw")
    @classmethod
    def validate_card_pw(cls, v):
        if not v.isdigit() or len(v) != 2:
            raise ValueError("移대뱶 鍮꾨?踰덊샇 ??2?먮━瑜??낅젰?댁＜?몄슂")
        return v

    @field_validator("buyer_phone")
    @classmethod
    def validate_buyer_phone(cls, v):
        v = v.replace("-", "").strip()
        if not re.match(r'^01[016789]\d{7,8}$', v):
            raise ValueError("?좏슚???대??곕쾲?몃? ?낅젰?댁＜?몄슂")
        return v


class CardPayRequest(BaseModel):
    """Payment request using a registered card."""
    user_id: str
    card_id: int        # ?깅줉??移대뱶??DB ID
    plan_id: str        # 寃곗젣???뚮옖 ID
    phone: str          # ?섏떊???꾪솕踰덊샇

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        v = v.replace("-", "").strip()
        if not re.match(r'^01[016789]\d{7,8}$', v):
            raise ValueError("?좏슚???대??곕쾲?몃? ?낅젰?댁＜?몄슂")
        return v


class CardDeleteRequest(BaseModel):
    """Delete registered card request."""
    user_id: str
    card_id: int        # ??젣??移대뱶??DB ID


class SubscribeCreateRequest(BaseModel):
    """Recurring subscription create request."""
    user_id: str
    phone: str                          # ?섏떊???꾪솕踰덊샇
    plan_id: str                        # 援щ룆 ?뚮옖 ID
    cycle_type: str = "Month"           # 寃곗젣 二쇨린 (Month/Week/Day)
    cycle_day: int = 1                  # 寃곗젣??(1~31, 90=留먯씪)
    expire_date: Optional[str] = None   # 留뚮즺??(yyyy-mm-dd), 誘몄엯????1????
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        v = v.replace("-", "").strip()
        if not re.match(r'^01[016789]\d{7,8}$', v):
            raise ValueError("?좏슚???대??곕쾲?몃? ?낅젰?댁＜?몄슂")
        return v

    @field_validator("cycle_type")
    @classmethod
    def validate_cycle_type(cls, v):
        if v not in ("Month", "Week", "Day"):
            raise ValueError("cycle_type must be one of Month, Week, Day")
        return v

    @field_validator("cycle_day")
    @classmethod
    def validate_cycle_day(cls, v):
        if v not in range(1, 32) and v != 90:
            raise ValueError("cycle_day must be 1-31 or 90")
        return v

    @field_validator("expire_date")
    @classmethod
    def validate_expire_date(cls, v):
        if v is None:
            return v
        try:
            d = datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("expire_date must be in yyyy-mm-dd format")
        if d < datetime.now():
            raise ValueError("expire_date must be today or later")
        max_date = datetime.now() + timedelta(days=366)
        if d > max_date:
            raise ValueError("expire_date must be within 1 year")
        return v


class SubscribeManageRequest(BaseModel):
    """Recurring subscription management request (cancel/stop/start)."""
    user_id: str
    rebill_no: str  # PayApp recurring subscription id


# --- Helper: feedbackurl ?앹꽦 ---

def _get_feedback_url(request: Request) -> str:
    """Build validated feedback URL for PayApp callbacks."""
    base_url = _resolve_payment_base_url(request)
    return f"{base_url}/payments/payapp/webhook"


# --- Card Endpoints (移대뱶 寃곗젣 API) ---

@router.post("/payapp/card/register")
@limiter.limit("5/minute")
async def register_card(
    request: Request,
    data: CardRegisterRequest,
    x_user_id: str = Header(..., alias="X-User-ID"),
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db),
):
    """
    PayApp 移대뱶 ?깅줉 (鍮뚮쭅??諛쒓툒)
    Register card and obtain billing key via PayApp billRegist API.

    Security:
    - Requires Authorization + X-User-ID headers
    - Card password (cardPw) is forwarded to PayApp only, never stored
    - Full card number is never logged or stored
    """
    _validate_authenticated_user(db, str(x_user_id), authorization)
    if str(data.user_id) != str(x_user_id):
        raise HTTPException(status_code=403, detail="User mismatch")

    user_id = str(x_user_id)
    # 移대뱶踰덊샇 留덉뒪??(??4?먮━留?濡쒓렇???쒖떆)
    masked_card = data.card_no[:4] + "****" if len(data.card_no) >= 4 else "****"
    logger.info(f"[PayApp Card] Register request: user={user_id}, card={masked_card}")

    if not PAYAPP_USERID:
        return {"success": False, "message": "寃곗젣 ?ㅼ젙???꾨즺?섏? ?딆븯?듬땲??"}
    if not has_encryption_key():
        logger.error("[PayApp Card] Billing key encryption not configured")
        return {"success": False, "message": "결제 보안 설정이 완료되지 않았습니다."}

    # 移대뱶 ?깅줉 媛쒖닔 ?쒗븳 (Limit active cards per user)
    active_count = db.query(BillingKey).filter(
        BillingKey.user_id == user_id,
        BillingKey.is_active == True,
    ).count()
    if active_count >= MAX_CARDS_PER_USER:
        return {"success": False, "message": f"理쒕? {MAX_CARDS_PER_USER}媛쒖쓽 移대뱶留??깅줉?????덉뒿?덈떎."}

    params = {
        "cmd": "billRegist",
        "userid": PAYAPP_USERID,
        "cardNo": data.card_no,
        "expMonth": data.exp_month,
        "expYear": data.exp_year,
        "buyerAuthNo": data.buyer_auth_no,
        "cardPw": data.card_pw,
        "buyerPhone": data.buyer_phone.replace("-", ""),
        "buyerName": data.buyer_name,
    }
    # billRegist docs/examples are inconsistent on linkkey requirement.
    # Send it when configured for wider merchant-environment compatibility.
    if PAYAPP_LINKKEY:
        params["linkkey"] = PAYAPP_LINKKEY

    try:
        result = _call_payapp_api(params)

        if result.get("state") == "1":
            enc_bill = result.get("encBill", "")
            if not enc_bill:
                logger.error("[PayApp Card] Missing encBill in PayApp response")
                return {"success": False, "message": "카드 등록 처리에 실패했습니다. 다시 시도해주세요."}
            try:
                encrypted_enc_bill = encrypt_billing_key(enc_bill)
            except RuntimeError as e:
                logger.error(f"[PayApp Card] Billing key encryption failed: {e}")
                return {"success": False, "message": "결제 보안 설정 오류로 카드 등록에 실패했습니다."}
            card_no_masked = _force_masked_card_number(
                result.get("cardno", ""),
                masked_card,
            )
            card_name = result.get("cardname", "")

            # DB??鍮뚮쭅?????(Save billing key to DB)
            billing_key = BillingKey(
                user_id=user_id,
                enc_bill=encrypted_enc_bill,
                card_no_masked=card_no_masked,
                card_name=card_name,
                is_active=True,
            )
            db.add(billing_key)
            try:
                db.commit()
                db.refresh(billing_key)
            except Exception as db_err:
                db.rollback()
                logger.error(f"[PayApp Card] DB commit failed after registration: {db_err}", exc_info=True)
                # Compensating action: delete the billing key from PayApp
                try:
                    _call_payapp_api({"cmd": "billDelete", "userid": PAYAPP_USERID, "encBill": enc_bill})
                except Exception:
                    logger.critical(f"[PayApp Card] ORPHANED billing key for user={user_id}")
                return {"success": False, "message": "移대뱶 ?깅줉 泥섎━ 以??ㅻ쪟媛 諛쒖깮?덉뒿?덈떎. ?ㅼ떆 ?쒕룄?댁＜?몄슂."}

            logger.info(f"[PayApp Card] Card registered: user={user_id}, card_name={card_name}")
            return {
                "success": True,
                "card_id": billing_key.id,
                "card_no_masked": card_no_masked,
                "card_name": card_name,
            }
        else:
            error_msg = result.get("errorMessage", "移대뱶 ?깅줉 ?ㅽ뙣")
            logger.warning(f"[PayApp Card] Register failed: {error_msg}")
            return {"success": False, "message": "移대뱶 ?깅줉???ㅽ뙣?덉뒿?덈떎. ?낅젰 ?뺣낫瑜??뺤씤 ???ㅼ떆 ?쒕룄?댁＜?몄슂."}

    except RuntimeError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error(f"[PayApp Card] Register error: {e}", exc_info=True)
        return {"success": False, "message": "移대뱶 ?깅줉 泥섎━ 以??ㅻ쪟媛 諛쒖깮?덉뒿?덈떎."}


@router.post("/payapp/card/pay")
@limiter.limit("10/minute")
async def pay_with_card(
    request: Request,
    data: CardPayRequest,
    x_user_id: str = Header(..., alias="X-User-ID"),
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db),
):
    """
    ?깅줉??移대뱶濡?寃곗젣 (鍮뚮쭅??寃곗젣)
    Pay with registered card via PayApp billPay API.

    Security:
    - Requires Authorization + X-User-ID headers
    - enc_bill ownership is verified against DB
    """
    _validate_authenticated_user(db, str(x_user_id), authorization)
    if str(data.user_id) != str(x_user_id):
        raise HTTPException(status_code=403, detail="User mismatch")

    user_id = str(x_user_id)
    logger.info(f"[PayApp Card] Pay request: user={user_id}, plan={data.plan_id}")

    if not PAYAPP_USERID:
        return {"success": False, "message": "寃곗젣 ?ㅼ젙???꾨즺?섏? ?딆븯?듬땲??"}

    # 鍮뚮쭅???뚯쑀???뺤씤 (Verify billing key ownership via card_id)
    billing_key = (
        db.query(BillingKey)
        .filter(
            BillingKey.id == data.card_id,
            BillingKey.user_id == user_id,
            BillingKey.is_active == True,
        )
        .first()
    )
    if not billing_key:
        raise HTTPException(status_code=404, detail="?깅줉??移대뱶瑜?李얠쓣 ???놁뒿?덈떎.")

    payapp_enc_bill = _decrypt_enc_bill_or_raise(billing_key.enc_bill)
    if not is_encrypted(billing_key.enc_bill) and has_encryption_key():
        try:
            billing_key.enc_bill = encrypt_billing_key(billing_key.enc_bill)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning(f"[PayApp Card] Legacy billing key re-encryption skipped: {e}")

    # ?뚮옖 媛寃?議고쉶 (Get plan price)
    plan_price = PLAN_PRICES.get(data.plan_id)
    if plan_price is None or plan_price <= 0:
        return {"success": False, "message": f"?좏슚?섏? ?딆? ?뚮옖?낅땲?? {data.plan_id}"}

    good_name = f"?쇳븨?륂뤌硫붿씠而?{PLAN_NAMES.get(data.plan_id, '?꾨줈 援щ룆')}"

    # 濡쒖뺄 寃곗젣 ?몄뀡 ?앹꽦 (Create local payment session)
    local_payment_id = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    try:
        feedback_url = _get_feedback_url(request)
    except RuntimeError as e:
        logger.error(f"[PayApp Card] Invalid feedback URL configuration: {e}")
        return {"success": False, "message": "결제 서버 설정 오류"}

    # ?멸툑 怨꾩궛 (Tax calculation: 遺媛???ы븿 媛寃?湲곗?)
    amount_taxfree = 0
    amount_vat = int(plan_price / 11)  # VAT = price / 11 (遺媛???ы븿 媛寃?
    amount_taxable = plan_price - amount_vat

    params = {
        "cmd": "billPay",
        "userid": PAYAPP_USERID,
        "encBill": payapp_enc_bill,
        "goodname": good_name,
        "price": str(plan_price),
        "recvphone": data.phone.replace("-", ""),
        "amount_taxable": str(amount_taxable),
        "amount_taxfree": str(amount_taxfree),
        "amount_vat": str(amount_vat),
        "feedbackurl": feedback_url,
        "var1": local_payment_id,
        "var2": user_id,
    }

    try:
        result = _call_payapp_api(params)

        if result.get("state") == "1":
            mul_no = result.get("mul_no", "")

            # DB??寃곗젣 ?몄뀡 ???(Save payment session to DB)
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
            try:
                db.commit()
            except Exception as db_err:
                db.rollback()
                logger.error(f"[PayApp Card] DB commit failed after card payment: {db_err}", exc_info=True)
                # 蹂댁긽 議곗튂: 寃곗젣 痍⑥냼 ?쒕룄 (Compensating action: attempt to cancel the charge)
                try:
                    _call_payapp_api({
                        "cmd": "paycancel",
                        "userid": PAYAPP_USERID,
                        "linkkey": PAYAPP_LINKKEY,
                        "mul_no": mul_no,
                        "cancelmemo": "DB ?ㅻ쪟濡??명븳 ?먮룞 痍⑥냼",
                        "partcancel": "0",
                    })
                except Exception:
                    logger.critical(
                        f"[PayApp Card] ORPHANED payment: mul_no={mul_no}, user={user_id}, amount={plan_price}"
                    )
                return {"success": False, "message": "移대뱶 寃곗젣 泥섎━ 以??ㅻ쪟媛 諛쒖깮?덉뒿?덈떎. ?ㅼ떆 ?쒕룄?댁＜?몄슂."}

            logger.info(f"[PayApp Card] Payment initiated: mul_no={mul_no}, payment_id={local_payment_id}")
            return {
                "success": True,
                "payment_id": local_payment_id,
                "mul_no": mul_no,
            }
        else:
            error_msg = result.get("errorMessage", "移대뱶 寃곗젣 ?ㅽ뙣")
            logger.warning(f"[PayApp Card] Pay failed: {error_msg}")
            return {"success": False, "message": "移대뱶 寃곗젣???ㅽ뙣?덉뒿?덈떎. ?ㅼ떆 ?쒕룄?댁＜?몄슂."}

    except RuntimeError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error(f"[PayApp Card] Pay error: {e}", exc_info=True)
        return {"success": False, "message": "移대뱶 寃곗젣 泥섎━ 以??ㅻ쪟媛 諛쒖깮?덉뒿?덈떎."}


@router.post("/payapp/card/delete")
@limiter.limit("10/minute")
async def delete_card(
    request: Request,
    data: CardDeleteRequest,
    x_user_id: str = Header(..., alias="X-User-ID"),
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db),
):
    """
    ?깅줉??移대뱶 ??젣 (鍮뚮쭅????젣)
    Delete registered card via PayApp billDelete API.

    Security:
    - Requires Authorization + X-User-ID headers
    - enc_bill ownership is verified against DB
    """
    _validate_authenticated_user(db, str(x_user_id), authorization)
    if str(data.user_id) != str(x_user_id):
        raise HTTPException(status_code=403, detail="User mismatch")

    user_id = str(x_user_id)
    logger.info(f"[PayApp Card] Delete request: user={user_id}")

    if not PAYAPP_USERID:
        return {"success": False, "message": "寃곗젣 ?ㅼ젙???꾨즺?섏? ?딆븯?듬땲??"}

    # ?쒖꽦 ?뺢린寃곗젣 ?뺤씤 (Check for active recurring subscriptions)
    active_subs = db.query(RecurringSubscription).filter(
        RecurringSubscription.user_id == user_id,
        RecurringSubscription.status == SubscriptionStatus.ACTIVE,
    ).count()
    if active_subs > 0:
        return {
            "success": False,
            "message": "?쒖꽦 ?뺢린寃곗젣媛 ?덈뒗 寃쎌슦 移대뱶瑜???젣?????놁뒿?덈떎. 癒쇱? ?뺢린寃곗젣瑜?痍⑥냼?댁＜?몄슂."
        }

    # 鍮뚮쭅???뚯쑀???뺤씤 (Verify billing key ownership via card_id)
    billing_key = (
        db.query(BillingKey)
        .filter(
            BillingKey.id == data.card_id,
            BillingKey.user_id == user_id,
            BillingKey.is_active == True,
        )
        .first()
    )
    if not billing_key:
        raise HTTPException(status_code=404, detail="?깅줉??移대뱶瑜?李얠쓣 ???놁뒿?덈떎.")

    payapp_enc_bill = _decrypt_enc_bill_or_raise(billing_key.enc_bill)
    if not is_encrypted(billing_key.enc_bill) and has_encryption_key():
        try:
            billing_key.enc_bill = encrypt_billing_key(billing_key.enc_bill)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning(f"[PayApp Card] Legacy billing key re-encryption skipped: {e}")

    params = {
        "cmd": "billDelete",
        "userid": PAYAPP_USERID,
        "encBill": payapp_enc_bill,
    }

    try:
        result = _call_payapp_api(params)

        if result.get("state") == "1":
            # DB?먯꽌 鍮꾪솢?깊솕 (Soft delete in DB)
            billing_key.is_active = False
            db.commit()

            logger.info(f"[PayApp Card] Card deleted: user={user_id}")
            return {"success": True, "message": "移대뱶媛 ??젣?섏뿀?듬땲??"}
        else:
            error_msg = result.get("errorMessage", "移대뱶 ??젣 ?ㅽ뙣")
            logger.warning(f"[PayApp Card] Delete failed: {error_msg}")
            return {"success": False, "message": "移대뱶 ??젣???ㅽ뙣?덉뒿?덈떎. ?ㅼ떆 ?쒕룄?댁＜?몄슂."}

    except RuntimeError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error(f"[PayApp Card] Delete error: {e}", exc_info=True)
        return {"success": False, "message": "移대뱶 ??젣 泥섎━ 以??ㅻ쪟媛 諛쒖깮?덉뒿?덈떎."}


@router.get("/payapp/card/list")
@limiter.limit("30/minute")
async def list_cards(
    request: Request,
    x_user_id: str = Header(..., alias="X-User-ID"),
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db),
):
    """
    ?깅줉??移대뱶 紐⑸줉 議고쉶
    List user's registered (active) cards.

    Security:
    - Requires Authorization + X-User-ID headers
    - Returns only cards belonging to the authenticated user
    """
    _validate_authenticated_user(db, str(x_user_id), authorization)
    user_id = str(x_user_id)

    cards = (
        db.query(BillingKey)
        .filter(BillingKey.user_id == user_id, BillingKey.is_active == True)
        .order_by(BillingKey.created_at.desc())
        .all()
    )

    card_list = [
        {
            "card_id": card.id,
            "card_no_masked": card.card_no_masked,
            "card_name": card.card_name,
            "created_at": card.created_at.isoformat() if card.created_at else None,
        }
        for card in cards
    ]

    logger.info(f"[PayApp Card] List cards: user={user_id}, count={len(card_list)}")
    return {"success": True, "cards": card_list}


# --- Recurring Subscription Endpoints (?뺢린寃곗젣 API) ---

@router.post("/payapp/subscribe")
@limiter.limit("5/minute")
async def create_subscription(
    request: Request,
    data: SubscribeCreateRequest,
    x_user_id: str = Header(..., alias="X-User-ID"),
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db),
):
    """
    ?뺢린寃곗젣 援щ룆 ?앹꽦
    Create recurring subscription via PayApp rebillRegist API.

    Security:
    - Requires Authorization + X-User-ID headers
    - Default expire_date is 1 year from now if not provided
    """
    _validate_authenticated_user(db, str(x_user_id), authorization)
    if str(data.user_id) != str(x_user_id):
        raise HTTPException(status_code=403, detail="User mismatch")

    user_id = str(x_user_id)
    masked_phone = data.phone[:3] + "****" + data.phone[-4:] if len(data.phone) > 7 else "***"
    logger.info(
        f"[PayApp Subscribe] Create request: user={user_id}, plan={data.plan_id}, "
        f"cycle={data.cycle_type}/{data.cycle_day}, phone={masked_phone}"
    )

    if not PAYAPP_USERID:
        return {"success": False, "message": "寃곗젣 ?ㅼ젙???꾨즺?섏? ?딆븯?듬땲??"}

    # ?뚮옖 媛寃?議고쉶 (Get plan price)
    plan_price = PLAN_PRICES.get(data.plan_id)
    if plan_price is None or plan_price <= 0:
        return {"success": False, "message": f"?좏슚?섏? ?딆? ?뚮옖?낅땲?? {data.plan_id}"}

    good_name = f"?쇳븨?륂뤌硫붿씠而?{PLAN_NAMES.get(data.plan_id, '?꾨줈 援щ룆')}"

    # 留뚮즺??湲곕낯媛? 1????(Default expire date: 1 year from now)
    expire_date = data.expire_date
    if not expire_date:
        expire_date = (datetime.now(timezone.utc) + timedelta(days=365)).strftime("%Y-%m-%d")

    try:
        feedback_url = _get_feedback_url(request)
    except RuntimeError as e:
        logger.error(f"[PayApp Subscribe] Invalid feedback URL configuration: {e}")
        return {"success": False, "message": "결제 서버 설정 오류"}

    # cycle_type? Pydantic 紐⑤뜽?먯꽌 ?대? 寃利앸맖 (Validated in Pydantic model)

    params = {
        "cmd": "rebillRegist",
        "userid": PAYAPP_USERID,
        "goodname": good_name,
        "goodprice": str(plan_price),
        "recvphone": data.phone.replace("-", ""),
        "rebillCycleType": data.cycle_type,
        "rebillCycleMonth": str(data.cycle_day),
        "rebillExpire": expire_date,
        "feedbackurl": feedback_url,
        "smsuse": "n",
    }

    try:
        result = _call_payapp_api(params)

        if result.get("state") == "1":
            rebill_no = result.get("rebill_no", "")
            payurl = result.get("payurl", "")

            # DB???뺢린寃곗젣 援щ룆 ???(Save recurring subscription to DB)
            subscription = RecurringSubscription(
                user_id=user_id,
                rebill_no=rebill_no,
                plan_id=data.plan_id,
                amount=plan_price,
                cycle_type=data.cycle_type,
                cycle_value=data.cycle_day,
                expire_date=expire_date,
                status=SubscriptionStatus.ACTIVE,
            )
            db.add(subscription)
            try:
                db.commit()
            except Exception as db_err:
                db.rollback()
                logger.error(f"[PayApp Subscribe] DB commit failed after subscription creation: {db_err}", exc_info=True)
                # Compensating action: cancel the subscription on PayApp
                try:
                    _call_payapp_api({"cmd": "rebillCancel", "userid": PAYAPP_USERID, "linkkey": PAYAPP_LINKKEY, "rebill_no": rebill_no})
                except Exception:
                    logger.critical(f"[PayApp Subscribe] ORPHANED subscription rebill_no={rebill_no} for user={user_id}")
                return {"success": False, "message": "?뺢린寃곗젣 ?깅줉 泥섎━ 以??ㅻ쪟媛 諛쒖깮?덉뒿?덈떎. ?ㅼ떆 ?쒕룄?댁＜?몄슂."}

            logger.info(f"[PayApp Subscribe] Subscription created: rebill_no={rebill_no}")
            return {
                "success": True,
                "rebill_no": rebill_no,
                "payurl": payurl,
            }
        else:
            error_msg = result.get("errorMessage", "?뺢린寃곗젣 ?깅줉 ?ㅽ뙣")
            logger.warning(f"[PayApp Subscribe] Create failed: {error_msg}")
            return {"success": False, "message": "?뺢린寃곗젣 ?깅줉???ㅽ뙣?덉뒿?덈떎. ?ㅼ떆 ?쒕룄?댁＜?몄슂."}

    except RuntimeError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error(f"[PayApp Subscribe] Create error: {e}", exc_info=True)
        return {"success": False, "message": "?뺢린寃곗젣 ?깅줉 泥섎━ 以??ㅻ쪟媛 諛쒖깮?덉뒿?덈떎."}


@router.post("/payapp/subscribe/cancel")
@limiter.limit("10/minute")
async def cancel_subscription(
    request: Request,
    data: SubscribeManageRequest,
    x_user_id: str = Header(..., alias="X-User-ID"),
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db),
):
    """
    ?뺢린寃곗젣 痍⑥냼
    Cancel recurring subscription via PayApp rebillCancel API.

    Security:
    - Requires Authorization + X-User-ID headers
    - rebill_no ownership is verified against DB
    """
    _validate_authenticated_user(db, str(x_user_id), authorization)
    if str(data.user_id) != str(x_user_id):
        raise HTTPException(status_code=403, detail="User mismatch")

    user_id = str(x_user_id)
    logger.info(f"[PayApp Subscribe] Cancel request: user={user_id}, rebill_no={data.rebill_no}")

    # 援щ룆 ?뚯쑀???뺤씤 (Verify subscription ownership with row lock)
    subscription = (
        db.query(RecurringSubscription)
        .filter(
            RecurringSubscription.user_id == user_id,
            RecurringSubscription.rebill_no == data.rebill_no,
        )
        .with_for_update()
        .first()
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="?뺢린寃곗젣瑜?李얠쓣 ???놁뒿?덈떎.")

    if subscription.status == SubscriptionStatus.CANCELLED:
        return {"success": False, "message": "?대? 痍⑥냼???뺢린寃곗젣?낅땲??"}

    params = {
        "cmd": "rebillCancel",
        "userid": PAYAPP_USERID,
        "linkkey": PAYAPP_LINKKEY,
        "rebill_no": data.rebill_no,
    }

    try:
        result = _call_payapp_api(params)

        if result.get("state") == "1":
            subscription.status = SubscriptionStatus.CANCELLED
            db.commit()

            logger.info(f"[PayApp Subscribe] Cancelled: rebill_no={data.rebill_no}")
            return {"success": True, "message": "?뺢린寃곗젣媛 痍⑥냼?섏뿀?듬땲??"}
        else:
            error_msg = result.get("errorMessage", "?뺢린寃곗젣 痍⑥냼 ?ㅽ뙣")
            logger.warning(f"[PayApp Subscribe] Cancel failed: {error_msg}")
            return {"success": False, "message": "?뺢린寃곗젣 痍⑥냼???ㅽ뙣?덉뒿?덈떎. ?ㅼ떆 ?쒕룄?댁＜?몄슂."}

    except RuntimeError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error(f"[PayApp Subscribe] Cancel error: {e}", exc_info=True)
        return {"success": False, "message": "?뺢린寃곗젣 痍⑥냼 泥섎━ 以??ㅻ쪟媛 諛쒖깮?덉뒿?덈떎."}


@router.post("/payapp/subscribe/stop")
@limiter.limit("10/minute")
async def stop_subscription(
    request: Request,
    data: SubscribeManageRequest,
    x_user_id: str = Header(..., alias="X-User-ID"),
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db),
):
    """
    ?뺢린寃곗젣 ?쇱떆以묒?
    Pause recurring subscription via PayApp rebillStop API.

    Security:
    - Requires Authorization + X-User-ID headers
    - rebill_no ownership is verified against DB
    """
    _validate_authenticated_user(db, str(x_user_id), authorization)
    if str(data.user_id) != str(x_user_id):
        raise HTTPException(status_code=403, detail="User mismatch")

    user_id = str(x_user_id)
    logger.info(f"[PayApp Subscribe] Stop request: user={user_id}, rebill_no={data.rebill_no}")

    # 援щ룆 ?뚯쑀???뺤씤 (Verify subscription ownership with row lock)
    subscription = (
        db.query(RecurringSubscription)
        .filter(
            RecurringSubscription.user_id == user_id,
            RecurringSubscription.rebill_no == data.rebill_no,
        )
        .with_for_update()
        .first()
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="?뺢린寃곗젣瑜?李얠쓣 ???놁뒿?덈떎.")

    if subscription.status != SubscriptionStatus.ACTIVE:
        return {"success": False, "message": f"?꾩옱 ?곹깭({subscription.status.value})?먯꽌??以묒??????놁뒿?덈떎."}

    params = {
        "cmd": "rebillStop",
        "userid": PAYAPP_USERID,
        "linkkey": PAYAPP_LINKKEY,
        "rebill_no": data.rebill_no,
    }

    try:
        result = _call_payapp_api(params)

        if result.get("state") == "1":
            subscription.status = SubscriptionStatus.STOPPED
            db.commit()

            logger.info(f"[PayApp Subscribe] Stopped: rebill_no={data.rebill_no}")
            return {"success": True, "message": "?뺢린寃곗젣媛 ?쇱떆以묒??섏뿀?듬땲??"}
        else:
            error_msg = result.get("errorMessage", "?뺢린寃곗젣 以묒? ?ㅽ뙣")
            logger.warning(f"[PayApp Subscribe] Stop failed: {error_msg}")
            return {"success": False, "message": "?뺢린寃곗젣 以묒????ㅽ뙣?덉뒿?덈떎. ?ㅼ떆 ?쒕룄?댁＜?몄슂."}

    except RuntimeError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error(f"[PayApp Subscribe] Stop error: {e}", exc_info=True)
        return {"success": False, "message": "?뺢린寃곗젣 以묒? 泥섎━ 以??ㅻ쪟媛 諛쒖깮?덉뒿?덈떎."}


@router.post("/payapp/subscribe/start")
@limiter.limit("10/minute")
async def start_subscription(
    request: Request,
    data: SubscribeManageRequest,
    x_user_id: str = Header(..., alias="X-User-ID"),
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db),
):
    """
    ?뺢린寃곗젣 ?ш컻
    Resume recurring subscription via PayApp rebillStart API.

    Security:
    - Requires Authorization + X-User-ID headers
    - rebill_no ownership is verified against DB
    """
    _validate_authenticated_user(db, str(x_user_id), authorization)
    if str(data.user_id) != str(x_user_id):
        raise HTTPException(status_code=403, detail="User mismatch")

    user_id = str(x_user_id)
    logger.info(f"[PayApp Subscribe] Start request: user={user_id}, rebill_no={data.rebill_no}")

    # 援щ룆 ?뚯쑀???뺤씤 (Verify subscription ownership with row lock)
    subscription = (
        db.query(RecurringSubscription)
        .filter(
            RecurringSubscription.user_id == user_id,
            RecurringSubscription.rebill_no == data.rebill_no,
        )
        .with_for_update()
        .first()
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="?뺢린寃곗젣瑜?李얠쓣 ???놁뒿?덈떎.")

    if subscription.status != SubscriptionStatus.STOPPED:
        return {"success": False, "message": f"?꾩옱 ?곹깭({subscription.status.value})?먯꽌???ш컻?????놁뒿?덈떎."}

    params = {
        "cmd": "rebillStart",
        "userid": PAYAPP_USERID,
        "linkkey": PAYAPP_LINKKEY,
        "rebill_no": data.rebill_no,
    }

    try:
        result = _call_payapp_api(params)

        if result.get("state") == "1":
            subscription.status = SubscriptionStatus.ACTIVE
            db.commit()

            logger.info(f"[PayApp Subscribe] Resumed: rebill_no={data.rebill_no}")
            return {"success": True, "message": "?뺢린寃곗젣媛 ?ш컻?섏뿀?듬땲??"}
        else:
            error_msg = result.get("errorMessage", "?뺢린寃곗젣 ?ш컻 ?ㅽ뙣")
            logger.warning(f"[PayApp Subscribe] Start failed: {error_msg}")
            return {"success": False, "message": "?뺢린寃곗젣 ?ш컻???ㅽ뙣?덉뒿?덈떎. ?ㅼ떆 ?쒕룄?댁＜?몄슂."}

    except RuntimeError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error(f"[PayApp Subscribe] Start error: {e}", exc_info=True)
        return {"success": False, "message": "?뺢린寃곗젣 ?ш컻 泥섎━ 以??ㅻ쪟媛 諛쒖깮?덉뒿?덈떎."}


@router.get("/payapp/subscribe/status")
@limiter.limit("30/minute")
async def get_subscription_status(
    request: Request,
    x_user_id: str = Header(..., alias="X-User-ID"),
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db),
):
    """
    ?뺢린寃곗젣 援щ룆 ?곹깭 議고쉶
    Get user's recurring subscriptions.

    Security:
    - Requires Authorization + X-User-ID headers
    - Returns only subscriptions belonging to the authenticated user
    """
    _validate_authenticated_user(db, str(x_user_id), authorization)
    user_id = str(x_user_id)

    subscriptions = (
        db.query(RecurringSubscription)
        .filter(RecurringSubscription.user_id == user_id)
        .order_by(RecurringSubscription.created_at.desc())
        .all()
    )

    sub_list = [
        {
            "rebill_no": sub.rebill_no,
            "plan_id": sub.plan_id,
            "amount": sub.amount,
            "cycle_type": sub.cycle_type,
            "cycle_value": sub.cycle_value,
            "expire_date": sub.expire_date,
            "status": sub.status.value if sub.status else None,
            "created_at": sub.created_at.isoformat() if sub.created_at else None,
            "updated_at": sub.updated_at.isoformat() if sub.updated_at else None,
        }
        for sub in subscriptions
    ]

    logger.info(f"[PayApp Subscribe] Status query: user={user_id}, count={len(sub_list)}")
    return {"success": True, "subscriptions": sub_list}



