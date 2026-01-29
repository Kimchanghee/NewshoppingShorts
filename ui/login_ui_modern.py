# -*- coding: utf-8 -*-
"""
Modern Login UI for Shopping Shorts Maker
쇼핑 숏폼 메이커 모던 로그인 UI

좌표 기반 레이아웃 (setGeometry 사용)
폰트: 맑은 고딕 (Malgun Gothic) 통일
"""

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QFrame, QLabel, QLineEdit,
    QPushButton, QCheckBox, QMessageBox
)
from PyQt5.QtGui import QFont, QIcon, QPixmap


class UsernameCheckWorker(QThread):
    """아이디 중복 확인 백그라운드 워커"""
    finished = pyqtSignal(bool, str)  # (available, message)

    def __init__(self, username: str):
        super().__init__()
        self.username = username

    def run(self):
        import os
        import requests

        try:
            api_url = os.getenv('API_SERVER_URL', 'https://ssmaker-auth-api-1049571775048.us-central1.run.app/')
            resp = requests.get(
                f"{api_url}user/check-username/{self.username}",
                timeout=5
            )

            if resp.status_code == 200:
                data = resp.json()
                self.finished.emit(data.get("available", False), data.get("message", ""))
            else:
                self.finished.emit(False, "확인 실패 - 다시 시도해주세요")
        except Exception:
            self.finished.emit(False, "확인 실패 - 네트워크 오류")

# 공통 폰트 설정
FONT_FAMILY = "맑은 고딕"


class ModernLoginUi:
    """
    모던 로그인 UI 클래스 (좌표 기반)
    Modern Login UI class (coordinate-based layout)
    """

    def setupUi(self, LoginWindow: QMainWindow):
        """UI 설정 / Setup UI"""

        # 윈도우 기본 설정 (700x500 - 레거시와 동일)
        LoginWindow.setObjectName("LoginWindow")
        LoginWindow.resize(700, 500)
        LoginWindow.setMinimumSize(QtCore.QSize(700, 500))
        LoginWindow.setMaximumSize(QtCore.QSize(700, 500))

        # 중앙 위젯
        self.centralwidget = QWidget(LoginWindow)
        self.centralwidget.setObjectName("centralwidget")

        # ═══════════════════════════════════════════════════════════════
        # 왼쪽 패널 - 브랜딩 영역 (레드 그라데이션)
        # ═══════════════════════════════════════════════════════════════
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
        self.leftFrame.setFrameShape(QFrame.StyledPanel)
        self.leftFrame.setObjectName("leftFrame")

        # 로고 아이콘 (텍스트 기반)
        self.logoIcon = QLabel(self.leftFrame)
        self.logoIcon.setGeometry(QtCore.QRect(75, 100, 150, 100))
        self.logoIcon.setAlignment(Qt.AlignCenter)
        self.logoIcon.setFont(QFont(FONT_FAMILY, 60, QFont.Bold))
        self.logoIcon.setStyleSheet("""
            color: white;
            background: rgba(255,255,255,0.15);
            border-radius: 25px;
        """)
        self.logoIcon.setText("SS")
        self.logoIcon.setObjectName("logoIcon")

        # 로고 배지 (MAKER)
        self.logoBadge = QLabel(self.leftFrame)
        self.logoBadge.setGeometry(QtCore.QRect(95, 190, 110, 28))
        self.logoBadge.setAlignment(Qt.AlignCenter)
        self.logoBadge.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        self.logoBadge.setStyleSheet("""
            color: #e31639;
            background: white;
            border-radius: 14px;
            padding: 2px;
        """)
        self.logoBadge.setText("SHORTS MAKER")
        self.logoBadge.setObjectName("logoBadge")

        # 앱 제목
        self.titleLabel = QLabel(self.leftFrame)
        self.titleLabel.setGeometry(QtCore.QRect(0, 240, 300, 60))
        self.titleLabel.setAlignment(Qt.AlignCenter)
        self.titleLabel.setFont(QFont(FONT_FAMILY, 20, QFont.Bold))
        self.titleLabel.setStyleSheet("color: white; background: transparent;")
        self.titleLabel.setText("쇼핑 숏폼 메이커")
        self.titleLabel.setObjectName("titleLabel")

        # 서브 타이틀
        self.subtitleLabel = QLabel(self.leftFrame)
        self.subtitleLabel.setGeometry(QtCore.QRect(0, 305, 300, 50))
        self.subtitleLabel.setAlignment(Qt.AlignCenter)
        self.subtitleLabel.setFont(QFont(FONT_FAMILY, 10))
        self.subtitleLabel.setStyleSheet("color: rgba(255,255,255,0.85); background: transparent;")
        self.subtitleLabel.setText("중국 쇼핑 영상을\n한국어 숏폼으로 자동 변환")
        self.subtitleLabel.setObjectName("subtitleLabel")

        # 기능 아이콘들
        self.featureIcons = QLabel(self.leftFrame)
        self.featureIcons.setGeometry(QtCore.QRect(0, 380, 300, 30))
        self.featureIcons.setAlignment(Qt.AlignCenter)
        self.featureIcons.setFont(QFont(FONT_FAMILY, 9))
        self.featureIcons.setStyleSheet("color: rgba(255,255,255,0.7); background: transparent;")
        self.featureIcons.setText("AI 번역  |  자동 편집  |  숏폼 제작")
        self.featureIcons.setObjectName("featureIcons")

        # 버전 정보
        self.versionLabel = QLabel(self.leftFrame)
        self.versionLabel.setGeometry(QtCore.QRect(0, 460, 300, 30))
        self.versionLabel.setAlignment(Qt.AlignCenter)
        self.versionLabel.setFont(QFont(FONT_FAMILY, 9))
        self.versionLabel.setStyleSheet("color: rgba(255,255,255,0.5); background: transparent;")
        self.versionLabel.setText("v2.0.0")
        self.versionLabel.setObjectName("versionLabel")

        # ═══════════════════════════════════════════════════════════════
        # 오른쪽 패널 - 로그인 폼
        # ═══════════════════════════════════════════════════════════════
        self.rightFrame = QFrame(self.centralwidget)
        self.rightFrame.setGeometry(QtCore.QRect(300, 0, 400, 500))
        self.rightFrame.setStyleSheet("background-color: #ffffff;")
        self.rightFrame.setFrameShape(QFrame.StyledPanel)
        self.rightFrame.setObjectName("rightFrame")

        # 최소화 버튼
        self.minimumButton = QPushButton(self.rightFrame)
        self.minimumButton.setGeometry(QtCore.QRect(330, 10, 25, 25))
        self.minimumButton.setFont(QFont(FONT_FAMILY, 10))
        self.minimumButton.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                border: none;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #E5E7EB;
            }
        """)
        self.minimumButton.setText("")
        icon_min = QIcon()
        icon_min.addPixmap(QPixmap("resource/Minimize_icon.png"), QIcon.Normal, QIcon.On)
        self.minimumButton.setIcon(icon_min)
        self.minimumButton.setIconSize(QtCore.QSize(12, 12))
        self.minimumButton.setObjectName("minimumButton")
        self.minimumButton.setCursor(Qt.PointingHandCursor)

        # 닫기 버튼
        self.exitButton = QPushButton(self.rightFrame)
        self.exitButton.setGeometry(QtCore.QRect(360, 10, 25, 25))
        self.exitButton.setFont(QFont(FONT_FAMILY, 10))
        self.exitButton.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                border: none;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #FEE2E2;
            }
        """)
        self.exitButton.setText("")
        icon_close = QIcon()
        icon_close.addPixmap(QPixmap("resource/Close_icon.png"), QIcon.Normal, QIcon.On)
        self.exitButton.setIcon(icon_close)
        self.exitButton.setIconSize(QtCore.QSize(12, 12))
        self.exitButton.setObjectName("exitButton")
        self.exitButton.setCursor(Qt.PointingHandCursor)

        # 로그인 타이틀
        self.loginTitleLabel = QLabel(self.rightFrame)
        self.loginTitleLabel.setGeometry(QtCore.QRect(50, 70, 300, 40))
        self.loginTitleLabel.setFont(QFont(FONT_FAMILY, 22, QFont.Bold))
        self.loginTitleLabel.setStyleSheet("color: #1F2937; background: transparent;")
        self.loginTitleLabel.setText("로그인")
        self.loginTitleLabel.setObjectName("loginTitleLabel")

        # 로그인 서브타이틀
        self.loginSubtitleLabel = QLabel(self.rightFrame)
        self.loginSubtitleLabel.setGeometry(QtCore.QRect(50, 110, 300, 25))
        self.loginSubtitleLabel.setFont(QFont(FONT_FAMILY, 10))
        self.loginSubtitleLabel.setStyleSheet("color: #6B7280; background: transparent;")
        self.loginSubtitleLabel.setText("계정 정보를 입력해주세요")
        self.loginSubtitleLabel.setObjectName("loginSubtitleLabel")

        # 아이디 라벨
        self.label_id = QLabel(self.rightFrame)
        self.label_id.setGeometry(QtCore.QRect(50, 160, 100, 25))
        self.label_id.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self.label_id.setStyleSheet("color: #374151; background: transparent;")
        self.label_id.setText("아이디")
        self.label_id.setObjectName("label_id")

        # 아이디 입력 필드
        self.idEdit = QLineEdit(self.rightFrame)
        self.idEdit.setGeometry(QtCore.QRect(50, 190, 300, 45))
        self.idEdit.setFont(QFont(FONT_FAMILY, 11))
        self.idEdit.setPlaceholderText("아이디를 입력하세요")
        self.idEdit.setStyleSheet("""
            QLineEdit {
                background-color: #F9FAFB;
                color: #1F2937;
                border: 1px solid #E5E7EB;
                border-radius: 10px;
                padding: 10px 15px;
            }
            QLineEdit:focus {
                border: 2px solid #e31639;
                background-color: #ffffff;
            }
            QLineEdit::placeholder {
                color: #9CA3AF;
            }
        """)
        self.idEdit.setObjectName("idEdit")

        # 비밀번호 라벨
        self.label_pw = QLabel(self.rightFrame)
        self.label_pw.setGeometry(QtCore.QRect(50, 250, 100, 25))
        self.label_pw.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self.label_pw.setStyleSheet("color: #374151; background: transparent;")
        self.label_pw.setText("비밀번호")
        self.label_pw.setObjectName("label_pw")

        # 비밀번호 입력 필드
        self.pwEdit = QLineEdit(self.rightFrame)
        self.pwEdit.setGeometry(QtCore.QRect(50, 280, 300, 45))
        self.pwEdit.setFont(QFont(FONT_FAMILY, 11))
        self.pwEdit.setPlaceholderText("비밀번호를 입력하세요")
        self.pwEdit.setEchoMode(QLineEdit.Password)
        self.pwEdit.setStyleSheet("""
            QLineEdit {
                background-color: #F9FAFB;
                color: #1F2937;
                border: 1px solid #E5E7EB;
                border-radius: 10px;
                padding: 10px 15px;
            }
            QLineEdit:focus {
                border: 2px solid #e31639;
                background-color: #ffffff;
            }
            QLineEdit::placeholder {
                color: #9CA3AF;
            }
        """)
        self.pwEdit.setObjectName("pwEdit")

        # ID/PW 저장 체크박스
        self.idpw_checkbox = QCheckBox(self.rightFrame)
        self.idpw_checkbox.setGeometry(QtCore.QRect(50, 335, 150, 25))
        self.idpw_checkbox.setFont(QFont(FONT_FAMILY, 10))
        self.idpw_checkbox.setStyleSheet("""
            QCheckBox {
                color: #6B7280;
                background: transparent;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid #D1D5DB;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                background-color: #e31639;
                border-color: #e31639;
            }
        """)
        self.idpw_checkbox.setText("ID/PW 저장")
        self.idpw_checkbox.setObjectName("idpw_checkbox")

        # 로그인 버튼
        self.loginButton = QPushButton(self.rightFrame)
        self.loginButton.setGeometry(QtCore.QRect(50, 375, 300, 45))
        self.loginButton.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        self.loginButton.setStyleSheet("""
            QPushButton {
                color: #ffffff;
                background-color: #e31639;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #c41231;
            }
            QPushButton:pressed {
                background-color: #a01028;
            }
        """)
        self.loginButton.setText("로그인")
        self.loginButton.setObjectName("loginButton")
        self.loginButton.setCursor(Qt.PointingHandCursor)

        # 회원가입 요청 버튼 (원격지원 대체)
        self.registerRequestButton = QPushButton(self.rightFrame)
        self.registerRequestButton.setGeometry(QtCore.QRect(50, 430, 300, 45))
        self.registerRequestButton.setFont(QFont(FONT_FAMILY, 11))
        self.registerRequestButton.setStyleSheet("""
            QPushButton {
                color: #e31639;
                background-color: #ffffff;
                border: 2px solid #e31639;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #FEF2F2;
            }
            QPushButton:pressed {
                background-color: #FEE2E2;
            }
        """)
        self.registerRequestButton.setText("회원가입 요청")
        self.registerRequestButton.setObjectName("registerRequestButton")
        self.registerRequestButton.setCursor(Qt.PointingHandCursor)

        # 하단 저작권 표시
        self.copyrightLabel = QLabel(self.rightFrame)
        self.copyrightLabel.setGeometry(QtCore.QRect(50, 480, 300, 15))
        self.copyrightLabel.setAlignment(Qt.AlignCenter)
        self.copyrightLabel.setFont(QFont(FONT_FAMILY, 8))
        self.copyrightLabel.setStyleSheet("color: #9CA3AF; background: transparent;")
        self.copyrightLabel.setText("© 2025 쇼핑 숏폼 메이커")
        self.copyrightLabel.setObjectName("copyrightLabel")

        LoginWindow.setCentralWidget(self.centralwidget)
        self.retranslateUi(LoginWindow)
        QtCore.QMetaObject.connectSlotsByName(LoginWindow)

    def retranslateUi(self, LoginWindow):
        """번역 설정 / Translation setup"""
        _translate = QtCore.QCoreApplication.translate
        LoginWindow.setWindowTitle(_translate("LoginWindow", "쇼핑 숏폼 메이커 - 로그인"))
        self.label_id.setText(_translate("LoginWindow", "아이디"))
        self.label_pw.setText(_translate("LoginWindow", "비밀번호"))
        self.idpw_checkbox.setText(_translate("LoginWindow", "ID/PW 저장"))
        self.loginButton.setText(_translate("LoginWindow", "로그인"))
        self.registerRequestButton.setText(_translate("LoginWindow", "회원가입 요청"))


class RegistrationRequestDialog(QWidget):
    """
    회원가입 요청 다이얼로그 (좌표 기반)
    Registration Request Dialog (coordinate-based layout)
    """

    registrationRequested = pyqtSignal(str, str, str, str)
    backRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._username_available = False  # 아이디 중복 확인 상태
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedSize(400, 650)  # 높이 증가 (580 -> 650)
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
            QPushButton:hover {
                background-color: #E5E7EB;
            }
        """)
        self.backButton.setCursor(Qt.PointingHandCursor)
        self.backButton.clicked.connect(self._on_back)

        # 타이틀
        self.titleLabel = QLabel(self)
        self.titleLabel.setGeometry(QtCore.QRect(30, 65, 340, 35))
        self.titleLabel.setFont(QFont(FONT_FAMILY, 20, QFont.Bold))
        self.titleLabel.setStyleSheet("color: #1F2937; background: transparent;")
        self.titleLabel.setText("회원가입 요청")

        # 서브타이틀
        self.subtitleLabel = QLabel(self)
        self.subtitleLabel.setGeometry(QtCore.QRect(30, 100, 340, 40))
        self.subtitleLabel.setFont(QFont(FONT_FAMILY, 10))
        self.subtitleLabel.setStyleSheet("color: #6B7280; background: transparent;")
        self.subtitleLabel.setText("가입 정보를 입력해주세요.\n가입 후 바로 로그인 가능합니다. (체험판 3회)")

        # 가입자 명 라벨
        self.nameLabel = QLabel(self)
        self.nameLabel.setGeometry(QtCore.QRect(30, 150, 100, 25))
        self.nameLabel.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self.nameLabel.setStyleSheet("color: #374151; background: transparent;")
        self.nameLabel.setText("가입자 명")

        # 가입자 명 입력
        self.nameEdit = QLineEdit(self)
        self.nameEdit.setGeometry(QtCore.QRect(30, 175, 340, 42))
        self.nameEdit.setFont(QFont(FONT_FAMILY, 11))
        self.nameEdit.setPlaceholderText("이름을 입력하세요")
        self._apply_input_style(self.nameEdit)

        # 아이디 라벨
        self.usernameLabel = QLabel(self)
        self.usernameLabel.setGeometry(QtCore.QRect(30, 225, 100, 25))
        self.usernameLabel.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self.usernameLabel.setStyleSheet("color: #374151; background: transparent;")
        self.usernameLabel.setText("아이디")

        # 아이디 입력 (중복확인 버튼 공간 확보)
        self.usernameEdit = QLineEdit(self)
        self.usernameEdit.setGeometry(QtCore.QRect(30, 250, 240, 42))
        self.usernameEdit.setFont(QFont(FONT_FAMILY, 11))
        self.usernameEdit.setPlaceholderText("영문, 숫자, 밑줄(_)만 사용")
        self._apply_input_style(self.usernameEdit)
        self.usernameEdit.textChanged.connect(self._on_username_changed)

        # 중복확인 버튼
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
            QPushButton:hover {
                background-color: #4B5563;
            }
            QPushButton:disabled {
                background-color: #D1D5DB;
                color: #9CA3AF;
            }
        """)
        self.checkUsernameBtn.setCursor(Qt.PointingHandCursor)
        self.checkUsernameBtn.clicked.connect(self._check_username)

        # 아이디 상태 라벨
        self.usernameStatusLabel = QLabel(self)
        self.usernameStatusLabel.setGeometry(QtCore.QRect(30, 294, 340, 18))
        self.usernameStatusLabel.setFont(QFont(FONT_FAMILY, 9))
        self.usernameStatusLabel.setStyleSheet("color: #6B7280; background: transparent;")
        self.usernameStatusLabel.setText("")

        # 비밀번호 라벨
        self.passwordLabel = QLabel(self)
        self.passwordLabel.setGeometry(QtCore.QRect(30, 320, 100, 25))
        self.passwordLabel.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self.passwordLabel.setStyleSheet("color: #374151; background: transparent;")
        self.passwordLabel.setText("비밀번호")

        # 비밀번호 입력
        self.passwordEdit = QLineEdit(self)
        self.passwordEdit.setGeometry(QtCore.QRect(30, 345, 340, 42))
        self.passwordEdit.setFont(QFont(FONT_FAMILY, 11))
        self.passwordEdit.setPlaceholderText("6자 이상 입력")
        self.passwordEdit.setEchoMode(QLineEdit.Password)
        self._apply_input_style(self.passwordEdit)

        # 비밀번호 안내 라벨
        self.passwordHintLabel = QLabel(self)
        self.passwordHintLabel.setGeometry(QtCore.QRect(30, 389, 340, 18))
        self.passwordHintLabel.setFont(QFont(FONT_FAMILY, 9))
        self.passwordHintLabel.setStyleSheet("color: #9CA3AF; background: transparent;")
        self.passwordHintLabel.setText("※ 영문, 숫자 포함 6자 이상 권장")

        # 비밀번호 확인 라벨
        self.passwordConfirmLabel = QLabel(self)
        self.passwordConfirmLabel.setGeometry(QtCore.QRect(30, 410, 120, 25))
        self.passwordConfirmLabel.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self.passwordConfirmLabel.setStyleSheet("color: #374151; background: transparent;")
        self.passwordConfirmLabel.setText("비밀번호 확인")

        # 비밀번호 확인 입력
        self.passwordConfirmEdit = QLineEdit(self)
        self.passwordConfirmEdit.setGeometry(QtCore.QRect(30, 435, 340, 42))
        self.passwordConfirmEdit.setFont(QFont(FONT_FAMILY, 11))
        self.passwordConfirmEdit.setPlaceholderText("비밀번호를 다시 입력")
        self.passwordConfirmEdit.setEchoMode(QLineEdit.Password)
        self._apply_input_style(self.passwordConfirmEdit)

        # 연락처 라벨
        self.contactLabel = QLabel(self)
        self.contactLabel.setGeometry(QtCore.QRect(30, 485, 100, 25))
        self.contactLabel.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        self.contactLabel.setStyleSheet("color: #374151; background: transparent;")
        self.contactLabel.setText("연락처")

        # 연락처 입력
        self.contactEdit = QLineEdit(self)
        self.contactEdit.setGeometry(QtCore.QRect(30, 510, 340, 42))
        self.contactEdit.setFont(QFont(FONT_FAMILY, 11))
        self.contactEdit.setPlaceholderText("010-1234-5678")
        self._apply_input_style(self.contactEdit)

        # 제출 버튼
        self.submitButton = QPushButton(self)
        self.submitButton.setGeometry(QtCore.QRect(30, 565, 340, 45))
        self.submitButton.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        self.submitButton.setText("회원가입")
        self.submitButton.setStyleSheet("""
            QPushButton {
                color: #ffffff;
                background-color: #e31639;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #c41231;
            }
            QPushButton:pressed {
                background-color: #a01028;
            }
        """)
        self.submitButton.setCursor(Qt.PointingHandCursor)
        self.submitButton.clicked.connect(self._on_submit)

    def _apply_input_style(self, widget):
        """입력 필드 스타일 적용"""
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
            QLineEdit::placeholder {
                color: #9CA3AF;
            }
        """)

    def _on_back(self):
        self.backRequested.emit()

    def _on_username_changed(self, text):
        """아이디 입력 변경 시 중복확인 초기화"""
        self._username_available = False
        self.usernameStatusLabel.setText("")
        self.usernameStatusLabel.setStyleSheet("color: #6B7280; background: transparent;")

    def _check_username(self):
        """아이디 중복 확인 (비동기)"""
        import re

        username = self.usernameEdit.text().strip()

        if not username or len(username) < 4:
            self._show_error("아이디는 4자 이상이어야 합니다.")
            return

        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            self._show_error("아이디는 영문, 숫자, 밑줄(_)만 사용할 수 있습니다.")
            return

        # 버튼 비활성화
        self.checkUsernameBtn.setEnabled(False)
        self.checkUsernameBtn.setText("확인중...")
        self.usernameStatusLabel.setText("확인 중...")
        self.usernameStatusLabel.setStyleSheet("color: #6B7280; background: transparent;")

        # 비동기 API 호출
        self._username_worker = UsernameCheckWorker(username)
        self._username_worker.finished.connect(self._on_username_check_done)
        self._username_worker.start()

    def _on_username_check_done(self, available: bool, message: str):
        """아이디 중복 확인 완료 콜백"""
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

    def _on_submit(self):
        import re

        name = self.nameEdit.text().strip()
        username = self.usernameEdit.text().strip()
        password = self.passwordEdit.text()
        password_confirm = self.passwordConfirmEdit.text()
        contact = self.contactEdit.text().strip()

        # 유효성 검사
        if not name or len(name) < 2:
            self._show_error("가입자 명은 2자 이상 입력해주세요.")
            return

        if not username or len(username) < 4:
            self._show_error("아이디는 4자 이상이어야 합니다.")
            return

        if not re.match(r'^[a-zA-Z0-9_]+$', username):
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

        contact_digits = re.sub(r'[^0-9]', '', contact)
        if len(contact_digits) < 10:
            self._show_error("올바른 연락처를 입력해주세요.")
            return

        self.registrationRequested.emit(name, username, password, contact)

    def _show_error(self, message: str):
        msgBox = QMessageBox(self)
        msgBox.setIcon(QMessageBox.Warning)
        msgBox.setWindowTitle("입력 오류")
        msgBox.setText(message)
        msgBox.setStandardButtons(QMessageBox.Ok)
        msgBox.exec_()

    def clear_fields(self):
        self.nameEdit.clear()
        self.usernameEdit.clear()
        self.passwordEdit.clear()
        self.passwordConfirmEdit.clear()
        self.contactEdit.clear()


# 호환성을 위한 별칭
Ui_LoginWindow = ModernLoginUi
