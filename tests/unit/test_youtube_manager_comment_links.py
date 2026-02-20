from managers.youtube_manager import YouTubeManager


class _DummySettings:
    def __init__(self, enabled=True, prompt="", manual_link=""):
        self._enabled = enabled
        self._prompt = prompt
        self._manual_link = manual_link

    def get_youtube_comment_enabled(self):
        return self._enabled

    def get_youtube_comment_prompt(self):
        return self._prompt

    def get_youtube_comment_manual_product_link(self):
        return self._manual_link


def test_auto_comment_includes_purchase_and_original_links(monkeypatch):
    manager = object.__new__(YouTubeManager)
    settings = _DummySettings(
        enabled=True,
        prompt="고정 댓글에서 제품 정보를 확인해 주세요.",
        manual_link="",
    )
    monkeypatch.setattr("managers.youtube_manager.get_settings_manager", lambda: settings)

    text = manager._build_auto_comment_text(
        {
            "source_url": "https://www.coupang.com/vp/products/12345",
            "coupang_deep_link": "https://link.coupang.com/a/abc123",
        }
    )

    assert "고정 댓글에서 제품 정보를 확인해 주세요." in text
    assert "구매 링크: https://link.coupang.com/a/abc123" in text
    assert "원상품 링크: https://www.coupang.com/vp/products/12345" in text


def test_auto_comment_supports_placeholder_tokens_without_duplication(monkeypatch):
    manager = object.__new__(YouTubeManager)
    settings = _DummySettings(
        enabled=True,
        prompt="구매: {purchase_link}\n원상품: {original_link}",
        manual_link="https://www.coupang.com/vp/products/manual",
    )
    monkeypatch.setattr("managers.youtube_manager.get_settings_manager", lambda: settings)

    text = manager._build_auto_comment_text(
        {
            "source_url": "https://www.coupang.com/vp/products/source",
            "coupang_deep_link": "https://link.coupang.com/a/token",
        }
    )

    assert "구매: https://link.coupang.com/a/token" in text
    assert "원상품: https://www.coupang.com/vp/products/manual" in text
    assert "구매 링크:" not in text
    assert "원상품 링크:" not in text


def test_auto_comment_skips_original_link_for_non_coupang_source(monkeypatch):
    manager = object.__new__(YouTubeManager)
    settings = _DummySettings(
        enabled=True,
        prompt="댓글 안내문",
        manual_link="",
    )
    monkeypatch.setattr("managers.youtube_manager.get_settings_manager", lambda: settings)

    text = manager._build_auto_comment_text(
        {
            "source_url": "https://www.1688.com/offer/123",
            "coupang_deep_link": "",
        }
    )

    assert text == "댓글 안내문"
