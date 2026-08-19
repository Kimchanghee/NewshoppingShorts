import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from ui.panels.url_input_panel import URLInputPanel


QT_APP = QApplication.instance() or QApplication([])


def _build_panel():
    gui = SimpleNamespace(
        state=SimpleNamespace(processing_mode="single", mix_video_urls=[]),
        add_url_from_entry=lambda: None,
        paste_and_extract=lambda: None,
        queue_manager=SimpleNamespace(add_mix_job=lambda _urls: "mix://job/test"),
        _on_step_selected=lambda _step: None,
        step_nav=SimpleNamespace(set_active=lambda _step: None),
    )
    return URLInputPanel(None, gui), gui


def _texts(panel):
    return [widget.text() for widget in panel.findChildren(QLabel)] + [
        widget.text() for widget in panel.findChildren(QPushButton)
    ]


def test_manual_video_input_surface_is_link_only():
    panel, _gui = _build_panel()
    texts = _texts(panel)

    assert any("영상 링크" in text for text in texts)
    assert not any("내 컴퓨터" in text for text in texts)
    assert not any("영상 파일" in text for text in texts)
    assert not hasattr(panel, "_select_local_file")
    assert not hasattr(panel, "_add_local_file_to_queue")
    assert "영상 링크 1개" in panel.gui.url_entry.placeholderText()


def test_mix_mode_remains_url_only():
    panel, gui = _build_panel()
    gui.state.processing_mode = "mix"
    panel.refresh_mode()
    texts = _texts(panel)

    assert panel.mix_mode_container.isHidden() is False
    assert panel.single_mode_container.isHidden() is True
    assert any("영상 링크 붙여넣기" in text for text in texts)
    assert not any("파일 추가" in text for text in texts)
