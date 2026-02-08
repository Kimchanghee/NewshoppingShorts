import logging
import sys
import os
from uuid import uuid4
from fastapi import FastAPI, Request, Header, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from app.errors import AppError
from app.routers import auth, registration, admin, subscription, payment
from app.routers.auth import limiter, rate_limit_exceeded_handler
from app.configuration import get_settings
from app.database import init_db

# 로깅 설정 - 모든 로그를 터미널에 출력
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# SQLAlchemy 로그 레벨 조정 (너무 많은 로그 방지)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
settings = get_settings()

# Disable docs in production
docs_url = "/docs" if settings.ENVIRONMENT != "production" else None
redoc_url = "/redoc" if settings.ENVIRONMENT != "production" else None

app = FastAPI(
    title="SSMaker Auth API",
    version="2.0.0",
    docs_url=docs_url,
    redoc_url=redoc_url,
)


from sqlalchemy import text
from app.database import engine

def run_auto_migration():
    """Directly attempt to add missing columns and ignore if already exists (1060)"""
    logger.info("Starting schema auto-migration...")
    
    with engine.connect() as conn:
        # Tables and columns to ensure
        migrations = {
            "users": [
                ("user_type", "ENUM('trial', 'subscriber', 'admin') DEFAULT 'trial'"),
                ("current_task", "VARCHAR(255) NULL"),
                ("is_online", "BOOLEAN DEFAULT FALSE"),
                ("last_heartbeat", "TIMESTAMP NULL"),
                ("app_version", "VARCHAR(20) NULL"),
                ("trial_cycle_started_at", "TIMESTAMP NULL"),
            ],
            "registration_requests": [
                ("email", "VARCHAR(255) NULL")
            ]
        }
        
        for table, columns in migrations.items():
            for col, type_def in columns:
                try:
                    # Direct ALTER TABLE attempt
                    conn.execute(text(f"ALTER TABLE `{table}` ADD COLUMN `{col}` {type_def}"))
                    logger.info(f"Successfully added column {table}.{col}")
                except Exception as e:
                    # Ignore "Duplicate column name" error (1060)
                    if "1060" in str(e) or "Duplicate column" in str(e):
                        logger.info(f"Column {table}.{col} already exists, skipping.")
        conn.commit()
    logger.info("Schema auto-migration finished.")

@app.on_event("startup")
async def startup_event():
    """Initialize database tables and run migrations on startup"""
    logger.info("Initializing SSMaker Auth API...")
    
    try:
        # 1. First ensure tables exist
        init_db()
        
        # 2. Then ensure columns exist (migrations)
        run_auto_migration()
    except Exception as e:
        logger.error(f"Startup error during DB init/migration: {e}", exc_info=True)


# Register rate limiter with app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


# Global AppError handler
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    """
    Global error handler for AppError exceptions.
    Provides consistent error response format.
    """
    is_production = settings.ENVIRONMENT == "production"

    # Log error with details (internal only)
    logger.error(
        f"AppError: code={exc.code} status={exc.status} "
        f"request_id={exc.request_id} details={exc.details}"
    )

    return JSONResponse(
        status_code=exc.status,
        content=exc.to_dict(is_production=is_production),
    )


# Sensitive field names that must NEVER appear in validation error responses
_SENSITIVE_FIELDS = frozenset(
    {
        "pw",
        "password",
        "key",
        "token",
        "secret",
        "api_key",
        "authorization",
        "card_no",
        "cardpw",
        "card_pw",
        "enc_bill",
        "linkkey",
        "linkval",
        "buyer_auth_no",
        "buyer_phone",
        "exp_month",
        "exp_year",
        "rebill_no",
    }
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """
    Sanitize Pydantic 422 validation errors to prevent sensitive data leaks.
    Strips 'input' values for fields like pw, password, key, token, etc.
    Also strips non-JSON-serializable objects (e.g. ValueError in ctx).
    """
    safe_details = []
    for err in exc.errors():
        sanitized = {}
        for k, v in err.items():
            if k == "input":
                continue  # handle separately below
            if k == "ctx":
                # ctx may contain non-serializable objects (ValueError, etc.)
                # Only keep simple string/number values
                try:
                    sanitized[k] = {
                        ck: str(cv) if not isinstance(cv, (str, int, float, bool, type(None))) else cv
                        for ck, cv in v.items()
                    } if isinstance(v, dict) else str(v)
                except Exception:
                    pass  # skip unserializable ctx entirely
                continue
            sanitized[k] = v

        # Only include 'input' if the field is NOT sensitive
        field_names = {str(loc).lower() for loc in err.get("loc", [])}
        if not field_names & _SENSITIVE_FIELDS:
            if "input" in err:
                inp = err["input"]
                # Ensure input is serializable
                if isinstance(inp, (str, int, float, bool, type(None), list, dict)):
                    sanitized["input"] = inp

        safe_details.append(sanitized)

    request_id = str(uuid4())
    logger.warning(
        f"ValidationError: request_id={request_id} path={request.url.path} "
        f"errors={len(safe_details)}"
    )

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "입력값이 올바르지 않습니다.",
                "requestId": request_id,
                "details": safe_details,
            },
        },
    )


# Catch-all for unhandled exceptions (prevent stack trace leaks in production)
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = str(uuid4())
    logger.error(
        f"UnhandledException: request_id={request_id} path={request.url.path} "
        f"error={type(exc).__name__}: {exc}",
        exc_info=True,
    )
    is_production = settings.ENVIRONMENT == "production"
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "서버 오류가 발생했습니다." if is_production else str(exc),
                "requestId": request_id,
            },
        },
    )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all API requests and responses"""

    async def dispatch(self, request: Request, call_next) -> Response:
        # 요청 로깅
        client_ip = request.client.host if request.client else "unknown"
        logger.info(f">>> {request.method} {request.url.path} | IP: {client_ip}")

        try:
            response = await call_next(request)
            # 응답 로깅
            logger.info(
                f"<<< {request.method} {request.url.path} | Status: {response.status_code}"
            )
            return response
        except Exception as e:
            logger.error(f"!!! {request.method} {request.url.path} | Error: {str(e)}")
            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add comprehensive security headers to all responses (OWASP recommended)"""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        # XSS / injection prevention
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"  # Modern: rely on CSP, disable legacy filter
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        # Content Security Policy - API-only, deny all content embedding
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        # Permissions Policy - disable all browser features
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        # HSTS in production (preload-ready)
        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        # Remove server identification headers
        if "server" in response.headers:
            del response.headers["server"]
        return response


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """Audit log for admin/sensitive endpoints"""
    _AUDIT_PREFIXES = ("/user/admin/", "/user/register/approve", "/user/register/reject",
                       "/user/subscription/approve", "/user/subscription/reject",
                       "/payments/webhook", "/payments/mock/", "/payments/payapp/webhook",
                       "/payments/payapp/card/", "/payments/payapp/subscribe/",
                       "/app/version/update")

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        needs_audit = any(path.startswith(p) for p in self._AUDIT_PREFIXES)
        if not needs_audit:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        audit_logger = logging.getLogger("audit")
        audit_logger.info(
            f"[AUDIT] {request.method} {path} | IP: {client_ip} | "
            f"Admin-Key: {'present' if request.headers.get('x-admin-api-key') else 'absent'}"
        )

        response = await call_next(request)

        audit_logger.info(
            f"[AUDIT] {request.method} {path} | Status: {response.status_code}"
        )
        return response


# Security headers middleware (added first, executed last)
app.add_middleware(SecurityHeadersMiddleware)

# Audit logging middleware (before request logging to capture admin actions)
app.add_middleware(AuditLoggingMiddleware)

# Request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# CORS middleware - validate credentials with origins
allow_credentials = "*" not in settings.ALLOWED_ORIGINS
if "*" in settings.ALLOWED_ORIGINS and settings.ENVIRONMENT == "production":
    logger.error("CRITICAL: CORS wildcard with credentials is insecure!")
    allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-ID",
        "X-Admin-API-Key",
        "X-User-ID",
    ],
)

# Ensure static directory exists before mounting
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)
    logger.info(f"Created missing static directory at {static_dir}")

app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    return {"status": "ok", "service": "SSMaker Auth API"}


# Include routers
app.include_router(auth.router)
app.include_router(registration.router)
app.include_router(admin.router)
app.include_router(subscription.router)
app.include_router(payment.router)

@app.get("/health")
async def health():
    return {"status": "healthy"}

# ===== Auto Update API =====
# 최신 버전 정보 (배포 시 이 값을 업데이트)
_DEFAULT_DOWNLOAD_URL = os.getenv("APP_DOWNLOAD_URL", "https://github.com/Kimchanghee/NewshoppingShorts/releases/download/v1.3.20/ssmaker_v1.3.20.exe")

APP_VERSION_INFO = {
    "version": "1.3.20",
    "min_required_version": "1.0.0",
    "download_url": _DEFAULT_DOWNLOAD_URL,
    "release_notes": """버전 1.3.20 업데이트:

🔄 자동 업데이트 안정화
• 이전 버전에서 최신 버전으로 자동 업데이트가 안 되던 문제 수정
• 파일 해시 검증을 선택적으로 변경 (해시 있으면 검증, 없으면 경고만)
• 업데이트 다운로드 및 재시작 안정성 개선

✅ 포함된 기능
• 게임 스타일 자동 업데이트 (사용자 확인 불필요)
• 업데이트 완료 후 릴리즈 노트 표시
• 구독 요금제 월 단위 가격 표시""",
    "is_mandatory": False,
    "update_channel": "stable",
    "file_hash": "",
}


class VersionUpdateRequest(BaseModel):
    """Request model for version update"""
    version: str
    download_url: str
    release_notes: Optional[str] = None
    is_mandatory: bool = False
    min_required_version: Optional[str] = None
    file_hash: Optional[str] = None  # SHA256 hash of the download file


@app.get("/app/version")
async def get_app_version():
    """
    Get latest app version info for auto-update.
    자동 업데이트를 위한 최신 앱 버전 정보 반환.

    Returns:
        {
            "version": "1.0.1",
            "min_required_version": "1.0.0",
            "download_url": "https://...",
            "release_notes": "...",
            "is_mandatory": false
        }
    """
    return APP_VERSION_INFO


@app.post("/app/version/update")
async def update_app_version(
    request: VersionUpdateRequest,
    authorization: str = Header(None)
):
    """
    Update app version info (CI/CD endpoint).
    GitHub Actions에서 빌드 후 버전 정보를 업데이트하는 엔드포인트.

    Requires Bearer token authentication.
    """
    global APP_VERSION_INFO

    # Validate authorization
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")

    token = authorization[7:]  # Remove "Bearer " prefix

    # Check against ADMIN_API_KEY from settings (constant-time comparison)
    import secrets as _secrets
    expected_key = settings.ADMIN_API_KEY
    if not expected_key or not _secrets.compare_digest(token, expected_key):
        logger.warning("Invalid API key attempt for version update")
        raise HTTPException(status_code=403, detail="Invalid API key")

    # Atomic replacement - build new dict then assign
    new_info = {**APP_VERSION_INFO}
    new_info["version"] = request.version
    new_info["download_url"] = request.download_url
    if request.release_notes:
        new_info["release_notes"] = request.release_notes
    if request.min_required_version:
        new_info["min_required_version"] = request.min_required_version
    new_info["is_mandatory"] = request.is_mandatory
    if request.file_hash:
        new_info["file_hash"] = request.file_hash
    APP_VERSION_INFO = new_info

    logger.info(f"App version updated to {request.version} by CI/CD")

    return {
        "success": True,
        "message": f"Version updated to {request.version}",
        "version_info": APP_VERSION_INFO
    }


@app.get("/app/version/check")
async def check_app_version(current_version: str = Query(..., max_length=20)):
    """
    Check if update is available.
    업데이트 가능 여부 확인.
    
    Args:
        current_version: Current client version (e.g., "1.0.0")
    
    Returns:
        {
            "update_available": true/false,
            "current_version": "1.0.0",
            "latest_version": "1.0.1",
            "download_url": "https://...",
            "is_mandatory": false
        }
    """
    latest_version = APP_VERSION_INFO["version"]
    min_required = APP_VERSION_INFO.get("min_required_version", "0.0.0")
    
    # Parse versions for comparison
    def parse_ver(v: str):
        try:
            parts = v.strip().split('.')
            return tuple(int(p) for p in parts[:3])
        except (ValueError, IndexError):
            return (0, 0, 0)
    
    current_tuple = parse_ver(current_version)
    latest_tuple = parse_ver(latest_version)
    min_tuple = parse_ver(min_required)
    
    update_available = current_tuple < latest_tuple
    is_mandatory = current_tuple < min_tuple
    
    return {
        "update_available": update_available,
        "current_version": current_version,
        "latest_version": latest_version,
        "download_url": APP_VERSION_INFO.get("download_url"),
        "release_notes": APP_VERSION_INFO.get("release_notes", ""),
        "is_mandatory": is_mandatory,
        "file_hash": APP_VERSION_INFO.get("file_hash", ""),
    }
