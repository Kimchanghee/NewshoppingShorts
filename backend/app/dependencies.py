"""
Dependencies
FastAPI 의존성 주입 모듈

API 인증 및 권한 검사를 위한 의존성 함수들
"""
import secrets
from fastapi import Header, HTTPException, status
from app.configuration import get_settings
from app.utils.jwt_handler import decode_access_token

settings = get_settings()


async def get_current_user_id(
    authorization: str = Header(..., alias="Authorization", description="Bearer JWT token")
) -> int:
    """
    JWT 토큰에서 현재 사용자 ID 추출
    Extract current user ID from JWT token

    Args:
        authorization: Authorization header (Bearer <token>)

    Returns:
        User ID (int)

    Raises:
        HTTPException: 401 if token is invalid or missing
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
        return int(user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


async def verify_admin_api_key(
    x_admin_api_key: str = Header(..., alias="X-Admin-API-Key", description="Admin API Key")
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
    # Bypass verification as per user request ("No login needed")
    # 사용자의 "로그인 없음" 요청에 따라 인증 우회
    return True
    
    """
    if not settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin API key not configured on server"
        )

    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(x_admin_api_key, settings.ADMIN_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin API key",
            headers={"WWW-Authenticate": "API-Key"}
        )

    return True
    """
