import logging
import sys
import os
import re
import hashlib
import hmac
import json
import asyncio
import time
import urllib.error
import urllib.request
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
from app.utils.billing_crypto import decrypt_billing_key, validate_billing_crypto_startup
from app.scheduler.auth_maintenance import cleanup_auth_records_once, run_auth_cleanup_loop

# 濡쒓퉭 ?ㅼ젙 - 紐⑤뱺 濡쒓렇瑜??곕??먯뿉 異쒕젰
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# SQLAlchemy 濡쒓렇 ?덈꺼 議곗젙 (?덈Т 留롮? 濡쒓렇 諛⑹?)
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


def _calc_billing_key_hash(enc_bill: str) -> str:
    return hashlib.sha256(enc_bill.encode("utf-8")).hexdigest()


def _ensure_billing_key_hash_index(conn) -> None:
    """Backfill billing key hashes and add the duplicate-protection index."""
    try:
        rows = conn.execute(
            text(
                """
                SELECT id, enc_bill
                FROM `billing_keys`
                WHERE enc_bill_hash IS NULL OR enc_bill_hash = ''
                """
            )
        ).fetchall()
    except Exception as e:
        logger.debug("billing_keys hash backfill skipped: %s", e)
        return

    for row in rows:
        try:
            raw_enc_bill = decrypt_billing_key(row[1])
            conn.execute(
                text("UPDATE `billing_keys` SET enc_bill_hash = :hash WHERE id = :id"),
                {"hash": _calc_billing_key_hash(raw_enc_bill), "id": row[0]},
            )
        except Exception as e:
            logger.warning("billing_keys hash backfill skipped for id=%s: %s", row[0], e)

    try:
        missing_count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM `billing_keys`
                WHERE enc_bill_hash IS NULL OR enc_bill_hash = ''
                """
            )
        ).scalar() or 0
    except Exception:
        missing_count = 1

    if missing_count:
        logger.warning("billing_keys hash index skipped because %s rows are not backfilled", missing_count)
        return

    try:
        conn.execute(text("ALTER TABLE `billing_keys` DROP INDEX `uq_user_enc_bill`"))
    except Exception as e:
        msg = str(e).lower()
        if "1091" not in msg and "can't drop" not in msg and "check that column/key exists" not in msg:
            logger.debug("Old billing key index drop skipped: %s", e)

    try:
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX `uq_user_enc_bill_hash`
                ON `billing_keys` (`user_id`, `enc_bill_hash`)
                """
            )
        )
        logger.info("billing_keys hash unique index ensured.")
    except Exception as e:
        msg = str(e).lower()
        if "1061" in msg or "duplicate key name" in msg or "already exists" in msg:
            logger.debug("billing_keys hash unique index already exists.")
        else:
            logger.warning("billing_keys hash unique index creation skipped: %s", e)


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
                    ("ym_news_opt_in", "BOOLEAN DEFAULT FALSE"),
                ],
                "registration_requests": [
                    ("email", "VARCHAR(255) NULL"),
                    ("ym_news_opt_in", "BOOLEAN DEFAULT FALSE"),
                ],
                "billing_keys": [
                    # SHA-256 hex of enc_bill for duplicate checks without indexing encrypted secret material.
                    ("enc_bill_hash", "CHAR(64) NOT NULL DEFAULT ''"),
                ],
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

            _ensure_billing_key_hash_index(conn)
                            
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
                "message": "?낅젰媛믪씠 ?щ컮瑜댁? ?딆뒿?덈떎.",
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
                "message": "?쒕쾭 ?ㅻ쪟媛 諛쒖깮?덉뒿?덈떎.",
                "requestId": request_id,
            },
        },
    )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all API requests and responses"""

    async def dispatch(self, request: Request, call_next) -> Response:
        # ?붿껌 濡쒓퉭
        client_ip = request.client.host if request.client else "unknown"
        logger.info(f">>> {request.method} {request.url.path} | IP: {client_ip}")

        try:
            response = await call_next(request)
            # ?묐떟 濡쒓퉭
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
# 理쒖떊 踰꾩쟾 ?뺣낫 (諛고룷 ????媛믪쓣 ?낅뜲?댄듃)
_DEFAULT_APP_VERSION = (os.getenv("APP_LATEST_VERSION", "1.4.21") or "1.4.21").strip()
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
    "release_notes": """### v1.4.21 업데이트
- 회원 DB에 YM 소식/정보 수신 동의(ym_news_opt_in) 항목 추가
- 회원가입/관리자 조회 API에 수신 동의 필드 반영
- 사용자 활동 로그 보관 정책을 환경변수 기반(기본 7일)으로 개선""",
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
_GITHUB_RELEASE_API_URL = os.getenv(
    "APP_VERSION_GITHUB_RELEASE_API_URL",
    "https://api.github.com/repos/Kimchanghee/NewshoppingShorts/releases/latest",
).strip()
_GITHUB_VERSION_CACHE_TTL_SECONDS = int(os.getenv("APP_VERSION_GITHUB_CACHE_TTL_SECONDS", "300") or "300")
_GITHUB_VERSION_CACHE: dict = {"checked_at": 0.0, "info": None}


def _parse_version_tuple(version: str) -> tuple[int, int, int]:
    try:
        parts = str(version or "").strip().split(".")
        parsed = [int(p) for p in parts[:3]]
        while len(parsed) < 3:
            parsed.append(0)
        return tuple(parsed[:3])
    except (ValueError, TypeError):
        return (0, 0, 0)


def _extract_sha256(text_value: str) -> str:
    match = re.search(r"\b([a-fA-F0-9]{64})\b", str(text_value or ""))
    return match.group(1).lower() if match else ""


def _fetch_github_release_version_info() -> Optional[dict]:
    if not _GITHUB_RELEASE_API_URL:
        return None

    now = time.time()
    cached_info = _GITHUB_VERSION_CACHE.get("info")
    checked_at = float(_GITHUB_VERSION_CACHE.get("checked_at") or 0)
    if cached_info is not None and now - checked_at < _GITHUB_VERSION_CACHE_TTL_SECONDS:
        return cached_info

    try:
        request = urllib.request.Request(
            _GITHUB_RELEASE_API_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "SSMaker-Version-API",
            },
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))

        latest_version = str(payload.get("tag_name", "")).strip().lstrip("vV")
        if not latest_version:
            return None

        assets = payload.get("assets", []) or []
        preferred_name = f"ssmaker_setup_v{latest_version}.exe"
        installer_asset = next(
            (
                asset
                for asset in assets
                if str(asset.get("name", "")).lower() == preferred_name
            ),
            None,
        )
        if installer_asset is None:
            installer_asset = next(
                (
                    asset
                    for asset in assets
                    if str(asset.get("name", "")).lower().endswith(".exe")
                ),
                None,
            )
        if installer_asset is None:
            return None

        digest = str(installer_asset.get("digest", "")).strip()
        file_hash = digest.split(":", 1)[1].strip() if digest.lower().startswith("sha256:") else ""
        if not file_hash:
            file_hash = _extract_sha256(payload.get("body", ""))
        download_url = str(installer_asset.get("browser_download_url", "")).strip()
        if not download_url or not file_hash:
            return None

        info = {
            "version": latest_version,
            "download_url": download_url,
            "release_notes": payload.get("body", ""),
            "is_mandatory": False,
            "file_hash": file_hash,
            "update_channel": "stable",
        }
        _GITHUB_VERSION_CACHE["checked_at"] = now
        _GITHUB_VERSION_CACHE["info"] = info
        return info
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
        logger.warning("GitHub version fallback failed: %s", e)
        _GITHUB_VERSION_CACHE["checked_at"] = now
        _GITHUB_VERSION_CACHE["info"] = None
        return None


def _get_effective_app_version_info() -> dict:
    effective_info = dict(APP_VERSION_INFO)
    github_info = _fetch_github_release_version_info()
    if not github_info:
        return effective_info

    if _parse_version_tuple(str(effective_info.get("version", "0.0.0"))) < _parse_version_tuple(
        str(github_info.get("version", "0.0.0"))
    ):
        merged = dict(effective_info)
        merged.update(github_info)
        merged.setdefault("min_required_version", effective_info.get("min_required_version", "1.0.0"))
        return merged
    return effective_info


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
    ?먮룞 ?낅뜲?댄듃瑜??꾪븳 理쒖떊 ??踰꾩쟾 ?뺣낫 諛섑솚.

    Returns:
        {
            "version": "1.0.1",
            "min_required_version": "1.0.0",
            "download_url": "https://...",
            "release_notes": "...",
            "is_mandatory": false
        }
    """
    return _get_effective_app_version_info()


@app.get("/free/lately/")
async def get_legacy_free_lately(item: Optional[int] = Query(None)):
    """Legacy desktop-client version endpoint compatibility."""
    return {
        **_get_effective_app_version_info(),
        "item": item,
    }


@app.post("/app/version/update")
async def update_app_version(
    request: VersionUpdateRequest,
    authorization: str = Header(None),
    x_update_signature: str = Header(None, alias="X-Update-Signature"),
):
    """
    Update app version info (CI/CD endpoint).
    GitHub Actions?먯꽌 鍮뚮뱶 ??踰꾩쟾 ?뺣낫瑜??낅뜲?댄듃?섎뒗 ?붾뱶?ъ씤??

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
    ?낅뜲?댄듃 媛???щ? ?뺤씤.
    
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
    version_info = _get_effective_app_version_info()
    latest_version = version_info["version"]
    min_required = version_info.get("min_required_version", "0.0.0")
    
    current_tuple = _parse_version_tuple(current_version)
    latest_tuple = _parse_version_tuple(latest_version)
    min_tuple = _parse_version_tuple(min_required)
    
    update_available = current_tuple < latest_tuple
    is_mandatory = current_tuple < min_tuple
    
    return {
        "update_available": update_available,
        "current_version": current_version,
        "latest_version": latest_version,
        "download_url": version_info.get("download_url"),
        "release_notes": version_info.get("release_notes", ""),
        "is_mandatory": is_mandatory,
        "file_hash": version_info.get("file_hash", ""),
    }
