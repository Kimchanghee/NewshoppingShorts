import os
import ipaddress
import os
import re
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from app.database import get_db
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    CheckRequest,
    UseWorkRequest,
    UseWorkResponse,
    CheckWorkResponse,
)
from app.services.auth_service import AuthService
from app.models.user import User
from app.models.registration_request import RegistrationRequest, RequestStatus

logger = logging.getLogger(__name__)

# Trusted proxy configuration - configure for your infrastructure
# 신뢰할 수 있는 프록시 설정 - 인프라에 맞게 설정하세요
# Set via environment variable: TRUSTED_PROXIES=127.0.0.1,10.0.0.0/8
_DEFAULT_TRUSTED_PROXIES = [
    "127.0.0.1",
    "::1",
]


def _get_trusted_proxies() -> List[str]:
    """Get trusted proxy list from environment or defaults."""
    env_proxies = os.environ.get("TRUSTED_PROXIES", "")
    if env_proxies:
        return [p.strip() for p in env_proxies.split(",") if p.strip()]
    return _DEFAULT_TRUSTED_PROXIES


def _is_trusted_proxy(ip: str) -> bool:
    """
    Check if IP is from a trusted proxy.
    신뢰할 수 있는 프록시에서 온 IP인지 확인

    Args:
        ip: IP address to check

    Returns:
        True if IP is from a trusted proxy
    """
    if not ip:
        return False

    trusted_proxies = _get_trusted_proxies()

    try:
        client_addr = ipaddress.ip_address(ip)
        for proxy in trusted_proxies:
            try:
                if "/" in proxy:
                    # CIDR notation (e.g., "10.0.0.0/8")
                    if client_addr in ipaddress.ip_network(proxy, strict=False):
                        return True
                else:
                    # Single IP
                    if client_addr == ipaddress.ip_address(proxy):
                        return True
            except ValueError:
                continue
    except ValueError:
        return False

    return False


def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request with proxy spoofing protection.
    프록시 스푸핑 방지가 포함된 클라이언트 IP 추출

    Security: Only trusts X-Forwarded-For header when request comes from
    a configured trusted proxy. This prevents IP spoofing attacks.

    보안: 요청이 설정된 신뢰할 수 있는 프록시에서 온 경우에만
    X-Forwarded-For 헤더를 신뢰합니다. IP 스푸핑 공격을 방지합니다.

    Args:
        request: FastAPI Request object

    Returns:
        Client IP address as string
    """
    # Get direct connection IP
    direct_ip = request.client.host if request.client else None

    # Only trust X-Forwarded-For if request comes from trusted proxy
    if direct_ip and _is_trusted_proxy(direct_ip):
        forwarded_for: Optional[str] = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For format: "client, proxy1, proxy2, ..."
            # Take the first (leftmost) IP which is the original client
            ips = [ip.strip() for ip in forwarded_for.split(",")]
            for ip in ips:
                # Skip empty or trusted proxy IPs
                if ip and not _is_trusted_proxy(ip):
                    return ip
            # If all IPs are trusted proxies, use the first one
            if ips and ips[0]:
                return ips[0]

    # Return direct IP if available, otherwise "unknown"
    return direct_ip or "unknown"


# Create rate limiter instance using the secure IP extraction
limiter = Limiter(key_func=get_client_ip)

router = APIRouter(prefix="/user", tags=["auth"])


# Rate limit exceeded exception handler
async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Handle rate limit exceeded errors with a JSON response."""
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "error": {
                "code": "RATE_LIMIT_ERROR",
                "message": "Too many login attempts. Please try again later.",
                "retry_after": exc.detail,
            },
        },
    )


@router.post("/login/god", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login(request: Request, data: LoginRequest, db: Session = Depends(get_db)):
    """Login endpoint - backward compatible with existing client"""
    client_ip = get_client_ip(request)
    logger.info(f"[Login Request] ID: {data.id}, IP: {client_ip}, Force: {data.force}")
    
    service = AuthService(db)
    result = await service.login(
        username=data.id, password=data.pw, ip_address=client_ip, force=data.force
    )
    
    log_status = result.get("status")
    log_msg = result.get("message", "-") if not isinstance(log_status, bool) else "Success"
    logger.info(f"[Login Response] ID: {data.id}, Status: {log_status}, Message: {log_msg}")
    
    return result


@router.post("/logout/god")
@limiter.limit("30/minute")
async def logout(request: Request, data: LogoutRequest, db: Session = Depends(get_db)):
    """Logout endpoint with rate limiting"""
    service = AuthService(db)
    result = await service.logout(user_id=data.id, token=data.key)
    return {"status": result}


@router.post("/login/god/check")
@limiter.limit("120/minute")
async def check_session(
    request: Request, data: CheckRequest, db: Session = Depends(get_db)
):
    """Session check endpoint with rate limiting - called every 5 seconds"""
    client_ip = get_client_ip(request)
    service = AuthService(db)
    return await service.check_session(
        user_id=data.id, token=data.key, ip_address=client_ip
    )


@router.get("/check-username/{username}")
@limiter.limit("30/minute")
async def check_username(
    request: Request, username: str, db: Session = Depends(get_db)
):
    """
    Check if username is available for registration.
    아이디 사용 가능 여부 확인
    """
    # Redundant imports removed
    username = username.lower()

    try:
        # 유효성 검사
        if not username or len(username) < 4 or len(username) > 50:
            return {"available": False, "message": "아이디는 4~50자여야 합니다."}

        if not re.match(r"^[a-zA-Z0-9_]+$", username):
            return {
                "available": False,
                "message": "아이디는 영문, 숫자, 밑줄(_)만 사용 가능합니다.",
            }

        # 기존 사용자 확인
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            return {"available": False, "message": "이미 사용 중인 아이디입니다."}

        # 대기 중인 가입 요청 확인
        pending_request = (
            db.query(RegistrationRequest)
            .filter(
                RegistrationRequest.username == username,
                RegistrationRequest.status == RequestStatus.PENDING,
            )
            .first()
        )
        if pending_request:
            return {"available": False, "message": "승인 대기 중인 아이디입니다."}

        return {"available": True, "message": "사용 가능한 아이디입니다."}
    except Exception as e:
        logger.error(f"Error checking username: {e}", exc_info=True)
        # DEBUG: Return actual error to client
        return {"available": False, "message": f"서버 오류: {str(e)}"}


@router.post("/work/check", response_model=CheckWorkResponse)
@limiter.limit("60/minute")
async def check_work(
    request: Request, data: UseWorkRequest, db: Session = Depends(get_db)
):
    """
    Check if user can perform work (has remaining work count).
    작업 가능 여부 확인 (잔여 작업 횟수 확인)
    """
    service = AuthService(db)
    return await service.check_work_available(user_id=data.user_id, token=data.token)


@router.post("/work/use", response_model=UseWorkResponse)
@limiter.limit("60/minute")
async def use_work(
    request: Request, data: UseWorkRequest, db: Session = Depends(get_db)
):
    """
    Increment work_used after successful work completion.
    작업 완료 후 사용 횟수 증가
    """
    service = AuthService(db)
    return await service.use_work(user_id=data.user_id, token=data.token)
