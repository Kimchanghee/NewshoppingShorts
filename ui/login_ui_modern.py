# -*- coding: utf-8 -*-
"""
Modern Login UI for Shopping Shorts Maker
쇼핑 숏폼 메이커 모던 로그인 UI

STITCH MCP 디자인 기반 리팩토링
기존 기능 100% 보존 + 모던 UI/UX 적용
"""

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QGraphicsDropShadowEffect
)
from PyQt5.QtGui import QFont, QIcon, QPixmap, QColor, QPainter, QLinearGradient

from ui.design_system import get_design_system, get_color


class ModernLineEdit(QLineEdit):
    """
    모던 스타일 입력 필드
    Modern styled input field with icon support

    Fixed: Removed emoji icon painting that caused text overlap
    수정: 텍스트 겹침을 유발하던 이모지 아이콘 페인팅 제거
    """

    def __init__(self, placeholder: str = "", icon: str = "", parent=None):
        super().__init__(parent)
        self._icon = icon
        self.setPlaceholderText(placeholder)
        self._setup_icon()
        self._apply_style()

    def _setup_icon(self):
        """Setup icon as a child label instead of painting"""
        if self._icon:
            self._icon_label = QLabel(self)
            self._icon_label.setText(self._icon)
            self._icon_label.setFixedSize(30, 30)
            self._icon_label.setAlignment(Qt.AlignCenter)
            self._icon_label.setStyleSheet("""
                QLabel {
                    background: transparent;
                    color: #6B7280;
                    font-size: 16px;
                }
            """)
            self._icon_label.move(8, 0)
            self._icon_label.setAttribute(Qt.WA_TransparentForMouseEvents)

    def resizeEvent(self, event):
        """Position icon label on resize"""
        super().resizeEvent(event)
        if hasattr(self, '_icon_label') and self._icon_label:
            # Center icon vertically
            y_pos = (self.height() - self._icon_label.height()) // 2
            self._icon_label.move(8, y_pos)

    def _apply_style(self):
        ds = get_design_system()
        c = ds.colors

        # Increased left padding when icon is present to prevent overlap
        # 아이콘이 있을 때 겹침 방지를 위해 왼쪽 패딩 증가
        left_padding = 44 if self._icon else 16

        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: {c.bg_input};
                color: {c.text_primary};
                border: 1px solid {c.border_light};
                border-radius: 10px;
                padding: 12px 16px;
                padding-left: {left_padding}px;
                font-size: 13px;
                font-family: "맑은 고딕", "Malgun Gothic", sans-serif;
            }}
            QLineEdit:focus {{
                border: 2px solid {c.primary};
                background-color: {c.bg_card};
            }}
            QLineEdit:hover {{
                border-color: {c.primary};
            }}
            QLineEdit::placeholder {{
                color: {c.text_disabled};
            }}
        """)


class ModernButton(QPushButton):
    """
    모던 스타일 버튼
    Modern styled button with hover animations
    """

    def __init__(self, text: str, style: str = "primary", parent=None):
        super().__init__(text, parent)
        self._style = style
        self._apply_style()
        self.setCursor(Qt.PointingHandCursor)

    def _apply_style(self):
        ds = get_design_system()
        self.setStyleSheet(ds.get_button_style(self._style))
        self.setMinimumHeight(44)
        self.setFont(QFont("맑은 고딕", 11, QFont.Bold))


class AnimatedCard(QFrame):
    """
    애니메이션 효과가 있는 카드 프레임
    Animated card frame with shadow
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_shadow()
        self._apply_style()

    def _setup_shadow(self):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(10)
        shadow.setColor(QColor(0, 0, 0, 40))
        self.setGraphicsEffect(shadow)

    def _apply_style(self):
        ds = get_design_system()
        c = ds.colors

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {c.bg_card};
                border-radius: 20px;
                border: none;
            }}
        """)


class ModernLoginUi:
    """
    모던 로그인 UI 클래스
    Modern Login UI class

    기존 Ui_LoginWindow의 모든 기능을 보존하면서 모던 UI/UX 적용
    """

    def setupUi(self, LoginWindow: QMainWindow):
        """UI 설정 / Setup UI"""

        ds = get_design_system()
        c = ds.colors

        # 윈도우 기본 설정
        LoginWindow.setObjectName("LoginWindow")
        LoginWindow.resize(800, 540)
        LoginWindow.setMinimumSize(QtCore.QSize(800, 540))
        LoginWindow.setMaximumSize(QtCore.QSize(800, 540))
        LoginWindow.setWindowFlags(Qt.FramelessWindowHint)
        LoginWindow.setAttribute(Qt.WA_TranslucentBackground)

        # 중앙 위젯
        self.centralwidget = QWidget(LoginWindow)
        self.centralwidget.setObjectName("centralwidget")

        # 메인 컨테이너 (그림자 효과를 위한)
        self.mainContainer = AnimatedCard(self.centralwidget)
        self.mainContainer.setGeometry(QtCore.QRect(0, 0, 800, 540))

        # ═══════════════════════════════════════════════════════════════
        # 왼쪽 패널 - 브랜딩 영역 (보라색 그라데이션)
        # ═══════════════════════════════════════════════════════════════
        self.leftPanel = QFrame(self.mainContainer)
        self.leftPanel.setGeometry(QtCore.QRect(0, 0, 320, 540))
        self.leftPanel.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {c.gradient_start},
                    stop:1 {c.gradient_end}
                );
                border-top-left-radius: 20px;
                border-bottom-left-radius: 20px;
            }}
        """)

        # 브랜딩 컨텐츠 레이아웃
        self.brandingLayout = QVBoxLayout(self.leftPanel)
        self.brandingLayout.setContentsMargins(40, 60, 40, 40)
        self.brandingLayout.setSpacing(20)

        # 로고 아이콘
        self.logoLabel = QLabel(self.leftPanel)
        self.logoLabel.setAlignment(Qt.AlignCenter)
        self.logoLabel.setStyleSheet("""
            font-size: 64px;
            background: transparent;
            color: white;
        """)
        self.logoLabel.setText("🚀")
        self.brandingLayout.addWidget(self.logoLabel)

        # 앱 타이틀
        self.appTitle = QLabel("쇼핑 숏폼\n메이커", self.leftPanel)
        self.appTitle.setAlignment(Qt.AlignCenter)
        self.appTitle.setStyleSheet("""
            font-size: 28px;
            font-weight: bold;
            color: white;
            background: transparent;
            line-height: 1.3;
        """)
        self.brandingLayout.addWidget(self.appTitle)

        # 서브타이틀
        self.appSubtitle = QLabel("중국 쇼핑 영상을\n한국어 숏폼으로 자동 변환", self.leftPanel)
        self.appSubtitle.setAlignment(Qt.AlignCenter)
        self.appSubtitle.setStyleSheet("""
            font-size: 13px;
            color: rgba(255, 255, 255, 0.85);
            background: transparent;
            line-height: 1.5;
        """)
        self.brandingLayout.addWidget(self.appSubtitle)

        self.brandingLayout.addStretch()

        # 버전 정보
        self.versionLabel = QLabel("v2.0.0", self.leftPanel)
        self.versionLabel.setAlignment(Qt.AlignCenter)
        self.versionLabel.setStyleSheet("""
            font-size: 11px;
            color: rgba(255, 255, 255, 0.6);
            background: transparent;
        """)
        self.brandingLayout.addWidget(self.versionLabel)

        # ═══════════════════════════════════════════════════════════════
        # 오른쪽 패널 - 로그인 폼
        # ═══════════════════════════════════════════════════════════════
        self.rightPanel = QFrame(self.mainContainer)
        self.rightPanel.setGeometry(QtCore.QRect(320, 0, 480, 540))
        self.rightPanel.setStyleSheet(f"""
            QFrame {{
                background-color: {c.bg_card};
                border-top-right-radius: 20px;
                border-bottom-right-radius: 20px;
            }}
        """)

        # 윈도우 컨트롤 버튼 (최소화, 닫기)
        self.controlsFrame = QFrame(self.rightPanel)
        self.controlsFrame.setGeometry(QtCore.QRect(390, 15, 70, 30))
        self.controlsFrame.setStyleSheet("background: transparent;")

        controlsLayout = QHBoxLayout(self.controlsFrame)
        controlsLayout.setContentsMargins(0, 0, 0, 0)
        controlsLayout.setSpacing(8)

        # 최소화 버튼
        self.minimumButton = QPushButton(self.controlsFrame)
        self.minimumButton.setFixedSize(24, 24)
        self.minimumButton.setCursor(Qt.PointingHandCursor)
        self.minimumButton.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.bg_secondary};
                border: none;
                border-radius: 12px;
                color: {c.text_secondary};
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {c.bg_hover};
            }}
        """)
        self.minimumButton.setText("─")
        self.minimumButton.setObjectName("minimumButton")
        controlsLayout.addWidget(self.minimumButton)

        # 닫기 버튼
        self.exitButton = QPushButton(self.controlsFrame)
        self.exitButton.setFixedSize(24, 24)
        self.exitButton.setCursor(Qt.PointingHandCursor)
        self.exitButton.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.bg_secondary};
                border: none;
                border-radius: 12px;
                color: {c.text_secondary};
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {c.error};
                color: white;
            }}
        """)
        self.exitButton.setText("✕")
        self.exitButton.setObjectName("exitButton")
        controlsLayout.addWidget(self.exitButton)

        # 로그인 폼 컨테이너
        self.formContainer = QWidget(self.rightPanel)
        self.formContainer.setGeometry(QtCore.QRect(60, 100, 360, 380))

        formLayout = QVBoxLayout(self.formContainer)
        formLayout.setContentsMargins(0, 0, 0, 0)
        formLayout.setSpacing(16)

        # 로그인 타이틀
        self.loginTitle = QLabel("로그인")
        self.loginTitle.setStyleSheet(f"""
            font-size: 24px;
            font-weight: bold;
            color: {c.text_primary};
            background: transparent;
        """)
        formLayout.addWidget(self.loginTitle)

        # 서브타이틀
        self.loginSubtitle = QLabel("계정에 로그인하여 시작하세요")
        self.loginSubtitle.setStyleSheet(f"""
            font-size: 13px;
            color: {c.text_secondary};
            background: transparent;
            margin-bottom: 16px;
        """)
        formLayout.addWidget(self.loginSubtitle)

        formLayout.addSpacing(8)

        # 아이디 라벨
        self.label_id = QLabel("아이디")
        self.label_id.setStyleSheet(f"""
            font-size: 12px;
            font-weight: bold;
            color: {c.text_primary};
            background: transparent;
        """)
        self.label_id.setObjectName("label_id")
        formLayout.addWidget(self.label_id)

        # 아이디 입력 필드
        self.idEdit = ModernLineEdit(placeholder="아이디를 입력하세요", icon="👤")
        self.idEdit.setObjectName("idEdit")
        formLayout.addWidget(self.idEdit)

        formLayout.addSpacing(4)

        # 비밀번호 라벨
        self.label_pw = QLabel("비밀번호")
        self.label_pw.setStyleSheet(f"""
            font-size: 12px;
            font-weight: bold;
            color: {c.text_primary};
            background: transparent;
        """)
        self.label_pw.setObjectName("label_pw")
        formLayout.addWidget(self.label_pw)

        # 비밀번호 입력 필드
        self.pwEdit = ModernLineEdit(placeholder="비밀번호를 입력하세요", icon="🔒")
        self.pwEdit.setEchoMode(QLineEdit.Password)
        self.pwEdit.setObjectName("pwEdit")
        formLayout.addWidget(self.pwEdit)

        formLayout.addSpacing(8)

        # ID/PW 저장 체크박스
        self.idpw_checkbox = QCheckBox("ID/PW 저장")
        self.idpw_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {c.text_secondary};
                font-size: 12px;
                background: transparent;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid {c.border_light};
                background-color: {c.bg_card};
            }}
            QCheckBox::indicator:checked {{
                background-color: {c.primary};
                border-color: {c.primary};
            }}
            QCheckBox::indicator:hover {{
                border-color: {c.primary};
            }}
        """)
        self.idpw_checkbox.setObjectName("idpw_checkbox")
        formLayout.addWidget(self.idpw_checkbox)

        formLayout.addSpacing(16)

        # 로그인 버튼
        self.loginButton = ModernButton("로그인", "primary")
        self.loginButton.setMinimumHeight(48)
        self.loginButton.setObjectName("loginButton")
        formLayout.addWidget(self.loginButton)

        formLayout.addSpacing(8)

        # 원격지원 버튼
        self.remoteButton = ModernButton("원격지원", "outline")
        self.remoteButton.setMinimumHeight(44)
        self.remoteButton.setObjectName("remoteButton")
        formLayout.addWidget(self.remoteButton)

        formLayout.addStretch()

        # 하단 정보
        self.footerLabel = QLabel("© 2024 Shopping Shorts Maker")
        self.footerLabel.setAlignment(Qt.AlignCenter)
        self.footerLabel.setStyleSheet(f"""
            font-size: 11px;
            color: {c.text_disabled};
            background: transparent;
        """)
        formLayout.addWidget(self.footerLabel)

        # 중앙 위젯 설정
        LoginWindow.setCentralWidget(self.centralwidget)

        # 시그널 연결을 위한 참조 호환성 (기존 코드와 호환)
        # 기존 idFrame, pwFrame 등은 제거되었지만 입력 필드는 동일한 이름으로 유지

        self.retranslateUi(LoginWindow)
        QtCore.QMetaObject.connectSlotsByName(LoginWindow)

    def retranslateUi(self, LoginWindow):
        """번역 설정 / Translation setup"""
        _translate = QtCore.QCoreApplication.translate
        LoginWindow.setWindowTitle(_translate("LoginWindow", "쇼핑 숏폼 메이커 - 로그인"))
        self.idpw_checkbox.setText(_translate("LoginWindow", "ID/PW 저장"))
        self.loginButton.setText(_translate("LoginWindow", "로그인"))
        self.remoteButton.setText(_translate("LoginWindow", "원격지원"))
        self.label_id.setText(_translate("LoginWindow", "아이디"))
        self.label_pw.setText(_translate("LoginWindow", "비밀번호"))


# 기존 Ui_LoginWindow와의 호환성을 위한 별칭
Ui_LoginWindow = ModernLoginUi
