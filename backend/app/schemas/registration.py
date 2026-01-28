"""
Registration Request Schemas
회원가입 요청 스키마

Pydantic 모델을 사용한 요청/응답 검증
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum
import re


class RequestStatusEnum(str, Enum):
    """가입 요청 상태"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RegistrationRequestCreate(BaseModel):
    """회원가입 요청 생성 스키마"""
    name: str = Field(..., min_length=2, max_length=100, description="가입자 명")
    username: str = Field(..., min_length=4, max_length=50, description="사용할 아이디")
    password: str = Field(..., min_length=6, max_length=100, description="비밀번호")
    contact: str = Field(..., min_length=10, max_length=50, description="연락처")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """이름 유효성 검증 및 XSS 방지"""
        import html
        # Strip whitespace
        cleaned = v.strip()
        # HTML escape to prevent XSS
        cleaned = html.escape(cleaned)
        # Only allow letters (Korean, English), numbers, spaces, dots, hyphens
        if not re.match(r'^[\w\s\.\-\u3131-\u3163\uac00-\ud7a3]+$', cleaned, re.UNICODE):
            raise ValueError('이름에 허용되지 않는 문자가 포함되어 있습니다.')
        return cleaned

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """아이디 유효성 검증"""
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('아이디는 영문, 숫자, 밑줄(_)만 사용할 수 있습니다.')
        return v.lower()

    @field_validator('contact')
    @classmethod
    def validate_contact(cls, v: str) -> str:
        """연락처 유효성 검증 (기본적인 형식 체크)"""
        # 숫자와 하이픈만 허용
        cleaned = re.sub(r'[^0-9\-]', '', v)
        if len(cleaned) < 10:
            raise ValueError('올바른 연락처를 입력해주세요.')
        return v


class RegistrationRequestResponse(BaseModel):
    """회원가입 요청 응답 스키마"""
    id: int
    name: str
    username: str
    contact: str
    status: RequestStatusEnum
    created_at: datetime
    updated_at: datetime
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    class Config:
        from_attributes = True


class RegistrationRequestList(BaseModel):
    """회원가입 요청 목록 응답 스키마"""
    requests: List[RegistrationRequestResponse]
    total: int
    page: int
    page_size: int


class ApproveRequest(BaseModel):
    """가입 승인 요청 스키마"""
    request_id: int = Field(..., description="승인할 요청 ID")
    subscription_days: int = Field(default=30, ge=1, le=365, description="구독 기간 (일)")
    work_count: int = Field(default=-1, ge=-1, description="작업 횟수 (-1 = 무제한)")


class RejectRequest(BaseModel):
    """가입 거부 요청 스키마"""
    request_id: int = Field(..., description="거부할 요청 ID")
    reason: Optional[str] = Field(None, max_length=500, description="거부 사유")


class RegistrationResponse(BaseModel):
    """일반 응답 스키마"""
    success: bool
    message: str
    data: Optional[dict] = None
