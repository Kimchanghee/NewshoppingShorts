import logging
import sys
import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
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
                ("last_heartbeat", "TIMESTAMP NULL")
            ],
            "registration_requests": [
                ("email", "VARCHAR(255) NULL")
            ]
        }
        
        for table, columns in migrations.items():
            for col, type_def in columns:
                try:
                    # Direct ALTER TABLE attempt
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {type_def}"))
                    logger.info(f"Successfully added column {table}.{col}")
                except Exception as e:
                    # Ignore "Duplicate column name" error (1060)
                    if "1060" in str(e) or "Duplicate column" in str(e):
                        logger.info(f"Column {table}.{col} already exists, skipping.")
                    else:
                        logger.warning(f"Failed to add column {table}.{col}: {e}")
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
    """Add security headers to all responses"""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response


# Security headers middleware (added first, executed last)
app.add_middleware(SecurityHeadersMiddleware)

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
APP_VERSION_INFO = {
    "version": "1.0.1", # Bumped for testing
    "min_required_version": "1.0.0",
    "download_url": "https://ssmaker-auth-api-1049571775048.us-central1.run.app/static/ssmaker_setup.exe", # Production URL
    # "download_url": "https://storage.googleapis.com/your-bucket/ssmaker_setup.exe", # Production GCS URL
    "release_notes": "버전 1.0.1 업데이트: 자동 업데이트 기능이 추가되었습니다.",
    "is_mandatory": False,
    "update_channel": "stable",
}


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


@app.get("/app/version/check")
async def check_app_version(current_version: str):
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
    }
