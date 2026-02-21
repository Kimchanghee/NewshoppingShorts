import logging
import sys
import os
import re
import hashlib
import hmac
import json
import asyncio
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
from app.routers import auth, registration, admin, subscription, payment, logs
from app.routers.auth import limiter, rate_limit_exceeded_handler
from app.configuration import get_settings
from app.database import init_db
from app.utils.billing_crypto import validate_billing_crypto_startup
from app.scheduler.auth_maintenance import cleanup_auth_records_once, run_auth_cleanup_loop

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
_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_auth_cleanup_stop_event: Optional[asyncio.Event] = None
_auth_cleanup_task: Optional[asyncio.Task] = None

# Disable docs and OpenAPI schema in production
_is_prod = settings.ENVIRONMENT == "production"
docs_url = "/docs" if not _is_prod else None
redoc_url = "/redoc" if not _is_prod else None
openapi_url = "/openapi.json" if not _is_prod else None

app = FastAPI(
    title="SSMaker Auth API",
    version="2.0.0",
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
)


from sqlalchemy import text
from app.database import engine

def run_auto_migration():
    """Directly attempt to add missing columns and ignore if already exists (1060)"""
    logger.info("Starting schema auto-migration...")
    
    # Use AUTOCOMMIT for DDL operations to prevent transaction issues
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            # Tables and columns to ensure
            migrations = {
                "users": [
                    ("user_type", "ENUM('trial', 'subscriber', 'admin') DEFAULT 'trial' NOT NULL"),
                    ("current_task", "VARCHAR(255) NULL"),
                    ("is_online", "BOOLEAN DEFAULT FALSE"),
                    ("last_heartbeat", "TIMESTAMP NULL"),
                    ("app_version", "VARCHAR(20) NULL"),
                    ("trial_cycle_started_at", "TIMESTAMP NULL"),
                    ("program_type", "ENUM('ssmaker', 'stmaker') DEFAULT 'ssmaker' NOT NULL"),
                ],
                "registration_requests": [
                    ("email", "VARCHAR(255) NULL")
                ]
            }
            
            # Ensure user_logs table exists
            try:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS `user_logs` (
                        `id` INTEGER NOT NULL AUTO_INCREMENT,
                        `user_id` INTEGER NOT NULL,
                        `level` VARCHAR(20) NOT NULL DEFAULT 'INFO',
                        `action` VARCHAR(255) NOT NULL,
                        `content` TEXT NULL,
                        `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (`id`),
                        INDEX `ix_user_logs_user_id` (`user_id`),
                        INDEX `ix_user_logs_created_at` (`created_at`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """))
                logger.info("user_logs table ensured.")
            except Exception as e:
                logger.warning(f"user_logs table creation warning: {e}")

            for table, columns in migrations.items():
                for col, type_def in columns:
                    try:
                        # Defensive guard: only allow safe SQL identifiers.
                        if not _SQL_IDENTIFIER_RE.fullmatch(table) or not _SQL_IDENTIFIER_RE.fullmatch(col):
                            raise ValueError(f"Unsafe identifier detected: {table}.{col}")
                        # Direct ALTER TABLE attempt
                        conn.execute(text(f"ALTER TABLE `{table}` ADD COLUMN `{col}` {type_def}"))
                        logger.info(f"Successfully added column {table}.{col}")
                    except Exception as e:
                        # Ignore "Duplicate column name" error (1060)
                        msg = str(e).lower()
                        if "1060" in msg or "duplicate column" in msg:
                            logger.debug(f"Column {table}.{col} already exists.")
                        else:
                            # Log other errors but try to proceed
                            logger.warning(f"Migration warning for {table}.{col}: {e}")
                            
    except Exception as e:
        logger.error(f"Migration critical error: {e}", exc_info=True)
    
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
        # 3. Ensure settings table for persistent app metadata.
        _ensure_system_settings_table()
        # 4. Validate billing key crypto at startup (fail fast on bad Fernet key).
        validate_billing_crypto_startup(
            require_key=(settings.ENVIRONMENT == "production")
        )
        # 5. Run one cleanup at startup + periodic cleanup loop.
        cleanup_auth_records_once()
        global _auth_cleanup_task
        global _auth_cleanup_stop_event
        if _auth_cleanup_stop_event is None:
            _auth_cleanup_stop_event = asyncio.Event()
        if _auth_cleanup_task is None or _auth_cleanup_task.done():
            _auth_cleanup_stop_event.clear()
            _auth_cleanup_task = asyncio.create_task(run_auth_cleanup_loop(_auth_cleanup_stop_event))
    except Exception as e:
        logger.error(f"Startup error during DB init/migration: {e}", exc_info=True)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Gracefully stop background maintenance tasks."""
    global _auth_cleanup_task
    if _auth_cleanup_stop_event is not None:
        _auth_cleanup_stop_event.set()
    if _auth_cleanup_task and not _auth_cleanup_task.done():
        try:
            await asyncio.wait_for(_auth_cleanup_task, timeout=5)
        except Exception:
            _auth_cleanup_task.cancel()


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


def _contains_sensitive_keys(value) -> bool:
    """
    Recursively detect whether a payload contains sensitive field names.
    Used to prevent reflected 422 inputs from leaking card/auth secrets.
    """
    if isinstance(value, dict):
        for k, v in value.items():
            if str(k).lower() in _SENSITIVE_FIELDS:
                return True
            if _contains_sensitive_keys(v):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_sensitive_keys(item) for item in value)
    return False


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
                    sanitized[k] = {"sanitized": True}
                continue
            sanitized[k] = v

        # Only include 'input' if the field is NOT sensitive
        field_names = {str(loc).lower() for loc in err.get("loc", [])}
        is_sensitive_location = bool(field_names & _SENSITIVE_FIELDS)
        is_body_level_error = "body" in field_names
        input_has_sensitive_keys = _contains_sensitive_keys(err.get("input"))

        if not is_sensitive_location and not is_body_level_error and not input_has_sensitive_keys:
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
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "서버 오류가 발생했습니다.",
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

# CORS middleware - desktop app uses requests library (not browser),
# so CORS is only relevant if a web admin panel is added later.
# In production, deny all cross-origin browser requests.
if settings.ENVIRONMENT == "production" and "*" in settings.ALLOWED_ORIGINS:
    logger.warning("CORS: Production wildcard overridden to empty (desktop app does not need CORS)")
    _cors_origins: list = []
else:
    _cors_origins = settings.ALLOWED_ORIGINS

allow_credentials = "*" not in _cors_origins and len(_cors_origins) > 0

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
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
app.include_router(logs.router)

@app.get("/health")
async def health():
    return {"status": "healthy"}

# ===== Auto Update API =====
# 최신 버전 정보 (배포 시 이 값을 업데이트)
_DEFAULT_APP_VERSION = (os.getenv("APP_LATEST_VERSION", "1.4.16") or "1.4.16").strip()
_DEFAULT_DOWNLOAD_URL = os.getenv(
    "APP_DOWNLOAD_URL",
    "https://github.com/Kimchanghee/NewshoppingShorts/releases/download/v"
    + _DEFAULT_APP_VERSION
    + "/SSMaker_Setup_v"
    + _DEFAULT_APP_VERSION
    + ".exe",
)

APP_VERSION_INFO = {
    "version": _DEFAULT_APP_VERSION,
    "min_required_version": "1.0.0",
    "download_url": _DEFAULT_DOWNLOAD_URL,
    "release_notes": """### v1.4.16 대형 업데이트
- 샤오홍슈(小红书) 영상 링크 다운로드 공식 지원 추가
- 도우인/틱톡/샤오홍슈 플랫폼 자동 감지 라우터 도입
- 다운로드 모듈 구조 정리 (platforms 분리)
- UI 안내 문구를 도우인 + 샤오홍슈 기준으로 업데이트""",
    "is_mandatory": True,
    "update_channel": "stable",
    "file_hash": "b3b1dea69ced9f2cfdab0765cfe136b830465585cc4736bbf5efc8b168a369ea",
}

_APP_VERSION_INFO_SETTING_KEY = "app_version_info_v1"


def _ensure_system_settings_table() -> None:
    """Ensure key-value settings table exists for small persistent config."""
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS `system_settings` (
                        `setting_key` VARCHAR(128) NOT NULL,
                        `setting_value` TEXT NOT NULL,
                        `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        PRIMARY KEY (`setting_key`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                )
            )
    except Exception as e:
        logger.warning("system_settings ensure warning: %s", e)


def _load_app_version_info_from_db(default_info: dict) -> dict:
    """Load persisted app version info from DB, fallback to defaults."""
    try:
        _ensure_system_settings_table()
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT setting_value
                    FROM system_settings
                    WHERE setting_key = :setting_key
                    LIMIT 1
                    """
                ),
                {"setting_key": _APP_VERSION_INFO_SETTING_KEY},
            ).fetchone()

        if not row:
            return default_info

        raw_value = row[0]
        if not raw_value:
            return default_info

        loaded = json.loads(raw_value)
        if not isinstance(loaded, dict):
            return default_info

        merged = dict(default_info)
        for key in (
            "version",
            "min_required_version",
            "download_url",
            "release_notes",
            "is_mandatory",
            "update_channel",
            "file_hash",
        ):
            if key in loaded:
                merged[key] = loaded[key]
        return merged
    except Exception as e:
        logger.warning("Failed loading APP_VERSION_INFO from DB: %s", e)
        return default_info


def _persist_app_version_info_to_db(version_info: dict) -> None:
    """Persist app version info so restarts do not lose update metadata."""
    try:
        _ensure_system_settings_table()
        payload = json.dumps(version_info, ensure_ascii=False)
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO system_settings (setting_key, setting_value)
                    VALUES (:setting_key, :setting_value)
                    ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
                    """
                ),
                {
                    "setting_key": _APP_VERSION_INFO_SETTING_KEY,
                    "setting_value": payload,
                },
            )
    except Exception as e:
        logger.warning("Failed persisting APP_VERSION_INFO to DB: %s", e)


APP_VERSION_INFO = _load_app_version_info_from_db(APP_VERSION_INFO)


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
    authorization: str = Header(None),
    x_update_signature: str = Header(None, alias="X-Update-Signature"),
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

    # Check against dedicated update API key first.
    # Fallback to ADMIN_API_KEY only in non-production for compatibility.
    import secrets as _secrets
    expected_key = (settings.APP_VERSION_UPDATE_API_KEY or "").strip()
    if settings.ENVIRONMENT == "production" and not expected_key:
        logger.error("APP_VERSION_UPDATE_API_KEY is not configured in production")
        raise HTTPException(status_code=500, detail="Update API key not configured")
    if not expected_key:
        expected_key = settings.ADMIN_API_KEY
        logger.warning("Using ADMIN_API_KEY fallback for /app/version/update (set APP_VERSION_UPDATE_API_KEY)")

    if not expected_key or not _secrets.compare_digest(token, expected_key):
        logger.warning("Invalid API key attempt for version update")
        raise HTTPException(status_code=403, detail="Invalid API key")

    # Optional payload HMAC verification for stronger CI/CD integrity.
    signing_key = (settings.APP_VERSION_UPDATE_HMAC_KEY or "").strip()
    if signing_key:
        if not x_update_signature:
            raise HTTPException(status_code=401, detail="Missing X-Update-Signature")
        provided_sig = str(x_update_signature).strip()
        if provided_sig.lower().startswith("sha256="):
            provided_sig = provided_sig.split("=", 1)[1].strip()
        payload_json = request.model_dump_json(exclude_none=True)
        expected_sig = hmac.new(
            signing_key.encode("utf-8"),
            payload_json.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not _secrets.compare_digest(provided_sig.lower(), expected_sig.lower()):
            logger.warning("Invalid update payload signature")
            raise HTTPException(status_code=403, detail="Invalid update signature")

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
    _persist_app_version_info_to_db(APP_VERSION_INFO)

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
