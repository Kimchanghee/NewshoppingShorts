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
from PyQt6.QtCore import Qt, QUrl, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QVBoxLayout,
    QFormLayout,
    QScrollArea,
)
from PyQt6.QtGui import QDesktopServices, QFont, QIcon, QPixmap

from ui.design_system_v2 import get_design_system, ColorPalette
from ui.components.custom_dialog import show_info, show_warning, show_error, show_success
from ui.responsive import bounded_size
from utils.app_identity import load_app_identity
from user_facing_errors import sanitize_user_message

# Initialize design system and ALWAYS use light palette for login
ds = get_design_system()
# Use light colors for login screen regardless of app-wide dark mode
light_colors = ColorPalette()

def login_color(key: str) -> str:
    """Get color from light palette for login UI"""
    return getattr(light_colors, key, "#000000")


def apply_visible_line_edit_style(
    widget: QLineEdit,
    *,
    radius: int,
    vertical_padding: int,
    horizontal_padding: int,
) -> None:
    """Force login form inputs to keep readable colors on every OS theme."""
    text_color = login_color("text_primary")
    placeholder_color = login_color("text_muted")
    background_color = login_color("background")
    focused_background = login_color("surface")
    border_color = login_color("border")
    primary_color = login_color("primary")

    palette = widget.palette()
    palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(text_color))
    palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(background_color))
    palette.setColor(QtGui.QPalette.ColorRole.PlaceholderText, QtGui.QColor(placeholder_color))
    palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(primary_color))
    palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor(focused_background))
    widget.setPalette(palette)
    widget.setStyleSheet(f"""
        QLineEdit {{
            background-color: {background_color};
            color: {text_color};
            placeholder-text-color: {placeholder_color};
            selection-background-color: {primary_color};
            selection-color: {focused_background};
            border: 1px solid {border_color};
            border-radius: {radius}px;
            padding: {vertical_padding}px {horizontal_padding}px;
        }}
        QLineEdit:focus {{
            color: {text_color};
            border: 2px solid {primary_color};
            background-color: {focused_background};
        }}
        QLineEdit:disabled {{
            color: {login_color('text_secondary')};
            background-color: {login_color('surface_variant')};
            border: 1px solid {border_color};
        }}
    """)

FONT_FAMILY = "맑은 고딕"
logger = logging.getLogger(__name__)
TERMS_DOCUMENT_VERSION = "2026-08-13"
PRIVACY_DOCUMENT_VERSION = "2026-08-08"
PRIVACY_POLICY_URL = "https://newshopping-shorts-auth.vercel.app/privacy"
TERMS_OF_SERVICE_URL = "https://newshopping-shorts-auth.vercel.app/terms"


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
                with open(path, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
                version = str(data.get("version", "")).strip()
                if version:
                    return version
        except Exception:
            continue
    return "1.0.0"


class UsernameCheckWorker(QThread):
    """아이디 중복 확인 백그라운드 워커"""

    finished = pyqtSignal(str, bool, str)  # (username, available, message)

    def __init__(self, username: str):
        super().__init__()
        self.username = username

    def run(self):
        try:
            from caller import rest

            result = rest.checkUsernameAvailability(
                self.username, program_type="ssmaker"
            )
            self.finished.emit(
                self.username,
                bool(result.get("available", False)),
                str(result.get("message") or ""),
            )
        except Exception as e:
            logging.getLogger(__name__).warning(
                "Username availability request failed: %s", e
            )
            self.finished.emit(
                self.username,
                False,
                "서버와 연결하지 못했어요. 잠시 후 다시 확인해 주세요.",
            )


class RegistrationSubmitWorker(QThread):
    """Run the registration HTTP request without blocking the Qt event loop."""

    completed = pyqtSignal(dict)

    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self.payload = dict(payload)

    def run(self):
        try:
            from caller import rest

            result = rest.submitRegistrationRequest(**self.payload)
        except Exception:
            logger.exception("[UI] Registration worker exception")
            result = {
                "success": False,
                "message": "회원가입 요청 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            }
        self.completed.emit(dict(result or {}))


class ModernLoginUi:
    """
    모던 로그인 UI 클래스 (PyQt6)
    """

    def setupUi(self, LoginWindow: QMainWindow):
        LoginWindow.setObjectName("LoginWindow")
        screen = (
            QtWidgets.QApplication.screenAt(QtGui.QCursor.pos())
            or QtWidgets.QApplication.primaryScreen()
        )
        available = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1280, 800)
        login_size = bounded_size(
            available,
            QtCore.QSize(720, 760),
            QtCore.QSize(600, 520),
        )
        LoginWindow.setFixedSize(login_size)
        compact_width = login_size.width() < 680
        compact_height = login_size.height() < 700

        self.centralwidget = QWidget(LoginWindow)
        self.centralwidget.setObjectName("centralwidget")

        root_layout = QHBoxLayout(self.centralwidget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.leftFrame = QFrame(self.centralwidget)
        self.leftFrame.setMinimumWidth(300)
        self.leftFrame.setMaximumWidth(300)
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
        root_layout.addWidget(self.leftFrame)
        self.leftFrame.setVisible(not compact_width)

        left_layout = QVBoxLayout(self.leftFrame)
        left_layout.setContentsMargins(26, 28, 26, 24)
        left_layout.setSpacing(10)
        left_layout.addStretch(1)

        self.logoIcon = QLabel(self.leftFrame)
        self.logoIcon.setFixedSize(116, 116)
        self.logoIcon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logoIcon.setFont(QFont(FONT_FAMILY, ds.typography.size_3xl, QFont.Weight.Bold))
        self.logoIcon.setStyleSheet(f"""
            color: white;
            background: rgba(255,255,255,0.15);
            border-radius: {ds.radius.xl}px;
        """)
        self.logoIcon.setText("SS")
        left_layout.addWidget(self.logoIcon, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.logoBadge = QLabel(self.leftFrame)
        self.logoBadge.setFixedHeight(28)
        self.logoBadge.setMinimumWidth(120)
        self.logoBadge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logoBadge.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs, QFont.Weight.Bold))
        self.logoBadge.setStyleSheet(f"""
            color: {login_color('primary')};
            background: white;
            border-radius: {ds.radius.full}px;
            padding: {ds.spacing.space_1}px;
        """)
        self.logoBadge.setText("쇼츠 메이커")
        left_layout.addWidget(self.logoBadge, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.titleLabel = QLabel(self.leftFrame)
        self.titleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.titleLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_lg, QFont.Weight.Bold))
        self.titleLabel.setStyleSheet("color: white; background: transparent; padding-bottom: 3px;")
        self.titleLabel.setWordWrap(True)
        self.titleLabel.setText("쇼핑 숏폼 메이커")
        left_layout.addWidget(self.titleLabel)

        self.subtitleLabel = QLabel(self.leftFrame)
        self.subtitleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitleLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        self.subtitleLabel.setStyleSheet("color: rgba(255,255,255,0.85); background: transparent; padding-bottom: 3px;")
        self.subtitleLabel.setWordWrap(True)
        self.subtitleLabel.setText("쇼핑 영상을 숏폼 콘텐츠로 자동 변환합니다")
        left_layout.addWidget(self.subtitleLabel)

        self.featureIcons = QLabel(self.leftFrame)
        self.featureIcons.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.featureIcons.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        self.featureIcons.setStyleSheet("color: rgba(255,255,255,0.7); background: transparent;")
        self.featureIcons.setText("AI 번역  |  자동 편집  |  숏폼 제작")
        left_layout.addWidget(self.featureIcons)

        left_layout.addStretch(1)

        self.versionLabel = QLabel(self.leftFrame)
        self.versionLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.versionLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        self.versionLabel.setStyleSheet("color: rgba(255,255,255,0.5); background: transparent;")
        identity = load_app_identity()
        self.versionLabel.setText(identity.display_metadata)
        self.versionLabel.setAccessibleDescription(identity.accessible_description)
        left_layout.addWidget(self.versionLabel)

        self.rightFrame = QFrame(self.centralwidget)
        self.rightFrame.setMinimumWidth(360 if compact_width else 420)
        self.rightFrame.setMaximumWidth(QtWidgets.QWIDGETSIZE_MAX)
        self.rightFrame.setStyleSheet(f"background-color: {login_color('surface')};")
        self.rightFrame.setFrameShape(QFrame.Shape.StyledPanel)
        root_layout.addWidget(self.rightFrame, 1)

        right_layout = QVBoxLayout(self.rightFrame)
        side_margin = 24 if compact_width or compact_height else 40
        right_layout.setContentsMargins(side_margin, 14 if compact_height else 18, side_margin, 18 if compact_height else 24)
        right_layout.setSpacing(8 if compact_height else 10)

        titlebar_layout = QHBoxLayout()
        titlebar_layout.addStretch(1)

        self.minimumButton = QPushButton(self.rightFrame)
        self.minimumButton.setFixedSize(28, 28)
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
        titlebar_layout.addWidget(self.minimumButton)

        self.exitButton = QPushButton(self.rightFrame)
        self.exitButton.setFixedSize(28, 28)
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
        titlebar_layout.addWidget(self.exitButton)
        right_layout.addLayout(titlebar_layout)

        self.loginTitleLabel = QLabel(self.rightFrame)
        self.loginTitleLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_xl, QFont.Weight.Bold))
        self.loginTitleLabel.setStyleSheet(f"color: {login_color('text_primary')}; background: transparent;")
        self.loginTitleLabel.setText("로그인")
        right_layout.addWidget(self.loginTitleLabel)
        right_layout.addSpacing(6)

        self.label_id = QLabel(self.rightFrame)
        self.label_id.setFont(QFont(FONT_FAMILY, ds.typography.size_sm, QFont.Weight.Bold))
        self.label_id.setStyleSheet(f"color: {login_color('text_secondary')}; background: transparent;")
        self.label_id.setText("아이디")
        right_layout.addWidget(self.label_id)

        self.idEdit = QLineEdit(self.rightFrame)
        self.idEdit.setMinimumHeight(ds.button_sizes["md"].height)
        self.idEdit.setFont(QFont(FONT_FAMILY, ds.typography.size_sm))
        self.idEdit.setPlaceholderText("아이디를 입력하세요")
        apply_visible_line_edit_style(
            self.idEdit,
            radius=ds.radius.md,
            vertical_padding=ds.spacing.space_3,
            horizontal_padding=ds.spacing.space_4,
        )
        right_layout.addWidget(self.idEdit)
        right_layout.addSpacing(4)

        self.label_pw = QLabel(self.rightFrame)
        self.label_pw.setFont(QFont(FONT_FAMILY, ds.typography.size_sm, QFont.Weight.Bold))
        self.label_pw.setStyleSheet(f"color: {login_color('text_secondary')}; background: transparent;")
        self.label_pw.setText("비밀번호")
        right_layout.addWidget(self.label_pw)

        self.pwEdit = QLineEdit(self.rightFrame)
        self.pwEdit.setMinimumHeight(ds.button_sizes["md"].height)
        self.pwEdit.setFont(QFont(FONT_FAMILY, ds.typography.size_sm))
        self.pwEdit.setPlaceholderText("비밀번호를 입력하세요")
        self.pwEdit.setEchoMode(QLineEdit.EchoMode.Password)
        apply_visible_line_edit_style(
            self.pwEdit,
            radius=ds.radius.md,
            vertical_padding=ds.spacing.space_3,
            horizontal_padding=ds.spacing.space_4,
        )
        right_layout.addWidget(self.pwEdit)
        right_layout.addSpacing(4)

        login_options_layout = QHBoxLayout()
        login_options_layout.setContentsMargins(0, 0, 0, 0)
        login_options_layout.setSpacing(12)
        checkbox_style = f"""
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
        """

        self.rememberCheckbox = QCheckBox(self.rightFrame)
        self.rememberCheckbox.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        self.rememberCheckbox.setText("아이디 / 비밀번호 저장")
        self.rememberCheckbox.setStyleSheet(checkbox_style)
        self.rememberCheckbox.setCursor(Qt.CursorShape.PointingHandCursor)
        login_options_layout.addWidget(self.rememberCheckbox)

        self.autoLoginCheckbox = QCheckBox(self.rightFrame)
        self.autoLoginCheckbox.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        self.autoLoginCheckbox.setText("자동 로그인")
        self.autoLoginCheckbox.setStyleSheet(checkbox_style)
        self.autoLoginCheckbox.setCursor(Qt.CursorShape.PointingHandCursor)
        login_options_layout.addWidget(self.autoLoginCheckbox)
        login_options_layout.addStretch(1)
        right_layout.addLayout(login_options_layout)

        right_layout.addStretch(1)

        self.loginButton = QPushButton(self.rightFrame)
        self.loginButton.setMinimumHeight(ds.button_sizes["lg"].height)
        self.loginButton.setFont(QFont(FONT_FAMILY, ds.button_sizes["lg"].font_size, QFont.Weight.Bold))
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
        right_layout.addWidget(self.loginButton)
        right_layout.addSpacing(8)

        self.registerRequestButton = QPushButton(self.rightFrame)
        self.registerRequestButton.setMinimumHeight(ds.button_sizes["lg"].height)
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
        self.registerRequestButton.setText("회원가입 요청")
        right_layout.addWidget(self.registerRequestButton)

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
        self.registration_result = {}
        self._registration_in_progress = False
        self._pending_registration_fields = None
        self._setup_ui()
        self._connect_validation_signals()

    def _setup_ui(self):
        screen = (
            QtWidgets.QApplication.screenAt(QtGui.QCursor.pos())
            or QtWidgets.QApplication.primaryScreen()
        )
        available = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1280, 800)
        dialog_size = bounded_size(
            available,
            QtCore.QSize(420, 760),
            QtCore.QSize(360, 480),
        )
        self.resize(dialog_size)
        self.setMinimumSize(
            min(360, dialog_size.width()),
            min(480, dialog_size.height()),
        )
        self.setObjectName("registrationDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            QWidget#registrationDialog {{
                background-color: {login_color('surface_variant')};
                border: 2px solid {login_color('primary')};
                border-radius: {ds.radius.lg}px;
            }}
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        self.backButton = QPushButton(self)
        self.backButton.setFixedSize(36, 36)
        self.backButton.setFont(QFont(FONT_FAMILY, ds.typography.size_sm))
        self.backButton.setText("<")
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
        header_layout.addWidget(self.backButton, alignment=Qt.AlignmentFlag.AlignTop)

        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(4)

        self.titleLabel = QLabel(self)
        self.titleLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_lg, QFont.Weight.Bold))
        self.titleLabel.setStyleSheet(f"color: {login_color('text_primary')}; background: transparent;")
        self.titleLabel.setText("회원가입 요청")
        title_layout.addWidget(self.titleLabel)

        self.subtitleLabel = QLabel(self)
        self.subtitleLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        self.subtitleLabel.setStyleSheet(f"color: {login_color('text_muted')}; background: transparent; padding-bottom: 3px;")
        self.subtitleLabel.setWordWrap(True)
        self.subtitleLabel.setText("로그인과 별개의 새 계정 생성 화면입니다.")
        title_layout.addWidget(self.subtitleLabel)

        header_layout.addLayout(title_layout, 1)
        root_layout.addLayout(header_layout)

        self.scrollArea = QScrollArea(self)
        self.scrollArea.setObjectName("registrationScrollArea")
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.scrollArea.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scrollArea.setStyleSheet(f"""
            QScrollArea#registrationScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: {login_color('surface_variant')};
                width: 10px;
                margin: 4px 1px 4px 1px;
                border: none;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {login_color('primary')};
                min-height: 38px;
                border: 2px solid {login_color('surface_variant')};
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {login_color('secondary')};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
                border: none;
                background: transparent;
            }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """)
        self.scrollArea.viewport().setStyleSheet("background: transparent;")
        root_layout.addWidget(self.scrollArea, 1)

        form_container = QWidget()
        form_container.setObjectName("registrationFormCard")
        form_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        form_container.setStyleSheet(f"""
            QWidget#registrationFormCard {{
                background-color: {login_color('surface')};
                border: 1px solid {login_color('border')};
                border-radius: {ds.radius.md}px;
            }}
        """)
        self.scrollArea.setWidget(form_container)

        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(14, 14, 14, 14)
        form_layout.setSpacing(8)
        input_height = ds.button_sizes["md"].height

        def _field_label(text: str) -> QLabel:
            label = QLabel(form_container)
            label.setFont(QFont(FONT_FAMILY, ds.typography.size_sm, QFont.Weight.Bold))
            label.setStyleSheet(f"color: {login_color('text_secondary')}; background: transparent;")
            label.setText(text)
            return label

        self.nameLabel = _field_label("이름")
        form_layout.addWidget(self.nameLabel)

        self.nameEdit = QLineEdit(form_container)
        self.nameEdit.setMinimumHeight(input_height)
        self.nameEdit.setFont(QFont(FONT_FAMILY, ds.typography.size_sm))
        self.nameEdit.setPlaceholderText("이름을 입력하세요")
        self._apply_input_style(self.nameEdit)
        form_layout.addWidget(self.nameEdit)

        self.emailLabel = _field_label("이메일")
        form_layout.addWidget(self.emailLabel)

        self.emailEdit = QLineEdit(form_container)
        self.emailEdit.setMinimumHeight(input_height)
        self.emailEdit.setFont(QFont(FONT_FAMILY, ds.typography.size_sm))
        self.emailEdit.setPlaceholderText("example@email.com")
        self._apply_input_style(self.emailEdit)
        form_layout.addWidget(self.emailEdit)

        self.usernameLabel = _field_label("아이디")
        form_layout.addWidget(self.usernameLabel)

        username_row = QHBoxLayout()
        username_row.setSpacing(8)

        self.usernameEdit = QLineEdit(form_container)
        self.usernameEdit.setMinimumHeight(input_height)
        self.usernameEdit.setFont(QFont(FONT_FAMILY, ds.typography.size_sm))
        self.usernameEdit.setPlaceholderText("영문 소문자, 숫자, 밑줄(_) 사용")
        self._apply_input_style(self.usernameEdit)
        self.usernameEdit.textChanged.connect(self._on_username_changed)
        username_row.addWidget(self.usernameEdit, 1)

        self.checkUsernameBtn = QPushButton(form_container)
        self.checkUsernameBtn.setFixedHeight(input_height)
        self.checkUsernameBtn.setMinimumWidth(100)
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
        username_row.addWidget(self.checkUsernameBtn)
        form_layout.addLayout(username_row)

        self.usernameStatusLabel = QLabel(form_container)
        self.usernameStatusLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        self.usernameStatusLabel.setStyleSheet(f"color: {login_color('text_muted')}; background: transparent; padding-bottom: 3px;")
        self.usernameStatusLabel.setWordWrap(True)
        self.usernameStatusLabel.setText("")
        form_layout.addWidget(self.usernameStatusLabel)

        self.passwordLabel = _field_label("비밀번호")
        form_layout.addWidget(self.passwordLabel)

        self.passwordEdit = QLineEdit(form_container)
        self.passwordEdit.setMinimumHeight(input_height)
        self.passwordEdit.setFont(QFont(FONT_FAMILY, ds.typography.size_sm))
        self.passwordEdit.setPlaceholderText("영문+숫자 포함 8자 이상")
        self.passwordEdit.setEchoMode(QLineEdit.EchoMode.Password)
        self._apply_input_style(self.passwordEdit)
        form_layout.addWidget(self.passwordEdit)

        self.passwordHintLabel = QLabel(form_container)
        self.passwordHintLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        self.passwordHintLabel.setStyleSheet(f"color: {login_color('text_muted')}; background: transparent; padding-bottom: 3px;")
        self.passwordHintLabel.setWordWrap(True)
        self.passwordHintLabel.setText("영문+숫자 포함 8자 이상")
        form_layout.addWidget(self.passwordHintLabel)

        self.passwordConfirmLabel = _field_label("비밀번호 확인")
        form_layout.addWidget(self.passwordConfirmLabel)

        self.passwordConfirmEdit = QLineEdit(form_container)
        self.passwordConfirmEdit.setMinimumHeight(input_height)
        self.passwordConfirmEdit.setFont(QFont(FONT_FAMILY, ds.typography.size_sm))
        self.passwordConfirmEdit.setPlaceholderText("비밀번호를 다시 입력하세요")
        self.passwordConfirmEdit.setEchoMode(QLineEdit.EchoMode.Password)
        self._apply_input_style(self.passwordConfirmEdit)
        form_layout.addWidget(self.passwordConfirmEdit)

        self.passwordMatchLabel = QLabel(form_container)
        self.passwordMatchLabel.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        self.passwordMatchLabel.setStyleSheet(f"color: {login_color('text_muted')}; background: transparent; padding-bottom: 3px;")
        self.passwordMatchLabel.setWordWrap(True)
        self.passwordMatchLabel.setText("")
        form_layout.addWidget(self.passwordMatchLabel)

        self.contactLabel = _field_label("연락처")
        form_layout.addWidget(self.contactLabel)

        self.contactEdit = QLineEdit(form_container)
        self.contactEdit.setMinimumHeight(input_height)
        self.contactEdit.setFont(QFont(FONT_FAMILY, ds.typography.size_sm))
        self.contactEdit.setPlaceholderText("010-1234-5678")
        self._apply_input_style(self.contactEdit)
        form_layout.addWidget(self.contactEdit)

        form_layout.addSpacing(6)

        consent_title = _field_label("필수 동의")
        form_layout.addWidget(consent_title)

        def _consent_row(
            checkbox: QCheckBox, label_html: str
        ) -> tuple[QHBoxLayout, QLabel]:
            row = QHBoxLayout()
            row.setSpacing(7)
            checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
            checkbox.setAccessibleName(label_html.replace("<a href='#'>", "").replace("</a>", ""))
            row.addWidget(checkbox, alignment=Qt.AlignmentFlag.AlignTop)
            label = QLabel(label_html, form_container)
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            label.setOpenExternalLinks(False)
            label.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
            label.setStyleSheet(
                f"color:{login_color('text_secondary')}; background:transparent;"
                f"link-color:{login_color('primary')};"
            )
            label.setWordWrap(True)
            row.addWidget(label, 1)
            return row, label

        self.termsConsentCheckBox = QCheckBox(form_container)
        terms_row, self.termsLinkLabel = _consent_row(
            self.termsConsentCheckBox,
            "[필수] <a href='#'>서비스 이용약관</a>에 동의합니다.",
        )
        self.termsLinkLabel.linkActivated.connect(
            lambda _href: QDesktopServices.openUrl(QUrl(TERMS_OF_SERVICE_URL))
        )
        form_layout.addLayout(terms_row)

        self.privacyConsentCheckBox = QCheckBox(form_container)
        privacy_row, self.privacyLinkLabel = _consent_row(
            self.privacyConsentCheckBox,
            "[필수] <a href='#'>개인정보 수집·이용 및 처리방침</a>에 동의합니다.",
        )
        self.privacyLinkLabel.linkActivated.connect(
            lambda _href: QDesktopServices.openUrl(QUrl(PRIVACY_POLICY_URL))
        )
        form_layout.addLayout(privacy_row)

        consent_help = QLabel(
            "각 문서는 웹사이트에서 전문을 확인할 수 있으며, 필수 동의는 각각 선택합니다.",
            form_container,
        )
        consent_help.setWordWrap(True)
        consent_help.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        consent_help.setStyleSheet(
            f"color:{login_color('text_muted')}; background:transparent; padding-bottom:4px;"
        )
        form_layout.addWidget(consent_help)

        self.responsibilityNotice = QFrame(form_container)
        self.responsibilityNotice.setAccessibleName("이용 전 확인")
        self.responsibilityNotice.setStyleSheet(f"""
            QFrame {{
                background-color: {login_color('surface_variant')};
                border: 1px solid {login_color('border')};
                border-radius: {ds.radius.md}px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        notice_layout = QVBoxLayout(self.responsibilityNotice)
        notice_layout.setContentsMargins(12, 10, 12, 10)
        notice_layout.setSpacing(5)

        self.responsibilityNoticeTitle = QLabel("이용 전 확인", self.responsibilityNotice)
        self.responsibilityNoticeTitle.setFont(
            QFont(FONT_FAMILY, ds.typography.size_xs, QFont.Weight.Bold)
        )
        self.responsibilityNoticeTitle.setStyleSheet(
            f"color:{login_color('text_primary')}; background:transparent; border:none;"
        )
        notice_layout.addWidget(self.responsibilityNoticeTitle)

        self.responsibilityNoticeBody = QLabel(
            "SSMaker는 콘텐츠 제작과 운영을 돕는 도구이며 "
            "조회수·판매·제휴 수익을 보장하지 않습니다. 연결한 계정과 게시물은 "
            "직접 확인하고 각 플랫폼 정책, 광고 표시 및 저작권 기준에 맞게 운영해 주세요. "
            "외부 플랫폼의 정책·심사·장애로 생기는 제한에는 해당 플랫폼 기준이 적용됩니다. "
            "<a href='#'>이용약관에서 자세히 보기</a>",
            self.responsibilityNotice,
        )
        self.responsibilityNoticeBody.setAccessibleName("수익 및 연결 계정 운영 안내")
        self.responsibilityNoticeBody.setTextFormat(Qt.TextFormat.RichText)
        self.responsibilityNoticeBody.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        self.responsibilityNoticeBody.setOpenExternalLinks(False)
        self.responsibilityNoticeBody.setWordWrap(True)
        self.responsibilityNoticeBody.setFont(QFont(FONT_FAMILY, ds.typography.size_xs))
        self.responsibilityNoticeBody.setStyleSheet(
            f"color:{login_color('text_secondary')}; background:transparent; border:none;"
            f"link-color:{login_color('primary')};"
        )
        self.responsibilityNoticeBody.linkActivated.connect(
            lambda _href: QDesktopServices.openUrl(QUrl(TERMS_OF_SERVICE_URL))
        )
        notice_layout.addWidget(self.responsibilityNoticeBody)
        form_layout.addWidget(self.responsibilityNotice)

        self.submitButton = QPushButton(form_container)
        self.submitButton.setMinimumHeight(ds.button_sizes["lg"].height)
        self.submitButton.setFont(QFont(FONT_FAMILY, ds.button_sizes['lg'].font_size, QFont.Weight.Bold))
        self.submitButton.setText("회원가입 요청 제출")
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
        self.submitButton.setEnabled(not self._registration_in_progress)
        form_layout.addWidget(self.submitButton)
        form_layout.addStretch(1)

    def _apply_input_style(self, widget):
        apply_visible_line_edit_style(
            widget,
            radius=ds.radius.base,
            vertical_padding=ds.spacing.space_2,
            horizontal_padding=ds.spacing.space_3,
        )

    def _connect_validation_signals(self):
        """모든 입력 필드에 실시간 검증 연결"""
        self.nameEdit.textChanged.connect(self._validate_form)
        self.emailEdit.textChanged.connect(self._validate_form)
        self.usernameEdit.textChanged.connect(self._validate_form)
        self.passwordEdit.textChanged.connect(self._validate_form)
        self.passwordConfirmEdit.textChanged.connect(self._validate_form)
        self.contactEdit.textChanged.connect(self._validate_form)
        self.termsConsentCheckBox.toggled.connect(self._validate_form)
        self.privacyConsentCheckBox.toggled.connect(self._validate_form)

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
                self.passwordHintLabel.setStyleSheet(f"color: {login_color('error')}; background: transparent; padding-bottom: 3px;")
            else:
                self.passwordHintLabel.setText("※ 사용 가능한 비밀번호입니다")
                self.passwordHintLabel.setStyleSheet(f"color: {login_color('success')}; background: transparent; padding-bottom: 3px;")
        else:
            self.passwordHintLabel.setText("※ 영문+숫자 포함 8자 이상 필수")
            self.passwordHintLabel.setStyleSheet(f"color: {login_color('text_muted')}; background: transparent; padding-bottom: 3px;")

        if password_confirm:
            if password != password_confirm:
                self.passwordMatchLabel.setText("비밀번호가 일치하지 않습니다.")
                self.passwordMatchLabel.setStyleSheet(
                    f"color: {login_color('error')}; background: transparent; padding-bottom: 3px;"
                )
            else:
                self.passwordMatchLabel.setText("비밀번호가 일치합니다.")
                self.passwordMatchLabel.setStyleSheet(
                    f"color: {login_color('success')}; background: transparent; padding-bottom: 3px;"
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

        if not self.termsConsentCheckBox.isChecked():
            issues.append((
                "서비스 이용약관 동의",
                "서비스 이용약관을 확인하고 동의해주세요.",
                self.termsConsentCheckBox,
                "missing",
            ))
        if not self.privacyConsentCheckBox.isChecked():
            issues.append((
                "개인정보 수집·이용 동의",
                "개인정보 수집·이용 내용을 확인하고 동의해주세요.",
                self.privacyConsentCheckBox,
                "missing",
            ))

        return issues

    def _on_back(self):
        self.backRequested.emit()
        self.close()

    def _on_username_changed(self, text):
        self._username_available = False
        self.usernameStatusLabel.setText("")
        self.usernameStatusLabel.setStyleSheet(f"color: {login_color('text_muted')}; background: transparent; padding-bottom: 3px;")
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

        # Keep the existing request alive; terminating QThread during an HTTP
        # call can corrupt Qt state. Its result is ignored if the text changed.
        if hasattr(self, "_username_worker") and self._username_worker.isRunning():
            return

        self.checkUsernameBtn.setEnabled(False)
        self.checkUsernameBtn.setText("확인중...")
        self.usernameStatusLabel.setText("확인 중...")
        self.usernameStatusLabel.setStyleSheet(f"color: {login_color('text_muted')}; background: transparent; padding-bottom: 3px;")

        self._username_worker = UsernameCheckWorker(username)
        self._username_worker.finished.connect(self._on_username_check_done)
        self._username_worker.start()

    def _on_username_check_done(
        self, checked_username: str, available: bool, message: str
    ):
        self.checkUsernameBtn.setEnabled(True)
        self.checkUsernameBtn.setText("중복확인")

        current_username = self.usernameEdit.text().strip().lower()
        if current_username != checked_username:
            self._username_available = False
            self.usernameStatusLabel.setText("")
            self._validate_form()
            return

        message = sanitize_user_message(
            message,
            fallback="아이디 사용 여부를 확인하지 못했어요. 잠시 후 다시 시도해 주세요.",
        )

        if available:
            self._username_available = True
            self.usernameStatusLabel.setText("✓ 사용 가능한 아이디입니다")
            self.usernameStatusLabel.setStyleSheet(f"color: {login_color('success')}; background: transparent; padding-bottom: 3px;")
        elif "네트워크" in message or "실패" in message:
            self._username_available = False
            self.usernameStatusLabel.setText(message)
            self.usernameStatusLabel.setStyleSheet(f"color: {login_color('warning')}; background: transparent; padding-bottom: 3px;")
        else:
            self._username_available = False
            # Show the actual message from the server (e.g. "Pending approval", "Server error", etc.)
            self.usernameStatusLabel.setText(f"✗ {message}")
            self.usernameStatusLabel.setStyleSheet(f"color: {login_color('error')}; background: transparent; padding-bottom: 3px;")
        logger.info(
            "[UI] Username check result | available=%s message=%s",
            available,
            message,
        )
        # 중복확인 결과에 따라 폼 검증 재실행
        self._validate_form()

    def _on_submit(self):
        import re

        if self._registration_in_progress:
            return

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

        logger.info(
            "[UI] Registration API call | name=%s username=%s contact=%s email=%s",
            name,
            username,
            contact,
            email,
        )
        payload = {
            "name": name,
            "username": username,
            "password": password,
            "contact": contact,
            "email": email,
            "terms_accepted": self.termsConsentCheckBox.isChecked(),
            "privacy_accepted": self.privacyConsentCheckBox.isChecked(),
            "terms_version": TERMS_DOCUMENT_VERSION,
            "privacy_version": PRIVACY_DOCUMENT_VERSION,
        }
        self._pending_registration_fields = (
            name,
            username,
            password,
            contact,
            email,
        )
        self._registration_in_progress = True
        self.submitButton.setEnabled(False)
        self.submitButton.setText("가입 처리 중...")
        self._registration_worker = RegistrationSubmitWorker(payload, self)
        self._registration_worker.completed.connect(self._on_registration_done)
        self._registration_worker.start()

    def _on_registration_done(self, result: dict) -> None:
        self._registration_in_progress = False
        self.submitButton.setText("회원가입 요청 제출")
        self.submitButton.setEnabled(True)
        fields = self._pending_registration_fields
        self._pending_registration_fields = None

        if result.get("success") and fields:
            self.registration_result = dict(result)
            name, username, password, contact, email = fields
            logger.info("[UI] Registration success | username=%s", username)
            self.registrationRequested.emit(name, username, password, contact, email)
            self.close()
            return

        logger.warning(
            "[UI] Registration failed | message=%s", result.get("message")
        )
        self._show_error(
            result.get(
                "message", "알 수 없는 오류가 발생했습니다."
            )
        )

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
        show_warning(self, title, message)

    def clear_fields(self):
        self.nameEdit.clear()
        self.emailEdit.clear()
        self.usernameEdit.clear()
        self.passwordEdit.clear()
        self.passwordConfirmEdit.clear()
        self.contactEdit.clear()
        self.termsConsentCheckBox.setChecked(False)
        self.privacyConsentCheckBox.setChecked(False)
        self._username_available = False
        self._registration_in_progress = False
        self.usernameStatusLabel.setText("")
        self.submitButton.setEnabled(True)


Ui_LoginWindow = ModernLoginUi
