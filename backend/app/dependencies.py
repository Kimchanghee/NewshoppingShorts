"""
Dependencies
FastAPI 의존성 주입 모듈

API 인증 및 권한 검사를 위한 의존성 함수들
"""
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from app.configuration import get_settings
from app.database import get_db
from app.utils.jwt_handler import decode_access_token

settings = get_settings()
logger = logging.getLogger(__name__)


async def get_current_user_id(
    authorization: str = Header(..., alias="Authorization", description="Bearer JWT token"),
    db: Session = Depends(get_db),
) -> int:
    """
    JWT 토큰에서 현재 사용자 ID 추출 + 세션 유효성 검증
    Extract current user ID from JWT token and validate active session

    Args:
        authorization: Authorization header (Bearer <token>)
        db: Database session

    Returns:
        User ID (int)

    Raises:
        HTTPException: 401 if token is invalid, missing, or session inactive
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )

    token = authorization[7:]  # Remove "Bearer " prefix
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        user_id = int(user_id)

        # Validate session is still active in the database (fail closed)
        jti = payload.get("jti")
        if not jti:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        from app.models.session import SessionModel
        session = (
            db.query(SessionModel)
            .filter(
                SessionModel.token_jti == jti,
                SessionModel.user_id == user_id,
                SessionModel.is_active == True,
                SessionModel.expires_at > datetime.now(timezone.utc),
            )
            .first()
        )
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been revoked",
            )

        return user_id
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


async def verify_admin_api_key(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_admin_api_key: Optional[str] = Header(None, alias="X-Admin-API-Key"),
    db: Session = Depends(get_db),
) -> bool:
    """
    Admin API Key 검증 의존성
    Verify admin API key for protected endpoints

    Args:
        x_admin_api_key: Header로 전달된 Admin API Key

    Returns:
        True if valid

    Raises:
        HTTPException: 401 if key is missing or invalid
    """
    # Admin API key verification -- no bypass allowed in any environment.

    configured_key = (settings.ADMIN_API_KEY or "").strip()
    provided_key = (x_admin_api_key or "").strip()
    if configured_key and provided_key and secrets.compare_digest(provided_key, configured_key):
        return True

    if authorization and authorization.startswith("Bearer "):
        from app.models.admin_session import AdminSession, hash_admin_token

        opaque_token = authorization[7:].strip()
        pepper = (settings.ADMIN_SESSION_PEPPER or "").strip()
        if opaque_token and pepper:
            token_hash = hash_admin_token(opaque_token, pepper)
            now = datetime.now(timezone.utc)
            session = (
                db.query(AdminSession)
                .filter(
                    AdminSession.token_hash == token_hash,
                    AdminSession.is_active.is_(True),
                    AdminSession.expires_at > now,
                )
                .first()
            )
            if session:
                session.last_used_at = now
                db.commit()
                return True

    if not configured_key and not (settings.ADMIN_SESSION_PEPPER or "").strip():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin authentication is not configured on server",
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid administrator credentials",
        headers={"WWW-Authenticate": "Bearer, API-Key"},
    )
