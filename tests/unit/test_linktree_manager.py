from managers.linktree_manager import LinktreeManager


class _DummySettings:
    def __init__(self, data):
        self._data = dict(data)

    def get_linktree_settings(self):
        return dict(self._data)


class _DummyResponse:
    def __init__(self, status_code=200, text="ok"):
        self.status_code = status_code
        self.text = text


def _make_manager(settings_data):
    manager = object.__new__(LinktreeManager)
    manager.settings = _DummySettings(settings_data)
    return manager


def test_is_connected_requires_webhook_url():
    manager = _make_manager({"webhook_url": "", "api_key": "", "profile_url": "", "auto_publish": False})
    assert manager.is_connected() is False

    manager = _make_manager({"webhook_url": "https://example.com/hook", "api_key": "", "profile_url": "", "auto_publish": False})
    assert manager.is_connected() is True


def test_is_auto_publish_enabled_requires_flag_and_webhook():
    manager = _make_manager({"webhook_url": "https://example.com/hook", "api_key": "", "profile_url": "", "auto_publish": False})
    assert manager.is_auto_publish_enabled() is False

    manager = _make_manager({"webhook_url": "", "api_key": "", "profile_url": "", "auto_publish": True})
    assert manager.is_auto_publish_enabled() is False

    manager = _make_manager({"webhook_url": "https://example.com/hook", "api_key": "", "profile_url": "", "auto_publish": True})
    assert manager.is_auto_publish_enabled() is True


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

    manager = _make_manager({"webhook_url": "https://example.com/hook", "api_key": "", "profile_url": "", "auto_publish": True})
    ok = manager.publish_coupang_link(
        product_name="test product name",
        coupang_url="https://link.coupang.com/a/abc",
        source_url="https://www.coupang.com/vp/products/1",
    )

    assert ok is True
    assert captured["url"] == "https://link.coupang.com/a/abc"
    assert captured["title"].startswith("[1] test")
    assert len(captured["title"]) <= LinktreeManager.MAX_PRODUCT_TITLE_LENGTH
    assert captured["source_url"] == "https://www.coupang.com/vp/products/1"
    assert captured["extra"]["channel"] == "shopping_shorts_maker"


def test_concise_product_title_is_limited_to_15_chars():
    title = LinktreeManager._build_concise_product_title(
        "샤오미 무선 핸디 진공 청소기 초강력 흡입 업그레이드형"
    )
    assert len(title) <= LinktreeManager.MAX_PRODUCT_TITLE_LENGTH
    assert title


def test_concise_product_title_has_fallback():
    assert LinktreeManager._build_concise_product_title("") == "추천상품"
