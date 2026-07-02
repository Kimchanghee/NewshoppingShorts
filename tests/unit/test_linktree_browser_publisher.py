from urllib.parse import parse_qs, urlparse

from managers import linktree_browser_publisher as publisher


def test_build_create_link_url_encodes_linktree_deeplink_params():
    create_url = publisher._build_create_link_url(
        "[135] cooling towel sports towel",
        "https://www.coupang.com/vp/products/1775870654",
    )

    parsed = urlparse(create_url)
    params = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "linktr.ee"
    assert parsed.path == "/admin/links"
    assert params["action"] == ["create-link"]
    assert params["title"] == ["[135] cooling towel sports towel"]
    assert params["url"] == ["https://www.coupang.com/vp/products/1775870654"]
    assert params["active"] == ["true"]


def test_browser_publish_existing_card_does_not_open_browser(monkeypatch):
    monkeypatch.setenv("SSMAKER_LINKTREE_BROWSER_PUBLISH", "1")
    monkeypatch.setattr(
        publisher,
        "_verify_public_card",
        lambda number, purchase_url, profile_url: {"ok": True, "has_number": True, "has_purchase_url": True},
    )

    def fail_open_browser(_url):
        raise AssertionError("browser should not open when the card already exists")

    def fail_close_browser():
        raise AssertionError("browser cleanup should not run when no browser was opened")

    monkeypatch.setattr(publisher, "_open_browser_url", fail_open_browser)
    monkeypatch.setattr(publisher, "_close_linktree_browser_window", fail_close_browser)

    result = publisher.publish_link_via_visible_browser(
        title="[135] cooling towel sports towel",
        url="https://www.coupang.com/vp/products/1775870654",
        number="[135]",
    )

    assert result["ok"] is True
    assert result["method"] == "browser_existing"


def test_browser_publish_disabled_by_default_does_not_open_browser(monkeypatch):
    def fail_open_browser(_url):
        raise AssertionError("browser should not open unless the fallback is explicitly enabled")

    monkeypatch.delenv("SSMAKER_LINKTREE_BROWSER_PUBLISH", raising=False)
    monkeypatch.setattr(publisher, "_open_browser_url", fail_open_browser)

    result = publisher.publish_link_via_visible_browser(
        title="[135] cooling towel sports towel",
        url="https://www.coupang.com/vp/products/1775870654",
        number="[135]",
    )

    assert result["ok"] is False
    assert result["method"] == "browser_disabled"


def test_browser_publish_opens_create_link_deeplink_and_verifies(monkeypatch):
    monkeypatch.setenv("SSMAKER_LINKTREE_BROWSER_PUBLISH", "1")
    opened = []
    closed = []
    checks = [
        {"ok": False, "has_number": False, "has_purchase_url": False},
        {"ok": True, "has_number": True, "has_purchase_url": True},
    ]

    def fake_verify(number, purchase_url, profile_url):
        return checks.pop(0)

    monkeypatch.setattr(publisher, "_verify_public_card", fake_verify)
    monkeypatch.setattr(publisher, "_open_browser_url", lambda url: opened.append(url))
    monkeypatch.setattr(
        publisher,
        "_close_linktree_browser_window",
        lambda: closed.append(True) or {"attempted": True, "closed": True},
    )
    monkeypatch.setattr(publisher.time, "sleep", lambda _seconds: None)

    result = publisher.publish_link_via_visible_browser(
        title="[135] cooling towel sports towel",
        url="https://www.coupang.com/vp/products/1775870654",
        number="[135]",
    )

    assert result["ok"] is True
    assert result["method"] == "browser_deeplink"
    assert len(opened) == 1
    assert closed == [True]
    assert result["browser_cleanup"] == {"attempted": True, "closed": True}
    params = parse_qs(urlparse(opened[0]).query)
    assert params["action"] == ["create-link"]
    assert params["url"] == ["https://www.coupang.com/vp/products/1775870654"]


def test_browser_publish_closes_deeplink_window_after_timeout(monkeypatch):
    monkeypatch.setenv("SSMAKER_LINKTREE_BROWSER_PUBLISH", "1")
    opened = []
    closed = []
    now = [0]

    def fake_time():
        now[0] += 10
        return now[0]

    monkeypatch.setattr(
        publisher,
        "_verify_public_card",
        lambda number, purchase_url, profile_url: {"ok": False, "has_number": False, "has_purchase_url": False},
    )
    monkeypatch.setattr(publisher, "_open_browser_url", lambda url: opened.append(url))
    monkeypatch.setattr(
        publisher,
        "_close_linktree_browser_window",
        lambda: closed.append(True) or {"attempted": True, "closed": True},
    )
    monkeypatch.setattr(publisher.time, "time", fake_time)
    monkeypatch.setattr(publisher.time, "sleep", lambda _seconds: None)

    result = publisher.publish_link_via_visible_browser(
        title="[135] cooling towel sports towel",
        url="https://www.coupang.com/vp/products/1775870654",
        number="[135]",
        timeout_seconds=15,
    )

    assert result["ok"] is False
    assert result["method"] == "browser_deeplink"
    assert len(opened) == 1
    assert closed == [True]
    assert result["browser_cleanup"]["closed"] is True
