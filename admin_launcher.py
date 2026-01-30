# -*- coding: utf-8 -*-
"""
Admin Dashboard Launcher
관리자 대시보드 실행 스크립트

자동 로그인으로 바로 대시보드 실행
"""

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont

import os

# 기본 설정 - 환경 변수에서 로드 (보안을 위해 하드코딩 지양)
# Load from environment variables (avoid hardcoding for security)
DEFAULT_API_URL = os.getenv("SSMAKER_ADMIN_API_URL", "https://ssmaker-auth-api-1049571775048.us-central1.run.app")
DEFAULT_ADMIN_KEY = os.getenv("SSMAKER_ADMIN_KEY", "a11f0da7958f1fbf125bbe6e1e6b0cd95eac9b62fbff1b2c0e2437737ae8ae3c")

FONT_FAMILY = "맑은 고딕"


def main():
    app = QApplication(sys.argv)

    # 폰트 설정
    font = QFont(FONT_FAMILY, 10)
    app.setFont(font)

    # 대시보드 바로 실행 (로그인 다이얼로그 없이)
    from ui.admin_dashboard import AdminDashboard

    dashboard = AdminDashboard(DEFAULT_API_URL, DEFAULT_ADMIN_KEY)
    dashboard.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
