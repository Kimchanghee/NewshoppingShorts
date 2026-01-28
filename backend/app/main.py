import logging
import sys
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from app.routers import auth, registration, admin
from app.routers.auth import limiter, rate_limit_exceeded_handler
from app.config import get_settings
from app.database import init_db

# 로깅 설정 - 모든 로그를 터미널에 출력
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
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


@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup"""
    logger.info("Starting application...")
    # In production, tables should already exist via migrations
    # Only attempt init_db in development
    if settings.ENVIRONMENT != "production":
        try:
            init_db()
            logger.info("Database tables initialized successfully")
        except Exception as e:
            logger.warning(f"Database init skipped (may already exist): {e}")
    else:
        logger.info("Production mode - skipping table creation (use migrations)")


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
            logger.info(f"<<< {request.method} {request.url.path} | Status: {response.status_code}")
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
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
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
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Admin-API-Key"],
)

# Include routers
app.include_router(auth.router)
app.include_router(registration.router)
app.include_router(admin.router)


@app.get("/")
async def root():
    return {"status": "ok", "service": "SSMaker Auth API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
