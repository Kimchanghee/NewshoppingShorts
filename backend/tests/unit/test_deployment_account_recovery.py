"""One-time deployment account recovery regressions."""

import importlib.util
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import bcrypt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


backend_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_root))
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "127.0.0.1")
os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("JWT_SECRET_KEY", "a" * 64)
os.environ.setdefault("ADMIN_API_KEY", "b" * 64)
os.environ.setdefault("SSMAKER_API_KEY", "c" * 32)
os.environ.setdefault(
    "BILLING_KEY_ENCRYPTION_KEY",
    "uKVciQZlzUKtZPwuiKHl3wVCJJhQrWL6TqrFRClcEOI=",
)

from app.database import Base  # noqa: E402
from app.models.login_attempt import LoginAttempt  # noqa: E402
from app.models.session import SessionModel  # noqa: E402
from app.models.user import ProgramType, User  # noqa: E402
from app.models.user_log import UserLog  # noqa: E402
from app.utils.password import verify_password  # noqa: E402


script_path = backend_root / "scripts" / "apply_account_recovery.py"
spec = importlib.util.spec_from_file_location("apply_account_recovery", script_path)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_account_recovery_is_atomic_audited_and_single_use():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    user = User(
        username="recover_me",
        password_hash=bcrypt.hashpw(b"OldPassword123", bcrypt.gensalt(rounds=4)).decode(),
        is_active=True,
        program_type=ProgramType.SSMAKER,
    )
    db.add(user)
    db.flush()
    db.add(
        SessionModel(
            user_id=user.id,
            program_type="ssmaker",
            token_jti="recovery-session",
            ip_address="127.0.0.1",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            is_active=True,
        )
    )
    db.add(
        LoginAttempt(
            username=user.username,
            ip_address="127.0.0.1",
            success=False,
            program_type="ssmaker",
        )
    )
    db.commit()
    request_id = str(uuid4())
    new_hash = bcrypt.hashpw(b"FreshPassword123", bcrypt.gensalt(rounds=4)).decode()

    user_id, sessions_revoked, login_attempts_cleared = module.apply_account_recovery(
        db,
        username="RECOVER_ME",
        program_type="ssmaker",
        password_hash=new_hash,
        request_id=request_id,
    )

    db.refresh(user)
    assert user_id == user.id
    assert sessions_revoked == 1
    assert login_attempts_cleared == 1
    assert verify_password("FreshPassword123", user.password_hash) is True
    assert db.query(SessionModel).filter(SessionModel.is_active.is_(True)).count() == 0
    assert db.query(LoginAttempt).count() == 0
    audit = db.query(UserLog).filter(UserLog.action == "deployment_account_recovery").one()
    assert f"request_id={request_id}" in audit.content
    assert new_hash not in audit.content
    assert "FreshPassword123" not in audit.content
    assert "login_attempts_cleared=1" in audit.content

    with pytest.raises(RuntimeError, match="already applied"):
        module.apply_account_recovery(
            db,
            username="recover_me",
            program_type="ssmaker",
            password_hash=new_hash,
            request_id=request_id,
        )
    db.close()
