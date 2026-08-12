# -*- coding: utf-8 -*-
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel


QT_APP = QApplication.instance() or QApplication([])


def test_linktree_product_publish_blocks_non_partner_url(monkeypatch):
    from managers.linktree_manager import LinktreeManager

    manager = object.__new__(LinktreeManager)
    manager.settings = SimpleNamespace()
    monkeypatch.setattr(
        LinktreeManager,
        "publish_link",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("invalid URL must be blocked before publishing")
        ),
    )

    result = manager.publish_coupang_link_with_metadata(
        "상품", "https://www.coupang.com/vp/products/123"
    )

    assert result["ok"] is False
    assert result["error_code"] == "coupang_partner_link_required"
    assert "link.coupang.com" in result["error"]


def test_linktree_setup_says_public_profile_does_not_auto_publish(monkeypatch):
    from ui.components.linktree_setup_dialog import LinktreeSetupPanel

    settings = SimpleNamespace(
        get_linktree_settings=lambda: {
            "profile_url": "https://linktr.ee/example",
            "webhook_url": "",
            "api_key": "",
            "auto_publish": False,
        }
    )
    monkeypatch.setattr(
        "managers.settings_manager.get_settings_manager", lambda: settings
    )

    panel = LinktreeSetupPanel()
    text = "\n".join(label.text() for label in panel.findChildren(QLabel))

    assert "공개 주소만으로는 자동 등록되지 않아요" in text
    assert "실제 자동 상품 등록" in text
    assert "Webhook" in text
    assert panel.auto_publish_checkbox.isChecked() is False
