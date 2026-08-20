import errno
import os
from pathlib import Path
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
import requests

from caller import rest
from ui.windows import login_window


class _SocketHarness:
    def __init__(self, authoritative_port=34123):
        self._authoritative_port = authoritative_port
        self.serverSocket = None
        self.serverSockets = []
        self.server_port = None
        self.startup_error_code = None
        self.startup_error_context = {}

    def _fallback_port(self):
        return self._authoritative_port

    _configure_single_instance_socket = staticmethod(lambda _sock: None)


class _FakeSocket:
    def __init__(self, failures, created):
        self._failures = failures
        self.bound_port = None
        self.closed = False
        created.append(self)

    def bind(self, address):
        self.bound_port = address[1]
        failure = self._failures.get(self.bound_port)
        if failure:
            raise failure

    def listen(self, _backlog):
        return None

    def close(self):
        self.closed = True


def _install_fake_sockets(monkeypatch, failures):
    created = []
    monkeypatch.setattr(
        login_window.socket,
        "socket",
        lambda *_args: _FakeSocket(failures, created),
    )
    monkeypatch.delenv("SSMAKER_PORT", raising=False)
    monkeypatch.setattr(login_window, "DEFAULT_PROCESS_PORT", 20022)
    return created


def test_legacy_port_collision_is_nonfatal_after_authoritative_bind(monkeypatch):
    created = _install_fake_sockets(
        monkeypatch,
        {20022: OSError(errno.EADDRINUSE, "legacy port occupied")},
    )
    login = _SocketHarness(authoritative_port=34123)

    assert login_window.Login.setPort(login) is True
    assert login.server_port == 34123
    assert [sock.bound_port for sock in login.serverSockets] == [34123]
    assert created[0].closed is False
    assert created[1].closed is True
    assert login.startup_error_code is None


def test_authoritative_port_collision_blocks_second_instance(monkeypatch):
    created = _install_fake_sockets(
        monkeypatch,
        {34123: OSError(errno.EADDRINUSE, "authoritative port occupied")},
    )
    login = _SocketHarness(authoritative_port=34123)

    assert login_window.Login.setPort(login) is False
    assert login.serverSocket is None
    assert login.serverSockets == []
    assert created[0].closed is True
    assert login.startup_error_code == "STARTUP_INSTANCE_ALREADY_RUNNING"
    assert login.startup_error_context == {
        "authoritative_port": 34123,
        "errno": errno.EADDRINUSE,
        "reason": "port_in_use",
    }


def test_startup_lock_error_preserves_code_and_is_not_an_auth_state():
    error = login_window.StartupLockError(
        "STARTUP_INSTANCE_ALREADY_RUNNING", {"reason": "port_in_use"}
    )

    assert error.code == "STARTUP_INSTANCE_ALREADY_RUNNING"
    assert error.context == {"reason": "port_in_use"}
    assert "STARTUP_INSTANCE_ALREADY_RUNNING" in str(error)


def test_invalid_configured_port_has_clear_startup_failure(monkeypatch):
    monkeypatch.setenv("SSMAKER_PORT", "not-a-port")
    login = _SocketHarness()

    assert login_window.Login.setPort(login) is False
    assert login.startup_error_code == "STARTUP_PORT_CONFIG_INVALID"
    assert login.startup_error_context["setting"] == "SSMAKER_PORT"
    assert login.startup_error_context["value"] == "not-a-port"


@pytest.mark.parametrize(
    ("exception", "expected_code"),
    [
        (requests.exceptions.Timeout("slow"), "LOGIN_TIMEOUT"),
        (
            requests.exceptions.ConnectionError("connection refused"),
            "LOGIN_CONNECTION_ERROR",
        ),
        (
            requests.exceptions.ConnectionError("NameResolutionError: failed to resolve host"),
            "LOGIN_DNS_ERROR",
        ),
    ],
)
def test_login_transport_failures_are_retryable_and_offline_safe(
    monkeypatch, exception, expected_code
):
    class FailingSession:
        def post(self, *_args, **_kwargs):
            raise exception

    monkeypatch.setattr(rest, "_check_https_security", lambda: True)
    monkeypatch.setattr(rest, "_candidate_login_servers", lambda: ["https://auth.example"])
    monkeypatch.setattr(rest, "_secure_session", FailingSession())

    result = rest.login(
        userId="sstest_client",
        userPw="Password123",
        key="",
        ip="127.0.0.1",
        force=False,
    )

    assert result["error_module"] == "caller.rest"
    assert result["error_code"] == expected_code
    assert result["retryable"] is True
    assert result["offline_allowed"] is True


@pytest.mark.parametrize(
    ("http_status", "payload", "expected_code", "retryable", "offline_allowed"),
    [
        (
            500,
            {"status": "error", "message": "unavailable"},
            "LOGIN_SERVER_ERROR",
            True,
            True,
        ),
        (
            429,
            {"status": "error", "message": "too many"},
            "LOGIN_RATE_LIMITED",
            True,
            True,
        ),
        (
            401,
            {"status": "error", "message": "bad credentials"},
            "LOGIN_INVALID_CREDENTIALS",
            False,
            False,
        ),
        (
            403,
            {"status": "error", "message": "forbidden"},
            "LOGIN_FORBIDDEN",
            False,
            False,
        ),
        (
            200,
            {"status": False, "message": "bad credentials"},
            "LOGIN_INVALID_CREDENTIALS",
            False,
            False,
        ),
    ],
)
def test_login_http_failures_have_safe_recovery_classification(
    monkeypatch,
    http_status,
    payload,
    expected_code,
    retryable,
    offline_allowed,
):
    class FakeResponse:
        status_code = http_status
        text = __import__("json").dumps(payload)

    class FakeSession:
        def post(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr(rest, "_check_https_security", lambda: True)
    monkeypatch.setattr(rest, "_candidate_login_servers", lambda: ["https://auth.example"])
    monkeypatch.setattr(rest, "_secure_session", FakeSession())

    result = rest.login(
        userId="sstest_client",
        userPw="Password123",
        key="",
        ip="127.0.0.1",
        force=False,
    )

    assert result["error_module"] == "caller.rest"
    assert result["error_code"] == expected_code
    assert result["retryable"] is retryable
    assert result["offline_allowed"] is offline_allowed
    assert "token" not in result


def test_login_rate_limit_message_is_localized_before_reaching_the_dialog():
    payload = {
        "status": "EU005",
        "message": "Too many login attempts. Please try again later.",
        "error_code": "LOGIN_RATE_LIMITED",
    }

    message = rest._friendly_login_message(payload)

    assert "로그인 시도가 잠시 제한" in message
    assert "Too many" not in message


def _run_login_qt_script(script: str, tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "QT_QPA_PLATFORM": "offscreen",
            "HOME": str(tmp_path),
            "USERPROFILE": str(tmp_path),
            "APPDATA": str(tmp_path / "appdata"),
            "LOCALAPPDATA": str(tmp_path / "localappdata"),
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
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_login_window_does_not_offer_offline_settings_mode(tmp_path):
    _run_login_qt_script(
        r'''
import time
from PyQt6.QtWidgets import QApplication
from ui.windows import login_window
login_window.Login.setPort = lambda _self: True
login_window.ui_controller.userLoadInfo = lambda _self: None
login_window.Login._preload_ip = lambda _self: None
login_window.Login._warmup_server = lambda _self: None
app = QApplication([])
window = login_window.Login()
window.show()
app.processEvents()
assert not hasattr(window, "offlineSettingsButton")
assert not hasattr(window, "_enter_offline_mode")
assert not hasattr(app, "login_data")
window.close()
''',
        tmp_path,
    )


def test_login_window_supports_keyboard_login_navigation(tmp_path):
    _run_login_qt_script(
        r'''
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from ui.windows import login_window
login_window.Login.setPort = lambda _self: True
login_window.ui_controller.userLoadInfo = lambda _self: None
login_window.Login._preload_ip = lambda _self: None
login_window.Login._warmup_server = lambda _self: None
app = QApplication([])
requested = []
login_window.Login._loginCheck = lambda _self, *args, **kwargs: requested.append(True)
window = login_window.Login()
window.show()
app.processEvents()
window.idEdit.setFocus()
app.processEvents()
QTest.keyClick(window.idEdit, Qt.Key.Key_Return)
app.processEvents()
assert window.pwEdit.hasFocus()
assert requested == []
window.idEdit.setFocus()
window.idEdit.returnPressed.emit()
app.processEvents()
assert window.pwEdit.hasFocus()
window.pwEdit.returnPressed.emit()
assert requested == [True]
assert not window.loginButton.isDefault()
window._focus_id_shortcut.activated.emit()
assert window.idEdit.hasFocus()
window._focus_password_shortcut.activated.emit()
assert window.pwEdit.hasFocus()
window._submit_login_shortcut.activated.emit()
assert requested == [True, True]
assert window.idEdit.accessibleName() == "아이디 입력"
assert window.pwEdit.accessibleName() == "비밀번호 입력"
window.close()
''',
        tmp_path,
    )


def test_login_failure_hides_module_and_code_and_keeps_window(tmp_path):
    _run_login_qt_script(
        r'''
import time
from PyQt6.QtWidgets import QApplication
from ui.windows import login_window
login_window.Login.setPort = lambda _self: True
login_window.ui_controller.userLoadInfo = lambda _self: None
login_window.Login._preload_ip = lambda _self: None
login_window.Login._warmup_server = lambda _self: None
shown = []
login_window.show_warning = lambda _parent, title, message: shown.append((title, message))
login_window.rest.login = lambda **_kwargs: {
    "status": "error",
    "message": "server unavailable",
    "error_module": "caller.rest",
    "error_code": "LOGIN_CONNECTION_ERROR",
    "retryable": True,
    "offline_allowed": True,
}
app = QApplication([])
window = login_window.Login()
window._get_local_ip = lambda: "127.0.0.1"
window.idEdit.setText("sstest_client")
window.pwEdit.setText("Password123")
window.show()
app.processEvents()
window._loginCheck()
deadline = time.monotonic() + 2
while not shown and time.monotonic() < deadline:
    app.processEvents()
    time.sleep(0.01)
assert window.isVisible()
assert shown
assert shown[0][0] == "로그인 실패"
assert "caller.rest" not in shown[0][1]
assert "LOGIN_CONNECTION_ERROR" not in shown[0][1]
assert "server unavailable" not in shown[0][1]
assert "로그인하지 못했어요" in shown[0][1]
assert window.loginButton.isEnabled()
window.close()
''',
        tmp_path,
    )


def test_rejected_saved_auto_login_is_disabled_and_password_is_cleared(tmp_path):
    _run_login_qt_script(
        r'''
import time
from PyQt6.QtWidgets import QApplication
from ui.windows import login_window
login_window.Login.setPort = lambda _self: True
login_window.ui_controller.userLoadInfo = lambda self: (
    self.idEdit.setText("saved_user"),
    self.pwEdit.setText("RejectedPassword"),
    self.rememberCheckbox.setChecked(True),
    self.autoLoginCheckbox.setChecked(True),
    setattr(self, "auto_login_enabled", True),
)
login_window.Login._preload_ip = lambda _self: None
login_window.Login._warmup_server = lambda _self: None
cleared = []
def clear_rejected(self, login_id):
    cleared.append(login_id)
    self.auto_login_enabled = False
    self.autoLoginCheckbox.setChecked(False)
    self.pwEdit.clear()
login_window.ui_controller.clearRejectedAutoLogin = clear_rejected
login_window.rest.login = lambda **_kwargs: {
    "status": "EU001",
    "http_status": 401,
    "error_code": "LOGIN_INVALID_CREDENTIALS",
    "message": "invalid password",
}
app = QApplication([])
window = login_window.Login()
shown = []
window.showCustomMessageBox = lambda title, message: shown.append((title, message))
window._get_local_ip = lambda: "127.0.0.1"
window._attempt_auto_login()
deadline = time.monotonic() + 2
while not shown and time.monotonic() < deadline:
    app.processEvents()
    time.sleep(0.01)
assert cleared == ["saved_user"]
assert window.pwEdit.text() == ""
assert window.autoLoginCheckbox.isChecked() is False
assert "자동 로그인" in shown[0][1]
window.close()
''',
        tmp_path,
    )


def test_rejected_manual_login_clears_only_password_and_focuses_retry(tmp_path):
    _run_login_qt_script(
        r'''
import time
from PyQt6.QtWidgets import QApplication
from ui.windows import login_window
login_window.Login.setPort = lambda _self: True
login_window.ui_controller.userLoadInfo = lambda _self: None
login_window.Login._preload_ip = lambda _self: None
login_window.Login._warmup_server = lambda _self: None
login_window.rest.login = lambda **_kwargs: {
    "status": "EU001",
    "http_status": 401,
    "error_code": "LOGIN_INVALID_CREDENTIALS",
    "message": "invalid password",
}
app = QApplication([])
window = login_window.Login()
window.idEdit.setText("saved_user")
window.pwEdit.setText("RejectedPassword")
window._get_local_ip = lambda: "127.0.0.1"
shown = []
window.showCustomMessageBox = lambda title, message: shown.append((title, message))
window._loginCheck()
deadline = time.monotonic() + 2
while not shown and time.monotonic() < deadline:
    app.processEvents()
    time.sleep(0.01)
assert shown
assert window.idEdit.text() == "saved_user"
assert window.pwEdit.text() == ""
assert window.focusWidget() is window.pwEdit
window.close()
''',
        tmp_path,
    )


def test_login_request_keeps_ui_responsive_while_network_runs(tmp_path):
    _run_login_qt_script(
        r'''
import time
from PyQt6.QtWidgets import QApplication
from ui.windows import login_window
login_window.Login.setPort = lambda _self: True
login_window.ui_controller.userLoadInfo = lambda _self: None
login_window.Login._preload_ip = lambda _self: None
login_window.Login._warmup_server = lambda _self: None
def slow_login(**_kwargs):
    time.sleep(0.25)
    return {
        "status": "error",
        "message": "server unavailable",
        "error_module": "caller.rest",
        "error_code": "LOGIN_CONNECTION_ERROR",
    }
login_window.rest.login = slow_login
app = QApplication([])
window = login_window.Login()
window._get_local_ip = lambda: "127.0.0.1"
window.idEdit.setText("sstest_client")
window.pwEdit.setText("Password123")
shown = []
window.showCustomMessageBox = lambda title, message: shown.append((title, message))

started_at = time.perf_counter()
window._loginCheck()
returned_after = time.perf_counter() - started_at
assert returned_after < 0.1
assert window.loginButton.isEnabled() is False

deadline = time.monotonic() + 2
while not shown and time.monotonic() < deadline:
    app.processEvents()
    time.sleep(0.01)
assert shown
assert window.loginButton.isEnabled()
window.close()
''',
        tmp_path,
    )


def test_login_reuses_preloaded_local_ip_without_reopening_socket(tmp_path):
    _run_login_qt_script(
        r'''
from PyQt6.QtWidgets import QApplication
from ui.windows import login_window
login_window.Login.setPort = lambda _self: True
login_window.ui_controller.userLoadInfo = lambda _self: None
login_window.Login._preload_ip = lambda _self: None
login_window.Login._warmup_server = lambda _self: None
app = QApplication([])
window = login_window.Login()
window._cached_local_ip = "10.0.0.7"
login_window.socket.socket = lambda *_args, **_kwargs: (_ for _ in ()).throw(
    AssertionError("socket should not be reopened")
)
assert window._get_local_ip() == "10.0.0.7"
window.close()
''',
        tmp_path,
    )


def test_duplicate_login_is_blocked_without_force_takeover(tmp_path):
    _run_login_qt_script(
        r'''
import time
from PyQt6.QtWidgets import QApplication
from ui.windows import login_window
login_window.Login.setPort = lambda _self: True
login_window.ui_controller.userLoadInfo = lambda _self: None
login_window.Login._preload_ip = lambda _self: None
login_window.Login._warmup_server = lambda _self: None
shown = []
requests = []
login_window.show_warning = lambda _parent, title, message: shown.append((title, message))
def blocked_login(**kwargs):
    requests.append(kwargs)
    return {
        "status": "EU003",
        "error_module": "caller.rest",
        "error_code": "LOGIN_ALREADY_ACTIVE",
    }
login_window.rest.login = blocked_login
app = QApplication([])
window = login_window.Login()
window._get_local_ip = lambda: "127.0.0.1"
window.idEdit.setText("sstest_client")
window.pwEdit.setText("Password123")
window.show()
app.processEvents()
window._loginCheck()
deadline = time.monotonic() + 2
while not shown and time.monotonic() < deadline:
    app.processEvents()
    time.sleep(0.01)
assert len(requests) == 1
assert requests[0]["force"] is False
assert shown and shown[0][0] == "중복 로그인"
assert "기존 기기에서 로그아웃" in shown[0][1]
assert window.isVisible()
window.close()
''',
        tmp_path,
    )


def test_registration_uses_issued_session_without_second_login(tmp_path):
    _run_login_qt_script(
        r'''
from types import SimpleNamespace
from PyQt6.QtWidgets import QApplication
from ui.windows import login_window
login_window.Login.setPort = lambda _self: True
login_window.ui_controller.userLoadInfo = lambda _self: None
login_window.Login._preload_ip = lambda _self: None
login_window.Login._warmup_server = lambda _self: None
app = QApplication([])
window = login_window.Login()
window.reg_dialog = SimpleNamespace(registration_result={
    "success": True,
    "data": {
        "user_id": 91,
        "username": "new_member",
        "work_count": 5,
        "is_trial": True,
        "token": "registration-token",
    },
})
tokens = []
completed = []
login_window.rest._set_auth_token = tokens.append
window._handle_login_success = completed.append
window._on_registration_requested(
    "New Member",
    "new_member",
    "Password123!",
    "01012345678",
    "new_member@example.com",
)
assert tokens == ["registration-token"]
assert len(completed) == 1
assert completed[0]["status"] is True
assert completed[0]["data"]["token"] == "registration-token"
assert completed[0]["data"]["data"]["id"] == "91"
assert completed[0]["data"]["data"]["user_type"] == "trial"
window.close()
''',
        tmp_path,
    )


def test_main_window_is_resizable_and_first_page_keeps_overflow_reachable(tmp_path):
    _run_login_qt_script(
        r'''
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from main import VideoAnalyzerGUI
app = QApplication([])
window = VideoAnalyzerGUI(login_data=None, offline_mode=True, safe_mode=True)
window.show()
for _ in range(10):
    app.processEvents()
scroll = window.content_scroll
assert window.minimumWidth() <= window.width()
assert window.minimumHeight() <= window.height()
assert window.maximumWidth() > window.width()
assert window.maximumHeight() > window.height()
assert window.windowFlags() & Qt.WindowType.WindowMaximizeButtonHint
assert window.stack.currentIndex() == window.page_index["mode"]
assert window.mode_selection_panel._card_columns == 3
assert scroll.horizontalScrollBar().maximum() == 0
assert scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
window.close()
''',
        tmp_path,
    )
