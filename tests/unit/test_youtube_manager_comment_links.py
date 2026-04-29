from managers.youtube_manager import COUPANG_AFFILIATE_DISCLOSURE, YouTubeManager


class _DummySettings:
    def __init__(self, enabled=True, prompt="", manual_link="", linktree_profile_url=""):
        self._enabled = enabled
        self._prompt = prompt
        self._manual_link = manual_link
        self._linktree_profile_url = linktree_profile_url

    def get_youtube_comment_enabled(self):
        return self._enabled

    def get_youtube_comment_prompt(self):
        return self._prompt

    def get_youtube_comment_manual_product_link(self):
        return self._manual_link

    def get_linktree_settings(self):
        return {"profile_url": self._linktree_profile_url}


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


def test_auto_comment_always_includes_product_and_linktree_for_shopping_item(monkeypatch):
    manager = object.__new__(YouTubeManager)
    settings = _DummySettings(
        enabled=False,
        prompt="",
        manual_link="",
        linktree_profile_url="https://linktr.ee/studio.idol",
    )
    monkeypatch.setattr("managers.youtube_manager.get_settings_manager", lambda: settings)

    text = manager._build_auto_comment_text(
        {
            "product_info": "접이식 주방 선반 정리대",
            "source_url": "https://www.coupang.com/vp/products/12345",
            "coupang_deep_link": "https://link.coupang.com/a/abc123",
        }
    )

    assert "영상에서 소개한 상품 정보를 공유드립니다." in text
    assert "상품 설명: 접이식 주방 선반 정리대" in text
    assert "구매 링크: https://link.coupang.com/a/abc123" in text
    assert "Linktree: https://linktr.ee/studio.idol" in text
    assert "원상품 링크: https://www.coupang.com/vp/products/12345" in text


def test_auto_comment_uses_default_linktree_when_profile_is_empty(monkeypatch):
    manager = object.__new__(YouTubeManager)
    settings = _DummySettings(
        enabled=False,
        prompt="",
        manual_link="",
        linktree_profile_url="",
    )
    monkeypatch.setattr("managers.youtube_manager.get_settings_manager", lambda: settings)

    text = manager._build_auto_comment_text(
        {
            "product_info": "접이식 주방 선반 정리대",
            "source_url": "https://www.coupang.com/vp/products/12345",
            "coupang_deep_link": "https://link.coupang.com/a/abc123",
        }
    )

    assert "Linktree: https://linktr.ee/studio.idol" in text


def test_auto_comment_product_and_linktree_placeholders_do_not_duplicate(monkeypatch):
    manager = object.__new__(YouTubeManager)
    settings = _DummySettings(
        enabled=True,
        prompt="상품: {상품설명}\n모음: {linktree_link}",
        manual_link="",
        linktree_profile_url="https://linktr.ee/studio.idol",
    )
    monkeypatch.setattr("managers.youtube_manager.get_settings_manager", lambda: settings)

    text = manager._build_auto_comment_text(
        {
            "product_info": "접이식 주방 선반 정리대",
            "coupang_deep_link": "https://link.coupang.com/a/abc123",
        }
    )

    assert "상품: 접이식 주방 선반 정리대" in text
    assert "모음: https://linktr.ee/studio.idol" in text
    assert "상품 설명:" not in text
    assert "Linktree:" not in text
    assert "구매 링크: https://link.coupang.com/a/abc123" in text


def test_coupang_description_keeps_disclosure_and_purchase_link_visible():
    description = YouTubeManager.ensure_coupang_affiliate_compliance(
        "오늘의 쇼핑 추천입니다.",
        "https://link.coupang.com/a/example",
    )

    assert description.startswith(COUPANG_AFFILIATE_DISCLOSURE)
    assert "오늘의 쇼핑 추천입니다." in description
    assert "https://link.coupang.com/a/example" in description
