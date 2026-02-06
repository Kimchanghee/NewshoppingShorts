import hmac
import os
import re
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Union


class LoginRequest(BaseModel):
    """Login request with validated inputs"""
    id: str = Field(..., min_length=3, max_length=50, description="Username")
    pw: str = Field(..., min_length=6, max_length=128, description="Password")
    key: str = Field(..., max_length=256, description="API key")
    ip: str = Field(..., max_length=45, description="Client IP (legacy, server extracts actual IP)")
    force: bool = False

    @field_validator('id')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Username must be alphanumeric with limited special chars"""
        if not re.match(r'^[a-zA-Z0-9_@.\-]+$', v):
            raise ValueError('Username contains invalid characters')
        return v

    @field_validator('key')
    @classmethod
    def validate_key(cls, v: str) -> str:
        """
        Validate API key using constant-time comparison.
        상수 시간 비교를 사용한 API 키 검증 (타이밍 공격 방지)

        Security: Uses hmac.compare_digest() for constant-time comparison
        to prevent timing attacks that could leak the API key.
        """
        expected_key = os.environ.get("SSMAKER_API_KEY", "")
        if not expected_key:
            raise ValueError('API key not configured on server')

        # Use constant-time comparison to prevent timing attacks
        # 타이밍 공격을 방지하기 위해 상수 시간 비교 사용
        if not hmac.compare_digest(v.encode('utf-8'), expected_key.encode('utf-8')):
            raise ValueError('Invalid API key')
        return v


class LoginResponse(BaseModel):
    """Login response"""
    status: Union[bool, str]
    data: Optional[dict] = None
    message: Optional[str] = None


class LogoutRequest(BaseModel):
    """Logout request with validated inputs"""
    id: str = Field(..., min_length=1, max_length=50, description="User ID")
    key: str = Field(..., min_length=10, max_length=1024, description="JWT token")


class CheckRequest(BaseModel):
    """Session check request with validated inputs"""
    id: str = Field(..., min_length=1, max_length=50, description="User ID")
    key: str = Field(..., min_length=10, max_length=1024, description="JWT token")
    ip: str = Field(..., max_length=45, description="Client IP (legacy)")
    current_task: Optional[str] = Field(None, max_length=200, description="Current task status")
    app_version: Optional[str] = Field(None, max_length=20, description="Client app version")


class UseWorkRequest(BaseModel):
    """Work usage request - 작업 횟수 사용 요청"""
    user_id: str = Field(..., min_length=1, max_length=50, description="User ID")
    token: str = Field(..., min_length=10, max_length=1024, description="JWT token")


class UseWorkResponse(BaseModel):
    """Work usage response - 작업 횟수 사용 응답"""
    success: bool
    message: str
    remaining: Optional[int] = None  # -1 = unlimited
    used: Optional[int] = None


class CheckWorkResponse(BaseModel):
    """Work count check response - 작업 횟수 확인 응답"""
    success: bool
    can_work: bool
    work_count: int  # -1 = unlimited
    work_used: int
    remaining: int  # -1 = unlimited
