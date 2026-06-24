from managers.linktree_manager import COUPANG_AFFILIATE_DISCLOSURE, LinktreeManager


class _DummySettings:
    def __init__(self, data):
        self._data = dict(data)

    def get_linktree_settings(self):
        return dict(self._data)

    def get_linktree_account_verification(self):
        expected = str(self._data.get("expected_account_email", "") or "").strip().lower()
        actual = str(self._data.get("account_email", "") or "").strip().lower()
        if expected and actual != expected:
            return {
                "required": True,
                "ok": False,
                "expected": expected,
                "actual": actual,
                "message": f"Linktree 계정이 다릅니다. 기대: {expected}, 현재: {actual}",
            }
        return {"required": bool(expected), "ok": True, "expected": expected, "actual": actual, "message": ""}


class _DummyResponse:
    def __init__(self, status_code=200, text="ok"):
        self.status_code = status_code
        self.text = text


def _make_manager(settings_data):
    manager = object.__new__(LinktreeManager)
    manager.settings = _DummySettings(settings_data)
    return manager


def test_is_connected_requires_publish_path(monkeypatch):
    monkeypatch.setattr("managers.linktree_browser_publisher.browser_publish_enabled", lambda: False)
    manager = _make_manager({"webhook_url": "", "api_key": "", "profile_url": "", "auto_publish": False})
    assert manager.is_connected() is False

    manager = _make_manager({"webhook_url": "https://example.com/hook", "api_key": "", "profile_url": "", "auto_publish": False})
    assert manager.is_connected() is True


def test_is_connected_accepts_browser_fallback(monkeypatch):
    monkeypatch.setattr("managers.linktree_browser_publisher.browser_publish_enabled", lambda: True)
    manager = _make_manager({"webhook_url": "", "api_key": "", "profile_url": "", "auto_publish": False})

    assert manager.is_connected() is True


def test_is_auto_publish_enabled_requires_flag_and_publish_path(monkeypatch):
    monkeypatch.setattr("managers.linktree_browser_publisher.browser_publish_enabled", lambda: False)
    manager = _make_manager({"webhook_url": "https://example.com/hook", "api_key": "", "profile_url": "", "auto_publish": False})
    assert manager.is_auto_publish_enabled() is False

    manager = _make_manager({"webhook_url": "", "api_key": "", "profile_url": "", "auto_publish": True})
    assert manager.is_auto_publish_enabled() is False

    manager = _make_manager({"webhook_url": "https://example.com/hook", "api_key": "", "profile_url": "", "auto_publish": True})
    assert manager.is_auto_publish_enabled() is True


def test_is_auto_publish_enabled_accepts_browser_fallback(monkeypatch):
    monkeypatch.setattr("managers.linktree_browser_publisher.browser_publish_enabled", lambda: True)
    manager = _make_manager({"webhook_url": "", "api_key": "", "profile_url": "", "auto_publish": True})

    assert manager.is_auto_publish_enabled() is True


def test_connection_issue_requires_publish_path_for_auto_publish(monkeypatch):
    monkeypatch.setattr("managers.linktree_browser_publisher.browser_publish_enabled", lambda: False)
    manager = _make_manager({"webhook_url": "", "api_key": "", "profile_url": "https://linktr.ee/example", "auto_publish": True})

    ok, message = manager.require_connected_for_publish()

    assert ok is False
    assert "Webhook URL" in message
    assert "Linktree 자동 발행" in message


def test_connection_issue_rejects_invalid_webhook_scheme():
    manager = _make_manager({"webhook_url": "ftp://example.com/hook", "api_key": "", "profile_url": "", "auto_publish": True})

    ok, message = manager.require_connected_for_publish()

    assert ok is False
    assert "http://" in message


def test_connection_issue_rejects_wrong_linktree_account():
    manager = _make_manager(
        {
            "webhook_url": "https://example.com/hook",
            "api_key": "",
            "profile_url": "",
            "auto_publish": True,
            "account_email": "wrong@example.com",
            "expected_account_email": "k931103@gmail.com",
        }
    )

    ok, message = manager.require_connected_for_publish()

    assert ok is False
    assert "k931103@gmail.com" in message


def test_connection_issue_empty_when_publish_ready():
    manager = _make_manager({"webhook_url": "https://example.com/hook", "api_key": "", "profile_url": "", "auto_publish": True})

    ok, message = manager.require_connected_for_publish()

    assert ok is True
    assert message == ""


def test_publish_link_posts_payload_and_returns_true(monkeypatch):
    called = {}

    def _fake_post(url, json, headers, timeout):
        called["url"] = url
        called["json"] = json
        called["headers"] = headers
        called["timeout"] = timeout
        return _DummyResponse(status_code=201, text="created")

    monkeypatch.setattr("managers.linktree_manager.requests.post", _fake_post)

    manager = _make_manager(
        {
            "webhook_url": "https://example.com/hook",
            "api_key": "secret-token",
            "profile_url": "https://linktr.ee/example",
            "auto_publish": True,
        }
    )

    ok = manager.publish_link(
        title="Sample",
        url="https://link.coupang.com/a/abc",
        description="desc",
        source_url="https://www.coupang.com/vp/products/1",
        extra={"a": 1},
    )

    assert ok is True
    assert called["url"] == "https://example.com/hook"
    assert called["timeout"] == LinktreeManager.DEFAULT_TIMEOUT_SECONDS
    assert called["headers"]["Authorization"] == "Bearer secret-token"
    assert called["headers"]["X-API-Key"] == "secret-token"
    assert called["json"]["title"] == "Sample"
    assert called["json"]["url"] == "https://link.coupang.com/a/abc"
    assert called["json"]["extra"] == {"a": 1}


def test_publish_link_uses_browser_fallback_without_webhook(monkeypatch):
    called = {}

    def _fake_publish_link_via_visible_browser(**kwargs):
        called.update(kwargs)
        return {"ok": True, "method": "browser"}

    monkeypatch.setattr(
        "managers.linktree_browser_publisher.publish_link_via_visible_browser",
        _fake_publish_link_via_visible_browser,
    )

    manager = _make_manager(
        {
            "webhook_url": "",
            "api_key": "",
            "profile_url": "https://linktr.ee/example",
            "auto_publish": True,
        }
    )

    ok = manager.publish_link(
        title="Sample",
        url="https://www.coupang.com/vp/products/1",
        extra={"display_number": "[999]"},
    )

    assert ok is True
    assert called["title"] == "Sample"
    assert called["url"] == "https://www.coupang.com/vp/products/1"
    assert called["number"] == "[999]"
    assert called["profile_url"] == "https://linktr.ee/example"


def test_publish_link_returns_false_when_browser_fallback_fails(monkeypatch):
    monkeypatch.setattr(
        "managers.linktree_browser_publisher.publish_link_via_visible_browser",
        lambda **kwargs: {"ok": False, "method": "browser", "blocking_reason": "not verified"},
    )
    manager = _make_manager({"webhook_url": "", "api_key": "", "profile_url": "", "auto_publish": True})

    assert manager.publish_link(title="x", url="https://www.coupang.com/vp/products/1") is False


def test_publish_link_returns_false_on_http_failure(monkeypatch):
    def _fake_post(url, json, headers, timeout):
        return _DummyResponse(status_code=500, text="error")

    monkeypatch.setattr("managers.linktree_manager.requests.post", _fake_post)
    manager = _make_manager({"webhook_url": "https://example.com/hook", "api_key": "", "profile_url": "", "auto_publish": False})

    assert manager.publish_link(title="x", url="https://link.coupang.com/a/abc") is False


def test_publish_coupang_link_builds_expected_defaults(monkeypatch, tmp_path):
    captured = {}

    def _fake_publish_link(self, title, url, description="", source_url="", extra=None, timeout_seconds=None):
        captured["title"] = title
        captured["url"] = url
        captured["description"] = description
        captured["source_url"] = source_url
        captured["extra"] = extra
        return True

    monkeypatch.setattr(LinktreeManager, "publish_link", _fake_publish_link)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    manager = _make_manager({"webhook_url": "https://example.com/hook", "api_key": "", "profile_url": "", "auto_publish": True})
    ok = manager.publish_coupang_link(
        product_name="test product name",
        coupang_url="https://link.coupang.com/a/abc",
        source_url="https://www.coupang.com/vp/products/1",
    )

    assert ok is True
    assert captured["url"] == "https://link.coupang.com/a/abc"
    assert captured["title"].startswith("[001] test")
    assert len(captured["title"]) <= LinktreeManager.MAX_PRODUCT_TITLE_LENGTH
    assert captured["description"] == COUPANG_AFFILIATE_DISCLOSURE
    assert captured["source_url"] == "https://www.coupang.com/vp/products/1"
    assert captured["extra"]["channel"] == "shopping_shorts_maker"
    assert captured["extra"]["display_number"] == "[001]"


def test_publish_coupang_link_with_metadata_returns_matching_number(monkeypatch, tmp_path):
    captured = {}

    def _fake_publish_link(self, title, url, description="", source_url="", extra=None, timeout_seconds=None):
        captured["title"] = title
        captured["url"] = url
        captured["description"] = description
        captured["source_url"] = source_url
        captured["extra"] = extra
        return True

    monkeypatch.setattr(LinktreeManager, "publish_link", _fake_publish_link)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    manager = _make_manager({"webhook_url": "https://example.com/hook", "api_key": "", "profile_url": "", "auto_publish": True})
    result = manager.publish_coupang_link_with_metadata(
        product_name="카프 빅팬 접이식 핸디 선풍기",
        coupang_url="https://link.coupang.com/a/example",
        source_url="https://www.coupang.com/vp/products/1",
    )

    assert result["ok"] is True
    assert result["publish_index"] == 1
    assert result["number"] == "[001]"
    assert result["title"].startswith("[001] 카프")
    assert captured["title"] == result["title"]
    assert captured["extra"]["publish_index"] == 1
    assert captured["extra"]["display_number"] == "[001]"


def test_concise_product_title_is_limited_to_card_length():
    title = LinktreeManager._build_concise_product_title(
        "샤오미 무선 핸디 진공 청소기 초강력 흡입 업그레이드형"
    )
    assert len(title) <= LinktreeManager.MAX_PRODUCT_TITLE_LENGTH
    assert title


def test_concise_product_title_has_fallback():
    assert LinktreeManager._build_concise_product_title("") == "추천상품"


def test_profile_url_uses_default_when_not_configured():
    manager = _make_manager({"webhook_url": "", "api_key": "", "profile_url": "", "auto_publish": False})

    assert manager.get_profile_url() == "https://linktr.ee/studio.idol"
