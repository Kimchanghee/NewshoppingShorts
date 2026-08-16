"""Program-scoped account and duplicate-login regression tests."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from pydantic import ValidationError
import pytest


os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("JWT_SECRET_KEY", "a" * 64)

from app.models.login_attempt import LoginAttempt
from app.models.payment_session import PaymentSession
from app.models.registration_request import RegistrationRequest
from app.models.session import SessionModel
from app.models.user import ProgramType, User, UserType
from app.schemas.auth import LoginRequest
from app.services.auth_service import AuthService
from app.routers.auth import check_username


class _ProgramScopedAuthService(AuthService):
    async def _check_rate_limit(self, username, ip_address, program_type="ssmaker"):
        return {"allowed": True, "reason": None}

    def _record_login_attempt(
        self, username, ip_address, success, program_type="ssmaker"
    ):
        return None

    def apply_trial_monthly_reset(self, user):
        return None


def _create_auth_tables(engine) -> None:
    User.__table__.create(engine)
    SessionModel.__table__.create(engine)
    LoginAttempt.__table__.create(engine)
    PaymentSession.__table__.create(engine)
    RegistrationRequest.__table__.create(engine)


def _user(username: str, program_type: ProgramType) -> User:
    return User(
        username=username,
        password_hash="hash",
        is_active=True,
        user_type=UserType.TRIAL,
        work_count=5,
        work_used=0,
        program_type=program_type,
    )


def test_login_request_keeps_valid_program_scope_and_rejects_unknown_scope():
    request = LoginRequest(
        id="shared_user",
        pw="Password123",
        ip="127.0.0.1",
        program_type="stmaker",
    )

    assert request.program_type == "stmaker"
    with pytest.raises(ValidationError):
        LoginRequest(
            id="shared_user",
            pw="Password123",
            ip="127.0.0.1",
            program_type="other",
        )


def test_same_username_can_login_once_per_program_without_cross_program_eu003(
    monkeypatch,
):
    engine = create_engine("sqlite:///:memory:")
    _create_auth_tables(engine)

    with Session(engine) as db:
        ssmaker_user = _user("shared_user", ProgramType.SSMAKER)
        stmaker_user = _user("shared_user", ProgramType.STMAKER)
        db.add_all([ssmaker_user, stmaker_user])
        db.commit()
        db.refresh(ssmaker_user)
        db.refresh(stmaker_user)

        now = datetime.now(timezone.utc)
        db.add(
            SessionModel(
                user_id=ssmaker_user.id,
                token_jti="ssmaker-session",
                ip_address="1.1.1.1",
                expires_at=now + timedelta(hours=1),
                is_active=True,
            )
        )
        db.commit()

        tokens = iter(
            [
                ("st-token", "st-session", now + timedelta(hours=1)),
                ("st-token-2", "st-session-2", now + timedelta(hours=1)),
            ]
        )
        monkeypatch.setattr(
            "app.services.auth_service.verify_password", lambda *_args: True
        )
        monkeypatch.setattr(
            "app.services.auth_service.create_access_token",
            lambda *_args: next(tokens),
        )

        service = _ProgramScopedAuthService(db)
        first_stmaker_login = asyncio.run(
            service.login(
                username="shared_user",
                password="Password123",
                ip_address="2.2.2.2",
                force=False,
                program_type="stmaker",
            )
        )
        second_stmaker_login = asyncio.run(
            service.login(
                username="shared_user",
                password="Password123",
                ip_address="3.3.3.3",
                force=False,
                program_type="stmaker",
            )
        )

        assert first_stmaker_login["status"] is True
        assert first_stmaker_login["data"]["data"]["id"] == str(stmaker_user.id)
        assert second_stmaker_login == {"status": "EU003", "message": "EU003"}


def test_username_availability_is_scoped_to_requested_program():
    engine = create_engine("sqlite:///:memory:")
    _create_auth_tables(engine)

    with Session(engine) as db:
        db.add(_user("shared_user", ProgramType.SSMAKER))
        db.commit()

        route = check_username
        while hasattr(route, "__wrapped__"):
            route = route.__wrapped__
        request = SimpleNamespace(
            client=SimpleNamespace(host="127.0.0.1"),
            headers={},
        )

        ssmaker_result = asyncio.run(
            route(
                request=request,
                username="shared_user",
                program_type="ssmaker",
                db=db,
            )
        )
        stmaker_result = asyncio.run(
            route(
                request=request,
                username="shared_user",
                program_type="stmaker",
                db=db,
            )
        )

        assert ssmaker_result["available"] is False
        assert stmaker_result["available"] is True
