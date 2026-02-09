import re
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Union


class LoginRequest(BaseModel):
    """Login request with validated inputs"""
    id: str = Field(..., min_length=3, max_length=50, description="Username")
    pw: str = Field(..., min_length=4, max_length=128, description="Password")
    # Deprecated: desktop binaries cannot safely keep a shared client secret.
    # Kept for backward compatibility with older clients that still send `key`.
    key: str = Field("", max_length=256, description="Legacy client key (deprecated)")
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
        # Legacy field: only sanitize format; no shared-secret enforcement.
        return (v or "").strip()


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
    """Work usage request."""
    user_id: str = Field(..., min_length=1, max_length=50, description="User ID")
    token: str = Field(..., min_length=10, max_length=1024, description="JWT token")


class UseWorkResponse(BaseModel):
    """Work usage response."""
    success: bool
    message: str
    remaining: Optional[int] = None  # -1 = unlimited
    used: Optional[int] = None


class CheckWorkResponse(BaseModel):
    """Work count check response."""
    success: bool
    can_work: bool
    work_count: int  # -1 = unlimited
    work_used: int
    remaining: int  # -1 = unlimited
