# -*- coding: utf-8 -*-
"""
Login window for PyQt6
"""
import os
import sys
import socket
import threading
from typing import Optional, Any, Dict

from PyQt6 import QtCore, QtWidgets, QtGui
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtWidgets import QMainWindow, QApplication
from PyQt6.QtGui import QIcon

from caller import rest, ui_controller
from ui.login_Ui import Ui_LoginWindow
from utils.logging_config import get_logger
from startup.constants import DEFAULT_PROCESS_PORT

logger = get_logger(__name__)

class Login(QMainWindow, Ui_LoginWindow):
    """Login window with authentication functionality for PyQt6"""

    # Signal emitted when window is fully displayed
    window_ready = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowIcon(QIcon("resource/trayIcon.png"))
        self.oldPos: Optional[QPoint] = None
        self.serverSocket: Optional[socket.socket] = None
        
        if self.setPort():
            self.setupUi(self)
            ui_controller.userLoadInfo(self)
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            
            # Connect signals
            self.loginButton.clicked.connect(self._loginCheck)
            self.minimumButton.clicked.connect(self.showMinimized)
            self.exitButton.clicked.connect(self._closeWindow)
            self.registerRequestButton.clicked.connect(self._openRegistrationDialog)
            
            self._preload_ip()
            self._warmup_server()
        else:
            self.showCustomMessageBox("오류", "이미 실행 중입니다.")
            sys.exit()

    def setPort(self) -> bool:
        try:
            port = int(os.getenv("SSMAKER_PORT", str(DEFAULT_PROCESS_PORT)))
        except ValueError as e:
            logger.error(f"Invalid SSMAKER_PORT value: {e}")
            return False

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("localhost", port))
            sock.listen(1)
            self.serverSocket = sock
            logger.info(f"Server socket bound to port {port}")
            return True
        except OSError as e:
            logger.warning(f"Failed to bind socket to port {port}: {e}")
            return False

    def _preload_ip(self):
        threading.Thread(target=self._get_local_ip, daemon=True).start()

    def _warmup_server(self):
        threading.Thread(target=rest.getVersion, daemon=True).start()

    def _get_local_ip(self) -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except (OSError, socket.error) as e:
            logger.warning(f"Failed to get local IP: {e}")
            return "127.0.0.1"  # Fallback IP

    def _loginCheck(self, force: bool = False):
        user_id = self.idEdit.text()
        user_pw = self.pwEdit.text()
        ip = self._get_local_ip()
        
        try:
            res = rest.login(userId=user_id, userPw=user_pw, key="ssmaker", ip=ip, force=force)
            if res.get("status") is True:
                self._handle_login_success(res)
            elif res.get("status") == "EU003":
                # 중복 로그인 감지 - 사용자 확인 후 강제 로그인
                logger.info("Duplicate login detected (EU003).")
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "중복 로그인",
                    "다른 곳에서 이미 로그인되어 있습니다.\n기존 세션을 종료하고 여기서 로그인하시겠습니까?",
                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.No
                )
                if reply == QtWidgets.QMessageBox.StandardButton.Yes and not force:
                    self._loginCheck(force=True)
            else:
                # Use friendly message converter
                error_msg = rest._friendly_login_message(res)
                logger.warning(f"Login failed: {error_msg} (status={res.get('status')})")
                self.showCustomMessageBox("로그인 실패", error_msg)
        except Exception as e:
            logger.error(f"Login exception: {str(e)}", exc_info=True)
            self.showCustomMessageBox("오류", "로그인 처리 중 오류가 발생했습니다.\n잠시 후 다시 시도해주세요.")

    def _handle_login_success(self, res):
        # 로그인 정보 저장 처리
        remember = False
        if hasattr(self, 'rememberCheckbox'):
            remember = self.rememberCheckbox.isChecked()
        elif hasattr(self, 'idpw_checkbox'):
            remember = self.idpw_checkbox.isChecked()
        
        ui_controller.userSaveInfo(
            self,
            checkState=remember,
            loginid=self.idEdit.text(),
            loginpw=self.pwEdit.text()
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

    def _openRegistrationDialog(self):
        from ui.login_ui_modern import RegistrationRequestDialog
        self.reg_dialog = RegistrationRequestDialog(self)
        self.reg_dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.reg_dialog.registrationRequested.connect(self._on_registration_requested)
        self.reg_dialog.show()

    def showCustomMessageBox(self, title, message):
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.exec()

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
        if self.serverSocket: self.serverSocket.close()
        QApplication.quit()

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
