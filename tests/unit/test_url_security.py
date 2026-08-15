# -*- coding: utf-8 -*-
"""Network boundary validation tests."""

import pytest

from utils.url_security import (
    is_coupang_partner_link,
    is_official_coupang_url,
    is_public_http_url,
    is_trusted_service_url,
    normalize_coupang_partner_link,
)


def test_coupang_validator_rejects_lookalikes_credentials_and_http():
    assert is_official_coupang_url("https://www.coupang.com/vp/products/123")
    assert is_official_coupang_url("https://link.coupa.ng/a/example")
    assert not is_official_coupang_url("https://coupang.com.evil.example/product/123")
    assert not is_official_coupang_url("https://coupang.com@evil.example/product/123")
    assert not is_official_coupang_url("http://www.coupang.com/vp/products/123")


def test_coupang_partner_link_validator_rejects_normal_product_urls():
    assert is_coupang_partner_link("https://link.coupang.com/a/example")
    assert is_coupang_partner_link("https://link.coupa.ng/a/example")
    assert not is_coupang_partner_link("https://www.coupang.com/vp/products/123")
    assert not is_coupang_partner_link("https://coupang.com/vp/products/123")
    assert not is_coupang_partner_link("https://link.coupang.com/")
    assert not is_coupang_partner_link("https://link.coupang.com.evil.example/a/x")
    assert not is_coupang_partner_link("http://link.coupang.com/a/example")


def test_real_coupang_partner_links_are_normalized_and_accepted():
    urls = [
        "https://link.coupang.com/a/f8i3PuVSqi",
        "https://link.coupang.com/a/f8i6WhHkK4",
        "https://link.coupang.com/a/f8jcQoPoke",
        "https://link.coupang.com/a/f8jex1jVcG",
        "https://link.coupang.com/a/f8jkHwLWaO",
    ]

    for url in urls:
        assert normalize_coupang_partner_link(f"\ufeff\u200b  {url}  \u200b") == url
        assert is_coupang_partner_link(f"\ufeff\u200b{url}")


def test_coupang_partner_link_rejects_multiple_urls_in_single_input():
    combined = (
        "https://link.coupang.com/a/f8i3PuVSqi\n"
        "https://link.coupang.com/a/f8i6WhHkK4"
    )

    assert normalize_coupang_partner_link(combined) == ""
    assert not is_coupang_partner_link(combined)


def test_public_url_validator_rejects_private_network_targets():
    assert not is_public_http_url("http://127.0.0.1/internal")
    assert not is_public_http_url("http://169.254.169.254/latest/meta-data")
    assert not is_public_http_url("http://[::1]/internal")


def test_trusted_service_requires_exact_https_origin():
    trusted = ["https://newshopping-shorts-auth.vercel.app"]
    assert is_trusted_service_url(
        "https://newshopping-shorts-auth.vercel.app/api", trusted
    )
    assert not is_trusted_service_url(
        "https://newshopping-shorts-auth.vercel.app.evil.example", trusted
    )
    assert not is_trusted_service_url(
        "https://newshopping-shorts-auth.vercel.app@evil.example", trusted
    )
    assert not is_trusted_service_url(
        "http://newshopping-shorts-auth.vercel.app", trusted
    )


def test_computer_use_bridge_guard_blocks_token_exfiltration_origin(monkeypatch):
    from ui.panels.settings_tab import require_trusted_computer_use_bridge_url

    monkeypatch.delenv("COMPUTER_USE_TRUSTED_BRIDGE_ORIGINS", raising=False)
    assert require_trusted_computer_use_bridge_url(
        "https://newshopping-shorts-auth.vercel.app"
    ) == "https://newshopping-shorts-auth.vercel.app"

    try:
        require_trusted_computer_use_bridge_url("https://attacker.example")
    except ValueError as exc:
        assert "승인된 HTTPS" in str(exc)
    else:  # pragma: no cover - security regression
        raise AssertionError("untrusted bridge was accepted")


def test_computer_use_bridge_sends_server_owned_template_only(monkeypatch):
    from ui.panels import settings_tab

    captured = {}

    class Response:
        status_code = 202
        text = ""

        @staticmethod
        def json():
            return {"job_id": "job-1"}

    def fake_post(url, *, json, headers, timeout):
        captured.update(
            url=url,
            json=json,
            headers=headers,
            timeout=timeout,
        )
        return Response()

    class FakeSettingsTab:
        _setup_scope = "youtube"
        SETUP_STEP_DEFS = {"youtube": {"title": "YouTube"}}

        @staticmethod
        def _extract_logged_in_user_id():
            return "42"

        @staticmethod
        def _get_active_setup_step_id():
            return "youtube"

        @staticmethod
        def _computer_use_bridge_headers(api_key):
            return {"X-Computer-Use-Key": api_key}

    monkeypatch.setattr(settings_tab.requests, "post", fake_post)
    result = settings_tab.SettingsTab._submit_computer_use_bridge_job(
        FakeSettingsTab(),
        "https://newshopping-shorts-auth.vercel.app",
        "bridge-secret",
        "setup_target_youtube",
    )

    assert result["ok"] is True
    assert captured["json"]["template_id"] == "setup_target_youtube"
    assert "prompt" not in captured["json"]
    assert captured["headers"] == {"X-Computer-Use-Key": "bridge-secret"}


def test_hls_master_is_rejected_before_network_access(monkeypatch, tmp_path):
    from core.download import DouyinExtract

    monkeypatch.setattr(DouyinExtract.Tool, "validate_download_url", lambda _url: False)
    network_used = False

    def unexpected_request(*args, **kwargs):  # pragma: no cover - must not execute
        nonlocal network_used
        network_used = True
        raise AssertionError("network must not be reached")

    monkeypatch.setattr(DouyinExtract, "Request", unexpected_request)
    try:
        DouyinExtract._download_hls_m3u8(
            "http://169.254.169.254/latest/meta-data/master.m3u8",
            str(tmp_path / "out.ts"),
            {},
        )
    except ValueError as exc:
        assert "허용되지 않은 HLS URL" in str(exc)
    else:  # pragma: no cover - security regression
        raise AssertionError("unsafe HLS master was accepted")
    assert network_used is False


def test_validated_download_rejects_redirect_before_private_connection(monkeypatch):
    from urllib.parse import urlparse
    from utils import Tool

    connections = []

    class RedirectResponse:
        status = 302
        headers = {"Location": "http://169.254.169.254/latest/meta-data"}

        @staticmethod
        def close():
            return None

    class FakeConnection:
        def __init__(self, hostname, pinned_ip, *, port, timeout):
            connections.append((hostname, pinned_ip, port))

        def request(self, method, path, headers):
            return None

        @staticmethod
        def getresponse():
            return RedirectResponse()

        @staticmethod
        def close():
            return None

    monkeypatch.setattr(
        Tool,
        "resolve_public_http_url",
        lambda url, **kwargs: (urlparse(url), ("93.184.216.34",)),
    )
    monkeypatch.setattr(Tool, "_PinnedHTTPSConnection", FakeConnection)

    try:
        Tool.open_validated_url("https://v.douyin.com/safe")
    except ValueError as exc:
        assert "리다이렉트" in str(exc)
    else:  # pragma: no cover - security regression
        raise AssertionError("private redirect was followed")

    assert connections == [("v.douyin.com", "93.184.216.34", 443)]


def test_validated_download_rejects_https_downgrade_for_custom_allowlist(
    monkeypatch,
):
    from urllib.parse import urlparse
    from utils import Tool

    connections = []

    class RedirectResponse:
        status = 302
        headers = {"Location": "http://thumbnail.coupangcdn.com/image.jpg"}

        @staticmethod
        def close():
            return None

    class FakeConnection:
        def __init__(self, hostname, pinned_ip, *, port, timeout):
            connections.append((hostname, pinned_ip, port))

        def request(self, method, path, headers):
            return None

        @staticmethod
        def getresponse():
            return RedirectResponse()

        @staticmethod
        def close():
            return None

    monkeypatch.setattr(
        Tool,
        "resolve_public_http_url",
        lambda url, **_kwargs: (urlparse(url), ("93.184.216.34",)),
    )
    monkeypatch.setattr(Tool, "is_public_http_url", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(Tool, "_PinnedHTTPSConnection", FakeConnection)

    with pytest.raises(ValueError, match="downgrade"):
        Tool.open_validated_url(
            "https://thumbnail.coupangcdn.com/image.jpg",
            allowed_domains={"coupangcdn.com"},
            require_https=True,
        )

    assert connections == [("thumbnail.coupangcdn.com", "93.184.216.34", 443)]
