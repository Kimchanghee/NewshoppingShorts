# -*- coding: utf-8 -*-
"""
Admin Dashboard for Shopping Shorts Maker
관리자 대시보드 - 다크모드, 절대 좌표 배치, 5초 자동 새로고침
"""

import logging
import os
import sys
from dotenv import load_dotenv

# .env 파일 로드 (실행 파일과 같은 디렉토리에 있는 .env 우선)
load_dotenv()

# 프로젝트 루트 경로 추가 (단독 실행 시 필요)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QDialog,
    QAbstractItemView,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QFrame,
    QSizePolicy,
    QApplication,
    QSpinBox,
    QRadioButton,
    QButtonGroup,
)
from PyQt6.QtGui import QFont, QColor, QBrush, QIcon
from datetime import datetime, timedelta, timezone
import requests

# Design System V2
from ui.design_system_v2 import get_design_system, get_color, set_dark_mode

# Extracted dialog components
from ui.admin_dialogs import ExtendDialog, LoginHistoryDialog, RevokeDialog

# Initialize design system and set dark mode
ds = get_design_system()
set_dark_mode(True)

FONT_FAMILY = "Noto Sans KR"
logger = logging.getLogger(__name__)

# 색상 매핑 - DarkColorPalette 사용
def get_status_color(status: str) -> str:
    """상태에 따른 색상 반환"""
    color_map = {
        "primary": get_color("primary"),
        "secondary": get_color("secondary"),
        "success": get_color("success"),
        "warning": get_color("warning"),
        "error": get_color("error"),
        "info": get_color("info"),
        "bg": get_color("background"),
        "card": get_color("surface"),
        "surface_variant": get_color("surface_variant"),
        "text": get_color("text_primary"),
        "text_dim": get_color("text_muted"),
        "border": get_color("border"),
        "border_light": get_color("border_light"),
        "online": get_color("success"),
        "offline": get_color("text_muted"),
    }
    return color_map.get(status, get_color("text_primary"))

# Constants
API_TIMEOUT = 30
REFRESH_INTERVAL_MS = 60000
RETRY_DELAY_MS = 300000


def _styled_msg_box(parent, title: str, message: str, icon_type: str = "info"):
    """
    다크모드에 맞춘 스타일 메시지 박스
    icon_type: 'info', 'warning', 'error', 'question'
    """
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(message)

    if icon_type == "info":
        msg.setIcon(QMessageBox.Icon.Information)
    elif icon_type == "warning":
        msg.setIcon(QMessageBox.Icon.Warning)
    elif icon_type == "error":
        msg.setIcon(QMessageBox.Icon.Critical)
    elif icon_type == "question":
        msg.setIcon(QMessageBox.Icon.Question)

    msg.setStyleSheet(f"""
        QMessageBox {{
            background-color: {get_color('surface')};
            color: {get_color('text_primary')};
        }}
        QMessageBox QLabel {{
            color: {get_color('text_primary')};
            font-size: {ds.typography.size_sm}px;
        }}
        QPushButton {{
            background-color: {get_color('primary')};
            color: white;
            border: none;
            border-radius: {ds.radius.base}px;
            padding: {ds.spacing.space_2}px {ds.spacing.space_5}px;
            font-weight: bold;
            min-width: 80px;
        }}
        QPushButton:hover {{
            background-color: {get_color('secondary')};
        }}
    """)
    return msg


def _styled_question_box(parent, title: str, message: str) -> bool:
    """다크모드 확인 다이얼로그 - Yes/No 반환"""
    msg = _styled_msg_box(parent, title, message, "question")
    msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    msg.setDefaultButton(QMessageBox.StandardButton.No)
    return msg.exec() == QMessageBox.StandardButton.Yes


class ApiWorker(QThread):
    """백그라운드 API 호출"""

    data_ready = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, method: str, url: str, headers: dict = None, data: dict = None):
        super().__init__()
        self.method = method
        self.url = url
        self.headers = headers or {}
        self.data = data

    def run(self):
        try:
            logger.info("[Admin API] %s %s", self.method, self.url)
            if self.method == "GET":
                resp = requests.get(self.url, headers=self.headers, timeout=API_TIMEOUT)
            elif self.method == "POST":
                resp = requests.post(
                    self.url, headers=self.headers, json=self.data, timeout=API_TIMEOUT
                )
            elif self.method == "DELETE":
                resp = requests.delete(self.url, headers=self.headers, timeout=API_TIMEOUT)
            else:
                self.error.emit(f"지원하지 않는 요청 방식입니다: {self.method}")
                return

            logger.info("[Admin API] Response %s: %s", resp.status_code, resp.text[:400])

            if resp.status_code == 429:
                self.error.emit(f"429 {resp.text}")
                return

            if resp.status_code == 200:
                self.data_ready.emit(resp.json())
            elif resp.status_code == 204:
                self.data_ready.emit({"success": True})
            else:
                self.error.emit(f"오류 {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.exception("[Admin API] request failed")
            self.error.emit(str(e))


class AdminDashboard(QMainWindow):
    """관리자 대시보드"""

    def __init__(self, api_base_url: str, admin_api_key: str = None):
        super().__init__()
        self.api_base_url = api_base_url.rstrip("/")

        # Set admin icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resource", "admin_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Environment variable fallback chain: SSMAKER_ADMIN_KEY (preferred) -> ADMIN_API_KEY -> None
        self.admin_api_key = (
            admin_api_key 
            or os.getenv("SSMAKER_ADMIN_KEY") 
            or os.getenv("ADMIN_API_KEY")
        )



        if not self.admin_api_key:
            logger.error("[Admin UI] ADMIN_API_KEY not set - dashboard will not work")

        self.workers = []
        self._rate_limited = False
        self._admin_stats_loaded = False
        logger.info("[Admin UI] Dashboard start | api_base=%s key_set=%s", self.api_base_url, bool(self.admin_api_key))
        self._setup_ui()
        self._load_data()
        self._start_auto_refresh()

    def _cleanup_worker(self, worker):
        """작업 완료된 워커 정리"""
        if worker in self.workers:
            self.workers.remove(worker)
        worker.deleteLater()

    def closeEvent(self, event):
        """윈도우 종료 시 모든 워커 스레드와 타이머를 안전하게 정리"""
        logger.info("[Admin UI] Closing dashboard - cleaning up workers and timers")
        
        # 타이머 중지
        if hasattr(self, "refresh_timer") and self.refresh_timer.isActive():
            self.refresh_timer.stop()
        
        # 모든 실행 중인 워커 스레드 정리
        for worker in self.workers[:]:  # 복사본으로 순회
            if worker.isRunning():
                worker.quit()
                worker.wait(1000)  # 최대 1초 대기
                if worker.isRunning():
                    worker.terminate()  # 강제 종료
                    worker.wait(500)
            worker.deleteLater()
        self.workers.clear()
        
        logger.info("[Admin UI] Cleanup complete - closing window")
        event.accept()

    def _get_headers(self) -> dict:
        return {
            "X-Admin-API-Key": self.admin_api_key,
            "Content-Type": "application/json",
        }

    def _start_auto_refresh(self):
        """2초마다 자동 새로고침"""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._load_data)
        self.refresh_timer.start(REFRESH_INTERVAL_MS)  # 1분마다 자동 새로고침

    def _convert_to_kst(self, utc_str):
        """UTC 문자열을 KST 문자열로 변환 (YYYY-MM-DD HH:mm:ss)"""
        if not utc_str:
            return "-"
        try:
            dt_utc = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
            dt_kst = dt_utc + timedelta(hours=9)
            return dt_kst.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError) as e:
            logger.warning(f"DateTime parsing failed for '{utc_str}': {e}")
            return utc_str

    def _update_last_refresh_time(self):
        """마지막 업데이트 시간 갱신"""
        self.last_update_time = datetime.now()
        time_str = self.last_update_time.strftime("%Y-%m-%d %H:%M:%S")
        self.last_update_label.setText(f"마지막 업데이트: {time_str}")

    def _setup_ui(self):
        self.setWindowTitle("관리자 대시보드")

        # Screen-aware window sizing (fits any monitor)
        screen = QApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            target_w = min(1840, int(available.width() * 0.92))
            target_h = min(900, int(available.height() * 0.92))
            target_w = max(1200, target_w)
            target_h = max(700, target_h)
            self.resize(target_w, target_h)
            self.move(
                available.x() + (available.width() - target_w) // 2,
                available.y() + (available.height() - target_h) // 2,
            )
        else:
            self.resize(1840, 900)

        self.setMinimumSize(1200, 700)
        self.setStyleSheet(f"background-color: {get_color('background')};")

        # Central widget with layout
        self.central = QWidget(self)
        self.setCentralWidget(self.central)

        main_layout = QVBoxLayout(self.central)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(10)

        # --- Top bar (horizontal) ---
        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)

        title = QLabel("관리자 대시보드")
        title.setFont(QFont(FONT_FAMILY, ds.typography.size_2xl, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {get_color('text_primary')};")
        top_bar.addWidget(title)

        top_bar.addStretch()

        self.last_update_label = QLabel("마지막 업데이트: -")
        self.last_update_label.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        self.last_update_label.setStyleSheet(f"color: {get_color('text_muted')};")
        top_bar.addWidget(self.last_update_label)

        refresh_btn = QPushButton("새로고침")
        refresh_btn.setFont(QFont(FONT_FAMILY, ds.typography.size_sm, QFont.Weight.Bold))
        refresh_btn.setFixedSize(120, 36)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {get_color('surface')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border')};
                border-radius: {ds.radius.base}px;
            }}
            QPushButton:hover {{
                background-color: {get_color('border')};
                border: 1px solid {get_color('text_muted')};
            }}
        """)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._load_data)
        top_bar.addWidget(refresh_btn)

        self.connection_label = QLabel("")
        self.connection_label.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        self.connection_label.setStyleSheet(f"color: {get_color('success')};")
        self.connection_label.setMinimumWidth(120)
        top_bar.addWidget(self.connection_label)

        main_layout.addLayout(top_bar)

        # --- Tab Widget ---
        self.tab_widget = QTabWidget()
        self.tab_widget.setFont(QFont(FONT_FAMILY, ds.typography.size_sm, QFont.Weight.Bold))
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                background-color: {get_color('background')};
                border: 1px solid {get_color('border')};
                border-radius: {ds.radius.sm}px;
                top: -1px;
            }}
            QTabBar::tab {{
                background-color: {get_color('surface')};
                color: {get_color('text_muted')};
                border: 1px solid {get_color('border')};
                border-bottom: none;
                border-top-left-radius: {ds.radius.base}px;
                border-top-right-radius: {ds.radius.base}px;
                padding: 10px 30px;
                margin-right: 4px;
                min-width: 160px;
                font-weight: bold;
            }}
            QTabBar::tab:selected {{
                background-color: {get_color('background')};
                color: {get_color('primary')};
                border-bottom: 2px solid {get_color('primary')};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {get_color('surface_variant')};
                color: {get_color('text_primary')};
            }}
        """)

        self.ss_tab = QWidget()
        self.tab_widget.addTab(self.ss_tab, "쇼핑쇼츠메이커")
        self._build_tab_content(self.ss_tab, "ss")

        self.st_tab = QWidget()
        self.tab_widget.addTab(self.st_tab, "쇼츠스레드메이커")
        self._build_tab_content(self.st_tab, "st")

        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        main_layout.addWidget(self.tab_widget)

    def _on_tab_changed(self, index):
        """탭 전환 시 현재 탭의 데이터 갱신"""
        self._load_data()

    def _current_tab_prefix(self):
        """현재 선택된 탭의 prefix 반환"""
        return "st" if self.tab_widget.currentIndex() == 1 else "ss"

    def _build_tab_content(self, parent: QWidget, prefix: str):
        """탭 내부 콘텐츠 구성 (통계카드, 필터, 테이블) - 레이아웃 기반"""
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 통계 카드들
        self._create_stat_cards_for(layout, prefix)
        # 필터/검색 영역
        self._create_filter_area_for(layout, prefix)
        # 테이블
        self._create_tables_for(layout, prefix)

    def _create_stat_cards(self):
        """Legacy - no longer used directly."""
        pass

    def _create_stat_cards_for(self, parent_layout: QVBoxLayout, prefix: str):
        """Create top stat cards for a specific tab - 레이아웃 기반."""
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(ds.spacing.space_4)

        items = [
            ("전체 사용자", get_color("primary"), f"{prefix}_users_label"),
            ("접속 사용자", get_color("success"), f"{prefix}_online_label"),
            ("활성 구독", get_color("secondary"), f"{prefix}_active_sub_label"),
            ("총 작업 수", get_color("info"), f"{prefix}_total_work_used_label"),
        ]

        for title, color, attr_name in items:
            card, value_lbl = self._create_stat_card(title, color)
            setattr(self, attr_name, value_lbl)
            cards_layout.addWidget(card)

        parent_layout.addLayout(cards_layout)

    def _create_stat_card(self, title: str, accent_color: str):
        """통계 카드 위젯 생성 (레이아웃 기반)"""
        card = QFrame()
        card.setFixedHeight(80)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {get_color('surface')};
                border-radius: {ds.radius.md}px;
                border-left: 4px solid {accent_color};
            }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(15, 10, 15, 10)
        card_layout.setSpacing(2)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs))
        title_lbl.setStyleSheet(f"color: {get_color('text_muted')}; background: transparent; border: none;")
        card_layout.addWidget(title_lbl)

        value_lbl = QLabel("0")
        value_lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_xl, QFont.Weight.Bold))
        value_lbl.setStyleSheet(f"color: {get_color('text_primary')}; background: transparent; border: none;")
        card_layout.addWidget(value_lbl)

        return card, value_lbl

    def _create_card(self, x, y, w, h, title, color):
        """카드 생성 (legacy)"""
        self._create_card_on(self.central, x, y, w, h, title, color)

    def _create_card_on(self, parent, x, y, w, h, title, color):
        """카드 생성 (지정 부모)"""
        card = QWidget(parent)
        card.setGeometry(x, y, w, h)
        card.setStyleSheet(f"""
            background-color: {get_color('surface')};
            border-radius: {ds.radius.md}px;
            border-left: 4px solid {color};
        """)

        title_lbl = QLabel(title, card)
        title_lbl.setGeometry(15, 10, w - 30, 20)
        title_lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs ))
        title_lbl.setStyleSheet(f"color: {get_color('text_muted')}; background: transparent;")

    def _get_value_label(self, x, y, w, h) -> QLabel:
        """값 라벨 생성 및 반환 (legacy)"""
        return self._get_value_label_on(self.central, x, y, w, h)

    def _get_value_label_on(self, parent, x, y, w, h) -> QLabel:
        """값 라벨 생성 및 반환 (지정 부모)"""
        lbl = QLabel("0", parent)
        lbl.setGeometry(x + 15, y + 35, w - 30, 40)
        lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_xl , QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {get_color('text_primary')}; background: transparent;")
        return lbl

    def _create_filter_area(self):
        """Legacy - no longer used directly."""
        pass

    def _create_filter_area_for(self, parent_layout: QVBoxLayout, prefix: str):
        """필터/검색 영역 생성 (탭별) - 레이아웃 기반"""
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)

        search_label = QLabel("아이디 검색:")
        search_label.setFont(QFont(FONT_FAMILY, ds.typography.size_sm))
        search_label.setStyleSheet(f"color: {get_color('text_primary')};")
        filter_layout.addWidget(search_label)

        search_edit = QLineEdit()
        search_edit.setFixedHeight(36)
        search_edit.setMaximumWidth(250)
        search_edit.setFont(QFont(FONT_FAMILY, ds.typography.size_sm))
        search_edit.setPlaceholderText("검색어 입력...")
        search_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {get_color('surface')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border')};
                border-radius: {ds.radius.base}px;
                padding: 5px {ds.spacing.space_4}px;
            }}
            QLineEdit::placeholder {{
                color: {get_color('text_muted')};
            }}
        """)
        search_edit.textChanged.connect(self._on_search_changed)
        setattr(self, f"{prefix}_search_edit", search_edit)
        if prefix == "ss":
            self.search_edit = search_edit
        filter_layout.addWidget(search_edit)

        filter_layout.addStretch()

        parent_layout.addLayout(filter_layout)

    def _create_tables(self):
        """Legacy - no longer used directly."""
        pass

    def _create_tables_for(self, parent_layout: QVBoxLayout, prefix: str):
        """테이블 생성 (탭별) - 레이아웃 기반"""
        table = QTableWidget()
        table.setColumnCount(16)
        table.setHorizontalHeaderLabels(
            [
                "번호",
                "이름",
                "아이디",
                "비밀번호",
                "연락처",
                "이메일",
                "유형",
                "구독만료",
                "무료 횟수",
                "로그인",
                "마지막 로그인",
                "아이피",
                "접속",
                "현재작업",
                "버전",
                "작업",
            ]
        )
        self._style_table(
            table, [40, 80, 100, 80, 115, 160, 70, 125, 75, 55, 130, 110, 80, 90, 60, 310]
        )
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        setattr(self, f"{prefix}_users_table", table)
        if prefix == "ss":
            self.users_table = table

        parent_layout.addWidget(table, stretch=1)

    def _style_table(self, table: QTableWidget, widths: list):
        """테이블 스타일"""
        table.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs ))
        table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {get_color('surface')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border')};
                border-radius: {ds.radius.sm}px;
                gridline-color: {get_color('border')};
                selection-background-color: {get_color('primary')};
                selection-color: {get_color('text_primary')};
            }}
            QTableWidget::item {{
                padding: {ds.spacing.space_1}px {ds.spacing.space_2}px;
                border-bottom: 1px solid {get_color('border')};
            }}
            QHeaderView::section {{
                background-color: {get_color('background')};
                color: {get_color('text_muted')};
                font-weight: bold;
                padding: {ds.spacing.space_2}px;
                border: none;
                border-bottom: 1px solid {get_color('border')};
                text-transform: uppercase;
            }}
            QScrollBar:vertical {{
                background-color: {get_color('background')};
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {get_color('border')};
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        table.setAlternatingRowColors(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(50)

        header = table.horizontalHeader()
        for i, w in enumerate(widths):
            if i == len(widths) - 1:
                # Last column (작업) stretches to fill remaining space
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                table.setColumnWidth(i, w)

    def _load_data(self):
        """데이터 로드 - 현재 활성 탭의 데이터만 로드"""
        if not self.admin_api_key:
            self.connection_label.setText("관리자 키가 없습니다")
            self.connection_label.setStyleSheet(f"color: {get_color('warning')};")
            return

        if self._rate_limited:
            self.connection_label.setText("요청 제한 중 - 대기 후 재시도")
            self.connection_label.setStyleSheet(f"color: {get_color('warning')};")
            return
        self.connection_label.setText("연결 중...")
        self.connection_label.setStyleSheet(f"color: {get_color('warning')};")
        prefix = self._current_tab_prefix()
        logger.info("[Admin UI] Load data start (tab: %s)", prefix)
        self._admin_stats_loaded = False
        self._load_admin_stats(prefix)
        self._load_users(prefix)
        self._update_last_refresh_time()

    def _load_users(self, prefix: str = "ss"):
        """사용자 목록 로드"""
        search_edit = getattr(self, f"{prefix}_search_edit", None)
        search = search_edit.text().strip() if search_edit else ""
        # prefix -> program_type 매핑
        program_type = "stmaker" if prefix == "st" else "ssmaker"
        url = f"{self.api_base_url}/user/admin/users?program_type={program_type}"
        if search:
            url += f"&search={search}"

        logger.info("[Admin UI] Load users | tab=%s program=%s search=%s", prefix, program_type, search)
        worker = ApiWorker("GET", url, self._get_headers())
        worker.data_ready.connect(lambda data: self._on_users_loaded(data, prefix))
        worker.error.connect(self._on_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self.workers.append(worker)
        worker.start()

    def _on_users_loaded(self, data: dict, prefix: str = "ss"):
        """Handle loaded user list for the specified tab."""
        logger.info("[Admin UI] Users loaded (%d) for tab %s", len(data.get("users", [])), prefix)
        items = data.get("users", [])
        total_count = data.get("total", len(items))
        table = getattr(self, f"{prefix}_users_table", self.users_table)
        table.setRowCount(len(items))
        self.connection_label.setText("연결됨")
        self.connection_label.setStyleSheet(f"color: {get_color('success')};")

        online_count = 0
        active_sub_count = 0
        fallback_total_work_used = 0
        now = datetime.now(timezone.utc)

        for row, user in enumerate(items):
            table.setRowHeight(row, 50)

            # 0: ID
            self._set_cell(table, row, 0, str(user.get("id", "")))
            # 1: Name
            self._set_cell(table, row, 1, user.get("name") or "-")
            # 2: Username
            self._set_cell(table, row, 2, user.get("username", ""))
            # 3: Password (has_password flag from API)
            has_pw = user.get("has_password", False)
            self._set_cell(table, row, 3, "설정됨" if has_pw else "미설정",
                           get_color("success") if has_pw else get_color("warning"))
            # 4: Phone
            self._set_cell(table, row, 4, user.get("phone") or "-")
            # 5: Email
            self._set_cell(table, row, 5, user.get("email") or "-")

            # 6: Type
            utype = user.get("user_type", "trial")
            utype_text = {
                "trial": "무료 계정",
                "subscriber": "구독자",
                "admin": "관리자",
            }.get(utype, utype)
            utype_color = {
                "trial": get_color("text_muted"),
                "subscriber": get_color("primary"),
                "admin": get_color("warning"),
            }.get(utype, get_color("text_primary"))
            self._set_cell(table, row, 6, utype_text, utype_color)

            # 7: Subscription Expires
            expires_utc = user.get("subscription_expires_at")
            
            if utype == "trial":
                expires_str = "-"
                color = get_color("text_muted")
            else:
                expires_str = self._convert_to_kst(expires_utc) if expires_utc else "-"
                color = get_color("text_muted") if not expires_utc else get_color("text_primary")
                if expires_utc:
                    try:
                        dt = datetime.fromisoformat(expires_utc.replace("Z", "+00:00"))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        if dt < now:
                            color = get_color("error")
                        elif (dt - now).days <= 10:
                            color = get_color("error")
                        else:
                            color = get_color("success")
                            active_sub_count += 1
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Subscription expiry parsing failed for user: {e}")
            
            self._set_cell(table, row, 7, expires_str, color)

            # 8: Work usage
            raw_work_count = user.get("work_count", -1)
            raw_work_used = user.get("work_used", 0)
            try:
                work_count = int(raw_work_count)
            except (TypeError, ValueError):
                work_count = -1
            try:
                work_used = max(int(raw_work_used), 0)
            except (TypeError, ValueError):
                work_used = 0

            fallback_total_work_used += work_used
            if work_count == -1:
                work_str = f"무제한 | {work_used}"
                color = get_color("success")
            else:
                remaining = max(0, work_count - work_used)
                work_str = f"{remaining}/{work_count} | {work_used}"
                color = get_color("warning") if remaining <= 10 else get_color("text_primary")
            self._set_cell(table, row, 8, work_str, color)

            # 9: Login Count
            self._set_cell(table, row, 9, str(user.get("login_count", 0)))

            # 10: Last Login
            last_login = self._convert_to_kst(user.get("last_login_at"))
            self._set_cell(table, row, 10, last_login)

            # 11: IP
            self._set_cell(table, row, 11, user.get("last_login_ip", "-"))

            # 12: Online Status
            is_online = user.get("is_online", False)
            last_heartbeat_str = user.get("last_heartbeat")
            
            if is_online and last_heartbeat_str:
                try:
                    hb_dt = datetime.fromisoformat(last_heartbeat_str.replace("Z", "+00:00"))
                    if hb_dt.tzinfo is None:
                        hb_dt = hb_dt.replace(tzinfo=timezone.utc)
                    if (now - hb_dt).total_seconds() > 90:
                        is_online = False
                except Exception:
                    pass
            elif is_online and not last_heartbeat_str:
                is_online = False

            if is_online:
                online_count += 1

            self._set_cell(
                table, row, 12,
                "온라인" if is_online else "오프라인",
                get_color("success") if is_online else get_color("text_muted"),
            )

            # 13: Current Task
            self._set_cell(table, row, 13, user.get("current_task", "-"))

            # 14: App Version
            app_version = user.get("app_version") or "-"
            version_color = (
                get_color("text_muted")
                if app_version in ("-", "unknown")
                else get_color("success")
            )
            self._set_cell(table, row, 14, app_version, version_color)

            # 15: Actions
            widget = self._create_user_actions(
                user.get("id"),
                user.get("username"),
                row,
                user.get("has_password", False),
                user_type=utype,
            )
            table.setCellWidget(row, 15, widget)

        if not self._admin_stats_loaded:
            users_lbl = getattr(self, f"{prefix}_users_label", None)
            online_lbl = getattr(self, f"{prefix}_online_label", None)
            active_sub_lbl = getattr(self, f"{prefix}_active_sub_label", None)
            total_work_lbl = getattr(self, f"{prefix}_total_work_used_label", None)
            if users_lbl:
                users_lbl.setText(str(total_count))
            if online_lbl:
                online_lbl.setText(str(online_count))
            if active_sub_lbl:
                active_sub_lbl.setText(str(active_sub_count))
            if total_work_lbl:
                total_work_lbl.setText(str(fallback_total_work_used))

    def _load_admin_stats(self, prefix: str = "ss"):
        """Load admin summary stats."""
        program_type = "stmaker" if prefix == "st" else "ssmaker"
        url = f"{self.api_base_url}/user/admin/stats?program_type={program_type}"
        worker = ApiWorker("GET", url, self._get_headers())
        worker.data_ready.connect(lambda data: self._on_admin_stats_loaded(data, prefix))
        worker.error.connect(
            lambda e: logger.warning("[Admin UI] Failed to load admin stats: %s", e)
        )
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self.workers.append(worker)
        worker.start()

    def _on_admin_stats_loaded(self, data: dict, prefix: str = "ss"):
        """Update stat cards from admin stats response."""
        users = data.get("users", {}) or {}
        work = data.get("work", {}) or {}

        users_lbl = getattr(self, f"{prefix}_users_label", None)
        online_lbl = getattr(self, f"{prefix}_online_label", None)
        active_sub_lbl = getattr(self, f"{prefix}_active_sub_label", None)
        total_work_lbl = getattr(self, f"{prefix}_total_work_used_label", None)

        if users_lbl:
            users_lbl.setText(str(users.get("total", 0)))
        if online_lbl:
            online_lbl.setText(str(users.get("online", users.get("active", 0))))
        if active_sub_lbl:
            active_sub_lbl.setText(str(users.get("with_subscription", 0)))
        if total_work_lbl:
            total_work_lbl.setText(str(work.get("total_used", 0)))

            avg_used = work.get("avg_used_per_user", 0)
            users_with_work = work.get("users_with_work", 0)
            in_progress_users = work.get("in_progress_users", 0)
            total_work_lbl.setToolTip(
                f"Users with work history: {users_with_work}\n"
                f"Users currently working: {in_progress_users}\n"
                f"Average work per user: {avg_used}"
            )
        self._admin_stats_loaded = True

    def _set_cell(self, table, row, col, text, color=None):
        """셀 설정"""
        if text is None:
            text = ""
        item = QTableWidgetItem(str(text))
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        # 항상 텍스트 색상 설정 (기본: 흰색)
        item.setForeground(QBrush(QColor(color if color else get_color("text_primary"))))
        # 행 번호에 따른 배경색 설정 (교차 색상)
        bg_color = get_color("surface_variant") if row % 2 == 1 else get_color("surface")
        item.setBackground(QBrush(QColor(bg_color)))
        table.setItem(row, col, item)

    def _create_user_actions(
        self, user_id, username, row: int = 0, has_password: bool = False,
        user_type: str = "trial"
    ) -> QWidget:
        """사용자 작업 버튼 - 미니멀 디자인"""
        widget = QWidget()
        # Widen container to fit 6 buttons
        widget.setMinimumSize(330, 40)
        # 투명 배경 (테이블 행 색상 통과)
        widget.setStyleSheet("background-color: transparent;")

        layout = QWidget(widget)
        layout.setGeometry(0, 0, 330, 40)

        # Style definition for action buttons
        # Base style: Transparent with border and colored text on hover
        base_style = """
            QPushButton {
                background-color: transparent;
                border: 1px solid %s;
                border-radius: %dpx;
                color: %s;
                font-family: "Segoe UI", "맑은 고딕";
                font-size: %dpx;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: %s;
                color: #ffffff;
            }
        """

        x_pos = 0

        # 1. PW Check (Button)
        pw_btn = QPushButton("PW", widget)
        pw_btn.setGeometry(x_pos, 5, 40, 30)
        pw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        c_norm = get_color("text_muted")
        c_hov = get_color("border")
        pw_btn.setStyleSheet(base_style % (c_norm, ds.radius.sm, c_norm, ds.typography.size_2xs , c_hov))
        pw_btn.clicked.connect(lambda: self._show_password_info(username, has_password))
        x_pos += 45

        # 2. Extension (Blue/Info)
        ext_btn = QPushButton("연장", widget)
        ext_btn.setGeometry(x_pos, 5, 50, 30)
        ext_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        c_norm = get_color("info")
        ext_btn.setStyleSheet(base_style % (c_norm, ds.radius.sm, c_norm, ds.typography.size_2xs , c_norm))
        ext_btn.clicked.connect(lambda: self._extend_subscription(user_id, username))
        x_pos += 55

        # 3. Revoke Subscription (Orange) - 구독자만 표시
        if user_type == "subscriber":
            revoke_btn = QPushButton("박탈", widget)
            revoke_btn.setGeometry(x_pos, 5, 50, 30)
            revoke_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            c_norm = "#FF6B35"
            revoke_btn.setStyleSheet(base_style % (c_norm, ds.radius.sm, c_norm, ds.typography.size_2xs , c_norm))
            revoke_btn.clicked.connect(lambda: self._revoke_subscription(user_id, username))
            x_pos += 55

        # 4. Log (Yellow/Warning)
        stat_btn = QPushButton("로그", widget)
        stat_btn.setGeometry(x_pos, 5, 50, 30)
        stat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        c_norm = get_color("warning")
        stat_btn.setStyleSheet(base_style % (c_norm, ds.radius.sm, c_norm, ds.typography.size_2xs , c_norm))
        stat_btn.clicked.connect(lambda: self._show_user_logs(user_id, username))
        x_pos += 55

        # 5. History (Gray/Info)
        hist_btn = QPushButton("이력", widget)
        hist_btn.setGeometry(x_pos, 5, 50, 30)
        hist_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        c_norm = get_color("text_primary")
        c_hov = get_color("surface_variant")
        hist_btn.setStyleSheet(base_style % (get_color("border"), ds.radius.sm, c_norm, ds.typography.size_2xs , c_hov))
        hist_btn.clicked.connect(lambda: self._show_login_history(user_id, username))
        x_pos += 55

        # 6. Delete (Red/Danger)
        del_btn = QPushButton("삭제", widget)
        del_btn.setGeometry(x_pos, 5, 50, 30)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        c_norm = get_color("error")
        del_btn.setStyleSheet(base_style % (c_norm, ds.radius.sm, c_norm, ds.typography.size_2xs , c_norm))
        del_btn.clicked.connect(lambda: self._delete_user(user_id, username))

        return widget

    def _show_password_info(self, username, has_password: bool):
        """비밀번호 설정 상태 표시 (보안 정책: 해시값 미노출)"""
        status_text = "설정됨 (bcrypt 해시 저장)" if has_password else "미설정"
        status_color = get_color("success") if has_password else get_color("warning")

        dialog = QDialog(self)
        dialog.setWindowTitle(f"'{username}' 비밀번호 정보")
        dialog.setFixedSize(500, 220)
        dialog.setStyleSheet(f"background-color: {get_color('surface')};")

        title_lbl = QLabel(f"'{username}' 비밀번호 상태:", dialog)
        title_lbl.setGeometry(30, 25, 440, 25)
        title_lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {get_color('text_primary')};")

        status_lbl = QLabel(status_text, dialog)
        status_lbl.setGeometry(30, 65, 440, 30)
        status_lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_md // 2, QFont.Weight.Bold))
        status_lbl.setStyleSheet(f"color: {status_color};")

        note_lbl = QLabel(
            "※ 보안 정책에 따라 비밀번호 해시값은 API에서 제공되지 않습니다.\n"
            "※ 비밀번호는 bcrypt 해시로 안전하게 저장되며, 원본 복구는 불가합니다.",
            dialog,
        )
        note_lbl.setGeometry(30, 110, 440, 40)
        note_lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs // 2))
        note_lbl.setStyleSheet(f"color: {get_color('text_muted')};")

        close_btn = QPushButton("닫기", dialog)
        close_btn.setGeometry(370, 170, 100, 35)
        close_btn.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2))
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {get_color('background')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border')};
                border-radius: {ds.radius.base}px;
            }}
            QPushButton:hover {{
                background-color: {get_color('border')};
            }}
        """)
        close_btn.clicked.connect(dialog.accept)

        dialog.exec()

    def _on_search_changed(self, text):
        prefix = self._current_tab_prefix()
        logger.info("[Admin UI] Search changed (tab: %s): %s", prefix, text)
        self._load_users(prefix)

    def _extend_subscription(self, user_id, username):
        """구독 연장"""
        logger.info("[Admin UI] Extend clicked | user_id=%s username=%s", user_id, username)
        dialog = ExtendDialog(username, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            days = dialog.get_days()
            url = f"{self.api_base_url}/user/admin/users/{user_id}/extend"
            data = {"days": days}
            logger.info("[Admin UI] Extend request | user_id=%s days=%s", user_id, days)
            worker = ApiWorker("POST", url, self._get_headers(), data)
            worker.data_ready.connect(lambda d: self._on_action_done("구독 연장", d))
            worker.error.connect(self._on_error)
            worker.finished.connect(lambda: self._cleanup_worker(worker))
            self.workers.append(worker)
            worker.start()

    def _revoke_subscription(self, user_id, username):
        """구독 박탈 또는 기간 조정"""
        logger.info("[Admin UI] Revoke clicked | user_id=%s username=%s", user_id, username)
        dialog = RevokeDialog(username, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        mode = dialog.get_mode()  # "full" or "reduce"

        if mode == "full":
            # 완전 박탈
            url = f"{self.api_base_url}/user/admin/users/{user_id}/revoke-subscription"
            worker = ApiWorker("POST", url, self._get_headers(), {})
            worker.data_ready.connect(lambda d: self._on_action_done("구독 박탈", d))
            worker.error.connect(self._on_error)
            worker.finished.connect(lambda: self._cleanup_worker(worker))
            self.workers.append(worker)
            worker.start()
        else:
            # 기간 축소
            days = dialog.get_reduce_days()
            url = f"{self.api_base_url}/user/admin/users/{user_id}/reduce-subscription"
            data = {"days": days}
            worker = ApiWorker("POST", url, self._get_headers(), data)
            worker.data_ready.connect(lambda d: self._on_action_done("구독 기간 축소", d))
            worker.error.connect(self._on_error)
            worker.finished.connect(lambda: self._cleanup_worker(worker))
            self.workers.append(worker)
            worker.start()

    def _toggle_user(self, user_id, username):
        """사용자 상태 토글"""
        logger.info("[Admin UI] Toggle user | user_id=%s username=%s", user_id, username)
        if not _styled_question_box(
            self, "상태 변경", f"'{username}' 사용자의 상태를 변경하시겠습니까?"
        ):
            return

        url = f"{self.api_base_url}/user/admin/users/{user_id}/toggle-active"
        worker = ApiWorker("POST", url, self._get_headers(), {})
        worker.data_ready.connect(lambda d: self._on_action_done("상태 변경", d))
        worker.error.connect(self._on_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self.workers.append(worker)
        worker.start()

    def _show_user_logs(self, user_id, username):
        """사용자 로그 보기 (24시간)"""
        logger.info("[Admin UI] Show logs | user_id=%s username=%s", user_id, username)
        url = f"{self.api_base_url}/user/admin/users/{user_id}/logs"
        worker = ApiWorker("GET", url, self._get_headers())
        worker.data_ready.connect(lambda d: self._show_logs_dialog(username, d))
        worker.error.connect(self._on_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self.workers.append(worker)
        worker.start()

    def _show_logs_dialog(self, username: str, data: dict):
        """로그 목록 다이얼로그 표시"""
        logs = data.get("logs", [])

        if not logs:
            msg = _styled_msg_box(self, "활동 로그", f"'{username}' 사용자의 최근 24시간 활동 로그가 없습니다.", "info")
            msg.exec()
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"'{username}' 활동 로그 (최근 24시간)")
        dialog.setFixedSize(900, 600)
        dialog.setStyleSheet(f"background-color: {get_color('surface')}; color: {get_color('text_primary')};")
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        # Title
        title_lbl = QLabel(f"'{username}' 최근 활동 로그 ({len(logs)}건)", dialog)
        title_lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_md, QFont.Weight.Bold))
        layout.addWidget(title_lbl)

        # Table
        table = QTableWidget(dialog)
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["시간", "레벨", "동작", "내용"])
        
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # Time
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) # Level
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Action
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)          # Content
        
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setWordWrap(True)  # Enable word wrap for long content
        table.setStyleSheet(f"""
            QTableWidget {{
                gridline-color: {get_color('border')};
                background-color: {get_color('surface')};
                alternate-background-color: {get_color('surface_variant')};
            }}
            QHeaderView::section {{
                background-color: {get_color('surface_variant')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border')};
                padding: 4px;
            }}
        """)
        
        table.setRowCount(len(logs))
        
        # 작업 로그 액션별 색상 매핑
        action_color_map = {
            "작업 진행": "#FACC15",      # 노란색 - 단계 시작
            "작업 완료": "#22C55E",      # 초록색 - 단계 완료
            "작업 오류": "#EF4444",      # 빨간색 - 단계 오류
            "영상 처리 시작": "#60A5FA", # 파란색 - 영상 시작
            "영상 처리 완료": "#22C55E", # 초록색 - 영상 완료
            "영상 생성 시작": "#60A5FA", # 파란색 - 배치 시작
            "영상 생성 종료": "#818CF8", # 보라색 - 배치 종료
            "영상 생성 완료": "#22C55E", # 초록색
        }
        level_color_map = {
            "ERROR": get_color("error"),
            "WARN": get_color("warning"),
            "WARNING": get_color("warning"),
        }

        for row, log in enumerate(logs):
            created = log.get("created_at", "")
            try:
                # Assuming created_at is ISO format
                if created:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    # Convert to KST (+09:00)
                    kst = timezone(timedelta(hours=9))
                    created = dt.astimezone(kst).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

            action = log.get("action", "")
            level = log.get("level", "INFO")
            action_color = action_color_map.get(action)
            level_color = level_color_map.get(level.upper())

            self._set_cell(table, row, 0, created)
            self._set_cell(table, row, 1, level, level_color)
            self._set_cell(table, row, 2, action, action_color)

            # Content items might involve newlines, so usage of setCellWidget or careful text handling
            content_item = QTableWidgetItem(log.get("content", "") or "")
            content_color = action_color if action_color else get_color("text_primary")
            content_item.setForeground(QBrush(QColor(content_color)))
            table.setItem(row, 3, content_item)
            
        layout.addWidget(table)
        
        # Close button
        btn_layout = QVBoxLayout() # Just to align right? No, simple close button
        close_btn = QPushButton("닫기", dialog)
        close_btn.setFixedSize(100, 35)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {get_color('background')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border')};
                border-radius: {ds.radius.base}px;
            }}
            QPushButton:hover {{
                background-color: {get_color('border')};
            }}
        """)
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        dialog.exec()

    def _show_login_history(self, user_id, username):
        """로그인 이력 보기"""
        dialog = LoginHistoryDialog(
            username, user_id, self.api_base_url, self._get_headers(), self
        )
        dialog.exec()

    def _delete_user(self, user_id, username):
        """사용자 삭제"""
        logger.info("[Admin UI] Delete user clicked | user_id=%s username=%s", user_id, username)
        if not _styled_question_box(
            self,
            "사용자 삭제",
            f"'{username}' 사용자를 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.",
        ):
            return

        url = f"{self.api_base_url}/user/admin/users/{user_id}"
        worker = ApiWorker("DELETE", url, self._get_headers())
        worker.data_ready.connect(lambda d: self._on_action_done("삭제", d))
        worker.error.connect(lambda e: self._on_action_error("삭제", e))
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self.workers.append(worker)
        worker.start()

    def _on_action_error(self, action, error):
        """작업 실패 시 에러 메시지 표시"""
        self._on_error(error)
        msg = _styled_msg_box(self, "오류", f"{action} 실패: {error}", "error")
        msg.exec()
        self._load_data()

    def _on_action_done(self, action, data):
        if data.get("success"):
            msg = _styled_msg_box(
                self, "완료", f"{action} 처리가 완료되었습니다.", "info"
            )
            msg.exec()
            self._load_data()
        else:
            msg = _styled_msg_box(
                self,
                "오류",
                data.get("message", "처리 중 오류가 발생했습니다."),
                "warning",
            )
            msg.exec()

    def _on_error(self, error):
        self.connection_label.setText("연결 오류")
        self.connection_label.setStyleSheet(f"color: {get_color('error')};")
        logger.error("[Admin API] Error: %s", error)
        if "429" in str(error):
            self._handle_rate_limit(error)

    def _handle_rate_limit(self, error_text: str):
        """429 발생 시 Retry-After 헤더 기반 자동 재시도

        In production, the server should send a Retry-After header that could be parsed here.
        The Retry-After header can specify seconds (numeric) or an HTTP-date (RFC 7231).

        Example:
            - Retry-After: 120 (retry after 120 seconds)
            - Retry-After: Wed, 21 Oct 2025 07:28:00 GMT (retry at specific time)
        """
        if self._rate_limited:
            return

        self._rate_limited = True
        self.connection_label.setText("요청 제한 - 잠시 후 자동 재시도")
        self.connection_label.setStyleSheet(f"color: {get_color('warning')};")

        if hasattr(self, "refresh_timer") and self.refresh_timer.isActive():
            self.refresh_timer.stop()

        # Default: 5 minutes (300 seconds = 300000 ms)
        # TODO: Parse Retry-After header from response if available
        # retry_delay_seconds = int(response_headers.get('Retry-After', '300'))
        retry_delay_ms = RETRY_DELAY_MS

        logger.warning("[Admin UI] Rate limit triggered. Pausing for %d seconds. Detail: %s", retry_delay_ms // 1000, error_text)
        QTimer.singleShot(retry_delay_ms, self._resume_after_rate_limit)

    def _resume_after_rate_limit(self):
        self._rate_limited = False
        self.connection_label.setText("재시도 중...")
        self.connection_label.setStyleSheet(f"color: {get_color('warning')};")
        if hasattr(self, "refresh_timer"):
            self.refresh_timer.start(REFRESH_INTERVAL_MS)
        self._load_data()


# Dialog classes have been extracted to ui/admin_dialogs.py


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Get configuration from env or use defaults
    API_URL = os.getenv("API_SERVER_URL", "https://ssmaker-auth-api-1049571775048.us-central1.run.app")
    API_KEY = os.getenv("SSMAKER_ADMIN_KEY") or os.getenv("ADMIN_API_KEY")

    app = QApplication(sys.argv)
    
    # Set default font
    font = QFont(FONT_FAMILY, ds.typography.size_sm // 2)
    app.setFont(font)

    if not API_KEY:
        # Auto-connect without login (User request)
        API_KEY = "no-login-required"
        logger.info("[Admin UI] Auto-login enabled via dummy key")
        
        # from PyQt6.QtWidgets import QInputDialog, QLineEdit
        # logger.warning("[Admin UI] No admin key in env. Asking user.")
        # key, ok = QInputDialog.getText(None, "Authentication Required", 
        #                                "Admin API Key가 설정되지 않았습니다.\n키를 입력해주세요:", 
        #                                QLineEdit.EchoMode.Password)
        # if ok and key:
        #     API_KEY = key.strip()
        #     # Remember key for this session (or potentially save to file)
        #     os.environ["SSMAKER_ADMIN_KEY"] = API_KEY
        # else:
        #     logger.warning("[Admin UI] User cancelled key input")

    window = AdminDashboard(API_URL, API_KEY)
    window.show()

    sys.exit(app.exec())
