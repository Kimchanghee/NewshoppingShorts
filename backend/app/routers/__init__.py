"""
API Routers
- auth: 인증 관련 API 엔드포인트
- registration: 회원가입 요청 API 엔드포인트
- admin: 관리자 API 엔드포인트
"""
from app.routers.auth import router as auth_router
from app.routers.registration import router as registration_router
from app.routers.admin import router as admin_router

__all__ = [
    'auth_router',
    'registration_router',
    'admin_router',
]
