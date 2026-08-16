# -*- coding: utf-8 -*-
"""
Login window for PyQt6
"""
import os
import sys
import socket
import errno
import threading
import hashlib
import json
from pathlib import Path
from typing import Optional, Any, Dict

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtWidgets import QMainWindow, QApplication
from PyQt6.QtGui import QIcon

from caller import rest, ui_controller
from ui.login_ui_modern import ModernLoginUi as Ui_LoginWindow
from ui.components.custom_dialog import show_warning
from utils.logging_config import get_logger
from startup.constants import DEFAULT_PROCESS_PORT

logger = get_logger(__name__)


class StartupLockError(RuntimeError):
    """Structured local startup-lock failure; never eligible for offline bypass."""

    def __init__(self, code: str, context: Dict[str, Any]):
        self.code = str(code or "STARTUP_SINGLE_INSTANCE_FAILED")
        self.context = dict(context or {})
        super().__init__(
            f"[{self.code}] Unable to acquire the application startup lock; "
            f"context={self.context}"
        )

class Login(QMainWindow, Ui_LoginWindow):
    """Login window with authentication functionality for PyQt6"""

    WINDOW_WIDTH = 720
    WINDOW_HEIGHT = 760
    LEFT_PANEL_WIDTH = 300
    RIGHT_PANEL_WIDTH = 420

    # Signal emitted when window is fully displayed
    window_ready = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowIcon(QIcon("resource/trayIcon.png"))
        self.oldPos: Optional[QPoint] = None
        self.serverSocket: Optional[socket.socket] = None
        self.serverSockets: list[socket.socket] = []
        self.server_port: Optional[int] = None
        self.startup_error_code: Optional[str] = None
        self.startup_error_context: Dict[str, Any] = {}
        self.auto_login_enabled = False
        
        if self.setPort():
            self.setupUi(self)
            self._apply_version_label()
            ui_controller.userLoadInfo(self)
            self._connect_login_option_controls()
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self._center_on_active_screen()
            
            # Connect signals
            self.loginButton.clicked.connect(self._loginCheck)
            self.offlineSettingsButton.clicked.connect(self._enter_offline_mode)
            self.minimumButton.clicked.connect(self.showMinimized)
            self.exitButton.clicked.connect(self._closeWindow)
            self.registerRequestButton.clicked.connect(self._openRegistrationDialog)
            
            self._preload_ip()
            self._warmup_server()
            QtCore.QTimer.singleShot(450, self._attempt_auto_login)
        else:
            code = self.startup_error_code or "STARTUP_SINGLE_INSTANCE_FAILED"
            context = self.startup_error_context or {"reason": "unknown"}
            raise StartupLockError(code, context)

    def _center_on_active_screen(self) -> None:
        """Keep the frameless login window inside the monitor work area."""
        screen = QApplication.screenAt(QtGui.QCursor.pos()) or QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        frame.moveLeft(max(available.left(), min(frame.left(), available.right() - frame.width() + 1)))
        frame.moveTop(max(available.top(), min(frame.top(), available.bottom() - frame.height() + 1)))
        self.move(frame.topLeft())

    def _read_app_version(self) -> str:
        """
        Resolve app version from version.json.
        For frozen builds, prefer bundled (_MEIPASS) version to match current exe.
        """
        candidates = []
        if getattr(sys, "frozen", False):
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                candidates.append(Path(meipass) / "version.json")
            candidates.append(Path(sys.executable).resolve().parent / "version.json")
        else:
            candidates.append(Path(__file__).resolve().parents[2] / "version.json")
            candidates.append(Path.cwd() / "version.json")

        for path in candidates:
            try:
                if path.exists():
                    with open(path, "r", encoding="utf-8-sig") as f:
                        data = json.load(f)
                    version = str(data.get("version", "")).strip()
                    if version:
                        return version
            except Exception as e:
                logger.debug(f"Failed to read version from {path}: {e}")

        return "1.0.0"

    def _apply_version_label(self) -> None:
        """Apply dynamic app version text to login UI."""
        if hasattr(self, "versionLabel"):
            version = self._read_app_version()
            self.versionLabel.setText(f"v{version}")

    def _fallback_port(self) -> int:
        """
        Deterministic app-specific port for single-instance lock.

        This must be tried before the legacy default port. If the default port
        is tried first, a second app launch can skip to this port and start a
        duplicate instance when the first launch owns the default port.
        """
        seed = f"{os.path.expanduser('~')}|{os.path.abspath(sys.argv[0])}|ssmaker"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        return 30000 + (int(digest[:8], 16) % 20000)

    @staticmethod
    def _configure_single_instance_socket(sock: socket.socket) -> None:
        """
        Request exclusive ownership on Windows when available.
        """
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            except OSError:
                # Best effort only.
                pass

    def setPort(self) -> bool:
        """Acquire the authoritative per-user startup lock.

        The deterministic (or explicitly configured) port decides whether this
        process may start. Port 20022 is retained only as a best-effort legacy
        guard, so another program using that old global port cannot prevent a
        valid per-user instance from launching.
        """
        self.startup_error_code = None
        self.startup_error_context = {}
        raw_port = os.getenv("SSMAKER_PORT")
        try:
            authoritative_port = int(raw_port) if raw_port else self._fallback_port()
            legacy_port = int(DEFAULT_PROCESS_PORT)
            if not 1 <= authoritative_port <= 65535:
                raise ValueError("port must be between 1 and 65535")
        except (TypeError, ValueError) as exc:
            self.startup_error_code = "STARTUP_PORT_CONFIG_INVALID"
            self.startup_error_context = {
                "setting": "SSMAKER_PORT",
                "value": str(raw_port or ""),
                "reason": str(exc),
            }
            logger.error(
                "[%s] Invalid startup port configuration: %s",
                self.startup_error_code,
                self.startup_error_context,
            )
            return False

        authoritative_socket: Optional[socket.socket] = None
        try:
            authoritative_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._configure_single_instance_socket(authoritative_socket)
            authoritative_socket.bind(("127.0.0.1", authoritative_port))
            authoritative_socket.listen(1)
        except OSError as exc:
            if authoritative_socket is not None:
                try:
                    authoritative_socket.close()
                except OSError:
                    pass
            os_error = getattr(exc, "errno", None)
            already_active = os_error in {errno.EADDRINUSE, 10048}
            self.startup_error_code = (
                "STARTUP_INSTANCE_ALREADY_RUNNING"
                if already_active
                else "STARTUP_LOCK_BIND_FAILED"
            )
            self.startup_error_context = {
                "authoritative_port": authoritative_port,
                "errno": os_error,
                "reason": "port_in_use" if already_active else "bind_failed",
            }
            logger.warning(
                "[%s] Authoritative single-instance port %s could not be bound: %s",
                self.startup_error_code,
                authoritative_port,
                exc,
            )
            return False

        self.serverSockets = [authoritative_socket]
        self.serverSocket = authoritative_socket
        self.server_port = authoritative_port
        logger.info(
            "Authoritative single-instance socket bound to deterministic port %s",
            authoritative_port,
        )

        if legacy_port == authoritative_port:
            return True

        legacy_socket: Optional[socket.socket] = None
        try:
            legacy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._configure_single_instance_socket(legacy_socket)
            legacy_socket.bind(("127.0.0.1", legacy_port))
            legacy_socket.listen(1)
            self.serverSockets.append(legacy_socket)
            logger.info(
                "Additional single-instance guard bound to legacy port %s",
                legacy_port,
            )
        except OSError as exc:
            if legacy_socket is not None:
                try:
                    legacy_socket.close()
                except OSError:
                    pass
            logger.warning(
                "Legacy single-instance port %s is unavailable; continuing with "
                "authoritative port %s: %s",
                legacy_port,
                authoritative_port,
                exc,
            )
        return True

    def _preload_ip(self):
        threading.Thread(target=self._get_local_ip, daemon=True).start()

    def _warmup_server(self):
        threading.Thread(target=rest.getVersion, daemon=True).start()
        # Best-effort stale-session cleanup to reduce false EU003 after
        # abrupt app termination where logout was not sent.
        threading.Thread(target=rest.cleanup_local_session, daemon=True).start()

    def _connect_login_option_controls(self) -> None:
        if hasattr(self, "autoLoginCheckbox"):
            self.autoLoginCheckbox.toggled.connect(self._on_auto_login_toggled)
        if hasattr(self, "rememberCheckbox"):
            self.rememberCheckbox.toggled.connect(self._on_remember_login_toggled)

    def _on_auto_login_toggled(self, checked: bool) -> None:
        if checked and hasattr(self, "rememberCheckbox"):
            self.rememberCheckbox.setChecked(True)

    def _on_remember_login_toggled(self, checked: bool) -> None:
        if not checked and hasattr(self, "autoLoginCheckbox"):
            self.autoLoginCheckbox.setChecked(False)

    def _attempt_auto_login(self) -> None:
        if not getattr(self, "auto_login_enabled", False):
            return
        if hasattr(self, "autoLoginCheckbox") and not self.autoLoginCheckbox.isChecked():
            return
        if not self.idEdit.text().strip() or not self.pwEdit.text():
            return

        logger.info("Attempting saved auto login")
        self.loginButton.setText("자동 로그인 중...")
        self._loginCheck()

    def _get_local_ip(self) -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except (OSError, socket.error) as e:
            logger.warning(f"Failed to get local IP: {e}")
        return "127.0.0.1"  # Fallback IP

    def _close_single_instance_sockets(self) -> None:
        sockets = list(getattr(self, "serverSockets", []) or [])
        if self.serverSocket and self.serverSocket not in sockets:
            sockets.append(self.serverSocket)
        for sock in sockets:
            try:
                sock.close()
            except OSError:
                pass
        self.serverSockets = []
        self.serverSocket = None

    def _loginCheck(self, force: bool = False):
        user_id = self.idEdit.text()
        user_pw = self.pwEdit.text()
        ip = self._get_local_ip()
        if force:
            logger.info("Ignoring deprecated force-login request")
        
        try:
            client_key = os.getenv("SSMAKER_CLIENT_API_KEY", "").strip()
            res = rest.login(userId=user_id, userPw=user_pw, key=client_key, ip=ip, force=False)
            if res.get("status") is True:
                self._handle_login_success(res)
            elif res.get("status") == "EU003":
                logger.info("Duplicate login detected (EU003)")
                error_module = str(res.get("error_module") or "caller.rest")
                error_code = str(res.get("error_code") or "LOGIN_ALREADY_ACTIVE")
                show_warning(
                    self,
                    "중복 로그인",
                    f"[{error_module}/{error_code}]\n"
                    "다른 기기에서 이미 로그인되어 있습니다.\n"
                    "기존 기기에서 로그아웃한 뒤 다시 시도해주세요.",
                )
                self.loginButton.setText("로그인")
            else:
                # Use friendly message converter
                error_msg = rest._friendly_login_message(res)
                error_module = str(res.get("error_module") or "caller.rest")
                error_code = str(res.get("error_code") or "LOGIN_REJECTED")
                display_msg = f"[{error_module}/{error_code}]\n{error_msg}"
                if res.get("offline_allowed"):
                    display_msg += (
                        "\n\n서버 연결 없이 설정을 확인하려면 "
                        "'오프라인 설정 모드'를 선택하세요."
                    )
                logger.warning(
                    "Login failed: module=%s code=%s retryable=%s offline_allowed=%s status=%s",
                    error_module,
                    error_code,
                    bool(res.get("retryable")),
                    bool(res.get("offline_allowed")),
                    res.get("status"),
                )
                self.showCustomMessageBox("로그인 실패", display_msg)
                self.loginButton.setText("로그인")
        except Exception as e:
            logger.error(f"Login exception: {str(e)}", exc_info=True)
            self.showCustomMessageBox(
                "오류",
                "[ui.windows.login_window/LOGIN_UI_ERROR]\n"
                "로그인 처리 중 오류가 발생했습니다.\n잠시 후 다시 시도해주세요.",
            )
            self.loginButton.setText("로그인")

    def _enter_offline_mode(self) -> None:
        """Delegate to startup recovery without creating authenticated state."""
        controller = getattr(self, "controller", None)
        enter_offline_mode = getattr(controller, "enter_offline_mode", None)
        if not callable(enter_offline_mode):
            logger.error(
                "[ui.windows.login_window/OFFLINE_CONTROLLER_UNAVAILABLE] "
                "Offline settings mode has no controller"
            )
            self.showCustomMessageBox(
                "오프라인 설정 모드",
                "[ui.windows.login_window/OFFLINE_CONTROLLER_UNAVAILABLE]\n"
                "오프라인 설정 모드를 시작할 수 없습니다.",
            )
            return

        logger.warning(
            "[ui.windows.login_window/OFFLINE_SETTINGS_REQUESTED] "
            "Delegating offline settings mode; authentication remains unset"
        )
        enter_offline_mode()

    def _handle_login_success(self, res):
        # 로그인 정보 저장 처리
        remember = False
        if hasattr(self, 'rememberCheckbox'):
            remember = self.rememberCheckbox.isChecked()
        elif hasattr(self, 'idpw_checkbox'):
            remember = self.idpw_checkbox.isChecked()
        auto_login = False
        if hasattr(self, 'autoLoginCheckbox'):
            auto_login = self.autoLoginCheckbox.isChecked()
        
        ui_controller.userSaveInfo(
            self,
            checkState=remember,
            loginid=self.idEdit.text(),
            loginpw=self.pwEdit.text(),
            autoLogin=auto_login,
        )
        
        # Notify controller or app
        app = QApplication.instance()
        if app:
            app.login_data = res
        
        # Notify controller to proceed to next screen
        if hasattr(self, 'controller') and self.controller:
            logger.info("Login success, notifying controller")
            self.controller.on_login_success(res)
            # Controller will handle hiding/closing logic
        else:
            logger.warning("No controller found, closing login window")
            self.close()

    def prepare_for_reauthentication(self) -> None:
        """Reset transient login state before showing this window again."""
        self.pwEdit.clear()
        self.loginButton.setEnabled(True)
        self.loginButton.setText("로그인")
        self.pwEdit.setFocus()

    def _openRegistrationDialog(self):
        from ui.login_ui_modern import RegistrationRequestDialog
        self.reg_dialog = RegistrationRequestDialog(self)
        self.reg_dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.reg_dialog.registrationRequested.connect(self._on_registration_requested)
        self.reg_dialog.show()

    def showCustomMessageBox(self, title, message):
        show_warning(self, title, message)

    def _on_registration_requested(self, name, username, password, contact, email):
        logger.info(
            "[UI] Registration submitted | name=%s username=%s contact=%s email=%s",
            name,
            username,
            contact,
            email
        )
        # Auto-fill login fields
        self.idEdit.setText(username)
        self.pwEdit.setText(password)
        
        # Optional: Auto-focus login button
        self.loginButton.setFocus()
        
        self.showCustomMessageBox("가입 완료", "회원가입이 완료되었습니다.\n로그인 버튼을 눌러주세요.")

    def _closeWindow(self):
        self._close_single_instance_sockets()
        QApplication.quit()

    def closeEvent(self, event):
        self._close_single_instance_sockets()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
            self._loginCheck()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.oldPos:
            delta = event.globalPosition().toPoint() - self.oldPos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.oldPos = None

    def showEvent(self, event):
        """Emit window_ready signal when window is shown"""
        super().showEvent(event)
        # Use QTimer to ensure window is fully rendered before emitting
        QtCore.QTimer.singleShot(50, self.window_ready.emit)
