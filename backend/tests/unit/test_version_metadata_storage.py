import asyncio
import json
import os
from types import MappingProxyType

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "127.0.0.1")
os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("JWT_SECRET_KEY", "a" * 64)
os.environ.setdefault("ADMIN_API_KEY", "b" * 64)
os.environ.setdefault("APP_VERSION_UPDATE_API_KEY", "d" * 64)

from app import main


DEFAULT_INFO = {
    "version": "1.0.0",
    "min_required_version": "0.9.0",
    "download_url": "https://example.com/old.exe",
    "release_notes": "old notes",
    "is_mandatory": False,
    "update_channel": "stable",
    "file_hash": "a" * 64,
}
STORED_INFO = {
    "version": "2.0.0",
    "release_notes": "새 버전",
    "is_mandatory": True,
    "unknown_field": "must not escape storage",
}


@pytest.mark.parametrize(
    "raw_value",
    [
        dict(STORED_INFO),
        MappingProxyType(STORED_INFO),
        json.dumps(STORED_INFO, ensure_ascii=False),
        json.dumps(STORED_INFO, ensure_ascii=False).encode("utf-8"),
        bytearray(json.dumps(STORED_INFO, ensure_ascii=False).encode("utf-8")),
    ],
    ids=["dict", "mapping", "json-string", "utf8-bytes", "utf8-bytearray"],
)
def test_decode_app_version_info_normalizes_supported_storage_values(raw_value):
    decoded = main._decode_app_version_info(raw_value, DEFAULT_INFO)

    assert decoded == {
        **DEFAULT_INFO,
        "version": "2.0.0",
        "release_notes": "새 버전",
        "is_mandatory": True,
    }
    assert "unknown_field" not in decoded


@pytest.mark.parametrize(
    "raw_value",
    [
        None,
        "",
        "{not-json",
        b"\xff",
        bytearray(b"\xff"),
        "null",
        "[]",
        "42",
        42,
    ],
    ids=[
        "none",
        "empty-string",
        "malformed-json",
        "invalid-utf8-bytes",
        "invalid-utf8-bytearray",
        "json-null",
        "json-array",
        "json-number",
        "unsupported-number",
    ],
)
def test_decode_app_version_info_falls_back_safely(raw_value):
    decoded = main._decode_app_version_info(raw_value, DEFAULT_INFO)

    assert decoded == DEFAULT_INFO
    assert decoded is not DEFAULT_INFO


def test_decode_app_version_info_does_not_mutate_inputs():
    defaults = dict(DEFAULT_INFO)
    stored = dict(STORED_INFO)

    decoded = main._decode_app_version_info(stored, defaults)
    decoded["version"] = "changed-after-decoding"

    assert defaults == DEFAULT_INFO
    assert stored == STORED_INFO
    assert decoded is not defaults
    assert decoded is not stored


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _ReadSession:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def execute(self, _statement, _params):
        return _ScalarResult(self.value)


def test_version_endpoint_uses_mapping_value_returned_by_loader(monkeypatch):
    persisted = MappingProxyType(
        {
            "version": "9.0.0",
            "download_url": "https://example.com/new.exe",
            "release_notes": "loaded from JSON storage",
            "unknown_field": "ignored",
        }
    )
    monkeypatch.setattr(main, "SessionLocal", lambda: _ReadSession(persisted))
    monkeypatch.setattr(main, "APP_VERSION_INFO", dict(DEFAULT_INFO))
    monkeypatch.setattr(main, "_fetch_github_release_version_info", lambda: None)

    response = asyncio.run(main.get_app_version())

    assert response == main._decode_app_version_info(persisted, DEFAULT_INFO)
    assert "unknown_field" not in response


def test_public_version_endpoints_share_persisted_mapping_metadata(monkeypatch):
    persisted = MappingProxyType(
        {
            **DEFAULT_INFO,
            "version": "9.1.0",
            "download_url": "https://example.com/9.1.0.exe",
            "release_notes": "persisted JSONB metadata",
            "file_hash": "9" * 64,
        }
    )
    monkeypatch.setattr(main, "SessionLocal", lambda: _ReadSession(persisted))
    monkeypatch.setattr(main, "APP_VERSION_INFO", dict(DEFAULT_INFO))
    monkeypatch.setattr(main, "_fetch_github_release_version_info", lambda: None)

    version_response = asyncio.run(main.get_app_version())
    legacy_response = asyncio.run(main.get_legacy_free_lately(item=1))
    check_response = asyncio.run(main.check_app_version(current_version="9.0.0"))

    assert legacy_response["version"] == version_response["version"]
    assert check_response["latest_version"] == version_response["version"]
    for key in ("download_url", "release_notes", "file_hash"):
        assert legacy_response[key] == version_response[key]
        assert check_response[key] == version_response[key]


def test_persistence_keeps_json_text_compatibility(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE system_settings ("
                "setting_key VARCHAR(128) PRIMARY KEY, "
                "setting_value TEXT NOT NULL)"
            )
        )
    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=engine))
    version_info = {**DEFAULT_INFO, "release_notes": "한글 release notes"}

    assert main._persist_app_version_info_to_db(version_info) is True

    with engine.connect() as connection:
        raw_value = connection.execute(
            text(
                "SELECT setting_value FROM system_settings "
                "WHERE setting_key = :setting_key"
            ),
            {"setting_key": main._APP_VERSION_INFO_SETTING_KEY},
        ).scalar_one()

    assert isinstance(raw_value, str)
    assert json.loads(raw_value) == version_info
    assert main._load_app_version_info_from_db(DEFAULT_INFO) == version_info
