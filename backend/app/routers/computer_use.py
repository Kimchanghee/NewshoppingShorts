"""Computer Use bridge router."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from sqlalchemy.orm import Session

from app.configuration import get_settings
from app.database import get_db
from app.dependencies import get_current_user_id
from app.models.computer_use_job import ComputerUseJob, ComputerUseJobStatus
from app.models.user import User
from app.models.user_log import UserLog
from app.utils.ip_utils import get_client_ip
from app.utils.subscription_utils import is_subscription_active

logger = logging.getLogger(__name__)
settings = get_settings()

limiter = Limiter(key_func=get_client_ip)
router = APIRouter(prefix="/v1/computer-use", tags=["computer_use_bridge"])


class ComputerUseJobCreate(BaseModel):
    """Bridge job request payload from desktop app."""

    user_id: Optional[int] = None
    scope: str = Field(default="all", max_length=64)
    step_id: str = Field(default="", max_length=96)
    step_title: str = Field(default="", max_length=200)
    prompt: str = Field(min_length=20, max_length=12000)


class ComputerUseJobResponse(BaseModel):
    """Bridge intake response."""

    success: bool
    job_id: str
    status: str
    message: str
    queued_at: str


class ComputerUseJobStatusResponse(BaseModel):
    """Bridge job status response."""

    success: bool
    job_id: str
    status: str
    scope: str
    step_id: str
    step_title: str
    attempt_count: int
    queued_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    result_summary: Optional[str] = None
    error_message: Optional[str] = None


def _user_type_value(user: User) -> str:
    value = getattr(user, "user_type", None)
    if hasattr(value, "value"):
        return str(value.value)
    return str(value or "trial")


def is_paid_entitled_user(user: User) -> bool:
    """Determine whether user can use paid-only computer-use bridge."""
    user_type = _user_type_value(user)
    if user_type == "admin":
        return True

    expiry = getattr(user, "subscription_expires_at", None)
    work_count = int(getattr(user, "work_count", 0) or 0)

    if user_type == "subscriber":
        return expiry is None or is_subscription_active(expiry)

    # Defensive fallback: some old rows may carry unlimited work_count.
    if work_count == -1 and user_type != "trial":
        return True
    return False


def _verify_optional_bridge_key(x_bridge_api_key: Optional[str]) -> None:
    """Enforce bridge API key when configured on server."""
    required = str(settings.COMPUTER_USE_BRIDGE_API_KEY or "").strip()
    if not required:
        return
    provided = str(x_bridge_api_key or "").strip()
    if not provided or not secrets.compare_digest(provided, required):
        raise HTTPException(status_code=401, detail="Invalid bridge API key")


def _iso_utc(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _status_value(value) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    return str(value or "")


@router.post("/jobs", response_model=ComputerUseJobResponse)
@limiter.limit("30/minute")
async def create_computer_use_job(
    request: Request,
    payload: ComputerUseJobCreate,
    current_user_id: int = Depends(get_current_user_id),
    x_bridge_api_key: Optional[str] = Header(
        default=None,
        alias="X-Bridge-API-Key",
        description="Optional server-side bridge key",
    ),
    db: Session = Depends(get_db),
):
    """Create one centralized computer-use job for a paid user."""
    _verify_optional_bridge_key(x_bridge_api_key)

    user_id = int(current_user_id)
    if payload.user_id is not None and int(payload.user_id) != user_id:
        raise HTTPException(status_code=403, detail="User mismatch")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not is_paid_entitled_user(user):
        raise HTTPException(status_code=403, detail="Paid subscription required")

    job_id = str(uuid4())
    now = datetime.now(timezone.utc)
    prompt_text = str(payload.prompt or "")
    prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()

    log_body = {
        "job_id": job_id,
        "status": ComputerUseJobStatus.QUEUED.value,
        "scope": str(payload.scope or "all"),
        "step_id": str(payload.step_id or ""),
        "step_title": str(payload.step_title or ""),
        "prompt_sha256": prompt_hash,
        "prompt_length": len(prompt_text),
        "queued_at": now.isoformat(),
    }

    try:
        job = ComputerUseJob(
            job_id=job_id,
            user_id=user_id,
            scope=str(payload.scope or "all"),
            step_id=str(payload.step_id or ""),
            step_title=str(payload.step_title or ""),
            prompt=prompt_text,
            status=ComputerUseJobStatus.QUEUED,
            attempt_count=0,
        )
        db.add(job)
        db.add(
            UserLog(
                user_id=user_id,
                level="INFO",
                action="computer_use_bridge_job_queued",
                content=json.dumps(log_body, ensure_ascii=False),
            )
        )
        db.commit()
        db.refresh(job)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to persist computer-use bridge job: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to queue job") from exc

    queued_at = _iso_utc(job.created_at) or now.isoformat()
    return ComputerUseJobResponse(
        success=True,
        job_id=job_id,
        status=ComputerUseJobStatus.QUEUED.value,
        message="Computer Use job queued",
        queued_at=queued_at,
    )


@router.get("/jobs/{job_id}", response_model=ComputerUseJobStatusResponse)
@limiter.limit("120/minute")
async def get_computer_use_job_status(
    request: Request,
    job_id: str,
    current_user_id: int = Depends(get_current_user_id),
    x_bridge_api_key: Optional[str] = Header(
        default=None,
        alias="X-Bridge-API-Key",
        description="Optional server-side bridge key",
    ),
    db: Session = Depends(get_db),
):
    """Return one computer-use job status for the authenticated owner."""
    _verify_optional_bridge_key(x_bridge_api_key)

    user_id = int(current_user_id)
    job = (
        db.query(ComputerUseJob)
        .filter(
            ComputerUseJob.job_id == str(job_id or "").strip(),
            ComputerUseJob.user_id == user_id,
        )
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return ComputerUseJobStatusResponse(
        success=True,
        job_id=str(job.job_id),
        status=_status_value(job.status),
        scope=str(job.scope or "all"),
        step_id=str(job.step_id or ""),
        step_title=str(job.step_title or ""),
        attempt_count=int(job.attempt_count or 0),
        queued_at=_iso_utc(job.created_at) or "",
        started_at=_iso_utc(job.started_at),
        finished_at=_iso_utc(job.finished_at),
        result_summary=(job.result_summary or None),
        error_message=(job.error_message or None),
    )
