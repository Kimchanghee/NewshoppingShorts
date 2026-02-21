import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.auth_service import AuthService
from app.utils.password import hash_password, verify_password


def test_change_password_success():
    db = MagicMock()
    user = SimpleNamespace(
        id=1,
        is_active=True,
        password_hash=hash_password("OldPass123"),
    )

    user_query = MagicMock()
    user_query.filter.return_value.first.return_value = user

    session_query = MagicMock()
    session_query.filter.return_value.update.return_value = 1

    db.query.side_effect = [user_query, session_query]

    service = AuthService(db)
    result = asyncio.run(
        service.change_password(
            user_id="1",
            current_password="OldPass123",
            new_password="NewPass456",
        )
    )

    assert result["success"] is True
    assert verify_password("NewPass456", user.password_hash)
    db.commit.assert_called_once()


def test_change_password_rejects_invalid_current_password():
    db = MagicMock()
    user = SimpleNamespace(
        id=1,
        is_active=True,
        password_hash=hash_password("OldPass123"),
    )

    user_query = MagicMock()
    user_query.filter.return_value.first.return_value = user
    db.query.side_effect = [user_query]

    service = AuthService(db)
    result = asyncio.run(
        service.change_password(
            user_id="1",
            current_password="WrongPass999",
            new_password="NewPass456",
        )
    )

    assert result["success"] is False
    assert "incorrect" in result["message"].lower()
    db.commit.assert_not_called()
