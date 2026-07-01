from scripts import run_summer_coupang_queue_once as queue_runner


def test_coupang_partner_link_detection():
    assert queue_runner.is_coupang_partner_link("https://link.coupang.com/a/example")
    assert not queue_runner.is_coupang_partner_link("https://www.coupang.com/vp/products/12345")
    assert not queue_runner.is_coupang_partner_link("")


def test_purchase_validation_blocks_plain_coupang_url(monkeypatch):
    monkeypatch.delenv(queue_runner.AFFILIATE_LINK_REQUIRED_ENV, raising=False)
    monkeypatch.setattr(queue_runner, "coupang_api_keys_configured", lambda: False)

    result = queue_runner.validate_purchase_url_for_upload(
        {"coupang_url": "https://www.coupang.com/vp/products/12345"},
        "https://www.coupang.com/vp/products/12345",
    )

    assert result["ok"] is False
    assert result["affiliate_required"] is True
    assert "affiliate link is required" in result["blocking_reason"]


def test_purchase_validation_allows_partner_link(monkeypatch):
    monkeypatch.delenv(queue_runner.AFFILIATE_LINK_REQUIRED_ENV, raising=False)

    result = queue_runner.validate_purchase_url_for_upload(
        {"coupang_url": "https://www.coupang.com/vp/products/12345"},
        "https://link.coupang.com/a/example",
    )

    assert result == {"ok": True, "blocking_reason": ""}


def test_presourcing_validation_blocks_when_no_affiliate_inputs(monkeypatch):
    monkeypatch.delenv(queue_runner.AFFILIATE_LINK_REQUIRED_ENV, raising=False)
    monkeypatch.setattr(queue_runner, "coupang_api_keys_configured", lambda: False)

    result = queue_runner.validate_affiliate_inputs_before_sourcing(
        {"coupang_url": "https://www.coupang.com/vp/products/12345"}
    )

    assert result["ok"] is False
    assert result["coupang_keys_present"] is False


def test_presourcing_validation_allows_generation_when_keys_exist(monkeypatch):
    monkeypatch.delenv(queue_runner.AFFILIATE_LINK_REQUIRED_ENV, raising=False)
    monkeypatch.setattr(queue_runner, "coupang_api_keys_configured", lambda: True)

    result = queue_runner.validate_affiliate_inputs_before_sourcing(
        {"coupang_url": "https://www.coupang.com/vp/products/12345"}
    )

    assert result == {"ok": True, "blocking_reason": ""}


def test_affiliate_blocked_item_retries_after_keys_are_available(monkeypatch):
    item = {
        "status": queue_runner.AFFILIATE_LINK_BLOCKED_STATUS,
        "coupang_url": "https://www.coupang.com/vp/products/12345",
    }
    monkeypatch.setattr(queue_runner, "coupang_api_keys_configured", lambda: False)
    assert queue_runner.is_processable_queue_item(item) is False

    monkeypatch.setattr(queue_runner, "coupang_api_keys_configured", lambda: True)
    assert queue_runner.is_processable_queue_item(item) is True
