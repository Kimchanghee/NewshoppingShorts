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
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import QMainWindow, QApplication
from PyQt6.QtGui import QIcon

from caller import rest, ui_controller
from ui.login_Ui import Ui_LoginWindow
from utils.logging_config import get_logger
from startup.constants import DEFAULT_PROCESS_PORT

logger = get_logger(__name__)

class Login(QMainWindow, Ui_LoginWindow):
    """Login window with authentication functionality for PyQt6"""

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
        port = int(os.getenv("SSMAKER_PORT", str(DEFAULT_PROCESS_PORT)))
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("localhost", port))
            sock.listen(1)
            self.serverSocket = sock
            return True
        except:
            return False

    def _preload_ip(self):
        threading.Thread(target=self._get_local_ip, daemon=True).start()

    def _warmup_server(self):
        threading.Thread(target=rest.getVersion, daemon=True).start()

    def _get_local_ip(self) -> str:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]

    def _loginCheck(self):
        user_id = self.idEdit.text()
        user_pw = self.pwEdit.text()
        ip = self._get_local_ip()
        
        try:
            res = rest.login(userId=user_id, userPw=user_pw, key="ssmaker", ip=ip)
            if res.get("status") is True:
                self._handle_login_success(res)
            else:
                # Use friendly message converter
                error_msg = rest._friendly_login_message(res)
                logger.warning(f"Login failed: {error_msg} (Raw: {res})")
                self.showCustomMessageBox("로그인 실패", error_msg)
        except Exception as e:
            logger.error(f"Login exception: {str(e)}", exc_info=True)
            self.showCustomMessageBox("오류", f"로그인 처리 중 오류가 발생했습니다.\n{str(e)}")

    def _handle_login_success(self, res):
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
