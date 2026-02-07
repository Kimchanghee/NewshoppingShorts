"""
Dependencies
FastAPI 의존성 주입 모듈

API 인증 및 권한 검사를 위한 의존성 함수들
"""
import secrets
from fastapi import Header, HTTPException, status
from app.configuration import get_settings

settings = get_settings()


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
