import json
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from ui.design_system_v2 import DesignSystem
from ui.panels.topbar_panel import TopBarPanel
from utils import app_identity


_QT_APP = QApplication.instance() or QApplication([])


def test_load_app_identity_uses_installed_version_metadata(tmp_path, monkeypatch):
    version_file = tmp_path / "version.json"
    version_file.write_text(
        json.dumps(
            {
                "version": "2.3.4",
                "updated_at": "2026-08-11T15:30:00+09:00",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(app_identity, "get_version_file_path", lambda: version_file)
    monkeypatch.setattr(app_identity, "get_current_version", lambda: "0.0.0")

    identity = app_identity.load_app_identity()

    assert identity.name == "쇼핑 쇼츠 헬퍼"
    assert identity.version == "2.3.4"
    assert identity.display_metadata == "v2.3.4 · 업데이트 2026.08.11"
    assert "2026년 8월 11일" in identity.accessible_description


def test_topbar_displays_product_name_version_and_update_date(monkeypatch):
    identity = app_identity.AppIdentity(
        name="쇼핑 쇼츠 헬퍼",
        version="2.3.4",
        updated_at="2026-08-11",
        display_date="2026.08.11",
        accessible_date="2026년 8월 11일",
    )
    monkeypatch.setattr(
        "ui.panels.topbar_panel.load_app_identity",
        lambda: identity,
    )

    class Gui:
        login_data = None

    panel = TopBarPanel(Gui(), DesignSystem())

    assert panel.app_title.text() == "쇼핑 쇼츠 헬퍼"
    assert panel.app_title.minimumWidth() >= panel.app_title.sizeHint().width()
    assert panel.app_meta.text() == "v2.3.4 · 업데이트 2026.08.11"
    assert "현재 버전 2.3.4" in panel.app_meta.accessibleDescription()

    panel.set_compact_mode(True)
    assert not panel.brand_group.isHidden()
    assert panel.app_meta.text() == "v2.3.4 · 업데이트 2026.08.11"
    assert panel.minimumHeight() >= 112
    panel.close()


def test_topbar_logout_returns_to_login():
    calls = []

    class Gui:
        login_data = None
        exit_handler = SimpleNamespace(
            logout_to_login=lambda: calls.append("logout")
        )

    panel = TopBarPanel(Gui(), DesignSystem())

    panel.gui.logout_button.click()

    assert calls == ["logout"]
    panel.close()
