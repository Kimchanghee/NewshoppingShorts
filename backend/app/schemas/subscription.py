"""
Subscription Request Schemas
구독 신청 스키마

체험판 사용자의 구독 신청 관련 Pydantic 모델
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class SubscriptionRequestStatusEnum(str, Enum):
    """구독 신청 상태"""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SubscriptionRequestCreate(BaseModel):
    """구독 신청 생성 스키마"""
    message: Optional[str] = Field(None, max_length=500, description="구독 신청 메시지")


class SubscriptionRequestResponse(BaseModel):
    """구독 신청 응답 스키마"""
    id: int
    user_id: int
    username: Optional[str] = None
    status: SubscriptionRequestStatusEnum
    requested_work_count: int
    message: Optional[str] = None
    admin_response: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SubscriptionRequestList(BaseModel):
    """구독 신청 목록 응답 스키마"""
    requests: List[SubscriptionRequestResponse]
    total: int
    page: int
    page_size: int


class ApproveSubscriptionRequest(BaseModel):
    """구독 승인 요청 스키마"""
    request_id: int = Field(..., description="승인할 요청 ID")
    work_count: int = Field(default=-1, ge=-1, description="작업 횟수 (-1 = 무제한)")
    subscription_days: int = Field(default=30, ge=1, le=365, description="구독 기간 (일)")
    admin_response: Optional[str] = Field(None, max_length=500, description="관리자 응답 메시지")


class RejectSubscriptionRequest(BaseModel):
    """구독 거절 요청 스키마"""
    request_id: int = Field(..., description="거절할 요청 ID")
    admin_response: Optional[str] = Field(None, max_length=500, description="거절 사유")


class SubscriptionResponse(BaseModel):
    """일반 응답 스키마"""
    success: bool
    message: str
    data: Optional[dict] = None


class SubscriptionStatusResponse(BaseModel):
    """구독 상태 응답 스키마"""
    success: bool
    is_trial: bool = Field(..., description="체험판 여부")
    work_count: int = Field(..., description="총 작업 횟수 (-1 = 무제한)")
    work_used: int = Field(..., description="사용한 작업 횟수")
    remaining: int = Field(..., description="남은 작업 횟수 (-1 = 무제한)")
    can_work: bool = Field(..., description="작업 가능 여부")
    subscription_expires_at: Optional[str] = None
    has_pending_request: bool = Field(default=False, description="대기 중인 구독 신청 있음")
