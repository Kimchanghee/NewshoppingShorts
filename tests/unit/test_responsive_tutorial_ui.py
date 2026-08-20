import os
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QPushButton, QWidget

from ui.components.step_nav import StepNav
from ui.components.tutorial_manager import TutorialManager
from ui.components.tutorial_tooltip import TutorialTooltip
from ui.responsive import apply_fixed_window_geometry, calculate_window_rect, layout_profile


_QT_APP = QApplication.instance() or QApplication([])


def _app():
    return _QT_APP


def test_initial_window_geometry_never_exceeds_available_desktop():
    for available in (
        QRect(0, 0, 1024, 576),
        QRect(0, 0, 1280, 680),
        QRect(1920, 0, 1920, 1040),
        QRect(-1080, 0, 1080, 1880),
        QRect(0, 0, 3440, 1400),
        QRect(20, 30, 240, 200),
    ):
        result = calculate_window_rect(available)
        assert available.contains(result)
        assert result.width() <= 1280
        assert result.height() <= 800


def test_window_profile_stays_resizable_and_maximizable():
    window = QMainWindow()
    target = apply_fixed_window_geometry(window, QRect(0, 0, 1920, 1040))

    assert target.size() == QSize(1280, 800)
    assert window.size() == target.size()
    assert window.minimumSize() == QSize(760, 520)
    assert window.maximumWidth() > target.width()
    assert window.maximumHeight() > target.height()
    assert window.windowFlags() & Qt.WindowType.WindowMaximizeButtonHint

    compact = apply_fixed_window_geometry(window, QRect(0, 0, 1280, 680))
    assert compact.size() == QSize(1256, 656)
    assert window.minimumSize() == QSize(760, 520)
    window.resize(900, 560)
    assert window.size() == QSize(900, 560)
    window.close()


def test_shell_breakpoints_preserve_content_on_short_and_narrow_windows():
    narrow = layout_profile(QSize(800, 600))
    assert narrow.navigation_mode == "icons"
    assert narrow.show_progress_panel is False
    assert narrow.compact_topbar is True
    assert narrow.compact_mode_page is True

    medium = layout_profile(QSize(1024, 720))
    assert medium.navigation_mode == "icons"
    assert medium.show_progress_panel is False

    compact = layout_profile(QSize(1200, 720))
    assert compact.navigation_mode == "compact"

    large = layout_profile(QSize(1600, 900))
    assert large.navigation_mode == "full"
    assert large.show_progress_panel is True
    assert large.compact_mode_page is False


def test_tutorial_tooltip_and_next_button_stay_inside_every_viewport():
    app = _app()
    viewports = (
        QSize(800, 600),
        QSize(1024, 576),
        QSize(1024, 680),
        QSize(1280, 720),
        QSize(1440, 900),
        QSize(1080, 1800),
    )

    for viewport in viewports:
        parent = QWidget()
        parent.resize(viewport)
        parent.show()
        tooltip = TutorialTooltip(parent)
        tooltip.set_content(
            13,
            13,
            "API Key 연결과 자동 설정 도우미",
            "영상 제작을 시작하려면 Gemini API Key가 필요합니다. "
            "수동 입력이 어렵다면 자동 설정 도우미를 실행해 단계대로 진행하세요.",
            is_last=True,
        )
        tooltip.show()
        app.processEvents()

        safe = parent.rect().adjusted(12, 12, -12, -12)
        targets = (
            QRect(0, 0, 72, 36),
            QRect(viewport.width() - 200, 12, 180, 44),
            QRect(0, viewport.height() - 220, 220, 200),
            QRect(viewport.width() // 2 - 100, viewport.height() // 2 - 50, 200, 100),
        )
        for target in targets:
            rect = TutorialManager.calculate_tooltip_rect(safe, target, tooltip.size())
            tooltip.move(rect.topLeft())
            app.processEvents()

            assert safe.contains(tooltip.geometry())
            next_top_left = tooltip.next_btn.mapTo(parent, QPoint(0, 0))
            next_rect = QRect(next_top_left, tooltip.next_btn.size())
            assert safe.contains(next_rect)

        tooltip.close()
        parent.close()


def test_step_navigation_switches_to_accessible_compact_rails():
    app = _app()
    steps = [
        ("mode", "만들기 방식", "mode"),
        ("source", "영상 넣기", "source"),
        ("settings", "설정", "settings"),
    ]
    nav = StepNav(steps)
    nav.show()

    nav.set_display_mode("icons")
    app.processEvents()
    assert nav.width() == 72
    assert all(not button.text_label.isVisible() for button in nav._buttons.values())
    assert all(button.toolTip() for button in nav._buttons.values())

    nav.set_display_mode("compact")
    app.processEvents()
    assert nav.width() == 220
    assert all(button.text_label.isVisible() for button in nav._buttons.values())

    nav.set_display_mode("full")
    app.processEvents()
    assert nav.width() == 280
    nav.close()


def test_tutorial_prepare_reveals_nested_settings_sections():
    class FakeSettings(QWidget):
        def __init__(self):
            super().__init__()
            self.connect_selected = False
            self.api_selected = False

        def select_connect_tab(self):
            self.connect_selected = True

        def focus_api_key_setup(self):
            self.api_selected = True

    class FakeGui(QWidget):
        def __init__(self):
            super().__init__()
            self.settings_tab = FakeSettings()

    gui = FakeGui()
    manager = TutorialManager(gui)
    manager._prepare_step({"prepare": "select_connect_tab"})
    manager._prepare_step({"prepare": "focus_api_key_setup"})

    assert gui.settings_tab.connect_selected is True
    assert gui.settings_tab.api_selected is True


def test_platform_worker_updates_are_queued_to_qt_thread(monkeypatch):
    from ui.panels.sourcing_panel import SourcingPanel

    def setup_minimal_ui(panel):
        panel.results_label = QLabel()
        panel.btn_start = QPushButton()
        panel._apply_button_style = lambda *, disabled: None

    monkeypatch.setattr(SourcingPanel, "_setup_ui", setup_minimal_ui)
    panel = SourcingPanel(None, None)
    panel._running = True
    panel.btn_start.setEnabled(False)

    worker = threading.Thread(
        target=lambda: (
            panel._safe_set_results("백그라운드 작업 완료"),
            panel._reset_start_button(),
        )
    )
    worker.start()
    worker.join(timeout=2)
    _app().processEvents()

    assert panel.results_label.text() == "백그라운드 작업 완료"
    assert panel.btn_start.isEnabled() is True
    assert panel._running is False
