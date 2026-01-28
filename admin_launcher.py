# -*- coding: utf-8 -*-
"""
Admin Dashboard Launcher
관리자 대시보드 실행 스크립트

사용법:
    python admin_launcher.py [--url API_URL] [--key ADMIN_API_KEY]

예시:
    python admin_launcher.py
    python admin_launcher.py --url https://ssmaker-auth-xxxxx.run.app --key YOUR_ADMIN_KEY
"""

import sys
import argparse
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

# 기본 설정 (클라이언트와 동일한 URL 사용)
DEFAULT_API_URL = "https://ssmaker-auth-api-1049571775048.us-central1.run.app"
DEFAULT_ADMIN_KEY = ""  # 보안: 실행 시 입력 필요

FONT_FAMILY = "맑은 고딕"


class AdminLoginDialog(QDialog):
    """관리자 로그인 다이얼로그"""

    def __init__(self, default_url: str = "", default_key: str = ""):
        super().__init__()
        self.api_url = ""
        self.admin_key = ""
        self._setup_ui(default_url, default_key)

    def _setup_ui(self, default_url: str, default_key: str):
        self.setWindowTitle("관리자 대시보드 로그인")
        self.setFixedSize(500, 280)
        self.setStyleSheet("background-color: #F9FAFB;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        # 타이틀
        title = QLabel("관리자 대시보드")
        title.setFont(QFont(FONT_FAMILY, 18, QFont.Bold))
        title.setStyleSheet("color: #1F2937;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 설명
        desc = QLabel("API 서버 정보를 입력하세요")
        desc.setFont(QFont(FONT_FAMILY, 10))
        desc.setStyleSheet("color: #6B7280;")
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)

        layout.addSpacing(10)

        # API URL
        url_label = QLabel("API URL:")
        url_label.setFont(QFont(FONT_FAMILY, 11))
        url_label.setStyleSheet("color: #374151;")
        layout.addWidget(url_label)

        self.url_edit = QLineEdit()
        self.url_edit.setFont(QFont(FONT_FAMILY, 11))
        self.url_edit.setText(default_url)
        self.url_edit.setPlaceholderText("https://ssmaker-auth-xxxxx.run.app")
        self.url_edit.setStyleSheet("""
            QLineEdit {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 10px 15px;
            }
            QLineEdit:focus {
                border: 2px solid #e31639;
            }
        """)
        layout.addWidget(self.url_edit)

        # Admin API Key
        key_label = QLabel("Admin API Key:")
        key_label.setFont(QFont(FONT_FAMILY, 11))
        key_label.setStyleSheet("color: #374151;")
        layout.addWidget(key_label)

        self.key_edit = QLineEdit()
        self.key_edit.setFont(QFont(FONT_FAMILY, 11))
        self.key_edit.setText(default_key)
        self.key_edit.setPlaceholderText("X-Admin-API-Key 값")
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setStyleSheet("""
            QLineEdit {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 10px 15px;
            }
            QLineEdit:focus {
                border: 2px solid #e31639;
            }
        """)
        layout.addWidget(self.key_edit)

        layout.addSpacing(10)

        # 버튼
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("취소")
        cancel_btn.setFont(QFont(FONT_FAMILY, 11))
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #374151;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 10px 25px;
            }
            QPushButton:hover {
                background-color: #F3F4F6;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        login_btn = QPushButton("로그인")
        login_btn.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        login_btn.setStyleSheet("""
            QPushButton {
                background-color: #e31639;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 25px;
            }
            QPushButton:hover {
                background-color: #c41231;
            }
        """)
        login_btn.clicked.connect(self._on_login)
        btn_layout.addWidget(login_btn)

        layout.addLayout(btn_layout)

    def _on_login(self):
        url = self.url_edit.text().strip()
        key = self.key_edit.text().strip()

        if not url:
            QMessageBox.warning(self, "입력 오류", "API URL을 입력하세요.")
            return

        if not key:
            QMessageBox.warning(self, "입력 오류", "Admin API Key를 입력하세요.")
            return

        self.api_url = url.rstrip('/')
        self.admin_key = key
        self.accept()

    def get_credentials(self):
        return self.api_url, self.admin_key


def main():
    parser = argparse.ArgumentParser(description="관리자 대시보드 실행")
    parser.add_argument("--url", type=str, default=DEFAULT_API_URL, help="API 서버 URL")
    parser.add_argument("--key", type=str, default=DEFAULT_ADMIN_KEY, help="Admin API Key")
    parser.add_argument("--skip-login", action="store_true", help="로그인 다이얼로그 건너뛰기")
    args = parser.parse_args()

    app = QApplication(sys.argv)

    # 폰트 설정
    font = QFont(FONT_FAMILY, 10)
    app.setFont(font)

    if args.skip_login:
        api_url = args.url
        admin_key = args.key
    else:
        # 로그인 다이얼로그
        login_dialog = AdminLoginDialog(args.url, args.key)
        if login_dialog.exec_() != QDialog.Accepted:
            sys.exit(0)

        api_url, admin_key = login_dialog.get_credentials()

    # 대시보드 실행
    from ui.admin_dashboard import AdminDashboard

    dashboard = AdminDashboard(api_url, admin_key)
    dashboard.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
