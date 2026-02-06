# -*- coding: utf-8 -*-
"""
Admin Dashboard Launcher
관리자 대시보드 실행 스크립트

자동 로그인으로 바로 대시보드 실행

=== 동기화 설명 ===
AdminDashboard는 다음과 같이 서버와 동기화됩니다:
1. 5초마다 자동 새로고침 (_start_auto_refresh)
2. 모든 사용자 목록, 구독 요청 등을 API를 통해 가져옴
3. 사용자 관리 작업(승인, 삭제 등)은 즉시 API를 통해 서버에 반영됨

이 방식은 Pull 기반 동기화이며, 실시간 Push는 지원되지 않습니다.
실시간 Push가 필요한 경우 WebSocket 구현이 필요합니다.
"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtCore import QTimer
from ui.components.admin_loading_splash import AdminLoadingSplash

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import logging
from ui.admin_dashboard import WINDOW_WIDTH, WINDOW_HEIGHT # For consistent config if needed

# Setup logging for Admin EXE
def setup_logging():
    log_dir = os.path.join(os.path.expanduser('~'), '.ssmaker', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'admin_dashboard.log')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return log_file

# 기본 설정 - 환경 변수에서 로드 (보안을 위해 하드코딩 지양)
DEFAULT_API_URL = os.getenv(
    "SSMAKER_ADMIN_API_URL",
    "https://ssmaker-auth-api-1049571775048.us-central1.run.app"
)
DEFAULT_ADMIN_KEY = os.getenv("SSMAKER_ADMIN_KEY")

FONT_FAMILY = "맑은 고딕"


def main():
    # Setup logging first
    log_file = setup_logging()
    logging.info("Admin Dashboard starting...")

    app = QApplication(sys.argv)

    # 앱 아이콘 설정
    icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resource", "admin_icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # 폰트 설정
    font = QFont(FONT_FAMILY, 10)
    app.setFont(font)

    # Show splash immediately for instant feedback
    splash = AdminLoadingSplash()
    splash.show_splash()
    splash.update_progress(20, "환경 설정 중...")

    # 환경변수 체크 - 없으면 경고 후 종료 또는 로그인 유도 (현재는 종료)
    if not DEFAULT_ADMIN_KEY:
        logging.warning("SSMAKER_ADMIN_KEY not set. Dashboard access will likely fail.")
        # Fallback removed for security - user must provide key via env
        admin_key = "" 
    else:
        admin_key = DEFAULT_ADMIN_KEY

    splash.update_progress(40, "관리자 권한 확인 중...")

    def load_dashboard():
        """Load dashboard in background with lazy import"""
        try:
            splash.update_progress(60, "대시보드 구성 중...")

            # Lazy import - reduces initial startup time
            from ui.admin_dashboard import AdminDashboard

            splash.update_progress(80, "서버 연결 중...")
            dashboard = AdminDashboard(DEFAULT_API_URL, admin_key)

            splash.update_progress(100, "완료!")

            # Show dashboard and close splash with smooth transition
            dashboard.show()
            QTimer.singleShot(300, splash.close_splash)
            logging.info("Admin Dashboard loaded successfully")
        except Exception as e:
            logging.error(f"Failed to load dashboard: {e}", exc_info=True)
            splash.close_splash()
            # In a real app, show a message box here

    # Load dashboard after 100ms to allow splash to render first
    QTimer.singleShot(100, load_dashboard)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

