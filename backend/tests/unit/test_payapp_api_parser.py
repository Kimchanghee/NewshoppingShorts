# -*- coding: utf-8 -*-
"""
PayApp API parsing tests.
"""

import os
import sys
import importlib.util
import types
from pathlib import Path
from urllib.parse import quote


# Add backend root to path
backend_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_root))

# Minimal required env for app imports
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "127.0.0.1")
os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("JWT_SECRET_KEY", "a" * 64)
os.environ.setdefault("ENVIRONMENT", "development")

if "slowapi" not in sys.modules:
    slowapi_stub = types.ModuleType("slowapi")

    class _Limiter:
        def __init__(self, *_args, **_kwargs):
            pass

        def limit(self, *_args, **_kwargs):
            def _decorator(func):
                return func
            return _decorator

    slowapi_stub.Limiter = _Limiter
    sys.modules["slowapi"] = slowapi_stub

payment_path = backend_root / "app" / "routers" / "payment.py"
_spec = importlib.util.spec_from_file_location("payment_router_for_tests", payment_path)
assert _spec and _spec.loader
payment = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(payment)


class _FakeResponse:
    def __init__(self, body: bytes):
        self.content = body

    def raise_for_status(self):
        return None


def test_call_payapp_api_decodes_cp949_error_message(monkeypatch):
    msg = "유효하지 않은 상점 아이디"
    body = f"state=0&errorCode=1002&errorMessage={quote(msg, encoding='cp949')}".encode("ascii")

    def _fake_post(*_args, **_kwargs):
        return _FakeResponse(body)

    monkeypatch.setattr(payment.http_requests, "post", _fake_post)
    result = payment._call_payapp_api({"cmd": "payrequest", "userid": "merchant01"})

    assert result["state"] == "0"
    assert result["errorCode"] == "1002"
    assert result["errorMessage"] == msg


def test_call_payapp_api_sets_charset_by_default(monkeypatch):
    captured = {}

    def _fake_post(_url, data=None, **_kwargs):
        captured["data"] = dict(data or {})
        return _FakeResponse(b"state=1&payurl=https%3A%2F%2Fexample.com")

    monkeypatch.setattr(payment.http_requests, "post", _fake_post)
    payment._call_payapp_api({"cmd": "payrequest", "userid": "merchant01"})

    assert captured["data"]["charset"] == "utf-8"


def test_call_payapp_api_keeps_explicit_charset(monkeypatch):
    captured = {}

    def _fake_post(_url, data=None, **_kwargs):
        captured["data"] = dict(data or {})
        return _FakeResponse(b"state=1")

    monkeypatch.setattr(payment.http_requests, "post", _fake_post)
    payment._call_payapp_api({"cmd": "payrequest", "userid": "merchant01", "charset": "euc-kr"})

    assert captured["data"]["charset"] == "euc-kr"
