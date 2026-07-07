# -*- coding: utf-8 -*-
"""Unit tests for InstagramManager (official Graph API publishing)."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import managers.instagram_manager as ig_module
from managers.instagram_manager import (
    COUPANG_AFFILIATE_DISCLOSURE,
    INSTAGRAM_CAPTION_MAX_LEN,
    InstagramManager,
)


class _TestInstagramManager(InstagramManager):
    def __init__(self, user_dir: Path):
        self._test_user_dir = str(user_dir)
        super().__init__(gui=None, settings_file="instagram_settings_test.json")

    def _get_user_data_dir(self) -> str:
        return self._test_user_dir

    def _sync_settings_manager_state(self) -> None:
        # Keep unit tests isolated from the shared SettingsManager singleton.
        return


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.content = json.dumps(self._payload).encode("utf-8")
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload


@pytest.fixture
def manager(tmp_path):
    return _TestInstagramManager(tmp_path / "user")


@pytest.fixture
def connected_manager(manager):
    manager._account = ig_module.InstagramAccount(
        ig_user_id="17840000000000000",
        username="my_shop",
        page_id="1230000000",
        page_name="My Shop Page",
        connected_at="2026-07-06T00:00:00",
    )
    manager._credentials = ig_module.InstagramCredentials(
        user_access_token="user-token",
        page_access_token="page-token",
        expires_at=0.0,  # unknown expiry → treated as valid
        scope="instagram_basic,instagram_content_publish",
    )
    return manager


# ============ Settings persistence ============

def test_settings_round_trip_with_encrypted_tokens(tmp_path, connected_manager):
    assert connected_manager._save_settings()

    reloaded = _TestInstagramManager(Path(connected_manager._test_user_dir))
    assert reloaded.is_connected()
    assert reloaded._account.username == "my_shop"
    assert reloaded._credentials.user_access_token == "user-token"
    assert reloaded._credentials.page_access_token == "page-token"

    # Tokens must not be persisted as plaintext when encryption is available.
    raw = json.loads(
        (Path(connected_manager._test_user_dir) / "instagram_settings_test.json").read_text(
            encoding="utf-8"
        )
    )
    stored_token = raw["credentials"]["user_access_token"]
    if stored_token.startswith("fernet:"):
        assert "user-token" not in stored_token


# ============ App credentials validation ============

def test_install_app_credentials_rejects_invalid_formats(manager):
    with pytest.raises(ValueError):
        manager.install_app_credentials("not-a-number", "a" * 32)
    with pytest.raises(ValueError):
        manager.install_app_credentials("123456789012345", "짧음")


def test_install_and_load_app_credentials(monkeypatch, manager):
    store = {}
    fake_secrets = SimpleNamespace(
        set_credential=lambda key, value: store.__setitem__(key, value) or True,
        get_credential=lambda key: store.get(key),
    )
    monkeypatch.setattr(
        "utils.secrets_manager.get_secrets_manager", lambda: fake_secrets
    )

    assert manager.install_app_credentials("123456789012345", "f" * 32)
    creds = manager.load_app_credentials()
    assert creds == {"app_id": "123456789012345", "app_secret": "f" * 32}
    assert manager.has_app_credentials()


# ============ Caption builder ============

def test_build_caption_adds_coupang_disclosure_and_hashtags():
    caption = InstagramManager.build_caption(
        title="꿀템 발견",
        description="가성비 최고 상품입니다.",
        hashtags=["쇼핑", "#핫딜"],
        purchase_link="https://link.coupang.com/a/abc123",
        upload_number=7,
    )
    assert COUPANG_AFFILIATE_DISCLOSURE in caption
    assert "[007] 꿀템 발견" in caption
    assert "#쇼핑" in caption and "#핫딜" in caption
    assert "##" not in caption


def test_build_caption_respects_max_length():
    caption = InstagramManager.build_caption(
        title="제목",
        description="본문 " * 2000,
        hashtags=["tag1", "tag2"],
    )
    assert len(caption) <= INSTAGRAM_CAPTION_MAX_LEN
    assert "#tag1" in caption  # hashtags preserved after truncation


def test_build_caption_no_disclosure_for_non_coupang():
    caption = InstagramManager.build_caption(
        title="일반 상품",
        description="설명",
        purchase_link="https://smartstore.naver.com/x",
    )
    assert COUPANG_AFFILIATE_DISCLOSURE not in caption


# ============ Upload queue gating ============

def test_add_to_upload_queue_blocks_without_render_integrity(connected_manager):
    connected_manager.add_to_upload_queue(
        video_path="C:/video.mp4",
        title="t",
        description="d",
        render_integrity={"ok": False},
        render_integrity_required=True,
    )
    assert connected_manager.get_queue_count() == 0


def test_add_to_upload_queue_builds_caption(connected_manager):
    connected_manager.add_to_upload_queue(
        video_path="C:/video.mp4",
        title="제목",
        description="설명",
        hashtags=["태그"],
        coupang_deep_link="https://link.coupang.com/a/xyz",
        render_integrity={"ok": True},
        render_integrity_required=True,
        upload_number=3,
    )
    assert connected_manager.get_queue_count() == 1
    item = connected_manager._upload_queue[0]
    assert COUPANG_AFFILIATE_DISCLOSURE in item["caption"]
    assert "[003]" in item["caption"]


# ============ Account discovery ============

def test_discover_instagram_account_picks_page_with_ig(monkeypatch, manager):
    def fake_get(url, params=None, timeout=None):
        assert url.endswith("/me/accounts")
        return _FakeResponse(200, {
            "data": [
                {"id": "1", "name": "No IG Page", "access_token": "pt1"},
                {
                    "id": "2",
                    "name": "Shop Page",
                    "access_token": "pt2",
                    "instagram_business_account": {
                        "id": "178400001",
                        "username": "my_shop",
                    },
                },
            ]
        })

    monkeypatch.setattr(ig_module.requests, "get", fake_get)
    found = manager._discover_instagram_account("user-token")
    assert found is not None
    assert found["ig_user_id"] == "178400001"
    assert found["username"] == "my_shop"
    assert found["page_access_token"] == "pt2"


def test_discover_instagram_account_none_when_no_ig(monkeypatch, manager):
    monkeypatch.setattr(
        ig_module.requests,
        "get",
        lambda url, params=None, timeout=None: _FakeResponse(
            200, {"data": [{"id": "1", "name": "Page", "access_token": "pt"}]}
        ),
    )
    assert manager._discover_instagram_account("user-token") is None
    assert "인스타그램 프로페셔널 계정" in manager.get_last_error()


# ============ Reels publish flow (mocked Graph API) ============

def test_upload_reel_full_flow(monkeypatch, tmp_path, connected_manager):
    video = tmp_path / "reel.mp4"
    video.write_bytes(b"0" * 1024)

    calls = {"container": 0, "binary": 0, "status": 0, "publish": 0}

    def fake_post(url, data=None, headers=None, timeout=None):
        if url.endswith("/media"):
            calls["container"] += 1
            assert data["media_type"] == "REELS"
            assert data["upload_type"] == "resumable"
            return _FakeResponse(200, {"id": "container-1"})
        if "rupload.facebook.com" in url:
            calls["binary"] += 1
            assert headers["offset"] == "0"
            assert headers["Authorization"] == "OAuth page-token"
            return _FakeResponse(200, {"success": True})
        if url.endswith("/media_publish"):
            calls["publish"] += 1
            assert data["creation_id"] == "container-1"
            return _FakeResponse(200, {"id": "media-99"})
        raise AssertionError(f"unexpected POST {url}")

    def fake_get(url, params=None, timeout=None):
        if url.endswith("/content_publishing_limit"):
            return _FakeResponse(200, {"data": [{"quota_usage": 3, "config": {"quota_total": 100}}]})
        if url.endswith("/container-1"):
            calls["status"] += 1
            return _FakeResponse(200, {"status_code": "FINISHED"})
        if url.endswith("/media-99"):
            return _FakeResponse(200, {"permalink": "https://www.instagram.com/reel/xyz/"})
        raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr(ig_module.requests, "post", fake_post)
    monkeypatch.setattr(ig_module.requests, "get", fake_get)
    monkeypatch.setattr(ig_module.time, "sleep", lambda s: None)

    media_id = connected_manager.upload_reel(str(video), caption="테스트 캡션")
    assert media_id == "media-99"
    assert calls == {"container": 1, "binary": 1, "status": 1, "publish": 1}


def test_upload_reel_blocked_at_quota(monkeypatch, tmp_path, connected_manager):
    video = tmp_path / "reel.mp4"
    video.write_bytes(b"0" * 16)

    monkeypatch.setattr(
        ig_module.requests,
        "get",
        lambda url, params=None, timeout=None: _FakeResponse(
            200, {"data": [{"quota_usage": 100, "config": {"quota_total": 100}}]}
        ),
    )
    assert connected_manager.upload_reel(str(video), caption="c") is None
    assert "한도" in connected_manager.get_last_error()


def test_upload_reel_fails_on_container_error_status(monkeypatch, tmp_path, connected_manager):
    video = tmp_path / "reel.mp4"
    video.write_bytes(b"0" * 16)

    def fake_post(url, data=None, headers=None, timeout=None):
        if url.endswith("/media"):
            return _FakeResponse(200, {"id": "container-2"})
        if "rupload.facebook.com" in url:
            return _FakeResponse(200, {"success": True})
        raise AssertionError(f"unexpected POST {url}")

    def fake_get(url, params=None, timeout=None):
        if url.endswith("/content_publishing_limit"):
            return _FakeResponse(200, {"data": [{"quota_usage": 0, "config": {"quota_total": 100}}]})
        if url.endswith("/container-2"):
            return _FakeResponse(200, {"status_code": "ERROR", "status": "Processing failed"})
        raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr(ig_module.requests, "post", fake_post)
    monkeypatch.setattr(ig_module.requests, "get", fake_get)
    monkeypatch.setattr(ig_module.time, "sleep", lambda s: None)

    assert connected_manager.upload_reel(str(video), caption="c") is None
    assert "영상 처리 실패" in connected_manager.get_last_error()


def test_upload_reel_requires_connection(manager, tmp_path):
    video = tmp_path / "reel.mp4"
    video.write_bytes(b"0" * 16)
    assert manager.upload_reel(str(video), caption="c") is None
    assert "연결되지 않았습니다" in manager.get_last_error()
