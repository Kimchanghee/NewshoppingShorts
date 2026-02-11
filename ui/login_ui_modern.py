# -*- coding: utf-8 -*-
"""
Modern Login UI for Shopping Shorts Maker (PyQt6)
쇼핑 숏폼 메이커 모던 로그인 UI
"""

import logging
import json
import os
import sys
from pathlib import Path

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

from ui.design_system_v2 import get_design_system, ColorPalette

# Initialize design system and ALWAYS use light palette for login
ds = get_design_system()
# Use light colors for login screen regardless of app-wide dark mode
light_colors = ColorPalette()

def login_color(key: str) -> str:
    """Get color from light palette for login UI"""
    return getattr(light_colors, key, "#000000")

FONT_FAMILY = "맑은 고딕"
logger = logging.getLogger(__name__)


def _read_app_version() -> str:
    """
    Best-effort app version resolver for the login UI.

    NOTE:
    LoginWindow also applies the version label. This is a safe fallback so the
    value is not stuck on a hardcoded placeholder after updates.
    """
    candidates = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "version.json")
        candidates.append(Path(sys.executable).resolve().parent / "version.json")
    else:
        candidates.append(Path(__file__).resolve().parents[1] / "version.json")
        candidates.append(Path.cwd() / "version.json")

    for path in candidates:
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                version = str(data.get("version", "")).strip()
                if version:
                    return version
        except Exception:
            continue
    return "1.0.0"


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
        self.leftFrame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {login_color('primary')},
                    stop:1 {login_color('secondary')}
                );
            }}
        """)
        self.leftFrame.setFrameShape(QFrame.Shape.StyledPanel)

        self.logoIcon = QLabel(self.leftFrame)
        self.logoIcon.setGeometry(QtCore.QRect(75, 100, 150, 100))
        self.logoIcon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logoIcon.setFont(QFont(FONT_FAMILY, ds.typography.size_3xl, QFont.Weight.Bold))
        self.logoIcon.setStyleSheet(f"""
            color: white;
            background: rgba(255,255,255,0.15);
            border-radius: {ds.radius.xl}px;
        """)
        self.logoIcon.setText("SS")

        self.logoBadge = QLabel(self.leftFrame)
        self.logoBadge.setGeometry(QtCore.QRect(95, 190, 110, 28))
        self.logoBadge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logoBadge.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs, QFont.Weight.Bold))
        self.logoBadge.setStyleSheet(f"""
            color: {login_color('primary')};
            background: white;
            border-radius: {ds.radius.full}px;
            padding: {ds.spacing.space_1}px;
        """)
        self.logoBadge.setText("숏폼 메이커")

        self.titleLabel = QLabel(self.leftFrame)
        self.titleLabel.setGeometry(QtCore.QRect(0, 240, 300, 60))
        self.titleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.titleLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_lg, QFont.Weight.Bold))
        self.titleLabel.setStyleSheet("color: white; background: transparent;")
        self.titleLabel.setText("쇼핑 숏폼 메이커")

        self.subtitleLabel = QLabel(self.leftFrame)
        self.subtitleLabel.setGeometry(QtCore.QRect(0, 305, 300, 50))
        self.subtitleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitleLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        self.subtitleLabel.setStyleSheet("color: rgba(255,255,255,0.85); background: transparent;")
        self.subtitleLabel.setText("중국 쇼핑 영상을\n한국어 숏폼으로 자동 변환")

        self.featureIcons = QLabel(self.leftFrame)
        self.featureIcons.setGeometry(QtCore.QRect(0, 380, 300, 30))
        self.featureIcons.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.featureIcons.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        self.featureIcons.setStyleSheet("color: rgba(255,255,255,0.7); background: transparent;")
        self.featureIcons.setText("AI 번역  |  자동 편집  |  숏폼 제작")

        self.versionLabel = QLabel(self.leftFrame)
        self.versionLabel.setGeometry(QtCore.QRect(0, 460, 300, 30))
        self.versionLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.versionLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        self.versionLabel.setStyleSheet("color: rgba(255,255,255,0.5); background: transparent;")
        self.versionLabel.setText(f"v{_read_app_version()}")

        # 오른쪽 패널
        self.rightFrame = QFrame(self.centralwidget)
        self.rightFrame.setGeometry(QtCore.QRect(300, 0, 400, 500))
        self.rightFrame.setStyleSheet(f"background-color: {login_color('surface')};")
        self.rightFrame.setFrameShape(QFrame.Shape.StyledPanel)

        self.minimumButton = QPushButton(self.rightFrame)
        self.minimumButton.setGeometry(QtCore.QRect(330, 10, 25, 25))
        self.minimumButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.minimumButton.setStyleSheet(f"""
            QPushButton {{
                background-color: {login_color('surface_variant')};
                border: none;
                border-radius: {ds.radius.md}px;
            }}
            QPushButton:hover {{ background-color: {login_color('border')}; }}
        """)
        icon_min = QIcon()
        icon_min.addPixmap(QPixmap("resource/Minimize_icon.png"), QIcon.Mode.Normal, QIcon.State.On)
        self.minimumButton.setIcon(icon_min)

        self.exitButton = QPushButton(self.rightFrame)
        self.exitButton.setGeometry(QtCore.QRect(360, 10, 25, 25))
        self.exitButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exitButton.setStyleSheet(f"""
            QPushButton {{
                background-color: {login_color('surface_variant')};
                border: none;
                border-radius: {ds.radius.md}px;
            }}
            QPushButton:hover {{ background-color: {login_color('border')}; }}
        """)
        icon_close = QIcon()
        icon_close.addPixmap(QPixmap("resource/Close_icon.png"), QIcon.Mode.Normal, QIcon.State.On)
        self.exitButton.setIcon(icon_close)

        self.loginTitleLabel = QLabel(self.rightFrame)
        self.loginTitleLabel.setGeometry(QtCore.QRect(50, 70, 300, 40))
        self.loginTitleLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_xl, QFont.Weight.Bold))
        self.loginTitleLabel.setText("로그인")

        self.label_id = QLabel(self.rightFrame)
        self.label_id.setGeometry(QtCore.QRect(50, 160, 100, 25))
        self.label_id.setFont(QFont(FONT_FAMILY, ds.typography.size_sm, QFont.Weight.Bold))
        self.label_id.setText("아이디")

        self.idEdit = QLineEdit(self.rightFrame)
        self.idEdit.setGeometry(QtCore.QRect(50, 190, 300, ds.button_sizes['md'].height))
        self.idEdit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {login_color('background')};
                border: 1px solid {login_color('border')};
                border-radius: {ds.radius.md}px;
                padding: {ds.spacing.space_3}px {ds.spacing.space_4}px;
            }}
            QLineEdit:focus {{ border: 2px solid {login_color('primary')}; background-color: {login_color('surface')}; }}
        """)

        self.label_pw = QLabel(self.rightFrame)
        self.label_pw.setGeometry(QtCore.QRect(50, 250, 100, 25))
        self.label_pw.setFont(QFont(FONT_FAMILY, ds.typography.size_sm, QFont.Weight.Bold))
        self.label_pw.setText("비밀번호")

        self.pwEdit = QLineEdit(self.rightFrame)
        self.pwEdit.setGeometry(QtCore.QRect(50, 280, 300, ds.button_sizes['md'].height))
        self.pwEdit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwEdit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {login_color('background')};
                border: 1px solid {login_color('border')};
                border-radius: {ds.radius.md}px;
                padding: {ds.spacing.space_3}px {ds.spacing.space_4}px;
            }}
            QLineEdit:focus {{ border: 2px solid {login_color('primary')}; background-color: {login_color('surface')}; }}
        """)

        # 로그인 정보 저장 체크박스
        self.rememberCheckbox = QCheckBox(self.rightFrame)
        self.rememberCheckbox.setGeometry(QtCore.QRect(50, 335, 200, 25))
        self.rememberCheckbox.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        self.rememberCheckbox.setText("아이디/비밀번호 저장")
        self.rememberCheckbox.setStyleSheet(f"""
            QCheckBox {{
                color: {login_color('text_secondary')};
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {login_color('text_muted')};
                border-radius: {ds.radius.sm}px;
                background: {login_color('surface')};
            }}
            QCheckBox::indicator:checked {{
                background-color: {login_color('primary')};
                border-color: {login_color('primary')};
            }}
            QCheckBox::indicator:hover {{
                border-color: {login_color('primary')};
            }}
        """)
        self.rememberCheckbox.setCursor(Qt.CursorShape.PointingHandCursor)

        self.loginButton = QPushButton(self.rightFrame)
        self.loginButton.setGeometry(QtCore.QRect(50, 375, 300, ds.button_sizes['lg'].height))
        self.loginButton.setFont(QFont(FONT_FAMILY, ds.button_sizes['lg'].font_size, QFont.Weight.Bold))
        self.loginButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.loginButton.setStyleSheet(f"""
            QPushButton {{
                color: {login_color('surface')};
                background-color: {login_color('primary')};
                border: none;
                border-radius: {ds.radius.md}px;
            }}
            QPushButton:hover {{ background-color: {login_color('secondary')}; }}
        """)
        self.loginButton.setText("로그인")

        self.registerRequestButton = QPushButton(self.rightFrame)
        self.registerRequestButton.setGeometry(QtCore.QRect(50, 430, 300, ds.button_sizes['lg'].height))
        self.registerRequestButton.setFont(QFont(FONT_FAMILY, ds.typography.size_sm))
        self.registerRequestButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.registerRequestButton.setStyleSheet(f"""
            QPushButton {{
                color: {login_color('primary')};
                border: 2px solid {login_color('primary')};
                border-radius: {ds.radius.md}px;
            }}
            QPushButton:hover {{ background-color: rgba(227, 22, 57, 0.05); }}
        """)
        self.registerRequestButton.setText("회원가입")

        LoginWindow.setCentralWidget(self.centralwidget)


class RegistrationRequestDialog(QWidget):
    """
    회원가입 요청 다이얼로그 (좌표 기반, 모던 스타일)
    """

    registrationRequested = pyqtSignal(str, str, str, str, str)  # name, username, password, contact, email

    backRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._username_available = False
        self._setup_ui()
        self._connect_validation_signals()

    def _setup_ui(self):
        self.setFixedSize(400, 720)  # Height increased for Email field
        self.setStyleSheet(f"background-color: {login_color('surface')};")

        # 뒤로가기 버튼
        self.backButton = QPushButton(self)
        self.backButton.setGeometry(QtCore.QRect(15, 15, 35, 35))
        self.backButton.setFont(QFont(FONT_FAMILY, ds.typography.size_sm))
        self.backButton.setText("←")
        self.backButton.setStyleSheet(f"""
            QPushButton {{
                background-color: {login_color('surface_variant')};
                border: none;
                border-radius: {ds.radius.full}px;
                color: {login_color('text_secondary')};
            }}
            QPushButton:hover {{ background-color: {login_color('border')}; }}
        """)
        self.backButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.backButton.clicked.connect(self._on_back)

        # 타이틀
        self.titleLabel = QLabel(self)
        self.titleLabel.setGeometry(QtCore.QRect(30, 65, 340, 35))
        self.titleLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_lg, QFont.Weight.Bold))
        self.titleLabel.setStyleSheet(f"color: {login_color('text_primary')}; background: transparent;")
        self.titleLabel.setText("회원가입")

        # 서브타이틀
        self.subtitleLabel = QLabel(self)
        self.subtitleLabel.setGeometry(QtCore.QRect(30, 100, 340, 40))
        self.subtitleLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        self.subtitleLabel.setStyleSheet(f"color: {login_color('text_muted')}; background: transparent;")
        self.subtitleLabel.setText("가입 정보를 입력해주세요.\n가입 후 바로 로그인 가능합니다. (체험판 제공)")

        # 가입자 명
        self.nameLabel = QLabel(self)
        self.nameLabel.setGeometry(QtCore.QRect(30, 150, 100, 25))
        self.nameLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_sm, QFont.Weight.Bold))
        self.nameLabel.setStyleSheet(f"color: {login_color('text_secondary')}; background: transparent;")
        self.nameLabel.setText("가입자 명")

        self.nameEdit = QLineEdit(self)
        self.nameEdit.setGeometry(QtCore.QRect(30, 175, 340, ds.button_sizes['md'].height))
        self.nameEdit.setFont(QFont(FONT_FAMILY, ds.typography.size_sm))
        self.nameEdit.setPlaceholderText("이름을 입력하세요")
        self._apply_input_style(self.nameEdit)

        # 이메일
        self.emailLabel = QLabel(self)
        self.emailLabel.setGeometry(QtCore.QRect(30, 225, 100, 25))
        self.emailLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_sm, QFont.Weight.Bold))
        self.emailLabel.setStyleSheet(f"color: {login_color('text_secondary')}; background: transparent;")
        self.emailLabel.setText("이메일")

        self.emailEdit = QLineEdit(self)
        self.emailEdit.setGeometry(QtCore.QRect(30, 250, 340, ds.button_sizes['md'].height))
        self.emailEdit.setFont(QFont(FONT_FAMILY, ds.typography.size_sm))
        self.emailEdit.setPlaceholderText("example@email.com")
        self._apply_input_style(self.emailEdit)

        # 아이디 + 중복확인 (Shifted down +75)
        self.usernameLabel = QLabel(self)
        self.usernameLabel.setGeometry(QtCore.QRect(30, 300, 100, 25))
        self.usernameLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_sm, QFont.Weight.Bold))
        self.usernameLabel.setStyleSheet(f"color: {login_color('text_secondary')}; background: transparent;")
        self.usernameLabel.setText("아이디")

        self.usernameEdit = QLineEdit(self)
        self.usernameEdit.setGeometry(QtCore.QRect(30, 325, 240, ds.button_sizes['md'].height))
        self.usernameEdit.setFont(QFont(FONT_FAMILY, ds.typography.size_sm))
        self.usernameEdit.setPlaceholderText("영문, 숫자, 밑줄(_)만 사용")
        self._apply_input_style(self.usernameEdit)
        self.usernameEdit.textChanged.connect(self._on_username_changed)

        self.checkUsernameBtn = QPushButton(self)
        self.checkUsernameBtn.setGeometry(QtCore.QRect(280, 325, 90, ds.button_sizes['md'].height))
        self.checkUsernameBtn.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        self.checkUsernameBtn.setText("중복확인")
        self.checkUsernameBtn.setStyleSheet(f"""
            QPushButton {{
                background-color: {login_color('text_muted')};
                color: white;
                border: none;
                border-radius: {ds.radius.base}px;
            }}
            QPushButton:hover {{ background-color: {login_color('text_secondary')}; }}
            QPushButton:disabled {{
                background-color: {login_color('border')};
                color: {login_color('text_muted')};
            }}
        """)
        self.checkUsernameBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.checkUsernameBtn.clicked.connect(self._check_username)

        self.usernameStatusLabel = QLabel(self)
        self.usernameStatusLabel.setGeometry(QtCore.QRect(30, 369, 340, 18))
        self.usernameStatusLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        self.usernameStatusLabel.setStyleSheet(f"color: {login_color('text_muted')}; background: transparent;")
        self.usernameStatusLabel.setText("")

        # 비밀번호 (Shifted down +75)
        self.passwordLabel = QLabel(self)
        self.passwordLabel.setGeometry(QtCore.QRect(30, 395, 100, 25))
        self.passwordLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_sm, QFont.Weight.Bold))
        self.passwordLabel.setStyleSheet(f"color: {login_color('text_secondary')}; background: transparent;")
        self.passwordLabel.setText("비밀번호")

        self.passwordEdit = QLineEdit(self)
        self.passwordEdit.setGeometry(QtCore.QRect(30, 420, 340, ds.button_sizes['md'].height))
        self.passwordEdit.setFont(QFont(FONT_FAMILY, ds.typography.size_sm))
        self.passwordEdit.setPlaceholderText("8자 이상, 영문+숫자 포함")
        self.passwordEdit.setEchoMode(QLineEdit.EchoMode.Password)
        self._apply_input_style(self.passwordEdit)

        self.passwordHintLabel = QLabel(self)
        self.passwordHintLabel.setGeometry(QtCore.QRect(30, 464, 340, 18))
        self.passwordHintLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        self.passwordHintLabel.setStyleSheet(f"color: {login_color('text_muted')}; background: transparent;")
        self.passwordHintLabel.setText("※ 영문+숫자 포함 8자 이상 필수")

        # 비밀번호 확인 (Shifted down +75)
        self.passwordConfirmLabel = QLabel(self)
        self.passwordConfirmLabel.setGeometry(QtCore.QRect(30, 485, 120, 25))
        self.passwordConfirmLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_sm, QFont.Weight.Bold))
        self.passwordConfirmLabel.setStyleSheet(f"color: {login_color('text_secondary')}; background: transparent;")
        self.passwordConfirmLabel.setText("비밀번호 확인")

        self.passwordConfirmEdit = QLineEdit(self)
        self.passwordConfirmEdit.setGeometry(QtCore.QRect(30, 510, 340, ds.button_sizes['md'].height))
        self.passwordConfirmEdit.setFont(QFont(FONT_FAMILY, ds.typography.size_sm))
        self.passwordConfirmEdit.setPlaceholderText("비밀번호를 다시 입력")
        self.passwordConfirmEdit.setEchoMode(QLineEdit.EchoMode.Password)
        self._apply_input_style(self.passwordConfirmEdit)

        # 비밀번호 확인 상태 라벨 (passwordConfirmEdit 바로 아래)
        self.passwordMatchLabel = QLabel(self)
        self.passwordMatchLabel.setGeometry(QtCore.QRect(30, 556, 340, 18))
        self.passwordMatchLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        self.passwordMatchLabel.setStyleSheet(f"color: {login_color('text_muted')}; background: transparent;")
        self.passwordMatchLabel.setText("")

        # 연락처 (Shifted down for passwordMatchLabel)
        self.contactLabel = QLabel(self)
        self.contactLabel.setGeometry(QtCore.QRect(30, 578, 100, 25))
        self.contactLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_sm, QFont.Weight.Bold))
        self.contactLabel.setStyleSheet(f"color: {login_color('text_secondary')}; background: transparent;")
        self.contactLabel.setText("연락처")

        self.contactEdit = QLineEdit(self)
        self.contactEdit.setGeometry(QtCore.QRect(30, 603, 340, ds.button_sizes['md'].height))
        self.contactEdit.setFont(QFont(FONT_FAMILY, ds.typography.size_sm))
        self.contactEdit.setPlaceholderText("010-1234-5678")
        self._apply_input_style(self.contactEdit)

        # 제출 버튼 (Shifted down)
        self.submitButton = QPushButton(self)
        self.submitButton.setGeometry(QtCore.QRect(30, 660, 340, ds.button_sizes['lg'].height))
        self.submitButton.setFont(QFont(FONT_FAMILY, ds.button_sizes['lg'].font_size, QFont.Weight.Bold))
        self.submitButton.setText("회원가입")
        self.submitButton.setStyleSheet(f"""
            QPushButton {{
                color: {login_color('surface')};
                background-color: {login_color('primary')};
                border: none;
                border-radius: {ds.radius.md}px;
            }}
            QPushButton:hover {{ background-color: {login_color('secondary')}; }}
            QPushButton:pressed {{ background-color: {login_color('primary')}; }}
            QPushButton:disabled {{
                background-color: {login_color('border')};
                color: {login_color('text_muted')};
            }}
        """)
        self.submitButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.submitButton.clicked.connect(self._on_submit)
        self.submitButton.setEnabled(True)

    def _apply_input_style(self, widget):
        widget.setStyleSheet(f"""
            QLineEdit {{
                background-color: {login_color('background')};
                color: {login_color('text_primary')};
                border: 1px solid {login_color('border')};
                border-radius: {ds.radius.base}px;
                padding: {ds.spacing.space_2}px {ds.spacing.space_3}px;
            }}
            QLineEdit:focus {{
                border: 2px solid {login_color('primary')};
                background-color: {login_color('surface')};
            }}
            QLineEdit::placeholder {{ color: {login_color('text_muted')}; }}
        """)

    def _connect_validation_signals(self):
        """모든 입력 필드에 실시간 검증 연결"""
        self.nameEdit.textChanged.connect(self._validate_form)
        self.emailEdit.textChanged.connect(self._validate_form)
        self.usernameEdit.textChanged.connect(self._validate_form)
        self.passwordEdit.textChanged.connect(self._validate_form)
        self.passwordConfirmEdit.textChanged.connect(self._validate_form)
        self.contactEdit.textChanged.connect(self._validate_form)

    def _validate_form(self):
        """Update realtime hints. Final validation runs on submit."""
        import re
        password = self.passwordEdit.text()
        password_confirm = self.passwordConfirmEdit.text()

        # Real-time password strength feedback
        if password:
            pw_issues = []
            if len(password) < 8:
                pw_issues.append("8자 이상")
            if not re.search(r'[a-zA-Z]', password):
                pw_issues.append("영문 포함")
            if not re.search(r'[0-9]', password):
                pw_issues.append("숫자 포함")
            if pw_issues:
                self.passwordHintLabel.setText(f"※ 필요: {', '.join(pw_issues)}")
                self.passwordHintLabel.setStyleSheet(f"color: {login_color('error')}; background: transparent;")
            else:
                self.passwordHintLabel.setText("※ 사용 가능한 비밀번호입니다")
                self.passwordHintLabel.setStyleSheet(f"color: {login_color('success')}; background: transparent;")
        else:
            self.passwordHintLabel.setText("※ 영문+숫자 포함 8자 이상 필수")
            self.passwordHintLabel.setStyleSheet(f"color: {login_color('text_muted')}; background: transparent;")

        if password_confirm:
            if password != password_confirm:
                self.passwordMatchLabel.setText("비밀번호가 일치하지 않습니다.")
                self.passwordMatchLabel.setStyleSheet(
                    f"color: {login_color('error')}; background: transparent;"
                )
            else:
                self.passwordMatchLabel.setText("비밀번호가 일치합니다.")
                self.passwordMatchLabel.setStyleSheet(
                    f"color: {login_color('success')}; background: transparent;"
                )
        else:
            self.passwordMatchLabel.setText("")

        # Keep clickable so user can always get exact missing-field alert.
        self.submitButton.setEnabled(True)

    def _collect_form_issues(self):
        """Collect missing/invalid registration fields in display order."""
        import re

        issues = []

        name = self.nameEdit.text().strip()
        email = self.emailEdit.text().strip()
        username = self.usernameEdit.text().strip().lower()
        password = self.passwordEdit.text()
        password_confirm = self.passwordConfirmEdit.text()
        contact_raw = self.contactEdit.text().strip()
        contact = re.sub(r"[^0-9]", "", contact_raw)

        if not name:
            issues.append(("가입자 명", "가입자 명을 입력해주세요.", self.nameEdit, "missing"))
        elif len(name) < 2:
            issues.append(("가입자 명", "가입자 명은 2자 이상 입력해주세요.", self.nameEdit, "invalid"))

        if not email:
            issues.append(("이메일", "이메일을 입력해주세요.", self.emailEdit, "missing"))
        elif "@" not in email or "." not in email:
            issues.append(("이메일", "올바른 이메일 주소를 입력해주세요.", self.emailEdit, "invalid"))

        if not username:
            issues.append(("아이디", "아이디를 입력해주세요.", self.usernameEdit, "missing"))
        elif len(username) < 4:
            issues.append(("아이디", "아이디는 4자 이상이어야 합니다.", self.usernameEdit, "invalid"))
        elif not re.match(r"^[a-z0-9_]+$", username):
            issues.append(("아이디", "아이디는 영문, 숫자, 밑줄(_)만 사용할 수 있습니다.", self.usernameEdit, "invalid"))
        elif not self._username_available:
            issues.append(("아이디 중복확인", "아이디 중복확인을 해주세요.", self.checkUsernameBtn, "invalid"))

        if not password:
            issues.append(("비밀번호", "비밀번호를 입력해주세요.", self.passwordEdit, "missing"))
        elif len(password) < 8:
            issues.append(("비밀번호", "비밀번호는 8자 이상이어야 합니다.", self.passwordEdit, "invalid"))
        elif not re.search(r'[a-zA-Z]', password):
            issues.append(("비밀번호", "비밀번호에 영문자를 1자 이상 포함해주세요.", self.passwordEdit, "invalid"))
        elif not re.search(r'[0-9]', password):
            issues.append(("비밀번호", "비밀번호에 숫자를 1자 이상 포함해주세요.", self.passwordEdit, "invalid"))

        if not password_confirm:
            issues.append(("비밀번호 확인", "비밀번호 확인을 입력해주세요.", self.passwordConfirmEdit, "missing"))
        elif password != password_confirm:
            issues.append(("비밀번호 확인", "비밀번호가 일치하지 않습니다.", self.passwordConfirmEdit, "invalid"))

        if not contact_raw:
            issues.append(("연락처", "연락처를 입력해주세요.", self.contactEdit, "missing"))
        elif len(contact) < 10:
            issues.append(("연락처", "올바른 연락처를 입력해주세요.", self.contactEdit, "invalid"))

        return issues

    def _on_back(self):
        self.backRequested.emit()
        self.close()

    def _on_username_changed(self, text):
        self._username_available = False
        self.usernameStatusLabel.setText("")
        self.usernameStatusLabel.setStyleSheet(f"color: {login_color('text_muted')}; background: transparent;")
        # 아이디 변경 시 폼 재검증 (중복확인 필요 상태로 변경됨)
        self._validate_form()

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
        self.usernameStatusLabel.setStyleSheet(f"color: {login_color('text_muted')}; background: transparent;")

        self._username_worker = UsernameCheckWorker(username)
        self._username_worker.finished.connect(self._on_username_check_done)
        self._username_worker.start()

    def _on_username_check_done(self, available: bool, message: str):
        self.checkUsernameBtn.setEnabled(True)
        self.checkUsernameBtn.setText("중복확인")

        if available:
            self._username_available = True
            self.usernameStatusLabel.setText("✓ 사용 가능한 아이디입니다")
            self.usernameStatusLabel.setStyleSheet(f"color: {login_color('success')}; background: transparent;")
        elif "네트워크" in message or "실패" in message:
            self._username_available = False
            self.usernameStatusLabel.setText(message)
            self.usernameStatusLabel.setStyleSheet(f"color: {login_color('warning')}; background: transparent;")
        else:
            self._username_available = False
            # Show the actual message from the server (e.g. "Pending approval", "Server error", etc.)
            self.usernameStatusLabel.setText(f"✗ {message}")
            self.usernameStatusLabel.setStyleSheet(f"color: {login_color('error')}; background: transparent;")
        logger.info(
            "[UI] Username check result | available=%s message=%s",
            available,
            message,
        )
        # 중복확인 결과에 따라 폼 검증 재실행
        self._validate_form()

    def _on_submit(self):
        import re
        from caller import rest

        issues = self._collect_form_issues()
        if issues:
            missing = [issue for issue in issues if issue[3] == "missing"]
            if missing:
                self._show_missing_field_alert(missing)
                focus_target = missing[0][2]
            else:
                first_issue = issues[0]
                self._show_error(first_issue[1])
                focus_target = first_issue[2]

            if focus_target is not None:
                focus_target.setFocus()
                if isinstance(focus_target, QLineEdit):
                    focus_target.selectAll()
            return

        name = self.nameEdit.text().strip()
        username = self.usernameEdit.text().strip().lower()
        password = self.passwordEdit.text()
        contact_raw = self.contactEdit.text().strip()
        contact = re.sub(r"[^0-9]", "", contact_raw)
        email = self.emailEdit.text().strip()

        try:
            logger.info(
                "[UI] Registration API call | name=%s username=%s contact=%s email=%s",
                name,
                username,
                contact,
                email,
            )
            result = rest.submitRegistrationRequest(
                name=name,
                username=username,
                password=password,
                contact=contact,
                email=email,
            )
            if result.get("success"):
                QMessageBox.information(self, "\uC644\uB8CC", "\uD68C\uC6D0\uAC00\uC785\uC774 \uC644\uB8CC\uB418\uC5C8\uC2B5\uB2C8\uB2E4! \uBC14\uB85C \uB85C\uADF8\uC778\uD574\uC8FC\uC138\uC694.")
                logger.info("[UI] Registration success | username=%s", username)
                self.registrationRequested.emit(name, username, password, contact, email)
                self.close()
            else:
                logger.warning(
                    "[UI] Registration failed | username=%s message=%s",
                    username,
                    result.get("message"),
                )
                self._show_error(result.get("message", "\uC54C \uC218 \uC5C6\uB294 \uC624\uB958\uAC00 \uBC1C\uC0DD\uD588\uC2B5\uB2C8\uB2E4."))
        except Exception as e:
            logger.exception("[UI] Registration exception")
            QMessageBox.critical(self, "\uC624\uB958", str(e))

    def _show_missing_field_alert(self, missing_issues):
        """Show a clear alert describing exactly which required fields are missing."""
        missing_fields = [field_name for field_name, *_ in missing_issues]

        if len(missing_fields) == 1:
            message = f"'{missing_fields[0]}' 항목을 입력해주세요."
        else:
            bullets = "\n".join(f"- {field}" for field in missing_fields)
            message = (
                f"다음 항목이 비어 있습니다:\n{bullets}\n\n"
                "누락된 항목을 모두 입력해주세요."
            )

        self._show_error(message, title="입력 누락")

    def _show_error(self, message: str, title: str = "입력 오류"):
        msgBox = QMessageBox(self)
        msgBox.setIcon(QMessageBox.Icon.Warning)
        msgBox.setWindowTitle(title)
        msgBox.setText(message)
        msgBox.setStandardButtons(QMessageBox.StandardButton.Ok)
        msgBox.exec()

    def clear_fields(self):
        self.nameEdit.clear()
        self.emailEdit.clear()
        self.usernameEdit.clear()
        self.passwordEdit.clear()
        self.passwordConfirmEdit.clear()
        self.contactEdit.clear()
        self._username_available = False
        self.usernameStatusLabel.setText("")
        self.submitButton.setEnabled(True)


Ui_LoginWindow = ModernLoginUi
