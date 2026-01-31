import logging
import sys
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from app.routers import auth, registration, admin, subscription
from app.routers.auth import limiter, rate_limit_exceeded_handler
from app.config import get_settings
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
    """Temporary auto-migration for production"""
    try:
        with engine.connect() as conn:
            # Check user_type column
            result = conn.execute(text("SHOW COLUMNS FROM users LIKE 'user_type'"))
            if not result.fetchone():
                logger.info("Migrating: Adding user_type to users table...")
                conn.execute(text("ALTER TABLE users ADD COLUMN user_type ENUM('trial', 'subscriber', 'admin') DEFAULT 'trial'"))
                conn.commit()
                logger.info("Migration successful: user_type added")
            else:
                logger.info("Schema check: user_type column exists")
    except Exception as e:
        logger.error(f"Auto-migration error: {e}")

@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup"""
    logger.info("Starting application...")
    
    # Force init_db and migration in production to ensure schema is correct
    try:
        init_db()
        logger.info("Database tables initialized successfully")
        
        # Run column migration
        run_auto_migration()
    except Exception as e:
        logger.warning(f"Database init/migration warning: {e}")


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

# Include routers
app.include_router(auth.router)
app.include_router(registration.router)
app.include_router(admin.router)
app.include_router(subscription.router)


@app.get("/")
async def root():
    return {"status": "ok", "service": "SSMaker Auth API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/free/lately")
async def get_version(item: int = 22):
    """Version check endpoint (legacy compatibility)"""
    return {"version": "1.0.0", "item": item}


# ===== Auto Update API =====
# 최신 버전 정보 (배포 시 이 값을 업데이트)
APP_VERSION_INFO = {
    "version": "1.0.0",
    "min_required_version": "1.0.0",
    "download_url": None,  # 배포 시 설정: "https://example.com/ssmaker_v1.0.1.exe"
    "release_notes": "Initial release",
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
