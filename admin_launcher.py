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
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QTimer
from ui.components.admin_loading_splash import AdminLoadingSplash

# 기본 설정 - 환경 변수에서 로드 (보안을 위해 하드코딩 지양)
# Load from environment variables (avoid hardcoding for security)
DEFAULT_API_URL = os.getenv(
    "SSMAKER_ADMIN_API_URL",
    "https://ssmaker-auth-api-1049571775048.us-central1.run.app"
)
DEFAULT_ADMIN_KEY = os.getenv("SSMAKER_ADMIN_KEY")

FONT_FAMILY = "맑은 고딕"


def main():
    app = QApplication(sys.argv)

    # 폰트 설정
    font = QFont(FONT_FAMILY, 10)
    app.setFont(font)

    # Show splash immediately for instant feedback
    splash = AdminLoadingSplash()
    splash.show_splash()
    splash.update_progress(20, "환경 설정 중...")

    # 환경변수 체크 - 없으면 기본 키 사용
    if not DEFAULT_ADMIN_KEY:
        # 기본 키 사용 (개발용)
        admin_key = "a11f0da7958f1fbf125bbe6e1e6b0cd95eac9b62fbff1b2c0e2437737ae8ae3c"
    else:
        admin_key = DEFAULT_ADMIN_KEY

    splash.update_progress(40, "관리자 권한 확인 중...")

    def load_dashboard():
        """Load dashboard in background with lazy import"""
        splash.update_progress(60, "대시보드 구성 중...")

        # Lazy import - reduces initial startup time
        from ui.admin_dashboard import AdminDashboard

        splash.update_progress(80, "서버 연결 중...")
        dashboard = AdminDashboard(DEFAULT_API_URL, admin_key)

        splash.update_progress(100, "완료!")

        # Show dashboard and close splash with smooth transition
        dashboard.show()
        QTimer.singleShot(300, splash.close_splash)

    # Load dashboard after 100ms to allow splash to render first
    QTimer.singleShot(100, load_dashboard)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

