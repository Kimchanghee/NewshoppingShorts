# -*- coding: utf-8 -*-
"""Unit tests for TikTokManager official Content Posting API compliance."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import managers.tiktok_manager as tt_module
from managers.tiktok_manager import (
    COUPANG_AFFILIATE_DISCLOSURE,
    TIKTOK_CAPTION_MAX_LEN,
    TikTokManager,
)


class _TestTikTokManager(TikTokManager):
    def __init__(self, user_dir: Path):
        self._test_dir = str(user_dir)
        super().__init__(gui=None, settings_file="tiktok_settings_test.json")

    def _get_settings_path(self) -> str:
        return str(Path(self._test_dir) / self.settings_file)


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
    return _TestTikTokManager(tmp_path)


@pytest.fixture
def connected_manager(manager):
    manager._client_key = "awxyz123456"
    manager._client_secret = "secret1234567890"
    manager._credentials = tt_module.TikTokCredentials(
        access_token="tok",
        refresh_token="ref",
        open_id="open-1",
        expires_at=tt_module.time.time() + 100000,
        scope="video.publish",
    )
    manager._channel = tt_module.TikTokChannel(open_id="open-1", username="demo_tiktok")
    return manager


# ============ App credentials ============

def test_install_app_credentials_validates(manager, monkeypatch):
    store = {}
    monkeypatch.setattr(
        "utils.secrets_manager.get_secrets_manager",
        lambda: SimpleNamespace(
            set_credential=lambda k, v: store.__setitem__(k, v) or True,
            get_credential=lambda k: store.get(k),
        ),
    )
    with pytest.raises(ValueError):
        manager.install_app_credentials("bad key with spaces", "secret1234567890")

    assert manager.install_app_credentials("awabc123456", "secret1234567890", "http://localhost:8080/callback")
    assert manager.has_app_credentials()
    creds = manager.load_app_credentials()
    assert creds["client_key"] == "awabc123456"
    assert creds["redirect_uri"] == "http://localhost:8080/callback"


# ============ Caption builder ============

def test_build_caption_coupang_and_number():
    caption = TikTokManager.build_caption(
        title="꿀템",
        description="설명입니다",
        hashtags=["쇼핑", "#꿀템"],
        purchase_link="https://link.coupang.com/a/x",
        upload_number=5,
    )
    assert COUPANG_AFFILIATE_DISCLOSURE in caption
    assert "[005] 꿀템" in caption
    assert "#쇼핑" in caption
    assert "##" not in caption


def test_build_caption_truncates():
    caption = TikTokManager.build_caption(description="가" * 5000, hashtags=["tag"])
    assert len(caption) <= TIKTOK_CAPTION_MAX_LEN
    assert "#tag" in caption


# ============ creator_info compliance ============

def test_query_creator_info_success(monkeypatch, connected_manager):
    monkeypatch.setattr(
        tt_module.requests,
        "post",
        lambda url, headers=None, timeout=None: _FakeResponse(200, {
            "data": {
                "privacy_level_options": ["PUBLIC_TO_EVERYONE", "SELF_ONLY"],
                "comment_disabled": False,
                "max_video_post_duration_sec": 300,
            },
            "error": {"code": "ok"},
        }),
    )
    info = connected_manager.query_creator_info()
    assert "PUBLIC_TO_EVERYONE" in info["privacy_level_options"]
    assert connected_manager._resolve_privacy_level(info) == "PUBLIC_TO_EVERYONE"


def test_resolve_privacy_falls_back_to_self_only(connected_manager):
    # Unaudited apps only get SELF_ONLY.
    info = {"privacy_level_options": ["SELF_ONLY"]}
    assert connected_manager._resolve_privacy_level(info) == "SELF_ONLY"


def test_resolve_privacy_none_when_no_options(connected_manager):
    assert connected_manager._resolve_privacy_level({"privacy_level_options": []}) is None


# ============ Full upload flow (mocked) ============

def test_upload_video_full_flow(monkeypatch, tmp_path, connected_manager):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"0" * 2048)

    calls = {"creator": 0, "init": 0, "put": 0}

    def fake_post(url, headers=None, json=None, timeout=None, data=None):
        if url.endswith("/creator_info/query/"):
            calls["creator"] += 1
            return _FakeResponse(200, {
                "data": {"privacy_level_options": ["PUBLIC_TO_EVERYONE", "SELF_ONLY"]},
                "error": {"code": "ok"},
            })
        if url.endswith("/video/init/"):
            calls["init"] += 1
            # Direct Post: post_info carries caption + resolved privacy.
            assert json["post_info"]["privacy_level"] == "PUBLIC_TO_EVERYONE"
            assert json["post_info"]["title"]
            assert json["source_info"]["source"] == "FILE_UPLOAD"
            return _FakeResponse(200, {
                "data": {"publish_id": "pub-1", "upload_url": "https://upload.tiktok/x"},
                "error": {"code": "ok"},
            })
        raise AssertionError(f"unexpected POST {url}")

    def fake_put(url, headers=None, data=None, timeout=None):
        calls["put"] += 1
        return _FakeResponse(200, {})

    monkeypatch.setattr(tt_module.requests, "post", fake_post)
    monkeypatch.setattr(tt_module.requests, "put", fake_put)

    publish_id = connected_manager.upload_video(str(video), caption="테스트 캡션")
    assert publish_id == "pub-1"
    assert calls == {"creator": 1, "init": 1, "put": 1}
    assert "pub-1" in connected_manager._pending_uploads


def test_upload_video_blocked_when_cannot_post(monkeypatch, tmp_path, connected_manager):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"0" * 512)
    monkeypatch.setattr(
        tt_module.requests,
        "post",
        lambda url, headers=None, json=None, timeout=None, data=None: _FakeResponse(
            200, {"data": {"privacy_level_options": []}, "error": {"code": "ok"}}
        ),
    )
    assert connected_manager.upload_video(str(video), caption="c") is None
    assert "게시할 수 없습니다" in connected_manager.get_last_error()


def test_upload_video_requires_connection(manager, tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"0" * 512)
    assert manager.upload_video(str(video), caption="c") is None
    assert "연결되지 않았습니다" in manager.get_last_error()


# ============ Queue gating ============

def test_add_to_upload_queue_blocks_without_render_integrity(connected_manager):
    connected_manager.add_to_upload_queue(
        video_path="C:/v.mp4",
        title="t",
        description="d",
        render_integrity={"ok": False},
        render_integrity_required=True,
    )
    assert connected_manager.get_queue_count() == 0


def test_add_to_upload_queue_builds_caption(connected_manager):
    connected_manager.add_to_upload_queue(
        video_path="C:/v.mp4",
        title="제목",
        description="설명",
        hashtags=["태그"],
        coupang_deep_link="https://link.coupang.com/a/y",
        render_integrity={"ok": True},
        render_integrity_required=True,
        upload_number=2,
    )
    assert connected_manager.get_queue_count() == 1
    item = connected_manager._upload_queue[0]
    assert COUPANG_AFFILIATE_DISCLOSURE in item["caption"]
    assert "[002]" in item["caption"]
