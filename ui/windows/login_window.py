# -*- coding: utf-8 -*-
"""
Login window with authentication and registration.
"""

import os
import sys
import socket
import configparser
import threading
from typing import Optional, Dict, Any

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import Qt, QPoint, QCoreApplication
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtGui import QIcon

from caller import rest
from caller import ui_controller
from ui import login_Ui
from utils.logging_config import get_logger
from startup.constants import DEFAULT_PROCESS_PORT

logger = get_logger(__name__)


class Login(QMainWindow, login_Ui.Ui_LoginWindow):
    """Login window with authentication functionality."""

    def __init__(self) -> None:
        QMainWindow.__init__(self)
        login_Ui.Ui_LoginWindow.__init__(self)
        self.setWindowIcon(QIcon("resource/trayIcon.png"))

        self.oldPos: Optional[QPoint] = None
        self.controller: Optional[Any] = None
        self.serverSocket: Optional[socket.socket] = None
        self.registrationDialog: Optional[Any] = None
        self._cached_ip: Optional[str] = None  # IP 캐싱

        if self.setPort():
            self.setupUi(self)
            ui_controller.userLoadInfo(self)
            self.setWindowFlags(Qt.FramelessWindowHint)
            self.loginButton.clicked.connect(self._loginCheck)
            self.minimumButton.clicked.connect(self._minimumWindow)
            self.exitButton.clicked.connect(self._closeWindow)
            self.registerRequestButton.clicked.connect(self._openRegistrationDialog)
            # IP 사전 조회 (백그라운드) - 로그인 시 대기 시간 제거
            self._preload_ip()
            # 서버 웜업 (백그라운드) - 초기 응답 속도 개선
            self._warmup_server()
        else:
            self.showCustomMessageBox(
                "프로그램 실행 오류", "이미 실행중인 프로그램이 있습니다"
            )
            sys.exit()

    def setPort(self) -> bool:
        """
        Set up the process port for single instance check.
        Uses environment variable SSMAKER_PORT or default.
        """
        self.PROCESS_PORT = int(os.getenv("SSMAKER_PORT", str(DEFAULT_PROCESS_PORT)))

        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            server_socket.bind(("localhost", self.PROCESS_PORT))
            server_socket.listen(3)
            self.serverSocket = server_socket
            return True
        except (OSError, socket.error) as e:
            logger.debug("Port binding failed (likely already in use): %s", e)
            return False

    def closeSocket(self) -> None:
        """Close the server socket."""
        if self.serverSocket:
            try:
                self.serverSocket.close()
            except Exception as e:
                logger.debug("Socket close error (non-critical): %s", e)

    def _preload_ip(self) -> None:
        """Pre-load local IP in background thread."""

        def fetch_ip():
            try:
                self._get_local_ip()
            except Exception:
                pass  # 실패해도 무시, 로그인 시 다시 시도

        threading.Thread(target=fetch_ip, daemon=True).start()

    def _warmup_server(self) -> None:
        """Warm up the server to reduce cold start latency."""

        def warmup():
            try:
                # 가벼운 요청으로 서버 깨우기 (버전 확인 등)
                rest.getVersion()
            except Exception:
                pass

        threading.Thread(target=warmup, daemon=True).start()

    def _get_local_ip(self) -> str:
        """
        Get local IP address with caching.

        Returns:
            Local IP address string

        Raises:
            socket.timeout: If connection times out
            socket.error: If socket operation fails
            OSError: If OS-level error occurs
        """
        if self._cached_ip:
            return self._cached_ip

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(1)
            sock.connect(("8.8.8.8", 80))
            self._cached_ip = sock.getsockname()[0]
            return self._cached_ip

    def _get_api_key(self) -> str:
        """
        Get API key for authentication.
        Always returns the public client identifier 'ssmaker'.
        
        Returns:
            API key string
        """
        # info.on 파일의 레거시 키 대신 공통 클라이언트 ID 사용
        return "ssmaker"

    def _perform_login(self, force: bool = False) -> Optional[Dict[str, Any]]:
        """
        Perform login operation (common logic).

        Args:
            force: Force login even if already logged in elsewhere

        Returns:
            Login response dict or None if failed
        """
        # Get local IP
        try:
            user_ip = self._get_local_ip()
        except (socket.timeout, socket.error, OSError) as e:
            logger.warning("[Login] 네트워크 오류: %s", e, exc_info=True)
            self.showCustomMessageBox("네트워크 오류", "인터넷 연결을 확인해주세요")
            return None

        user_id = self.idEdit.text()
        user_pw = self.pwEdit.text()
        api_key = self._get_api_key()

        data = {
            "userId": user_id,
            "userPw": user_pw,
            "key": api_key,
            "ip": user_ip,
            "force": force,
        }

        try:
            return rest.login(**data)
        except Exception as e:
            logger.error("[Login] 로그인 요청 실패: %s", e, exc_info=True)
            self.showCustomMessageBox(
                "서버 연결 오류",
                "로그인 서버에 접속할 수 없습니다\n잠시 후 다시 시도해주세요",
            )
            return None

    def _validate_login_response(self, login_info: Any) -> bool:
        """
        Validate login response structure.

        Args:
            login_info: Response from login API

        Returns:
            True if valid, False otherwise
        """
        if not isinstance(login_info, dict):
            logger.warning("[Login] 잘못된 응답 형식 수신")
            self.showCustomMessageBox("로그인 오류", "서버 응답이 올바르지 않습니다")
            return False

        if "data" not in login_info or not isinstance(login_info.get("data"), dict):
            logger.warning("[Login] 응답에 'data' 필드 없음")
            self.showCustomMessageBox("로그인 오류", "서버 응답이 올바르지 않습니다")
            return False

        inner_data = login_info["data"].get("data")
        if not isinstance(inner_data, dict):
            logger.warning(
                "[Login] 응답의 'data.data'가 dict가 아님: %s",
                type(inner_data).__name__,
            )
            self.showCustomMessageBox(
                "로그인 오류", "서버 응답 구조가 올바르지 않습니다"
            )
            return False

        if "id" not in inner_data:
            logger.warning("[Login] 응답의 'data.data.id' 필드 없음")
            self.showCustomMessageBox("로그인 오류", "사용자 정보가 올바르지 않습니다")
            return False

        return True

    def _handle_login_success(self, login_info: Dict[str, Any]) -> None:
        """Handle successful login."""
        try:
            user_ip = self._get_local_ip()
        except (socket.timeout, socket.error, OSError):
            user_ip = "unknown"

        login_info["data"]["ip"] = user_ip

        # 로그인 성공 후 사용자 정보 저장 (비동기 처리)
        if hasattr(self, "_pending_save_info"):
            threading.Thread(
                target=ui_controller.userSaveInfo,
                args=(
                    self,
                    self._pending_save_info,
                    self.idEdit.text(),
                    self.pwEdit.text(),
                    "1.0.0",
                ),
                daemon=True,
            ).start()

        if hasattr(self, "controller") and self.controller:
            self.controller.on_login_success(login_info)
        else:
            # Fallback: old method
            self.close()
            app = QtWidgets.QApplication.instance()
            if app is not None:
                app.login_data = login_info
            QtCore.QCoreApplication.quit()

    def _loginCheck(self) -> None:
        """Main login check handler."""
        user_id = self.idEdit.text()
        # pw는 로깅하지 않음
        self._pending_save_info = self.idpw_checkbox.isChecked()  # 로그인 성공 후 저장

        logger.info(f"[UI] Login button clicked or Enter pressed. User: {user_id}, SaveInfo: {self._pending_save_info}")

        # Perform login (file I/O moved to after success)
        login_info = self._perform_login(force=False)
        if login_info is None:
            logger.error("[UI] Login returned None (Network error or Exception)")
            return

        login_status = login_info.get("status", False)
        logger.info(f"[UI] Login status received: {login_status}")
        
        login_message = login_info.get("message", "") if login_status is False else ""

        if login_status is not True:
            logger.warning(f"[UI] Login failed with status: {login_status}, message: {login_message}")
            self._handle_login_error(login_status, login_message)
        else:
            logger.info("[UI] Login success status confirmed. Validating response structure...")
            if not self._validate_login_response(login_info):
                logger.error("[UI] Login response validation failed")
                return
            
            logger.info("[UI] Response structure valid. Proceeding to success handler.")
            self._handle_login_success(login_info)

    def _handle_login_error(self, status: Any, message: str) -> None:
        """Handle login error based on status code."""
        if status == "EU001" or message == "EU001":
            self.showCustomMessageBox("로그인 에러", "아이디 또는 비밀번호가 틀렸습니다")
        elif status == "EU004" or message == "EU004":
            self.showCustomMessageBox("회원정보 없음", "회원정보가 없습니다. 회원가입 후 이용해주세요")
        elif status == "EU002" or message == "EU002":
            self.showCustomMessageBox("로그인 에러", "이용기간이 만료되었습니다")
        elif status == "EU003" or message == "EU003":
            self.showOtherPlaceMessageBox(
                "중복 로그인",
                "다른 장소에서 로그인 중입니다 \n접속을 끊고 로그인하시겠습니까?",
            )
        else:
            msg = message if message else "알 수 없는 오류가 발생했습니다"
            self.showCustomMessageBox("로그인 에러", msg)

    def showOtherPlaceMessageBox(self, title: str, message: str) -> None:
        """Show duplicate login confirmation dialog."""
        icon_path = "resource/trayIcon.png"
        msg_box = QtWidgets.QMessageBox()
        msg_box.setWindowTitle(title)
        msg_box.setWindowIcon(QtGui.QIcon(icon_path))
        msg_box.setText(f" \n   {message}   \n ")

        yes_button = msg_box.addButton("확인", QtWidgets.QMessageBox.YesRole)
        no_button = msg_box.addButton("취소", QtWidgets.QMessageBox.NoRole)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(yes_button)
        button_layout.addWidget(no_button)
        button_layout.addStretch(1)

        layout = msg_box.layout()
        layout.addLayout(button_layout, layout.rowCount(), 0, 1, layout.columnCount())
        msg_box.exec_()

        if msg_box.clickedButton() == yes_button:
            # Force login
            login_info = self._perform_login(force=True)
            if login_info is None:
                return

            login_status = login_info.get("status", False)
            if login_status is not True:
                login_message = login_info.get("message", "강제 로그인에 실패했습니다")
                self.showCustomMessageBox("로그인 오류", login_message)
                return

            if not self._validate_login_response(login_info):
                return

            self._handle_login_success(login_info)

    def showCustomMessageBox(self, title: str, message: str) -> None:
        """Show a custom message box."""
        icon_path = "resource/trayIcon.png"
        msg_box = QtWidgets.QMessageBox()
        msg_box.setWindowTitle(title)
        msg_box.setWindowIcon(QtGui.QIcon(icon_path))
        msg_box.setText(f" \n  {message}   \n ")
        msg_box.exec_()

    def _openRegistrationDialog(self) -> None:
        """Open registration request dialog."""
        from ui.login_ui_modern import RegistrationRequestDialog

        self.registrationDialog = RegistrationRequestDialog(self)
        self.registrationDialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        # 다이얼로그가 자체적으로 크기 설정함 (login_ui_modern.py에서 650px)

        self.registrationDialog.backRequested.connect(self._closeRegistrationDialog)
        self.registrationDialog.registrationRequested.connect(
            self._submitRegistrationRequest
        )

        # Center dialog
        self.registrationDialog.move(
            self.x() + (self.width() - self.registrationDialog.width()) // 2,
            self.y() + (self.height() - self.registrationDialog.height()) // 2,
        )
        self.registrationDialog.show()

    def _closeRegistrationDialog(self) -> None:
        """Close registration dialog."""
        if self.registrationDialog:
            self.registrationDialog.close()
            self.registrationDialog = None

    def _submitRegistrationRequest(
        self, name: str, username: str, password: str, contact: str
    ) -> None:
        """Submit registration request."""
        try:
            logger.info(f"[Registration] 회원가입 요청 시작: username={username}, name={name}")
            result = rest.submitRegistrationRequest(
                name=name, username=username, password=password, contact=contact
            )

            if result.get("success"):
                logger.info(f"[Registration] 회원가입 성공: username={username}")
                # 안전한 데이터 접근 (Safe data access)
                data_obj = result.get("data")
                if data_obj is None:
                    data_obj = {}

                # 회원가입 성공 - 체험판 5회 제공 (자동 신청됨)
                is_trial = data_obj.get("is_trial", True)
                work_count = data_obj.get("work_count", 5)

                # 토큰 확인 (백엔드에서 토큰을 포함해 응답)
                token = data_obj.get("token")

                if token:
                    logger.info(f"[Registration] 자동 로그인 토큰 획득: username={username}")
                    # 토큰이 있으면 즉시 자동 로그인
                    self.showCustomMessageBox(
                        "회원가입 완료",
                        f"회원가입이 완료되었습니다!\n체험판 5회가 제공됩니다.\n자동으로 로그인합니다.",
                    )
                    self._closeRegistrationDialog()

                    try:
                        user_ip = self._get_local_ip()
                    except Exception:
                        user_ip = "127.0.0.1"

                    # 로그인 데이터 구성 (기존 로그인 응답 형식과 동일하게)
                    login_info = {
                        "status": True,
                        "data": {
                            "data": {
                                "id": str(data_obj.get("user_id", "")),
                                "token": token,
                            },
                            "ip": user_ip,
                        },
                    }
                    # 토큰 저장
                    from caller.rest import _set_auth_token

                    _set_auth_token(token)

                    self._handle_login_success(login_info)
                else:
                    logger.info(f"[Registration] 토큰 없음, 수동 로그인 유도: username={username}")
                    # 토큰이 없으면 수동 로그인 유도
                    self.showCustomMessageBox(
                        "회원가입 완료",
                        f"회원가입이 완료되었습니다!\n체험판 5회가 제공됩니다.\n바로 로그인하세요.",
                    )
                    self._closeRegistrationDialog()

                    # 로그인 폼에 아이디 자동 입력
                    self.idEdit.setText(username)
                    self.pwEdit.setFocus()
            else:
                error_msg = result.get("message", "회원가입에 실패했습니다.")
                logger.warning(f"[Registration] 회원가입 실패 (서버 응답): {error_msg}")
                self.showCustomMessageBox("가입 실패", error_msg)

        except Exception as e:
            logger.error("[Registration] 회원가입 예외 발생: %s", e, exc_info=True)
            self.showCustomMessageBox(
                "가입 실패", "서버 연결에 실패했습니다.\n잠시 후 다시 시도해주세요."
            )

    def _perform_login_with_creds(self, user_id, user_pw):
        """Helper to perform credential login for auto-login fallback."""
        try:
            # 기본 로그인 로직 재사용 (Force=True로 중복 로그인 처리도 가능하게)
            api_key = self._get_api_key()
            user_ip = self._get_local_ip()

            data = {
                "userId": user_id,
                "userPw": user_pw,
                "key": api_key,
                "ip": user_ip,
                "force": True,  # 자동 로그인시에는 강제 로그인 시도
            }
            return rest.login(**data)
        except Exception:
            return None

    def _minimumWindow(self) -> None:
        """Minimize window."""
        self.showMinimized()

    def _closeWindow(self) -> None:
        """Close window and exit application."""
        self.closeSocket()
        QCoreApplication.instance().quit()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """Handle key press events."""
        if event.key() in [Qt.Key_Return, Qt.Key_Enter]:
            self._loginCheck()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """Handle mouse press for window dragging."""
        self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        """Handle mouse move for window dragging."""
        if self.oldPos is not None:
            delta = QPoint(event.globalPos() - self.oldPos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPos()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        """Handle mouse release for window dragging."""
        self.oldPos = None
