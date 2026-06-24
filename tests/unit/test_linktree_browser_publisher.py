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
    monkeypatch.setattr(
        publisher,
        "_verify_public_card",
        lambda number, purchase_url, profile_url: {"ok": True, "has_number": True, "has_purchase_url": True},
    )

    def fail_open_browser(_url):
        raise AssertionError("browser should not open when the card already exists")

    monkeypatch.setattr(publisher, "_open_browser_url", fail_open_browser)

    result = publisher.publish_link_via_visible_browser(
        title="[135] cooling towel sports towel",
        url="https://www.coupang.com/vp/products/1775870654",
        number="[135]",
    )

    assert result["ok"] is True
    assert result["method"] == "browser_existing"


def test_browser_publish_opens_create_link_deeplink_and_verifies(monkeypatch):
    opened = []
    checks = [
        {"ok": False, "has_number": False, "has_purchase_url": False},
        {"ok": True, "has_number": True, "has_purchase_url": True},
    ]

    def fake_verify(number, purchase_url, profile_url):
        return checks.pop(0)

    monkeypatch.setattr(publisher, "_verify_public_card", fake_verify)
    monkeypatch.setattr(publisher, "_open_browser_url", lambda url: opened.append(url))
    monkeypatch.setattr(publisher.time, "sleep", lambda _seconds: None)

    result = publisher.publish_link_via_visible_browser(
        title="[135] cooling towel sports towel",
        url="https://www.coupang.com/vp/products/1775870654",
        number="[135]",
    )

    assert result["ok"] is True
    assert result["method"] == "browser_deeplink"
    assert len(opened) == 1
    params = parse_qs(urlparse(opened[0]).query)
    assert params["action"] == ["create-link"]
    assert params["url"] == ["https://www.coupang.com/vp/products/1775870654"]
