import asyncio
import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException


# Ensure required settings exist before importing app modules.
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "127.0.0.1")
os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("JWT_SECRET_KEY", "a" * 64)

from app.configuration import get_settings

get_settings.cache_clear()

from app.dependencies import get_current_user_id


def _mock_db_with_session(session_obj):
    db = MagicMock()
    query = MagicMock()
    db.query.return_value = query
    query.filter.return_value = query
    query.first.return_value = session_obj
    return db


def test_get_current_user_id_rejects_missing_session(monkeypatch):
    monkeypatch.setattr(
        "app.dependencies.decode_access_token",
        lambda _token: {"sub": "7", "jti": "test-jti"},
    )
    db = _mock_db_with_session(None)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            get_current_user_id(
                authorization="Bearer test-token",
                db=db,
            )
        )

    assert exc.value.status_code == 401
    assert "revoked" in exc.value.detail.lower()


def test_get_current_user_id_rejects_missing_jti(monkeypatch):
    monkeypatch.setattr(
        "app.dependencies.decode_access_token",
        lambda _token: {"sub": "7"},
    )
    db = _mock_db_with_session(SimpleNamespace(is_active=True))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            get_current_user_id(
                authorization="Bearer test-token",
                db=db,
            )
        )

    assert exc.value.status_code == 401
    assert "payload" in exc.value.detail.lower()


def test_get_current_user_id_accepts_active_session(monkeypatch):
    monkeypatch.setattr(
        "app.dependencies.decode_access_token",
        lambda _token: {"sub": "7", "jti": "test-jti"},
    )
    db = _mock_db_with_session(SimpleNamespace(is_active=True))

    user_id = asyncio.run(
        get_current_user_id(
            authorization="Bearer test-token",
            db=db,
        )
    )

    assert user_id == 7
