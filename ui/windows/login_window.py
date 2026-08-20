# -*- coding: utf-8 -*-
"""
Login window for PyQt6
"""
import os
import sys
import socket
import errno
import threading
import time
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
from user_facing_errors import sanitize_user_message
from utils.logging_config import get_logger
from startup.constants import DEFAULT_PROCESS_PORT

logger = get_logger(__name__)


class LoginRequestWorker(QtCore.QThread):
    """Run authentication without freezing the login window."""

    completed = pyqtSignal(dict)

    def __init__(self, payload: Dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.payload = dict(payload)

    def run(self) -> None:
        try:
            result = rest.login(**self.payload)
        except Exception:
            logger.exception("Login request worker failed")
            result = {
                "status": "error",
                "message": "로그인 처리 중 오류가 발생했습니다.",
                "error_module": "ui.windows.login_window",
                "error_code": "LOGIN_WORKER_ERROR",
                "retryable": True,
                "offline_allowed": False,
            }
        self.completed.emit(dict(result or {}))


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
            self.idEdit.returnPressed.connect(self.pwEdit.setFocus)
            self.pwEdit.returnPressed.connect(self._loginCheck)
            self.idEdit.installEventFilter(self)
            # Do not make the button the dialog default: otherwise Enter in the
            # ID field submits an empty password before focus can move.
            self.loginButton.setDefault(False)
            self.loginButton.setAutoDefault(False)
            self.setTabOrder(self.idEdit, self.pwEdit)
            self.setTabOrder(self.pwEdit, self.rememberCheckbox)
            self.setTabOrder(self.rememberCheckbox, self.autoLoginCheckbox)
            self.setTabOrder(self.autoLoginCheckbox, self.loginButton)
            self.idEdit.setAccessibleName("아이디 입력")
            self.pwEdit.setAccessibleName("비밀번호 입력")
            self.loginButton.setAccessibleName("로그인 실행")
            self._focus_id_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Alt+I"), self)
            self._focus_id_shortcut.activated.connect(self.idEdit.setFocus)
            self._focus_password_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Alt+P"), self)
            self._focus_password_shortcut.activated.connect(self.pwEdit.setFocus)
            self._submit_login_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Alt+L"), self)
            self._submit_login_shortcut.activated.connect(self.loginButton.click)
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

    def eventFilter(self, watched, event):
        """Keep Enter in the ID field from submitting an empty password."""
        if (
            watched is getattr(self, "idEdit", None)
            and event.type() == QtCore.QEvent.Type.KeyPress
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        ):
            self.pwEdit.setFocus(Qt.FocusReason.TabFocusReason)
            event.accept()
            return True
        return super().eventFilter(watched, event)

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
        """Apply dynamic app version and update date to login UI."""
        if hasattr(self, "versionLabel"):
            from utils.app_identity import load_app_identity

            identity = load_app_identity()
            self.versionLabel.setText(identity.display_metadata)
            self.versionLabel.setAccessibleDescription(
                identity.accessible_description
            )

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
        self._auth_warmup_event = threading.Event()
        self._auth_warmup_started_at = time.monotonic()

        def _warm_auth_server() -> None:
            try:
                rest.getVersion()
            finally:
                self._auth_warmup_event.set()

        threading.Thread(target=_warm_auth_server, daemon=True).start()
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
        self._auto_login_in_progress = True
        self.loginButton.setText("자동 로그인 중...")
        self._loginCheck()

    @staticmethod
    def _is_definitive_invalid_credentials(res: dict) -> bool:
        status = res.get("status")
        error_code = str(res.get("error_code") or "").upper()
        http_status = res.get("http_status")
        return (
            status in {"EU001", "EU004", "INVALID_CREDENTIALS", "AUTH_FAIL"}
            or error_code == "LOGIN_INVALID_CREDENTIALS"
            or http_status == 401
        )

    def _get_local_ip(self) -> str:
        cached_ip = str(getattr(self, "_cached_local_ip", "") or "").strip()
        if cached_ip:
            return cached_ip
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                resolved_ip = s.getsockname()[0]
                self._cached_local_ip = resolved_ip
                return resolved_ip
        except (OSError, socket.error) as e:
            logger.warning(f"Failed to get local IP: {e}")
        self._cached_local_ip = "127.0.0.1"
        return self._cached_local_ip

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
        worker = getattr(self, "_login_worker", None)
        if worker is not None and worker.isRunning():
            return

        warmup_event = getattr(self, "_auth_warmup_event", None)
        warmup_started_at = float(
            getattr(self, "_auth_warmup_started_at", time.monotonic())
        )
        if (
            warmup_event is not None
            and not warmup_event.is_set()
            and time.monotonic() - warmup_started_at < 15
        ):
            self.loginButton.setEnabled(False)
            self.loginButton.setText("인증 서버 준비 중...")
            if not getattr(self, "_login_wait_scheduled", False):
                self._login_wait_scheduled = True

                def _retry_after_warmup() -> None:
                    self._login_wait_scheduled = False
                    self.loginButton.setEnabled(True)
                    self._loginCheck(force=force)

                QtCore.QTimer.singleShot(200, _retry_after_warmup)
            return

        user_id = self.idEdit.text()
        user_pw = self.pwEdit.text()
        ip = self._get_local_ip()
        if force:
            logger.info("Ignoring deprecated force-login request")
        
        client_key = os.getenv("SSMAKER_CLIENT_API_KEY", "").strip()
        self.loginButton.setEnabled(False)
        self.loginButton.setText("로그인 중...")
        self._login_worker = LoginRequestWorker(
            {
                "userId": user_id,
                "userPw": user_pw,
                "key": client_key,
                "ip": ip,
                "force": False,
            },
            self,
        )
        self._login_worker.completed.connect(self._on_login_request_done)
        self._login_worker.start()

    def _on_login_request_done(self, res: dict) -> None:
        was_auto_login = bool(getattr(self, "_auto_login_in_progress", False))
        self._auto_login_in_progress = False
        self.loginButton.setEnabled(True)
        if res.get("status") is True:
            self._handle_login_success(res)
            return
        if res.get("status") == "EU003":
            logger.info("Duplicate login detected (EU003)")
            show_warning(
                self,
                "중복 로그인",
                "이 프로그램이 다른 기기에서 이미 로그인되어 있습니다.\n"
                "기존 기기에서 로그아웃한 뒤 다시 시도해주세요.",
            )
            self.loginButton.setText("로그인")
            return

        error_msg = sanitize_user_message(
            rest._friendly_login_message(res),
            fallback="로그인하지 못했어요. 잠시 후 다시 시도해 주세요.",
        )
        error_module = str(res.get("error_module") or "caller.rest")
        error_code = str(res.get("error_code") or "LOGIN_REJECTED")
        logger.warning(
            "Login failed: module=%s code=%s retryable=%s offline_allowed=%s status=%s",
            error_module,
            error_code,
            bool(res.get("retryable")),
            bool(res.get("offline_allowed")),
            res.get("status"),
        )
        if self._is_definitive_invalid_credentials(res):
            if was_auto_login:
                ui_controller.clearRejectedAutoLogin(self, self.idEdit.text())
                error_msg = (
                    "저장된 비밀번호가 현재 계정과 맞지 않아 자동 로그인을 해제했어요.\n"
                    "비밀번호를 다시 입력해 로그인해 주세요."
                )
            else:
                self.pwEdit.clear()
                self.pwEdit.setFocus()
        self.showCustomMessageBox("로그인 실패", error_msg)
        self.loginButton.setText("로그인")

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
        self.reg_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.reg_dialog.setWindowTitle("SSMaker 회원가입")
        self.reg_dialog.registrationRequested.connect(self._on_registration_requested)
        self.reg_dialog.show()
        parent_rect = self.frameGeometry()
        dialog_rect = self.reg_dialog.frameGeometry()
        dialog_rect.moveCenter(parent_rect.center())
        self.reg_dialog.move(dialog_rect.topLeft())

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

        # Auto-approved registration already creates the authoritative session.
        # Re-posting /login would now be correctly rejected as a duplicate, so
        # continue with the token returned by registration instead.
        registration_result = getattr(
            getattr(self, "reg_dialog", None), "registration_result", {}
        )
        registration_data = (
            registration_result.get("data", {})
            if isinstance(registration_result, dict)
            else {}
        )
        token = (
            registration_data.get("token")
            if isinstance(registration_data, dict)
            else None
        )
        if token:
            rest._set_auth_token(token)
            user_data = dict(registration_data)
            user_data["id"] = str(user_data.get("user_id") or "")
            user_data.setdefault(
                "user_type", "trial" if user_data.get("is_trial") else "member"
            )
            self._handle_login_success(
                {
                    "status": True,
                    "data": {"data": user_data, "token": token},
                }
            )
            return
        
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
