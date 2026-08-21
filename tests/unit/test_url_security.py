# -*- coding: utf-8 -*-
"""Network boundary validation tests."""

from dataclasses import FrozenInstanceError

import pytest

from utils.url_security import (
    COUPANG_PARTNER_LINK_CONTRACT_ID,
    MAX_PARTNER_LINK_HTTP_TOKENS,
    PartnerLinkParseResult,
    _collect_http_tokens,
    build_coupang_partner_link_contract_report,
    extract_coupang_partner_links,
    is_coupang_partner_link,
    is_official_coupang_url,
    is_public_http_url,
    is_trusted_service_url,
    normalize_coupang_partner_link,
    parse_coupang_partner_links,
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
    assert not is_coupang_partner_link("https://link.coupang.com/not-a-partner/code")
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


def test_partner_links_are_extracted_from_decorated_clipboard_text_in_order():
    raw = (
        "첫 번째: [상품 보기](https://link.coupang.com/a/f8i3PuVSqi)\n"
        "두 번째 https://link.coupang.com/a/f8i6WhHkK4, 그리고 중복 "
        "https://link.coupang.com/a/f8i3PuVSqi"
    )

    assert extract_coupang_partner_links(raw) == [
        "https://link.coupang.com/a/f8i3PuVSqi",
        "https://link.coupang.com/a/f8i6WhHkK4",
    ]
    assert normalize_coupang_partner_link(
        "상품 링크: https://link.coupang.com/a/f8jcQoPoke."
    ) == "https://link.coupang.com/a/f8jcQoPoke"


def test_coupang_partner_link_rejects_multiple_urls_in_single_input():
    combined = (
        "https://link.coupang.com/a/f8i3PuVSqi\n"
        "https://link.coupang.com/a/f8i6WhHkK4"
    )

    assert normalize_coupang_partner_link(combined) == ""
    assert not is_coupang_partner_link(combined)


def test_partner_link_parse_result_preserves_case_and_is_immutable():
    url = "https://link.coupang.com/a/f8i3PuVSqi"
    raw = f"\ufeff\u200b  {url}  \u2060"

    parsed = parse_coupang_partner_links(raw)

    assert parsed == PartnerLinkParseResult(
        links=(url,),
        reason_code="ok",
        raw_length=len(raw),
        boundary_format_character_count=3,
    )
    with pytest.raises(FrozenInstanceError):
        parsed.reason_code = "invalid_partner_link"


@pytest.mark.parametrize(
    ("raw", "reason_code"),
    [
        ("https://link.coupang.com/a/good?next=1", "invalid_partner_link"),
        ("https://link.coupang.com/a/good?", "invalid_partner_link"),
        ("https://link.coupang.com/a/good#fragment", "invalid_partner_link"),
        ("https://link.coupang.com/a/good#", "invalid_partner_link"),
        ("https://link.coupang.com/a/good.evil", "invalid_partner_link"),
        ("https://link.coupang.com./a/good", "unsupported_url"),
        ("https://link.coupang.com/a/go\u200bod", "invalid_partner_link"),
        ("https://link.coupang.com/a/go od", "invalid_partner_link"),
        ("https://link.coupang.com/a/go\nod", "invalid_partner_link"),
        ("https://link.coupang.com/a/go\nod 설명", "invalid_partner_link"),
        (
            "https://link.coupang.com/a/go\nod "
            "https://link.coupang.com/a/other",
            "mixed_http_urls",
        ),
        (
            "https://evil.example/?next=https://link.coupang.com/a/good",
            "mixed_http_urls",
        ),
        (
            "https://link.coupang.com/a/good https://example.com/other",
            "mixed_http_urls",
        ),
    ],
)
def test_partner_parser_rejects_the_mandatory_malicious_corpus(raw, reason_code):
    parsed = parse_coupang_partner_links(raw)

    assert parsed.links == ()
    assert parsed.reason_code == reason_code


def test_partner_parser_accepts_decorated_links_and_deduplicates_in_order():
    first = "https://link.coupang.com/a/FirstCase9"
    second = "https://link.coupa.ng/a/second_Case-8"
    raw = (
        f"첫 번째: [상품 보기]({first}).\n"
        f"두 번째: <{second}> 그리고 중복 {first}!"
    )

    parsed = parse_coupang_partner_links(raw)

    assert parsed.reason_code == "ok"
    assert parsed.links == (first, second)
    assert extract_coupang_partner_links(raw) == [first, second]
    assert normalize_coupang_partner_link(raw) == ""


@pytest.mark.parametrize(
    ("raw", "reason_code"),
    [
        ("", "empty"),
        ("링크가 없습니다", "unsupported_url"),
        ("https://www.coupang.com/vp/products/123", "normal_coupang_product"),
        ("http://link.coupang.com/a/code", "invalid_partner_link"),
        ("https://link.coupang.com.evil.example/a/code", "unsupported_url"),
    ],
)
def test_partner_parser_reports_actionable_single_input_reasons(raw, reason_code):
    assert parse_coupang_partner_links(raw).reason_code == reason_code


def test_partner_parser_enforces_size_and_http_token_limits_in_priority_order():
    oversized = "https://link.coupang.com/a/good" + (
        "x" * 65_536
    )
    assert parse_coupang_partner_links(oversized).reason_code == "input_too_large"
    assert parse_coupang_partner_links(" " * 70_000).reason_code == "empty"

    too_many = "\n".join(
        f"https://link.coupang.com/a/code{index}"
        for index in range(MAX_PARTNER_LINK_HTTP_TOKENS + 1)
    )
    assert parse_coupang_partner_links(too_many).reason_code == "too_many_links"


def test_http_token_collection_stops_at_the_overflow_sentinel():
    malicious = ("https://" * 8_000)[:65_536]

    tokens = _collect_http_tokens(malicious)

    assert len(tokens) == MAX_PARTNER_LINK_HTTP_TOKENS + 1
    assert parse_coupang_partner_links(malicious).reason_code == "too_many_links"


def test_partner_contract_report_is_stable_and_self_validating():
    report = build_coupang_partner_link_contract_report()

    assert list(report) == ["schema_version", "contract_id", "ok", "cases"]
    assert report["schema_version"] == 1
    assert report["contract_id"] == COUPANG_PARTNER_LINK_CONTRACT_ID
    assert report["ok"] is True
    assert report["cases"][0] == {
        "id": "reported_partner_link",
        "accepted": True,
        "links": ["https://link.coupang.com/a/f8i3PuVSqi"],
        "reason_code": "ok",
    }
    assert all(
        list(case) == ["id", "accepted", "links", "reason_code"]
        for case in report["cases"]
    )


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
