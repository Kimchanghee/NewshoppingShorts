import asyncio
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "a" * 64)

from app.models.registration_request import RegistrationRequest, RequestStatus
from app.models.session import SessionModel
from app.models.user import User
from app.routers import registration
from app.schemas.registration import RegistrationRequestCreate


def test_registration_repairs_approved_request_without_user(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    User.__table__.create(engine)
    RegistrationRequest.__table__.create(engine)
    SessionModel.__table__.create(engine)

    monkeypatch.setattr(registration, "hash_password", lambda _password: "new-hash")
    monkeypatch.setattr(registration, "get_client_ip", lambda _request: "127.0.0.1")
    monkeypatch.setattr(
        registration,
        "create_access_token",
        lambda _user_id, _ip: (
            "new-token",
            "new-jti",
            datetime.now(timezone.utc) + timedelta(hours=1),
        ),
    )

    with Session(engine) as db:
        db.add(
            RegistrationRequest(
                name="Old Name",
                username="orphan_user",
                program_type="ssmaker",
                password_hash="old-hash",
                contact="01000000000",
                email="orphan-user@example.com",
                status=RequestStatus.APPROVED,
            )
        )
        db.commit()

        route = registration.submit_registration_request
        while hasattr(route, "__wrapped__"):
            route = route.__wrapped__

        result = asyncio.run(
            route(
                request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), headers={}),
                data=RegistrationRequestCreate(
                    name="테스트 사용자",
                    username="orphan_user",
                    password="Example123!",
                    contact="01000000000",
                    email="orphan-user@example.com",
                    terms_accepted=True,
                    privacy_accepted=True,
                    terms_version="2026-08-19",
                    privacy_version="2026-08-19",
                    program_type="ssmaker",
                ),
                db=db,
            )
        )

        assert result.success is True
        assert db.query(User).filter(User.username == "orphan_user").one().password_hash == "new-hash"
        requests = db.query(RegistrationRequest).filter(
            RegistrationRequest.username == "orphan_user"
        ).all()
        assert len(requests) == 1
        assert requests[0].status == RequestStatus.APPROVED
