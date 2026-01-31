# -*- coding: utf-8 -*-
"""
Modern Login UI for Shopping Shorts Maker (PyQt6)
쇼핑 숏폼 메이커 모던 로그인 UI
"""

import logging

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QMessageBox,
    QDialog,
    QVBoxLayout,
    QFormLayout,
)
from PyQt6.QtGui import QFont, QIcon, QPixmap

class UsernameCheckWorker(QThread):
    """아이디 중복 확인 백그라운드 워커"""

    finished = pyqtSignal(bool, str)  # (available, message)

    def __init__(self, username: str):
        super().__init__()
        self.username = username

    def run(self):
        import os
        import requests
        import logging

        logger = logging.getLogger(__name__)

        try:
            api_url = os.getenv(
                "API_SERVER_URL",
                "https://ssmaker-auth-api-1049571775048.us-central1.run.app/",
            )
            if not api_url.endswith("/"):
                api_url += "/"

            target_url = f"{api_url}user/check-username/{self.username}"
            logger.info(f"[UsernameCheck] 중복확인 요청 중: {target_url}")

            resp = requests.get(target_url, timeout=5)

            if resp.status_code == 200:
                data = resp.json()
                available = data.get("available", False)
                message = data.get("message", "")
                logger.info(f"[UsernameCheck] 중복확인 성공: available={available}, msg={message}")
                self.finished.emit(available, message)
            else:
                logger.warning(
                    f"[UsernameCheck] 중복확인 실패 (HTTP {resp.status_code}): {resp.text}"
                )
                self.finished.emit(False, f"서버 오류 ({resp.status_code})")
        except requests.exceptions.ConnectionError:
            self.finished.emit(False, "서버 연결 실패")
        except Exception as e:
            self.finished.emit(False, f"오류 발생 ({str(e)})")

FONT_FAMILY = "맑은 고딕"
logger = logging.getLogger(__name__)

class ModernLoginUi:
    """
    모던 로그인 UI 클래스 (PyQt6)
    """

    def setupUi(self, LoginWindow: QMainWindow):
        LoginWindow.setObjectName("LoginWindow")
        LoginWindow.resize(700, 500)
        LoginWindow.setMinimumSize(QtCore.QSize(700, 500))
        LoginWindow.setMaximumSize(QtCore.QSize(700, 500))

        self.centralwidget = QWidget(LoginWindow)
        self.centralwidget.setObjectName("centralwidget")

        # 왼쪽 패널
        self.leftFrame = QFrame(self.centralwidget)
        self.leftFrame.setGeometry(QtCore.QRect(0, 0, 300, 500))
        self.leftFrame.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #e31639,
                    stop:1 #ff4d6a
                );
            }
        """)
        self.leftFrame.setFrameShape(QFrame.Shape.StyledPanel)

        self.logoIcon = QLabel(self.leftFrame)
        self.logoIcon.setGeometry(QtCore.QRect(75, 100, 150, 100))
        self.logoIcon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logoIcon.setFont(QFont(FONT_FAMILY, 60, QFont.Weight.Bold))
        self.logoIcon.setStyleSheet("""
            color: white;
            background: rgba(255,255,255,0.15);
            border-radius: 25px;
        """)
        self.logoIcon.setText("SS")

        self.logoBadge = QLabel(self.leftFrame)
        self.logoBadge.setGeometry(QtCore.QRect(95, 190, 110, 28))
        self.logoBadge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logoBadge.setFont(QFont(FONT_FAMILY, 10, QFont.Weight.Bold))
        self.logoBadge.setStyleSheet("""
            color: #e31639;
            background: white;
            border-radius: 14px;
            padding: 2px;
        """)
        self.logoBadge.setText("SHORTS MAKER")

        self.titleLabel = QLabel(self.leftFrame)
        self.titleLabel.setGeometry(QtCore.QRect(0, 240, 300, 60))
        self.titleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.titleLabel.setFont(QFont(FONT_FAMILY, 20, QFont.Weight.Bold))
        self.titleLabel.setStyleSheet("color: white; background: transparent;")
        self.titleLabel.setText("쇼핑 숏폼 메이커")

        self.subtitleLabel = QLabel(self.leftFrame)
        self.subtitleLabel.setGeometry(QtCore.QRect(0, 305, 300, 50))
        self.subtitleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitleLabel.setFont(QFont(FONT_FAMILY, 10))
        self.subtitleLabel.setStyleSheet("color: rgba(255,255,255,0.85); background: transparent;")
        self.subtitleLabel.setText("중국 쇼핑 영상을\n한국어 숏폼으로 자동 변환")

        self.featureIcons = QLabel(self.leftFrame)
        self.featureIcons.setGeometry(QtCore.QRect(0, 380, 300, 30))
        self.featureIcons.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.featureIcons.setFont(QFont(FONT_FAMILY, 9))
        self.featureIcons.setStyleSheet("color: rgba(255,255,255,0.7); background: transparent;")
        self.featureIcons.setText("AI 번역  |  자동 편집  |  숏폼 제작")

        self.versionLabel = QLabel(self.leftFrame)
        self.versionLabel.setGeometry(QtCore.QRect(0, 460, 300, 30))
        self.versionLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.versionLabel.setFont(QFont(FONT_FAMILY, 9))
        self.versionLabel.setStyleSheet("color: rgba(255,255,255,0.5); background: transparent;")
        self.versionLabel.setText("v2.0.0")

        # 오른쪽 패널
        self.rightFrame = QFrame(self.centralwidget)
        self.rightFrame.setGeometry(QtCore.QRect(300, 0, 400, 500))
        self.rightFrame.setStyleSheet("background-color: #ffffff;")
        self.rightFrame.setFrameShape(QFrame.Shape.StyledPanel)

        self.minimumButton = QPushButton(self.rightFrame)
        self.minimumButton.setGeometry(QtCore.QRect(330, 10, 25, 25))
        self.minimumButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.minimumButton.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                border: none;
                border-radius: 12px;
            }
            QPushButton:hover { background-color: #E5E7EB; }
        """)
        icon_min = QIcon()
        icon_min.addPixmap(QPixmap("resource/Minimize_icon.png"), QIcon.Mode.Normal, QIcon.State.On)
        self.minimumButton.setIcon(icon_min)

        self.exitButton = QPushButton(self.rightFrame)
        self.exitButton.setGeometry(QtCore.QRect(360, 10, 25, 25))
        self.exitButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exitButton.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                border: none;
                border-radius: 12px;
            }
            QPushButton:hover { background-color: #FEE2E2; }
        """)
        icon_close = QIcon()
        icon_close.addPixmap(QPixmap("resource/Close_icon.png"), QIcon.Mode.Normal, QIcon.State.On)
        self.exitButton.setIcon(icon_close)

        self.loginTitleLabel = QLabel(self.rightFrame)
        self.loginTitleLabel.setGeometry(QtCore.QRect(50, 70, 300, 40))
        self.loginTitleLabel.setFont(QFont(FONT_FAMILY, 22, QFont.Weight.Bold))
        self.loginTitleLabel.setText("로그인")

        self.label_id = QLabel(self.rightFrame)
        self.label_id.setGeometry(QtCore.QRect(50, 160, 100, 25))
        self.label_id.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.Bold))
        self.label_id.setText("아이디")

        self.idEdit = QLineEdit(self.rightFrame)
        self.idEdit.setGeometry(QtCore.QRect(50, 190, 300, 45))
        self.idEdit.setStyleSheet("""
            QLineEdit {
                background-color: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 10px;
                padding: 10px 15px;
            }
            QLineEdit:focus { border: 2px solid #e31639; background-color: #ffffff; }
        """)

        self.label_pw = QLabel(self.rightFrame)
        self.label_pw.setGeometry(QtCore.QRect(50, 250, 100, 25))
        self.label_pw.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.Bold))
        self.label_pw.setText("비밀번호")

        self.pwEdit = QLineEdit(self.rightFrame)
        self.pwEdit.setGeometry(QtCore.QRect(50, 280, 300, 45))
        self.pwEdit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwEdit.setStyleSheet("""
            QLineEdit {
                background-color: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 10px;
                padding: 10px 15px;
            }
            QLineEdit:focus { border: 2px solid #e31639; background-color: #ffffff; }
        """)

        self.loginButton = QPushButton(self.rightFrame)
        self.loginButton.setGeometry(QtCore.QRect(50, 375, 300, 45))
        self.loginButton.setFont(QFont(FONT_FAMILY, 12, QFont.Weight.Bold))
        self.loginButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.loginButton.setStyleSheet("""
            QPushButton {
                color: #ffffff;
                background-color: #e31639;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover { background-color: #c41231; }
        """)
        self.loginButton.setText("로그인")

        self.registerRequestButton = QPushButton(self.rightFrame)
        self.registerRequestButton.setGeometry(QtCore.QRect(50, 430, 300, 45))
        self.registerRequestButton.setFont(QFont(FONT_FAMILY, 11))
        self.registerRequestButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.registerRequestButton.setStyleSheet("""
            QPushButton {
                color: #e31639;
                border: 2px solid #e31639;
                border-radius: 10px;
            }
            QPushButton:hover { background-color: #FEF2F2; }
        """)
        self.registerRequestButton.setText("회원가입")

        LoginWindow.setCentralWidget(self.centralwidget)

class RegistrationRequestDialog(QWidget):
    """
    회원가입 요청 다이얼로그 (좌표 기반, 모던 스타일)
    """

    registrationRequested = pyqtSignal(str, str, str, str)
    backRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._username_available = False
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedSize(400, 650)
        self.setStyleSheet("background-color: #ffffff;")

        # 뒤로가기 버튼
        self.backButton = QPushButton(self)
        self.backButton.setGeometry(QtCore.QRect(15, 15, 35, 35))
        self.backButton.setFont(QFont(FONT_FAMILY, 14))
        self.backButton.setText("←")
        self.backButton.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                border: none;
                border-radius: 17px;
                color: #374151;
            }
            QPushButton:hover { background-color: #E5E7EB; }
        """)
        self.backButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.backButton.clicked.connect(self._on_back)

        # 타이틀
        self.titleLabel = QLabel(self)
        self.titleLabel.setGeometry(QtCore.QRect(30, 65, 340, 35))
        self.titleLabel.setFont(QFont(FONT_FAMILY, 20, QFont.Weight.Bold))
        self.titleLabel.setStyleSheet("color: #1F2937; background: transparent;")
        self.titleLabel.setText("회원가입")

        # 서브타이틀
        self.subtitleLabel = QLabel(self)
        self.subtitleLabel.setGeometry(QtCore.QRect(30, 100, 340, 40))
        self.subtitleLabel.setFont(QFont(FONT_FAMILY, 10))
        self.subtitleLabel.setStyleSheet("color: #6B7280; background: transparent;")
        self.subtitleLabel.setText("가입 정보를 입력해주세요.\n가입 후 바로 로그인 가능합니다. (체험판 5회)")

        # 가입자 명
        self.nameLabel = QLabel(self)
        self.nameLabel.setGeometry(QtCore.QRect(30, 150, 100, 25))
        self.nameLabel.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.Bold))
        self.nameLabel.setStyleSheet("color: #374151; background: transparent;")
        self.nameLabel.setText("가입자 명")

        self.nameEdit = QLineEdit(self)
        self.nameEdit.setGeometry(QtCore.QRect(30, 175, 340, 42))
        self.nameEdit.setFont(QFont(FONT_FAMILY, 11))
        self.nameEdit.setPlaceholderText("이름을 입력하세요")
        self._apply_input_style(self.nameEdit)

        # 아이디 + 중복확인
        self.usernameLabel = QLabel(self)
        self.usernameLabel.setGeometry(QtCore.QRect(30, 225, 100, 25))
        self.usernameLabel.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.Bold))
        self.usernameLabel.setStyleSheet("color: #374151; background: transparent;")
        self.usernameLabel.setText("아이디")

        self.usernameEdit = QLineEdit(self)
        self.usernameEdit.setGeometry(QtCore.QRect(30, 250, 240, 42))
        self.usernameEdit.setFont(QFont(FONT_FAMILY, 11))
        self.usernameEdit.setPlaceholderText("영문, 숫자, 밑줄(_)만 사용")
        self._apply_input_style(self.usernameEdit)
        self.usernameEdit.textChanged.connect(self._on_username_changed)

        self.checkUsernameBtn = QPushButton(self)
        self.checkUsernameBtn.setGeometry(QtCore.QRect(280, 250, 90, 42))
        self.checkUsernameBtn.setFont(QFont(FONT_FAMILY, 10))
        self.checkUsernameBtn.setText("중복확인")
        self.checkUsernameBtn.setStyleSheet("""
            QPushButton {
                background-color: #6B7280;
                color: white;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #4B5563; }
            QPushButton:disabled {
                background-color: #D1D5DB;
                color: #9CA3AF;
            }
        """)
        self.checkUsernameBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.checkUsernameBtn.clicked.connect(self._check_username)

        self.usernameStatusLabel = QLabel(self)
        self.usernameStatusLabel.setGeometry(QtCore.QRect(30, 294, 340, 18))
        self.usernameStatusLabel.setFont(QFont(FONT_FAMILY, 9))
        self.usernameStatusLabel.setStyleSheet("color: #6B7280; background: transparent;")
        self.usernameStatusLabel.setText("")

        # 비밀번호
        self.passwordLabel = QLabel(self)
        self.passwordLabel.setGeometry(QtCore.QRect(30, 320, 100, 25))
        self.passwordLabel.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.Bold))
        self.passwordLabel.setStyleSheet("color: #374151; background: transparent;")
        self.passwordLabel.setText("비밀번호")

        self.passwordEdit = QLineEdit(self)
        self.passwordEdit.setGeometry(QtCore.QRect(30, 345, 340, 42))
        self.passwordEdit.setFont(QFont(FONT_FAMILY, 11))
        self.passwordEdit.setPlaceholderText("6자 이상 입력")
        self.passwordEdit.setEchoMode(QLineEdit.EchoMode.Password)
        self._apply_input_style(self.passwordEdit)

        self.passwordHintLabel = QLabel(self)
        self.passwordHintLabel.setGeometry(QtCore.QRect(30, 389, 340, 18))
        self.passwordHintLabel.setFont(QFont(FONT_FAMILY, 9))
        self.passwordHintLabel.setStyleSheet("color: #9CA3AF; background: transparent;")
        self.passwordHintLabel.setText("※ 영문, 숫자 포함 6자 이상 권장")

        # 비밀번호 확인
        self.passwordConfirmLabel = QLabel(self)
        self.passwordConfirmLabel.setGeometry(QtCore.QRect(30, 410, 120, 25))
        self.passwordConfirmLabel.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.Bold))
        self.passwordConfirmLabel.setStyleSheet("color: #374151; background: transparent;")
        self.passwordConfirmLabel.setText("비밀번호 확인")

        self.passwordConfirmEdit = QLineEdit(self)
        self.passwordConfirmEdit.setGeometry(QtCore.QRect(30, 435, 340, 42))
        self.passwordConfirmEdit.setFont(QFont(FONT_FAMILY, 11))
        self.passwordConfirmEdit.setPlaceholderText("비밀번호를 다시 입력")
        self.passwordConfirmEdit.setEchoMode(QLineEdit.EchoMode.Password)
        self._apply_input_style(self.passwordConfirmEdit)

        # 연락처
        self.contactLabel = QLabel(self)
        self.contactLabel.setGeometry(QtCore.QRect(30, 485, 100, 25))
        self.contactLabel.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.Bold))
        self.contactLabel.setStyleSheet("color: #374151; background: transparent;")
        self.contactLabel.setText("연락처")

        self.contactEdit = QLineEdit(self)
        self.contactEdit.setGeometry(QtCore.QRect(30, 510, 340, 42))
        self.contactEdit.setFont(QFont(FONT_FAMILY, 11))
        self.contactEdit.setPlaceholderText("010-1234-5678")
        self._apply_input_style(self.contactEdit)

        # 제출 버튼
        self.submitButton = QPushButton(self)
        self.submitButton.setGeometry(QtCore.QRect(30, 565, 340, 45))
        self.submitButton.setFont(QFont(FONT_FAMILY, 12, QFont.Weight.Bold))
        self.submitButton.setText("회원가입")
        self.submitButton.setStyleSheet("""
            QPushButton {
                color: #ffffff;
                background-color: #e31639;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover { background-color: #c41231; }
            QPushButton:pressed { background-color: #a01028; }
        """)
        self.submitButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.submitButton.clicked.connect(self._on_submit)

    def _apply_input_style(self, widget):
        widget.setStyleSheet("""
            QLineEdit {
                background-color: #F9FAFB;
                color: #1F2937;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 8px 12px;
            }
            QLineEdit:focus {
                border: 2px solid #e31639;
                background-color: #ffffff;
            }
            QLineEdit::placeholder { color: #9CA3AF; }
        """)

    def _on_back(self):
        self.backRequested.emit()
        self.close()

    def _on_username_changed(self, text):
        self._username_available = False
        self.usernameStatusLabel.setText("")
        self.usernameStatusLabel.setStyleSheet("color: #6B7280; background: transparent;")

    def _check_username(self):
        import re
        logger.info("[UI] Username check requested")

        username = self.usernameEdit.text().strip().lower()
        if not username or len(username) < 4:
            self._show_error("아이디는 4자 이상이어야 합니다.")
            return
        if not re.match(r"^[a-z0-9_]+$", username):
            self._show_error("아이디는 영문, 숫자, 밑줄(_)만 사용할 수 있습니다.")
            return

        # Cancel previous worker if still running
        if hasattr(self, "_username_worker") and self._username_worker.isRunning():
            self._username_worker.terminate()
            self._username_worker.wait()

        self.checkUsernameBtn.setEnabled(False)
        self.checkUsernameBtn.setText("확인중...")
        self.usernameStatusLabel.setText("확인 중...")
        self.usernameStatusLabel.setStyleSheet("color: #6B7280; background: transparent;")

        self._username_worker = UsernameCheckWorker(username)
        self._username_worker.finished.connect(self._on_username_check_done)
        self._username_worker.start()

    def _on_username_check_done(self, available: bool, message: str):
        self.checkUsernameBtn.setEnabled(True)
        self.checkUsernameBtn.setText("중복확인")

        if available:
            self._username_available = True
            self.usernameStatusLabel.setText("✓ 사용 가능한 아이디입니다")
            self.usernameStatusLabel.setStyleSheet("color: #10B981; background: transparent;")
        elif "네트워크" in message or "실패" in message:
            self._username_available = False
            self.usernameStatusLabel.setText(message)
            self.usernameStatusLabel.setStyleSheet("color: #F59E0B; background: transparent;")
        else:
            self._username_available = False
            self.usernameStatusLabel.setText("✗ 이미 사용 중인 아이디입니다")
            self.usernameStatusLabel.setStyleSheet("color: #EF4444; background: transparent;")
        logger.info(
            "[UI] Username check result | available=%s message=%s",
            available,
            message,
        )

    def _on_submit(self):
        import re
        from caller import rest

        name = self.nameEdit.text().strip()
        username = self.usernameEdit.text().strip().lower()
        password = self.passwordEdit.text()
        password_confirm = self.passwordConfirmEdit.text()
        contact_raw = self.contactEdit.text().strip()
        contact = re.sub(r"[^0-9]", "", contact_raw)

        if not name or len(name) < 2:
            self._show_error("가입자 명은 2자 이상 입력해주세요.")
            return
        if not username or len(username) < 4:
            self._show_error("아이디는 4자 이상이어야 합니다.")
            return
        if not re.match(r"^[a-z0-9_]+$", username):
            self._show_error("아이디는 영문, 숫자, 밑줄(_)만 사용할 수 있습니다.")
            return
        if not self._username_available:
            self._show_error("아이디 중복확인을 해주세요.")
            return
        if not password or len(password) < 6:
            self._show_error("비밀번호는 6자 이상이어야 합니다.")
            return
        if password != password_confirm:
            self._show_error("비밀번호가 일치하지 않습니다.")
            return
        if len(contact) < 10:
            self._show_error("올바른 연락처를 입력해주세요.")
            return

        try:
            logger.info(
                "[UI] Registration API call | name=%s username=%s contact=%s",
                name,
                username,
                contact,
            )
            result = rest.submitRegistrationRequest(
                name=name,
                username=username,
                password=password,
                contact=contact,
            )
            if result.get("success"):
                QMessageBox.information(self, "완료", "회원가입이 완료되었습니다! 바로 로그인해주세요.")
                logger.info("[UI] Registration success | username=%s", username)
                self.registrationRequested.emit(name, username, password, contact)
                self.close()
            else:
                logger.warning(
                    "[UI] Registration failed | username=%s message=%s",
                    username,
                    result.get("message"),
                )
                self._show_error(result.get("message", "알 수 없는 오류가 발생했습니다."))
        except Exception as e:
            logger.exception("[UI] Registration exception")
            QMessageBox.critical(self, "오류", str(e))

    def _show_error(self, message: str):
        msgBox = QMessageBox(self)
        msgBox.setIcon(QMessageBox.Icon.Warning)
        msgBox.setWindowTitle("입력 오류")
        msgBox.setText(message)
        msgBox.setStandardButtons(QMessageBox.StandardButton.Ok)
        msgBox.exec()

    def clear_fields(self):
        self.nameEdit.clear()
        self.usernameEdit.clear()
        self.passwordEdit.clear()
        self.passwordConfirmEdit.clear()
        self.contactEdit.clear()

Ui_LoginWindow = ModernLoginUi
