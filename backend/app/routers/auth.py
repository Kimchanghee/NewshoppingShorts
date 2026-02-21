import hashlib
import ipaddress
import os
import re
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, Request, Header, HTTPException
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
    ChangePasswordRequest,
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

    # Secure default: trust only loopback addresses.
    # For reverse proxies/load balancers, configure TRUSTED_PROXIES explicitly.
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


def _resolve_token(
    authorization: Optional[str],
    body_token: str,
) -> str:
    """Prefer Bearer token from header, fallback to legacy body token."""
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:].strip()
    return (body_token or "").strip()


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
    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:12] if client_ip else "unknown"
    logger.info(f"[Login Request] ID: {data.id}, IP_hash: {ip_hash}, Force: {data.force}")
    
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
async def logout(
    request: Request,
    data: LogoutRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
):
    """Logout endpoint with rate limiting"""
    token = _resolve_token(authorization, data.key)
    service = AuthService(db)
    result = await service.logout(user_id=data.id, token=token)
    return {"status": result}


@router.post("/login/god/check")
@limiter.limit("120/minute")
async def check_session(
    request: Request,
    data: CheckRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
):
    """Session check endpoint with rate limiting - called every 5 seconds"""
    client_ip = get_client_ip(request)
    token = _resolve_token(authorization, data.key)
    service = AuthService(db)
    return await service.check_session(
        user_id=data.id, token=token, ip_address=client_ip,
        current_task=data.current_task, app_version=data.app_version
    )


@router.post("/change-password")
@limiter.limit("10/hour")
async def change_password(
    request: Request,
    data: ChangePasswordRequest,
    x_user_id: str = Header(..., alias="X-User-ID"),
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db),
):
    """Change password for authenticated user."""
    if str(data.user_id) != str(x_user_id):
        raise HTTPException(status_code=403, detail="User mismatch")

    token = _resolve_token(authorization, "")
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    service = AuthService(db)
    session_check = await service.check_session(
        user_id=str(x_user_id),
        token=token,
        ip_address=get_client_ip(request),
    )
    if session_check.get("status") is not True:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    result = await service.change_password(
        user_id=str(x_user_id),
        current_password=data.current_password,
        new_password=data.new_password,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Password change failed"))

    return {"success": True}


@router.get("/check-username/{username}")
@limiter.limit("30/minute")
async def check_username(
    request: Request, username: str, db: Session = Depends(get_db)
):
    """
    Check if username is available for registration.
    아이디 사용 가능 여부 확인
    """
    # Normalize username
    username_clean = username.lower().strip()
    client_ip = get_client_ip(request)

    ck_ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:12] if client_ip else "unknown"
    logger.info(f"[CheckUsername] Request for: {username_clean} from IP_hash: {ck_ip_hash}")

    try:
        # 유효성 검사
        if not username_clean or len(username_clean) < 4:
            return {"available": False, "message": "아이디는 4자 이상이어야 합니다."}
        
        if len(username_clean) > 50:
            return {"available": False, "message": "아이디가 너무 깁니다 (최대 50자)."}

        if not re.match(r"^[a-z0-9_]+$", username_clean):
            return {
                "available": False,
                "message": "아이디는 영문 소문자, 숫자, 밑줄(_)만 사용 가능합니다.",
            }

        # 1. 기존 활성 사용자 확인
        existing_user = db.query(User).filter(User.username == username_clean).first()
        if existing_user:
            logger.info(f"[CheckUsername] Forbidden: Username exists in User table: {username_clean}")
            return {"available": False, "message": "이미 사용 중인 아이디입니다."}

        # 2. 대기 중인 가입 요청 또는 자동 승인된 요청 기록 확인 (RegistrationRequest unique constraint 때문)
        # RegistrationRequest에도 동일한 아이디가 있으면 (상태 불문) 충돌 가능성이 있음
        existing_reg = (
            db.query(RegistrationRequest)
            .filter(RegistrationRequest.username == username_clean)
            .first()
        )
        
        if existing_reg:
            if existing_reg.status == RequestStatus.PENDING:
                logger.info(f"[CheckUsername] Forbidden: Pending request exists: {username_clean}")
                return {"available": False, "message": "승인 대기 중인 아이디입니다."}
            elif existing_reg.status == RequestStatus.APPROVED:
                # 이미 승인되었는데 User 테이블에 없으면 (데이터 불일치 혹은 삭제)
                # registration.py에서 기존 요청 삭제 후 재등록 허용하므로 True 반환
                logger.warning(f"[CheckUsername] Warning: Approved request without User record: {username_clean}")
                return {"available": True, "message": "사용 가능한 아이디입니다."}

        logger.info(f"[CheckUsername] Success: Username {username_clean} is available")
        return {"available": True, "message": "사용 가능한 아이디입니다."}
    except Exception as e:
        logger.error(f"[CheckUsername] Error checking username '{username_clean}': {e}", exc_info=True)
        # Security: Do not expose internal error details to users
        return {"available": False, "message": "서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요."}


@router.post("/work/check", response_model=CheckWorkResponse)
@limiter.limit("60/minute")
async def check_work(
    request: Request,
    data: UseWorkRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
):
    """
    Check if user can perform work (has remaining work count).
    작업 가능 여부 확인 (잔여 작업 횟수 확인)
    """
    token = _resolve_token(authorization, data.token)
    service = AuthService(db)
    return await service.check_work_available(user_id=data.user_id, token=token)


@router.post("/work/use", response_model=UseWorkResponse)
@limiter.limit("60/minute")
async def use_work(
    request: Request,
    data: UseWorkRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
):
    """
    Increment work_used after successful work completion.
    작업 완료 후 사용 횟수 증가
    """
    token = _resolve_token(authorization, data.token)
    service = AuthService(db)
    return await service.use_work(user_id=data.user_id, token=token)
