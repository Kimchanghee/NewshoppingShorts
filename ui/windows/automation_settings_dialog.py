"""
Automation Settings Dialog
쿠팡 파트너스, Linktree, 1688 설정 관리 다이얼로그
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QScrollArea, QWidget
)
from ui.components.custom_dialog import show_info, show_warning, show_error
from PyQt6.QtCore import Qt
from managers.settings_manager import get_settings_manager
from managers.coupang_manager import get_coupang_manager
from managers.sourcing_manager import get_sourcing_manager
from managers.inpock_manager import get_inpock_manager

class AutomationSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = get_settings_manager()
        self.setWindowTitle("자동화 설정")
        self.setMinimumWidth(500)
        self.setMinimumHeight(600)
        
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # 1. Coupang Partners Settings
        coupang_group = QGroupBox("쿠팡 파트너스 설정")
        coupang_layout = QVBoxLayout()
        
        self.coupang_access = QLineEdit()
        self.coupang_access.setPlaceholderText("Access Key 입력")
        self.coupang_secret = QLineEdit()
        self.coupang_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.coupang_secret.setPlaceholderText("Secret Key 입력")
        
        coupang_layout.addWidget(QLabel("Access Key:"))
        coupang_layout.addWidget(self.coupang_access)
        coupang_layout.addWidget(QLabel("Secret Key:"))
        coupang_layout.addWidget(self.coupang_secret)
        
        test_coupang_btn = QPushButton("연동 테스트")
        test_coupang_btn.clicked.connect(self.test_coupang_connection)
        coupang_layout.addWidget(test_coupang_btn)
        
        coupang_group.setLayout(coupang_layout)
        content_layout.addWidget(coupang_group)
        
        # 2. Inpock Link Settings
        inpock_group = QGroupBox("인포크링크 설정")
        inpock_layout = QVBoxLayout()
        
        inpock_info = QLabel("인포크링크는 로그인이 필요합니다.\n'로그인 브라우저 열기'를 클릭하여 수동으로 로그인해주세요.")
        inpock_info.setWordWrap(True)
        inpock_layout.addWidget(inpock_info)
        
        inpock_login_btn = QPushButton("인포크링크 로그인 브라우저 열기")
        inpock_login_btn.clicked.connect(self.open_inpock_login)
        inpock_layout.addWidget(inpock_login_btn)
        
        inpock_group.setLayout(inpock_layout)
        content_layout.addWidget(inpock_group)
        
        # 3. 1688 Login Settings
        sourcing_group = QGroupBox("1688 소싱 설정")
        sourcing_layout = QVBoxLayout()
        
        sourcing_info = QLabel("1688 이미지 검색을 위해 로그인이 필요합니다.\n'로그인 브라우저 열기'를 클릭하여 수동으로 로그인해주세요.")
        sourcing_info.setWordWrap(True)
        sourcing_layout.addWidget(sourcing_info)
        
        login_btn = QPushButton("1688 로그인 브라우저 열기")
        login_btn.clicked.connect(self.open_1688_login)
        sourcing_layout.addWidget(login_btn)
        
        sourcing_group.setLayout(sourcing_layout)
        content_layout.addWidget(sourcing_group)
        
        content_layout.addStretch()
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
        
        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("저장")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("닫기")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def load_settings(self):
        coupang_keys = self.settings.get_coupang_keys()
        self.coupang_access.setText(coupang_keys.get("access_key", ""))
        self.coupang_secret.setText(coupang_keys.get("secret_key", ""))

    def save_settings(self):
        # Save Coupang Keys
        self.settings.set_coupang_keys(
            self.coupang_access.text().strip(),
            self.coupang_secret.text().strip()
        )
        
        # Inpock cookies are saved via manual login, no manual token entry needed
        
        show_info(self, "저장 완료", "설정이 저장되었습니다.")
        self.accept()

    def test_coupang_connection(self):
        # Temporarily save keys to test
        self.settings.set_coupang_keys(
            self.coupang_access.text().strip(),
            self.coupang_secret.text().strip()
        )
        
        manager = get_coupang_manager()
        if manager.check_connection():
            show_info(self, "성공", "쿠팡 파트너스 API 연동 성공!")
        else:
            show_warning(self, "실패", "API 연동 실패. 키를 확인해주세요.")

    def open_1688_login(self):
        try:
            manager = get_sourcing_manager()
            show_info(self, "알림", "브라우저가 열리면 1688에 로그인해주세요.\n로그인이 완료되면 자동으로 인식합니다 (최대 5분 대기).")
            manager.login_manual()
            show_info(self, "완료", "로그인 쿠키가 저장되었습니다.")
        except Exception as e:
            show_error(self, "오류", f"로그인 프로세스 시작 실패: {e}")

    def open_inpock_login(self):
        try:
            manager = get_inpock_manager()
            show_info(self, "알림", "브라우저가 열리면 인포크링크에 로그인해주세요.\n로그인이 완료되면 자동으로 인식합니다 (최대 5분 대기).")
            manager.login_manual()
            show_info(self, "완료", "로그인 쿠키가 저장되었습니다.")
        except Exception as e:
            show_error(self, "오류", f"로그인 프로세스 시작 실패: {e}")
