import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from startup.app_controller import AppController

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _App:
    def quitOnLastWindowClosed(self):
        return True

    def setQuitOnLastWindowClosed(self, _value):
        return None


def test_failed_main_construction_can_be_retried(monkeypatch):
    attempts = []

    class _BrokenMain:
        def __init__(self, **_kwargs):
            attempts.append("construct")
            raise RuntimeError("bad persisted setting")

    monkeypatch.setitem(
        sys.modules,
        "main",
        SimpleNamespace(VideoAnalyzerGUI=_BrokenMain),
    )
    controller = AppController(_App())
    recoveries = []
    monkeypatch.setattr(
        controller,
        "_record_startup_failure",
        lambda **_kwargs: {
            "code": "ST-M001",
            "component": "main.window",
            "offline_allowed": True,
        },
    )
    monkeypatch.setattr(
        controller,
        "_show_startup_recovery",
        lambda issue, **kwargs: recoveries.append((issue, kwargs)),
    )

    controller.launch_main_app()

    assert attempts == ["construct"]
    assert controller._main_launched is False
    assert controller._main_launching is False
    assert recoveries[0][0]["code"] == "ST-M001"
    recoveries[0][1]["retry_callback"]()
    assert attempts == ["construct", "construct"]


def test_offline_entry_never_creates_login_data(monkeypatch):
    controller = AppController(_App())
    controller.login_data = {"status": True, "data": {"token": "secret"}}
    calls = []
    monkeypatch.setattr(controller, "_proceed_to_loading", lambda: calls.append("load"))

    controller.enter_offline_mode()

    assert controller.login_data is None
    assert controller._offline_mode is True
    assert calls == ["load"]


def test_optional_manager_failure_is_contained(monkeypatch):
    pytest.importorskip("PyQt6")
    from main import VideoAnalyzerGUI

    gui = VideoAnalyzerGUI.__new__(VideoAnalyzerGUI)
    gui.safe_mode = False
    gui.startup_component_issues = []
    monkeypatch.setattr(
        "startup.diagnostics.record_startup_exception",
        lambda *_args, **_kwargs: SimpleNamespace(
            to_dict=lambda: {"code": "ST-Y001", "component": "youtube"}
        ),
    )

    result = gui._load_optional_manager(
        "youtube",
        "ST-Y001",
        lambda: (_ for _ in ()).throw(ValueError("corrupt settings")),
    )

    assert result is None
    assert gui.startup_component_issues == [
        {"code": "ST-Y001", "component": "youtube"}
    ]


def test_single_instance_failure_never_offers_offline_bypass(monkeypatch):
    from ui.windows.login_window import StartupLockError

    class _BrokenLogin:
        def __init__(self):
            raise StartupLockError(
                "STARTUP_INSTANCE_ALREADY_RUNNING", {"reason": "port_in_use"}
            )

    monkeypatch.setattr("ui.windows.login_window.Login", _BrokenLogin)
    controller = AppController(_App())
    recorded = []
    shown = []
    monkeypatch.setattr(controller, "_close_splash", lambda: None)
    monkeypatch.setattr(
        controller,
        "_record_startup_failure",
        lambda **kwargs: recorded.append(kwargs)
        or {
            "code": kwargs["code"],
            "component": kwargs["component"],
            "offline_allowed": kwargs["offline_allowed"],
        },
    )
    monkeypatch.setattr(
        controller,
        "_show_startup_recovery",
        lambda issue, **kwargs: shown.append((issue, kwargs)),
    )

    controller._show_login()

    assert recorded[0]["code"] == "STARTUP_INSTANCE_ALREADY_RUNNING"
    assert recorded[0]["component"] == "login.single_instance"
    assert recorded[0]["offline_allowed"] is False
    assert shown[0][1]["allow_offline"] is False


def test_offline_mode_disables_visible_work_controls():
    pytest.importorskip("PyQt6")
    from main import VideoAnalyzerGUI

    class _Control:
        def __init__(self):
            self.enabled = True
            self.tooltip = ""

        def setEnabled(self, value):
            self.enabled = bool(value)

        def isEnabled(self):
            return self.enabled

        def setToolTip(self, value):
            self.tooltip = value

        def toolTip(self):
            return self.tooltip

    gui = VideoAnalyzerGUI.__new__(VideoAnalyzerGUI)
    gui.start_batch_button = _Control()
    gui.sourcing_panel = SimpleNamespace(btn_start=_Control())

    gui._enforce_offline_settings_mode()

    assert gui.start_batch_button.isEnabled() is False
    assert gui.sourcing_panel.btn_start.isEnabled() is False
    assert "오프라인" in gui.start_batch_button.toolTip()


def test_settings_panel_failure_uses_recovery_panel_without_aborting_main(tmp_path):
    pytest.importorskip("PyQt6")
    script = r'''
from PyQt6.QtWidgets import QApplication
from app import ui_initializer

class BrokenSettingsTab:
    def __init__(self, *_args, **_kwargs):
        raise ValueError("corrupt Linktree setting")

ui_initializer.SettingsTab = BrokenSettingsTab
from main import VideoAnalyzerGUI
app = QApplication([])
app.setQuitOnLastWindowClosed(False)
gui = VideoAnalyzerGUI(login_data=None, offline_mode=True, safe_mode=True)
assert isinstance(gui.settings_tab, ui_initializer.UnavailableFeaturePanel)
assert gui.api_key_section is gui.settings_tab
assert any(issue.get("code") == "ST-T001" for issue in gui.startup_component_issues)
gui.close()
'''
    environment = os.environ.copy()
    environment.update(
        {
            "QT_QPA_PLATFORM": "offscreen",
            "HOME": str(tmp_path),
            "USERPROFILE": str(tmp_path),
            "APPDATA": str(tmp_path / "appdata"),
            "LOCALAPPDATA": str(tmp_path / "localappdata"),
            "SSMAKER_DISABLE_REMOTE_SETTINGS_SYNC": "1",
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
