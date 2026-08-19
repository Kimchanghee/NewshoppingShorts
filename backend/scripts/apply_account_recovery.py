"""Apply an explicitly requested one-time account recovery during deployment.

The build environment supplies a bcrypt hash, never a plaintext password. A
request UUID is recorded with the audit event and cannot be reused.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.configuration import get_settings
from app.models.login_attempt import LoginAttempt
from app.models.session import SessionModel
from app.models.user import User
from app.models.user_log import UserLog


def apply_account_recovery(
    db: Session,
    *,
    username: str,
    program_type: str,
    password_hash: str,
    request_id: str,
) -> tuple[int, int, int]:
    clean_username = username.strip().lower()
    clean_program = program_type.strip().lower()
    clean_hash = password_hash.strip()
    normalized_request_id = str(UUID(request_id.strip()))

    if clean_program not in {"ssmaker", "stmaker"}:
        raise ValueError("ACCOUNT_RECOVERY_PROGRAM must be ssmaker or stmaker")
    if not clean_hash.startswith(("$2a$", "$2b$", "$2y$")) or len(clean_hash) != 60:
        raise ValueError("ACCOUNT_RECOVERY_PASSWORD_HASH must be a bcrypt hash")
    if not clean_username:
        raise ValueError("ACCOUNT_RECOVERY_USERNAME is required")

    audit_marker = f"request_id={normalized_request_id}"
    already_applied = (
        db.query(UserLog)
        .filter(
            UserLog.action == "deployment_account_recovery",
            UserLog.content.contains(audit_marker),
        )
        .first()
    )
    if already_applied:
        raise RuntimeError("Account recovery request ID was already applied")

    user = (
        db.query(User)
        .filter(
            User.username == clean_username,
            User.program_type == clean_program,
        )
        .with_for_update()
        .first()
    )
    if not user:
        raise LookupError("Recovery target account was not found")

    user.password_hash = clean_hash
    sessions_revoked = (
        db.query(SessionModel)
        .filter(
            SessionModel.user_id == user.id,
            SessionModel.is_active.is_(True),
        )
        .update({SessionModel.is_active: False}, synchronize_session=False)
    )
    settings = get_settings()
    rate_limit_cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=settings.LOGIN_ATTEMPT_WINDOW_MINUTES
    )
    login_attempts_cleared = (
        db.query(LoginAttempt)
        .filter(
            LoginAttempt.username == clean_username,
            LoginAttempt.program_type == clean_program,
            LoginAttempt.attempted_at > rate_limit_cutoff,
        )
        .delete(synchronize_session=False)
    )
    db.add(
        UserLog(
            user_id=user.id,
            level="WARNING",
            action="deployment_account_recovery",
            content=(
                f"{audit_marker};program_type={clean_program};"
                f"sessions_revoked={sessions_revoked};"
                f"login_attempts_cleared={login_attempts_cleared}"
            ),
        )
    )
    db.commit()
    return user.id, sessions_revoked, login_attempts_cleared


def main() -> int:
    values = {
        "username": os.getenv("ACCOUNT_RECOVERY_USERNAME", ""),
        "program_type": os.getenv("ACCOUNT_RECOVERY_PROGRAM", ""),
        "password_hash": os.getenv("ACCOUNT_RECOVERY_PASSWORD_HASH", ""),
        "request_id": os.getenv("ACCOUNT_RECOVERY_REQUEST_ID", ""),
    }
    if not any(value.strip() for value in values.values()):
        print("No one-time account recovery requested.")
        return 0
    if not all(value.strip() for value in values.values()):
        raise RuntimeError("All ACCOUNT_RECOVERY_* values are required together")

    db = SessionLocal()
    try:
        user_id, sessions_revoked, login_attempts_cleared = apply_account_recovery(
            db, **values
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(
        "One-time account recovery completed: "
        f"user_id={user_id}, sessions_revoked={sessions_revoked}, "
        f"login_attempts_cleared={login_attempts_cleared}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
