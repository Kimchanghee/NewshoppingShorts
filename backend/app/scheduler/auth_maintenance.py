# -*- coding: utf-8 -*-
"""
Periodic maintenance tasks for auth/session tables.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.configuration import get_settings
from app.database import SessionLocal
from app.models.session import SessionModel
from app.models.login_attempt import LoginAttempt

logger = logging.getLogger(__name__)


def cleanup_auth_records_once() -> dict:
    """
    Clean expired/inactive sessions and stale login attempts.

    Returns cleanup stats for logging/monitoring.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    session_retention_days = max(1, int(settings.SESSION_RETENTION_DAYS or 7))
    login_attempt_retention_days = max(1, int(settings.LOGIN_ATTEMPT_RETENTION_DAYS or 30))

    session_cutoff = now - timedelta(days=session_retention_days)
    login_attempt_cutoff = now - timedelta(days=login_attempt_retention_days)

    db = SessionLocal()
    try:
        deleted_sessions = (
            db.query(SessionModel)
            .filter(
                SessionModel.expires_at < session_cutoff,
            )
            .delete(synchronize_session=False)
        )

        deleted_inactive_sessions = (
            db.query(SessionModel)
            .filter(
                SessionModel.is_active == False,  # noqa: E712
                SessionModel.created_at < session_cutoff,
            )
            .delete(synchronize_session=False)
        )

        deleted_attempts = (
            db.query(LoginAttempt)
            .filter(LoginAttempt.attempted_at < login_attempt_cutoff)
            .delete(synchronize_session=False)
        )

        db.commit()
        result = {
            "deleted_sessions": int(deleted_sessions or 0),
            "deleted_inactive_sessions": int(deleted_inactive_sessions or 0),
            "deleted_login_attempts": int(deleted_attempts or 0),
            "session_retention_days": session_retention_days,
            "login_attempt_retention_days": login_attempt_retention_days,
        }
        logger.info("[Maintenance] Auth cleanup completed: %s", result)
        return result
    except Exception:
        db.rollback()
        logger.exception("[Maintenance] Auth cleanup failed")
        return {
            "deleted_sessions": 0,
            "deleted_inactive_sessions": 0,
            "deleted_login_attempts": 0,
            "session_retention_days": session_retention_days,
            "login_attempt_retention_days": login_attempt_retention_days,
            "status": "failed",
        }
    finally:
        db.close()


async def run_auth_cleanup_loop(stop_event: asyncio.Event) -> None:
    """Run auth cleanup repeatedly until stop_event is set."""
    settings = get_settings()
    interval_minutes = max(5, int(settings.MAINTENANCE_TASK_INTERVAL_MINUTES or 60))
    interval_seconds = interval_minutes * 60

    while not stop_event.is_set():
        cleanup_auth_records_once()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue
