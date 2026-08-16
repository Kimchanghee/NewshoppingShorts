"""Regression tests for the database work on frequent account operations."""

from __future__ import annotations

import asyncio
import os


os.environ.setdefault("JWT_SECRET_KEY", "a" * 64)
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")

from app.routers import auth as auth_router
from app.services.auth_service import AuthService


class _QueryResult:
    def __init__(self, one_result=(0, 0)):
        self.one_result = one_result

    def filter(self, *_args):
        return self

    def first(self):
        return None

    def scalar(self):
        return 0

    def one(self):
        return self.one_result


class _CountingDB:
    def __init__(self, one_result=(0, 0)):
        self.query_count = 0
        self.one_result = one_result

    def query(self, *_args):
        self.query_count += 1
        return _QueryResult(self.one_result)


def test_login_rate_limit_counts_username_and_ip_in_one_query():
    db = _CountingDB()

    result = asyncio.run(AuthService(db)._check_rate_limit("tester", "1.1.1.1"))

    assert result == {"allowed": True, "reason": None}
    assert db.query_count == 1


def test_username_availability_uses_one_query(monkeypatch):
    db = _CountingDB()
    monkeypatch.setattr(auth_router, "get_client_ip", lambda _request: "1.1.1.1")
    endpoint = getattr(auth_router.check_username, "__wrapped__", auth_router.check_username)

    result = asyncio.run(endpoint(object(), "available_name", db))

    assert result["available"] is True
    assert db.query_count == 1


def test_username_check_does_not_promise_an_orphaned_approved_name(monkeypatch):
    from app.models.registration_request import RequestStatus

    db = _CountingDB(one_result=(False, RequestStatus.APPROVED))
    monkeypatch.setattr(auth_router, "get_client_ip", lambda _request: "1.1.1.1")
    endpoint = getattr(auth_router.check_username, "__wrapped__", auth_router.check_username)

    result = asyncio.run(endpoint(object(), "approved_name", db))

    assert result["available"] is False
