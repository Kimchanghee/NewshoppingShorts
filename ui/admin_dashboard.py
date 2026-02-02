# -*- coding: utf-8 -*-
"""
Admin Dashboard for Shopping Shorts Maker
관리자 대시보드 - 다크모드, 절대 좌표 배치, 5초 자동 새로고침
"""

import logging
import os

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QComboBox,
    QLineEdit,
    QMessageBox,
    QDialog,
    QSpinBox,
    QTextEdit,
    QScrollArea,
    QAbstractItemView,
    QFrame,
)
from PyQt6.QtGui import QFont, QColor, QBrush
from datetime import datetime, timedelta, timezone
import requests

# Design System V2
from ui.design_system_v2 import get_design_system, get_color, set_dark_mode

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
WINDOW_WIDTH = 1600
WINDOW_HEIGHT = 900
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

    finished = pyqtSignal(dict)
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
                self.error.emit(f"Unknown method: {self.method}")
                return

            logger.info("[Admin API] Response %s: %s", resp.status_code, resp.text[:400])

            if resp.status_code == 429:
                self.error.emit(f"429 {resp.text}")
                return

            if resp.status_code == 200:
                self.finished.emit(resp.json())
            elif resp.status_code == 204:
                self.finished.emit({"success": True})
            else:
                self.error.emit(f"Error {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.exception("[Admin API] request failed")
            self.error.emit(str(e))


class AdminDashboard(QMainWindow):
    """관리자 대시보드"""

    def __init__(self, api_base_url: str, admin_api_key: str = None):
        super().__init__()
        self.api_base_url = api_base_url.rstrip("/")

        # Environment variable fallback chain: SSMAKER_ADMIN_KEY (preferred) -> ADMIN_API_KEY -> None
        self.admin_api_key = (
            admin_api_key 
            or os.getenv("SSMAKER_ADMIN_KEY") 
            or os.getenv("ADMIN_API_KEY", "")
        )



        if not self.admin_api_key:
            logger.error("[Admin UI] ADMIN_API_KEY not set - dashboard will not work")

        self.workers = []
        self.current_tab = 0  # 0: 사용자 관리, 1: 구독 요청
        self.last_update_time = None
        self._rate_limited = False
        logger.info("[Admin UI] Dashboard start | api_base=%s key_set=%s", self.api_base_url, bool(self.admin_api_key))
        self._setup_ui()
        self._load_data()
        self._start_auto_refresh()

    def _cleanup_worker(self, worker):
        """작업 완료된 워커 정리"""
        if worker in self.workers:
            self.workers.remove(worker)
        worker.deleteLater()

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
        except:
            return utc_str

    def _update_last_refresh_time(self):
        """마지막 업데이트 시간 갱신"""
        self.last_update_time = datetime.now()
        time_str = self.last_update_time.strftime("%Y-%m-%d %H:%M:%S")
        self.last_update_label.setText(f"마지막 업데이트: {time_str}")

    def _setup_ui(self):
        self.setWindowTitle("관리자 대시보드")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(f"background-color: {get_color('background')};")

        # 중앙 위젯
        self.central = QWidget(self)
        self.setCentralWidget(self.central)

        # 타이틀
        title = QLabel("관리자 대시보드", self.central)
        title.setGeometry(40, 20, 400, 40)
        title.setFont(QFont(FONT_FAMILY, ds.typography.size_2xl // 2, QFont.Weight.Bold))  # 32 -> 16pt
        title.setStyleSheet(f"color: {get_color('text_primary')};")

        # 마지막 업데이트 시간 라벨
        self.last_update_label = QLabel("마지막 업데이트: -", self.central)
        self.last_update_label.setGeometry(900, 25, 300, 30)
        self.last_update_label.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs // 2))  # 10 -> 5pt
        self.last_update_label.setStyleSheet(f"color: {get_color('text_muted')};")
        self.last_update_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # 새로고침 버튼
        refresh_btn = QPushButton("새로고침", self.central)
        refresh_btn.setGeometry(1220, 20, 120, 40)
        refresh_btn.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2, QFont.Weight.Bold))  # 14 -> 7pt
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

        # 연결 상태 표시
        self.connection_label = QLabel("", self.central)
        self.connection_label.setGeometry(1360, 25, 200, 30)
        self.connection_label.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs // 2))  # 10 -> 5pt
        self.connection_label.setStyleSheet(f"color: {get_color('success')};")

        # 통계 카드들 (Y: 75)
        self._create_stat_cards()

        # 탭 버튼들 (Y: 180)
        self._create_tab_buttons()

        # 필터/검색 영역 (Y: 240)
        self._create_filter_area()

        # 테이블 (Y: 290)
        self._create_tables()

    def _create_stat_cards(self):
        """통계 카드 생성 - 균형 잡힌 레이아웃"""
        card_y = 75
        card_h = 80
        # 6개 카드를 균등 배치
        total_w = 1520
        gap = ds.spacing.space_4  # 16px
        card_w = (total_w - (gap * 5)) // 6
        start_x = 40

        # Create 6 cards
        items = [
            ("구독요청 대기", get_color("warning"), "pending_label"),
            ("구독요청 승인", get_color("success"), "approved_label"),
            ("구독요청 거부", get_color("error"), "rejected_label"),
            ("전체 사용자", get_color("primary"), "users_label"),
            ("온라인 사용자", get_color("success"), "online_label"),
            ("활성 구독자", get_color("secondary"), "active_sub_label")
        ]

        for i, (title, color, attr_name) in enumerate(items):
            x = start_x + i * (card_w + gap)
            self._create_card(x, card_y, card_w, card_h, title, color)
            # Create label
            lbl = self._get_value_label(x, card_y, card_w, card_h)
            setattr(self, attr_name, lbl)

    def _create_card(self, x, y, w, h, title, color):
        """카드 생성"""
        card = QWidget(self.central)
        card.setGeometry(x, y, w, h)
        card.setStyleSheet(f"""
            background-color: {get_color('surface')};
            border-radius: {ds.radius.md}px;
            border-left: 4px solid {color};
        """)

        title_lbl = QLabel(title, card)
        title_lbl.setGeometry(15, 10, w - 30, 20)
        title_lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs // 2))  # 10 -> 5pt
        title_lbl.setStyleSheet(f"color: {get_color('text_muted')}; background: transparent;")

    def _get_value_label(self, x, y, w, h) -> QLabel:
        """값 라벨 생성 및 반환"""
        lbl = QLabel("0", self.central)
        lbl.setGeometry(x + 15, y + 35, w - 30, 40)
        lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_xl // 2, QFont.Weight.Bold))  # 24 -> 12pt
        lbl.setStyleSheet(f"color: {get_color('text_primary')}; background: transparent;")
        return lbl

    def _create_tab_buttons(self):
        """탭 버튼 생성 (회원가입 요청 탭 제거 - 자동 승인됨)"""
        self.tab_users = QPushButton("사용자 관리", self.central)
        self.tab_users.setGeometry(40, 180, 130, 42)
        self.tab_users.setFont(QFont(FONT_FAMILY, ds.typography.size_base // 2, QFont.Weight.Bold))  # 16 -> 8pt
        self.tab_users.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tab_users.clicked.connect(lambda: self._switch_tab(0))

        self.tab_subscriptions = QPushButton("구독 요청", self.central)
        self.tab_subscriptions.setGeometry(180, 180, 130, 42)
        self.tab_subscriptions.setFont(QFont(FONT_FAMILY, ds.typography.size_base // 2))  # 16 -> 8pt
        self.tab_subscriptions.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tab_subscriptions.clicked.connect(lambda: self._switch_tab(1))

        self._update_tab_styles()

    def _update_tab_styles(self):
        """탭 스타일 업데이트"""
        active = f"""
            QPushButton {{
                background-color: transparent;
                color: {get_color('primary')};
                border: none;
                border-bottom: 2px solid {get_color('primary')};
                border-radius: {ds.radius.none}px;
                font-weight: bold;
            }}
        """
        inactive = f"""
            QPushButton {{
                background-color: transparent;
                color: {get_color('text_muted')};
                border: none;
                border-bottom: 2px solid transparent;
                border-radius: {ds.radius.none}px;
            }}
            QPushButton:hover {{
                color: {get_color('text_primary')};
            }}
        """
        self.tab_users.setStyleSheet(active if self.current_tab == 0 else inactive)
        self.tab_subscriptions.setStyleSheet(active if self.current_tab == 1 else inactive)

    def _switch_tab(self, tab_index):
        """탭 전환 (0: 사용자 관리, 1: 구독 요청)"""
        logger.info("[Admin UI] Switch tab -> %s", "사용자" if tab_index == 0 else "구독요청")
        self.current_tab = tab_index
        self._update_tab_styles()
        self.users_table.setVisible(tab_index == 0)
        self.subscriptions_table.setVisible(tab_index == 1)
        self.search_edit.setVisible(tab_index == 0)
        self.search_label.setVisible(tab_index == 0)
        self.sub_filter_combo.setVisible(tab_index == 1)
        self.sub_filter_label.setVisible(tab_index == 1)

    def _create_filter_area(self):
        """필터/검색 영역 생성 (회원가입 요청 필터 제거)"""
        # 사용자 검색 (기본 표시)
        self.search_label = QLabel("아이디 검색:", self.central)
        self.search_label.setGeometry(40, 245, 90, 30)
        self.search_label.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2))  # 14 -> 7pt
        self.search_label.setStyleSheet(f"color: {get_color('text_primary')};")

        self.search_edit = QLineEdit(self.central)
        self.search_edit.setGeometry(135, 242, 200, 36)
        self.search_edit.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2))  # 14 -> 7pt
        self.search_edit.setPlaceholderText("검색어 입력...")
        self.search_edit.setStyleSheet(f"""
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
        self.search_edit.textChanged.connect(self._on_search_changed)

        # 구독 요청 필터
        self.sub_filter_label = QLabel("상태 필터:", self.central)
        self.sub_filter_label.setGeometry(40, 245, 80, 30)
        self.sub_filter_label.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2))  # 14 -> 7pt
        self.sub_filter_label.setStyleSheet(f"color: {get_color('text_primary')};")
        self.sub_filter_label.setVisible(False)

        self.sub_filter_combo = QComboBox(self.central)
        self.sub_filter_combo.setGeometry(125, 242, 140, 36)
        self.sub_filter_combo.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2))  # 14 -> 7pt
        self.sub_filter_combo.addItems(["대기 중", "승인됨", "거부됨", "전체"])
        self.sub_filter_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {get_color('surface')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border')};
                border-radius: {ds.radius.base}px;
                padding: 5px {ds.spacing.space_4}px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {get_color('surface')};
                color: {get_color('text_primary')};
                selection-background-color: {get_color('primary')};
            }}
        """)
        self.sub_filter_combo.currentTextChanged.connect(self._on_sub_filter_changed)
        self.sub_filter_combo.setVisible(False)

    def _create_tables(self):
        """테이블 생성"""
        table_x = 40
        table_y = 290
        table_w = 1520
        table_h = 580

        # 사용자 관리 테이블 (확장된 컨럼 + 비밀번호)
        self.users_table = QTableWidget(self.central)
        self.users_table.setGeometry(table_x, table_y, table_w, table_h)
        self.users_table.setColumnCount(15)  # 컬럼 수 변경
        self.users_table.setHorizontalHeaderLabels(
            [
                "ID",
                "이름",
                "아이디",
                "비밀번호",
                "연락처",
                "이메일",
                "유형",
                "구독만료",
                "작업횟수",
                "로그인",
                "마지막 로그인",
                "IP",
                "접속",
                "현재작업",
                "작업",
            ]
        )
        self._style_table(
             # Increased Action column (last) to 330px to prevent button overflow
            self.users_table, [40, 80, 90, 80, 110, 150, 60, 130, 70, 50, 130, 100, 50, 90, 330]
        )
        # 사용자 테이블이 기본 표시됨

        # 구독 요청 테이블
        self.subscriptions_table = QTableWidget(self.central)
        self.subscriptions_table.setGeometry(table_x, table_y, table_w, table_h)
        self.subscriptions_table.setColumnCount(7)
        self.subscriptions_table.setHorizontalHeaderLabels(
            ["ID", "사용자", "상태", "요청작업", "메시지", "요청일시", "관리"]
        )
        self._style_table(
            # Column widths adjusted to prevent Action column overflow
            # Last column (Actions) increased from 250 -> 320 to fit 5 buttons
            self.subscriptions_table, [60, 80, 100, 350, 150, 80, 200]
        )
        self.subscriptions_table.setVisible(False)

    def _style_table(self, table: QTableWidget, widths: list):
        """테이블 스타일"""
        table.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs // 2))  # 10 -> 5pt
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
        # 기본 교차 색상 비활성화 (직접 행 배경색 설정)
        table.setAlternatingRowColors(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(50)

        for i, w in enumerate(widths):
            table.setColumnWidth(i, w)

    def _load_data(self):
        """데이터 로드 (회원가입 요청 제거 - 자동 승인됨)"""
        if self._rate_limited:
            self.connection_label.setText("요청 제한 중 - 대기 후 재시도")
            self.connection_label.setStyleSheet(f"color: {get_color('warning')};")
            return
        self.connection_label.setText("연결 중...")
        self.connection_label.setStyleSheet(f"color: {get_color('warning')};")
        logger.info("[Admin UI] Load data start")
        self._load_users()
        self._load_subscriptions()
        self._update_last_refresh_time()

    def _load_users(self):
        """사용자 목록 로드"""
        search = self.search_edit.text().strip()
        url = f"{self.api_base_url}/user/admin/users"
        if search:
            url += f"?search={search}"

        logger.info("[Admin UI] Load users | search=%s", search)
        worker = ApiWorker("GET", url, self._get_headers())
        worker.finished.connect(self._on_users_loaded)
        worker.error.connect(self._on_error)
        worker.finished.connect(lambda _: self._cleanup_worker(worker))
        worker.error.connect(lambda _: self._cleanup_worker(worker))
        self.workers.append(worker)
        worker.start()

    def _on_users_loaded(self, data: dict):
        """사용자 목록 로드 완료"""
        logger.info("[Admin UI] Users loaded (%d)", len(data.get("users", [])))
        items = data.get("users", [])
        self.users_table.setRowCount(len(items))
        self.users_label.setText(str(len(items)))
        self.connection_label.setText("연결 정상")
        self.connection_label.setStyleSheet(f"color: {get_color('success')};")

        online_count = 0
        active_sub_count = 0
        now = datetime.now(timezone.utc)

        for row, user in enumerate(items):
            self.users_table.setRowHeight(row, 50)
            
            # 0: ID
            self._set_cell(self.users_table, row, 0, str(user.get("id", "")))
            # 1: Name
            self._set_cell(self.users_table, row, 1, user.get("name") or "-")
            # 2: Username
            self._set_cell(self.users_table, row, 2, user.get("username", ""))
            # 3: Password (Hash truncated)
            pw_hash = user.get("hashed_password", "")
            self._set_cell(self.users_table, row, 3, pw_hash[:10] + "..." if pw_hash else "-")
            # 4: Phone
            self._set_cell(self.users_table, row, 4, user.get("phone") or "-")
            # 5: Email
            self._set_cell(self.users_table, row, 5, user.get("email") or "-")
            
            # 6: Type
            utype = user.get("user_type", "trial")
            utype_text = {
                "trial": "체험판",
                "subscriber": "구독자",
                "admin": "관리자",
            }.get(utype, utype)
            utype_color = {
                "trial": get_color("text_muted"),
                "subscriber": get_color("primary"),
                "admin": get_color("warning"),
            }.get(utype, get_color("text_primary"))
            self._set_cell(self.users_table, row, 6, utype_text, utype_color)

            # 7: Subscription Expires
            expires_utc = user.get("subscription_expires_at")
            expires_str = self._convert_to_kst(expires_utc)
            
            color = get_color("text_primary")
            if expires_utc:
                try:
                    dt = datetime.fromisoformat(expires_utc.replace("Z", "+00:00"))
                    if dt < now:
                         color = get_color("error")
                    elif (dt - now).days <= 7:
                         color = get_color("warning")
                    else:
                         color = get_color("success")
                         active_sub_count += 1
                except:
                    pass
            self._set_cell(self.users_table, row, 7, expires_str, color)

            # 8: Work Count
            work_count = user.get("work_count", -1)
            work_used = user.get("work_used", 0)
            if work_count == -1:
                work_str = "무제한"
                color = get_color("success")
            else:
                remaining = max(0, work_count - work_used)
                work_str = f"{remaining}/{work_count}"
                color = get_color("warning") if remaining <= 10 else get_color("text_primary")
            self._set_cell(self.users_table, row, 8, work_str, color)

            # 9: Login Count
            self._set_cell(self.users_table, row, 9, str(user.get("login_count", 0)))

            # 10: Last Login
            last_login = self._convert_to_kst(user.get("last_login_at"))
            self._set_cell(self.users_table, row, 10, last_login)

            # 11: IP
            self._set_cell(self.users_table, row, 11, user.get("last_login_ip", "-"))

            # 12: Online Status
            # Trust server's is_online field (set via heartbeat mechanism)
            is_online = user.get("is_online", False)

            if is_online:
                online_count += 1

            self._set_cell(self.users_table, row, 12, "ON" if is_online else "OFF",
                           get_color("success") if is_online else get_color("text_muted"))

            # 13: Current Task
            self._set_cell(self.users_table, row, 13, user.get("current_task", "-"))

            # 14: Actions
            widget = self._create_user_actions(
                user.get("id"),
                user.get("username"),
                row,
                user.get("hashed_password"),
            )
            self.users_table.setCellWidget(row, 14, widget)

        self.online_label.setText(str(online_count))
        self.active_sub_label.setText(str(active_sub_count))

    def _set_cell(self, table, row, col, text, color=None):
        """셀 설정"""
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        # 항상 텍스트 색상 설정 (기본: 흰색)
        item.setForeground(QBrush(QColor(color if color else get_color("text_primary"))))
        # 행 번호에 따른 배경색 설정 (교차 색상)
        bg_color = get_color("surface_variant") if row % 2 == 1 else get_color("surface")
        item.setBackground(QBrush(QColor(bg_color)))
        table.setItem(row, col, item)

    def _create_user_actions(
        self, user_id, username, row: int = 0, hashed_password: str = None
    ) -> QWidget:
        """사용자 작업 버튼 - 미니멀 디자인"""
        widget = QWidget()
        # Widen container to fit 5 buttons (55px * 5 + spacing)
        widget.setMinimumSize(320, 40)
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

        # 1. PW Check (Button)
        pw_btn = QPushButton("PW", widget)
        pw_btn.setGeometry(0, 5, 40, 30)
        pw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # Gray theme
        c_norm = get_color("text_muted")
        c_hov = get_color("border")
        pw_btn.setStyleSheet(base_style % (c_norm, ds.radius.sm, ds.typography.size_2xs // 2, c_norm, c_hov))
        pw_btn.clicked.connect(lambda: self._show_password_info(username, hashed_password))

        # 2. Extension (Green/Success)
        ext_btn = QPushButton("연장", widget)
        ext_btn.setGeometry(45, 5, 50, 30)
        ext_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        c_norm = get_color("info") # Blue
        ext_btn.setStyleSheet(base_style % (c_norm, ds.radius.sm, ds.typography.size_2xs // 2, c_norm, c_norm))
        ext_btn.clicked.connect(lambda: self._extend_subscription(user_id, username))
        
        # 3. Status (Yellow/Warning)
        stat_btn = QPushButton("상태", widget)
        stat_btn.setGeometry(100, 5, 50, 30)
        stat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        c_norm = get_color("warning")
        stat_btn.setStyleSheet(base_style % (c_norm, ds.radius.sm, ds.typography.size_2xs // 2, c_norm, c_norm))
        stat_btn.clicked.connect(lambda: self._check_work_status(user_id, username))

        # 4. History (Gray/Info)
        hist_btn = QPushButton("이력", widget)
        hist_btn.setGeometry(155, 5, 50, 30)
        hist_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        c_norm = get_color("text_primary")
        c_hov = get_color("surface_variant")
        hist_btn.setStyleSheet(base_style % (get_color("border"), ds.radius.sm, ds.typography.size_2xs // 2, c_norm, c_hov))
        hist_btn.clicked.connect(lambda: self._show_login_history(user_id, username))

        # 5. Delete (Red/Danger)
        del_btn = QPushButton("삭제", widget)
        del_btn.setGeometry(210, 5, 50, 30)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        c_norm = get_color("error")
        del_btn.setStyleSheet(base_style % (c_norm, ds.radius.sm, ds.typography.size_2xs // 2, c_norm, c_norm))
        del_btn.clicked.connect(lambda: self._delete_user(user_id, username))

        return widget

    def _show_password_info(self, username, hashed_password):
        """비밀번호 정보 표시 (보안 마스킹 적용)"""
        if not hashed_password:
            hashed_password = "(정보 없음)"
            masked_hash = hashed_password
        else:
            # 보안을 위해 해시 마스킹 (처음 8자와 마지막 8자만 표시)
            if len(hashed_password) > 16:
                masked_hash = f"{hashed_password[:8]}...{hashed_password[-8:]}"
            else:
                # 짧은 해시는 전체 표시하지 않음
                masked_hash = "******** (보안상 전체 표시 불가)"

        dialog = QDialog(self)
        dialog.setWindowTitle(f"'{username}' 비밀번호 정보")
        dialog.setFixedSize(500, 320)  # 크기 증가
        dialog.setStyleSheet(f"background-color: {get_color('surface')};")

        title_lbl = QLabel(f"'{username}' 비밀번호 해시 정보:", dialog)
        title_lbl.setGeometry(30, 25, 440, 25)
        title_lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {get_color('text_primary')};")

        # 보안 경고 메시지 강화
        warning_lbl = QLabel("⚠️ 보안 경고: 비밀번호 해시는 민감한 정보입니다.", dialog)
        warning_lbl.setGeometry(30, 55, 440, 20)
        warning_lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs // 2, QFont.Weight.Bold))
        warning_lbl.setStyleSheet(f"color: {get_color('warning')};")

        warning2_lbl = QLabel("이 정보는 관리자 권한으로만 확인 가능합니다.", dialog)
        warning2_lbl.setGeometry(30, 75, 440, 20)
        warning2_lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs // 2))
        warning2_lbl.setStyleSheet(f"color: {get_color('error')};")

        info_lbl = QLabel("필요한 경우에만 확인하고, 무단 공유를 금지합니다.", dialog)
        info_lbl.setGeometry(30, 95, 440, 20)
        info_lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs // 2))
        info_lbl.setStyleSheet(f"color: {get_color('text_muted')};")

        hash_edit = QLineEdit(dialog)
        hash_edit.setGeometry(30, 125, 440, 40)
        hash_edit.setText(masked_hash)
        hash_edit.setReadOnly(True)
        hash_edit.setFont(QFont("Consolas", ds.typography.size_2xs // 2))
        hash_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {get_color('background')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border')};
                border-radius: {ds.radius.base}px;
                padding: {ds.spacing.space_2}px;
            }}
        """)

        note_lbl = QLabel(
            "※ 보안상 비밀번호는 해시 형태로만 저장됩니다.\n   원본 비밀번호는 복구할 수 없습니다.",
            dialog,
        )
        note_lbl.setGeometry(30, 175, 440, 40)
        note_lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs // 2))
        note_lbl.setStyleSheet(f"color: {get_color('text_muted')};")

        # 추가 보안 정보
        security_lbl = QLabel(
            "※ 해시 알고리즘: bcrypt (안전한 비밀번호 저장)\n※ 마스킹 처리: 보안상 전체 해시 표시 제한",
            dialog,
        )
        security_lbl.setGeometry(30, 215, 440, 40)
        security_lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs // 2))
        security_lbl.setStyleSheet(f"color: {get_color('info')};")

        close_btn = QPushButton("닫기", dialog)
        close_btn.setGeometry(370, 265, 100, 35)
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
        logger.info("[Admin UI] Search changed: %s", text)
        self._load_users()

    def _on_sub_filter_changed(self, text):
        logger.info("[Admin UI] Subscription filter: %s", text)
        self._load_subscriptions()

    def _load_subscriptions(self):
        """구독 요청 목록 로드"""
        status_filter = self.sub_filter_combo.currentText()
        url = f"{self.api_base_url}/user/subscription/requests"
        if status_filter != "전체":
            status_map = {
                "대기 중": "PENDING",
                "승인됨": "APPROVED",
                "거부됨": "REJECTED",
            }
            url += f"?status={status_map.get(status_filter, '')}"

        logger.info("[Admin UI] Load subscriptions | filter=%s", status_filter)
        worker = ApiWorker("GET", url, self._get_headers())
        worker.finished.connect(self._on_subscriptions_loaded)
        worker.error.connect(self._on_error)
        worker.finished.connect(lambda _: self._cleanup_worker(worker))
        worker.error.connect(lambda _: self._cleanup_worker(worker))
        self.workers.append(worker)
        worker.start()

    def _on_subscriptions_loaded(self, data: dict):
        """구독 요청 목록 로드 완료"""
        logger.info("[Admin UI] Subscriptions loaded (%d)", len(data.get("requests", [])))
        items = data.get("requests", [])
        self.subscriptions_table.setRowCount(len(items))

        for row, req in enumerate(items):
            self.subscriptions_table.setRowHeight(row, 50)

            # 0: ID
            self._set_cell(self.subscriptions_table, row, 0, str(req.get("id", "")))
            # 1: 사용자ID
            self._set_cell(self.subscriptions_table, row, 1, str(req.get("user_id", "")))
            # 2: 아이디 (username)
            self._set_cell(self.subscriptions_table, row, 2, req.get("username", "-"))
            # 3: 메시지
            self._set_cell(self.subscriptions_table, row, 3, req.get("message", "") or "-")

            # 4: 요청일시
            created = req.get("created_at", "")
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    created = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    pass
            self._set_cell(self.subscriptions_table, row, 4, created or "-")

            # 5: 상태
            status = req.get("status", "")
            status_text = {
                "PENDING": "대기 중",
                "APPROVED": "승인됨",
                "REJECTED": "거부됨",
            }.get(status, status)
            status_color = {
                "PENDING": get_color("warning"),
                "APPROVED": get_color("success"),
                "REJECTED": get_color("error"),
            }.get(status, get_color("text_primary"))
            self._set_cell(self.subscriptions_table, row, 5, status_text, status_color)

            # 6: 작업 버튼
            if status == "PENDING":
                widget = self._create_subscription_actions(req.get("id"), row)
                self.subscriptions_table.setCellWidget(row, 6, widget)
            else:
                self._set_cell(self.subscriptions_table, row, 6, "-")
        
        # 정확한 통계를 위해 별도 API 호출
        self._load_subscription_stats()
    
    def _load_subscription_stats(self):
        """구독 요청 통계 로드 (정확한 카운트)"""
        url = f"{self.api_base_url}/user/subscription/stats"
        worker = ApiWorker("GET", url, self._get_headers())
        worker.finished.connect(self._on_subscription_stats_loaded)
        worker.error.connect(lambda e: logger.warning("[Admin UI] Failed to load subscription stats: %s", e))
        worker.finished.connect(lambda _: self._cleanup_worker(worker))
        worker.error.connect(lambda _: self._cleanup_worker(worker))
        self.workers.append(worker)
        worker.start()
    
    def _on_subscription_stats_loaded(self, data: dict):
        """구독 요청 통계 로드 완료"""
        self.pending_label.setText(str(data.get("pending", 0)))
        self.approved_label.setText(str(data.get("approved", 0)))
        self.rejected_label.setText(str(data.get("rejected", 0)))

    def _create_subscription_actions(self, request_id, row: int = 0) -> QWidget:
        """구독 요청 작업 버튼"""
        widget = QWidget()
        widget.setMinimumSize(200, 50)
        bg_color = get_color("surface_variant") if row % 2 == 1 else get_color("surface")
        widget.setStyleSheet(f"background-color: {bg_color};")

        approve_btn = QPushButton("승인", widget)
        approve_btn.setGeometry(10, 10, 80, 30)
        approve_btn.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs // 2))
        approve_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {get_color('success')};
                color: white;
                border: none;
                border-radius: {ds.radius.sm}px;
            }}
            QPushButton:hover {{
                background-color: #00e676;
            }}
        """)
        approve_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        approve_btn.clicked.connect(lambda: self._approve_subscription(request_id))

        reject_btn = QPushButton("거부", widget)
        reject_btn.setGeometry(100, 10, 80, 30)
        reject_btn.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs // 2))
        reject_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {get_color('error')};
                color: white;
                border: none;
                border-radius: {ds.radius.sm}px;
            }}
            QPushButton:hover {{
                background-color: #ff8a80;
            }}
        """)
        reject_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reject_btn.clicked.connect(lambda: self._reject_subscription(request_id))

        return widget

    def _approve_subscription(self, request_id):
        """구독 승인 다이얼로그"""
        logger.info("[Admin UI] Approve clicked | request_id=%s", request_id)
        dialog = ApproveDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            days = dialog.get_days()
            work_count = dialog.get_work_count()
            url = f"{self.api_base_url}/user/subscription/approve"
            data = {
                "request_id": request_id,
                "subscription_days": days,
                "work_count": work_count,
            }
            logger.info("[Admin UI] Approve request | request_id=%s days=%s work_count=%s", request_id, days, work_count)
            worker = ApiWorker("POST", url, self._get_headers(), data)
            worker.finished.connect(lambda d: self._on_action_done("구독 승인", d))
            worker.error.connect(self._on_error)
            worker.finished.connect(lambda _: self._cleanup_worker(worker))
            worker.error.connect(lambda _: self._cleanup_worker(worker))
            self.workers.append(worker)
            worker.start()

    def _reject_subscription(self, request_id):
        """구독 거부 다이얼로그"""
        logger.info("[Admin UI] Reject clicked | request_id=%s", request_id)
        dialog = RejectDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            reason = dialog.get_reason()
            url = f"{self.api_base_url}/user/subscription/reject"
            data = {"request_id": request_id, "admin_response": reason}
            logger.info("[Admin UI] Reject request | request_id=%s reason=%s", request_id, reason)
            worker = ApiWorker("POST", url, self._get_headers(), data)
            worker.finished.connect(lambda d: self._on_action_done("구독 거부", d))
            worker.error.connect(self._on_error)
            worker.finished.connect(lambda _: self._cleanup_worker(worker))
            worker.error.connect(lambda _: self._cleanup_worker(worker))
            self.workers.append(worker)
            worker.start()

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
            worker.finished.connect(lambda d: self._on_action_done("구독 연장", d))
            worker.error.connect(self._on_error)
            worker.finished.connect(lambda _: self._cleanup_worker(worker))
            worker.error.connect(lambda _: self._cleanup_worker(worker))
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
        worker.finished.connect(lambda d: self._on_action_done("상태 변경", d))
        worker.error.connect(self._on_error)
        worker.finished.connect(lambda _: self._cleanup_worker(worker))
        worker.error.connect(lambda _: self._cleanup_worker(worker))
        self.workers.append(worker)
        worker.start()

    def _check_work_status(self, user_id, username):
        """작업 상태 확인"""
        logger.info("[Admin UI] Check work status | user_id=%s username=%s", user_id, username)
        url = f"{self.api_base_url}/user/admin/users/{user_id}"
        worker = ApiWorker("GET", url, self._get_headers())
        worker.finished.connect(lambda d: self._show_work_status_dialog(username, d))
        worker.error.connect(self._on_error)
        worker.finished.connect(lambda _: self._cleanup_worker(worker))
        worker.error.connect(lambda _: self._cleanup_worker(worker))
        self.workers.append(worker)
        worker.start()
    
    def _show_work_status_dialog(self, username: str, data: dict):
        """작업 상태 다이얼로그 표시"""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"'{username}' 작업 상태")
        dialog.setFixedSize(450, 480)
        dialog.setStyleSheet(f"background-color: {get_color('surface')};")
        
        title_lbl = QLabel(f"'{username}' 상세 정보 및 상태", dialog)
        title_lbl.setGeometry(30, 25, 390, 25)
        title_lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_md // 2, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {get_color('text_primary')};")
        
        # 작업 횟수 정보
        work_count = data.get("work_count", -1)
        work_used = data.get("work_used", 0)
        
        if work_count == -1:
            work_status = "무제한"
            remaining = "무제한"
            color = get_color("success")
        else:
            remaining = max(0, work_count - work_used)
            work_status = f"{remaining} / {work_count}"
            color = get_color("warning") if remaining <= 10 else get_color("success")
        
        # 정보 표시
        y_pos = 70
        items = [
            ("실제 이름:", data.get("name") or "-"),
            ("이메일 주소:", data.get("email") or "-"),
            ("휴대폰 번호:", data.get("phone") or "-"),
            ("-" * 30, ""), # Separator
            ("작업 유형:", "구독자" if work_count == -1 else "제한형"),
            ("총 작업 횟수:", "무제한" if work_count == -1 else str(work_count)),
            ("사용한 작업:", str(work_used)),
            ("남은 작업:", str(remaining) if work_count != -1 else "무제한"),
            ("구독 만료:", self._convert_to_kst(data.get("subscription_expires_at"))),
            ("사용자 유형:", data.get("user_type", "trial")),
            ("현재 작업:", data.get("current_task") or "-"),
        ]
        
        for label, value in items:
            if label == "-" * 30:
                sep = QFrame(dialog)
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setFrameShadow(QFrame.Shadow.Sunken)
                sep.setGeometry(30, y_pos + 10, 390, 1)
                sep.setStyleSheet(f"background-color: {get_color('border')};")
                y_pos += 25
                continue

            lbl = QLabel(label, dialog)
            lbl.setGeometry(30, y_pos, 120, 25)
            lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2))
            lbl.setStyleSheet(f"color: {get_color('text_muted')};")
            
            val_lbl = QLabel(value, dialog)
            val_lbl.setGeometry(160, y_pos, 260, 25)
            val_lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2, QFont.Weight.Bold))
            val_lbl.setStyleSheet(f"color: {color if '남은 작업' in label else get_color('text_primary')};")
            
            y_pos += 35
        
        # 닫기 버튼
        close_btn = QPushButton("닫기", dialog)
        close_btn.setGeometry(320, 420, 100, 35)
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
        worker.finished.connect(lambda d: self._on_action_done("삭제", d))
        worker.error.connect(lambda e: self._on_action_error("삭제", e))
        worker.finished.connect(lambda _: self._cleanup_worker(worker))
        worker.error.connect(lambda _: self._cleanup_worker(worker))
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


class ApproveDialog(QDialog):
    """승인 다이얼로그 - 구독 기간 + 작업 횟수 설정"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("구독 승인")
        self.setFixedSize(420, 300)
        self.setStyleSheet(f"background-color: {get_color('surface')};")
        self._setup_ui()

    def _setup_ui(self):
        # 구독 기간
        lbl = QLabel("구독 기간:", self)
        lbl.setGeometry(30, 25, 120, 25)
        lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2))
        lbl.setStyleSheet(f"color: {get_color('text_primary')};")

        self.days_spin = QSpinBox(self)
        self.days_spin.setGeometry(30, 55, 120, 40)
        self.days_spin.setFont(QFont(FONT_FAMILY, ds.typography.size_md // 2))
        self.days_spin.setRange(1, 365)
        self.days_spin.setValue(30)
        self.days_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: {get_color('background')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border')};
                border-radius: {ds.radius.base}px;
                padding: {ds.spacing.space_2}px;
            }}
        """)

        day_lbl = QLabel("일", self)
        day_lbl.setGeometry(160, 63, 30, 25)
        day_lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2))
        day_lbl.setStyleSheet(f"color: {get_color('text_primary')};")

        # 작업 횟수
        work_lbl = QLabel("작업 횟수:", self)
        work_lbl.setGeometry(30, 110, 120, 25)
        work_lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2))
        work_lbl.setStyleSheet(f"color: {get_color('text_primary')};")

        self.unlimited_check = QPushButton("무제한", self)
        self.unlimited_check.setGeometry(230, 140, 80, 40)
        self.unlimited_check.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs // 2))
        self.unlimited_check.setCheckable(True)
        self.unlimited_check.setChecked(True)
        self.unlimited_check.setStyleSheet(f"""
            QPushButton {{
                background-color: {get_color('success')};
                color: white;
                border: none;
                border-radius: {ds.radius.base}px;
            }}
            QPushButton:checked {{
                background-color: {get_color('success')};
            }}
            QPushButton:!checked {{
                background-color: {get_color('background')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border')};
            }}
        """)
        self.unlimited_check.clicked.connect(self._toggle_unlimited)

        self.work_count_spin = QSpinBox(self)
        self.work_count_spin.setGeometry(30, 140, 120, 40)
        self.work_count_spin.setFont(QFont(FONT_FAMILY, ds.typography.size_md // 2))
        self.work_count_spin.setRange(1, 99999)
        self.work_count_spin.setValue(100)
        self.work_count_spin.setEnabled(False)
        self.work_count_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: {get_color('background')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border')};
                border-radius: {ds.radius.base}px;
                padding: {ds.spacing.space_2}px;
            }}
            QSpinBox:disabled {{
                color: {get_color('text_muted')};
            }}
        """)

        work_unit_lbl = QLabel("회", self)
        work_unit_lbl.setGeometry(160, 148, 30, 25)
        work_unit_lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2))
        work_unit_lbl.setStyleSheet(f"color: {get_color('text_primary')};")

        # 버튼
        cancel_btn = QPushButton("취소", self)
        cancel_btn.setGeometry(180, 240, 100, 40)
        cancel_btn.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2))
        cancel_btn.setStyleSheet(f"""
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
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("승인", self)
        ok_btn.setGeometry(290, 240, 100, 40)
        ok_btn.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2, QFont.Weight.Bold))
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {get_color('success')};
                color: white;
                border: none;
                border-radius: {ds.radius.base}px;
            }}
            QPushButton:hover {{
                background-color: #00e676;
            }}
        """)
        ok_btn.clicked.connect(self.accept)

    def _toggle_unlimited(self):
        is_unlimited = self.unlimited_check.isChecked()
        self.work_count_spin.setEnabled(not is_unlimited)

    def get_days(self):
        return self.days_spin.value()

    def get_work_count(self):
        """작업 횟수 반환 (-1 = 무제한)"""
        if self.unlimited_check.isChecked():
            return -1
        return self.work_count_spin.value()


class RejectDialog(QDialog):
    """거부 다이얼로그 - 다크모드"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("회원가입 거부")
        self.setFixedSize(420, 280)
        self.setStyleSheet(f"background-color: {get_color('surface')};")
        self._setup_ui()

    def _setup_ui(self):
        lbl = QLabel("거부 사유를 입력하세요 (선택사항):", self)
        lbl.setGeometry(30, 25, 360, 25)
        lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2))
        lbl.setStyleSheet(f"color: {get_color('text_primary')};")

        self.reason_edit = QTextEdit(self)
        self.reason_edit.setGeometry(30, 60, 360, 130)
        self.reason_edit.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2))
        self.reason_edit.setPlaceholderText("거부 사유 입력...")
        self.reason_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {get_color('background')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border')};
                border-radius: {ds.radius.base}px;
                padding: {ds.spacing.space_3}px;
            }}
        """)

        cancel_btn = QPushButton("취소", self)
        cancel_btn.setGeometry(190, 210, 100, 40)
        cancel_btn.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2))
        cancel_btn.setStyleSheet(f"""
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
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("거부", self)
        ok_btn.setGeometry(300, 210, 100, 40)
        ok_btn.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2, QFont.Weight.Bold))
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {get_color('error')};
                color: white;
                border: none;
                border-radius: {ds.radius.base}px;
            }}
            QPushButton:hover {{
                background-color: #ff8a80;
            }}
        """)
        ok_btn.clicked.connect(self.accept)

    def get_reason(self):
        return self.reason_edit.toPlainText().strip()


class ExtendDialog(QDialog):
    """구독 연장 다이얼로그 - 다크모드"""

    def __init__(self, username: str, parent=None):
        super().__init__(parent)
        self.username = username
        self.setWindowTitle("구독 연장")
        self.setFixedSize(380, 200)
        self.setStyleSheet(f"background-color: {get_color('surface')};")
        self._setup_ui()

    def _setup_ui(self):
        lbl = QLabel(f"'{self.username}' 구독 연장 기간:", self)
        lbl.setGeometry(30, 30, 320, 25)
        lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2))
        lbl.setStyleSheet(f"color: {get_color('text_primary')};")

        self.days_spin = QSpinBox(self)
        self.days_spin.setGeometry(30, 70, 120, 40)
        self.days_spin.setFont(QFont(FONT_FAMILY, ds.typography.size_md // 2))
        self.days_spin.setRange(1, 365)
        self.days_spin.setValue(30)
        self.days_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: {get_color('background')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border')};
                border-radius: {ds.radius.base}px;
                padding: {ds.spacing.space_2}px;
            }}
        """)

        day_lbl = QLabel("일 추가", self)
        day_lbl.setGeometry(160, 78, 60, 25)
        day_lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2))
        day_lbl.setStyleSheet(f"color: {get_color('text_primary')};")

        cancel_btn = QPushButton("취소", self)
        cancel_btn.setGeometry(150, 140, 100, 40)
        cancel_btn.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2))
        cancel_btn.setStyleSheet(f"""
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
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("연장", self)
        ok_btn.setGeometry(260, 140, 100, 40)
        ok_btn.setFont(QFont(FONT_FAMILY, ds.typography.size_sm // 2, QFont.Weight.Bold))
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {get_color('info')};
                color: white;
                border: none;
                border-radius: {ds.radius.base}px;
            }}
            QPushButton:hover {{
                background-color: #82b1ff;
            }}
        """)
        ok_btn.clicked.connect(self.accept)

    def get_days(self):
        return self.days_spin.value()


class LoginHistoryDialog(QDialog):
    """로그인 이력 다이얼로그"""

    def __init__(
        self, username: str, user_id: int, api_base_url: str, headers: dict, parent=None
    ):
        super().__init__(parent)
        self.username = username
        self.user_id = user_id
        self.api_base_url = api_base_url
        self.headers = headers
        self.setWindowTitle(f"'{username}' 로그인 이력")
        self.setFixedSize(700, 500)
        self.setStyleSheet(f"background-color: {get_color('surface')};")
        self._setup_ui()
        self._load_history()

    def _setup_ui(self):
        title_lbl = QLabel(f"'{self.username}' 로그인 이력", self)
        title_lbl.setGeometry(30, 20, 640, 30)
        title_lbl.setFont(QFont(FONT_FAMILY, ds.typography.size_md // 2, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {get_color('text_primary')};")

        # 이력 테이블
        self.history_table = QTableWidget(self)
        self.history_table.setGeometry(30, 60, 640, 380)
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(
            ["로그인 시간", "IP 주소", "세션 ID", "상태"]
        )
        self.history_table.setColumnWidth(0, 180)
        self.history_table.setColumnWidth(1, 150)
        self.history_table.setColumnWidth(2, 200)
        self.history_table.setColumnWidth(3, 80)
        self.history_table.setFont(QFont(FONT_FAMILY, ds.typography.size_2xs // 2))
        self.history_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {get_color('surface')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border')};
                border-radius: {ds.radius.base}px;
                gridline-color: {get_color('border')};
            }}
            QTableWidget::item {{
                padding: {ds.spacing.space_2}px;
                color: {get_color('text_primary')};
                background-color: {get_color('surface')};
            }}
            QHeaderView::section {{
                background-color: {get_color('background')};
                color: {get_color('text_primary')};
                font-weight: bold;
                padding: {ds.spacing.space_3}px;
                border: none;
            }}
        """)
        self.history_table.verticalHeader().setVisible(False)

        # 닫기 버튼
        close_btn = QPushButton("닫기", self)
        close_btn.setGeometry(560, 450, 100, 40)
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
        close_btn.clicked.connect(self.accept)

    def _load_history(self):
        """로그인 이력 로드 (API 연동 완료)"""
        try:
            url = f"{self.api_base_url}/user/admin/users/{self.user_id}/history"
            resp = requests.get(url, headers=self.headers, timeout=API_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                history = data.get("history", [])
                
                self.history_table.setRowCount(len(history))
                for row, item in enumerate(history):
                    # 0: 일시
                    at = item.get("attempted_at", "-")
                    try:
                        dt = datetime.fromisoformat(at.replace("Z", "+00:00"))
                        at = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        pass
                    
                    self._set_history_cell(row, 0, at)
                    # 1: IP 주소
                    self._set_history_cell(row, 1, item.get("ip_address", "-"))
                    # 2: 기기 (현재는 IP로 대체)
                    self._set_history_cell(row, 2, "PC/APP")
                    # 3: 상태
                    success = item.get("success", False)
                    status_text = "성공" if success else "실패"
                    status_color = get_color("success") if success else get_color("error")
                    self._set_history_cell(row, 3, status_text, status_color)
            else:
                self.history_table.setRowCount(1)
                self._set_history_cell(0, 0, f"로드 실패 (HTTP {resp.status_code})", get_color("error"))
        except Exception as e:
            logger.exception("Failed to load history")
            self.history_table.setRowCount(1)
            self._set_history_cell(0, 0, f"로드 오류: {str(e)[:50]}", get_color("error"))

    def _set_history_cell(self, row, col, text, color=None):
        """히스토리 테이블 셀 설정"""
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setForeground(QBrush(QColor(color if color else get_color("text_primary"))))
        item.setBackground(QBrush(QColor(get_color("surface"))))
        self.history_table.setItem(row, col, item)


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
    API_KEY = os.getenv("SSMAKER_ADMIN_KEY") or os.getenv("ADMIN_API_KEY", "ssmaker_admin_key_2024")

    app = QApplication(sys.argv)
    
    # Set default font
    font = QFont(FONT_FAMILY, ds.typography.size_sm // 2)
    app.setFont(font)

    window = AdminDashboard(API_URL, API_KEY)
    window.show()

    sys.exit(app.exec())
