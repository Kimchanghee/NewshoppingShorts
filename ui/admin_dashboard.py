# -*- coding: utf-8 -*-
"""
Admin Dashboard for Shopping Shorts Maker
관리자 대시보드 - 다크모드, 절대 좌표 배치, 5초 자동 새로고침
"""

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import (
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
)
from PyQt5.QtGui import QFont, QColor, QBrush
from datetime import datetime
import requests

FONT_FAMILY = "맑은 고딕"

# 다크모드 색상
DARK = {
    "bg": "#1a1a2e",
    "card": "#16213e",
    "primary": "#e31639",
    "primary_hover": "#ff1744",
    "success": "#00c853",
    "warning": "#ffc107",
    "danger": "#ff5252",
    "info": "#448aff",
    "text": "#ffffff",
    "text_dim": "#8892b0",
    "border": "#2d3748",
    "table_bg": "#0f0f23",
    "table_alt": "#1a1a35",
    "table_header": "#252550",
    "online": "#00e676",
    "offline": "#757575",
}


def _styled_msg_box(parent, title: str, message: str, icon_type: str = "info"):
    """
    다크모드에 맞춘 스타일 메시지 박스
    icon_type: 'info', 'warning', 'error', 'question'
    """
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(message)

    if icon_type == "info":
        msg.setIcon(QMessageBox.Information)
    elif icon_type == "warning":
        msg.setIcon(QMessageBox.Warning)
    elif icon_type == "error":
        msg.setIcon(QMessageBox.Critical)
    elif icon_type == "question":
        msg.setIcon(QMessageBox.Question)

    msg.setStyleSheet(f"""
        QMessageBox {{
            background-color: {DARK["card"]};
            color: {DARK["text"]};
        }}
        QMessageBox QLabel {{
            color: {DARK["text"]};
            font-size: 12px;
            min-width: 300px;
        }}
        QPushButton {{
            background-color: {DARK["primary"]};
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 20px;
            font-weight: bold;
            min-width: 80px;
        }}
        QPushButton:hover {{
            background-color: {DARK["primary_hover"]};
        }}
    """)
    return msg


def _styled_question_box(parent, title: str, message: str) -> bool:
    """다크모드 확인 다이얼로그 - Yes/No 반환"""
    msg = _styled_msg_box(parent, title, message, "question")
    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msg.setDefaultButton(QMessageBox.No)
    return msg.exec_() == QMessageBox.Yes


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
            if self.method == "GET":
                resp = requests.get(self.url, headers=self.headers, timeout=30)
            elif self.method == "POST":
                resp = requests.post(
                    self.url, headers=self.headers, json=self.data, timeout=30
                )
            elif self.method == "DELETE":
                resp = requests.delete(self.url, headers=self.headers, timeout=30)
            else:
                self.error.emit(f"Unknown method: {self.method}")
                return

            if resp.status_code == 200:
                self.finished.emit(resp.json())
            elif resp.status_code == 204:
                self.finished.emit({"success": True})
            else:
                self.error.emit(f"Error {resp.status_code}: {resp.text}")
        except Exception as e:
            self.error.emit(str(e))


class AdminDashboard(QMainWindow):
    """관리자 대시보드"""

    def __init__(self, api_base_url: str, admin_api_key: str):
        super().__init__()
        self.api_base_url = api_base_url.rstrip("/")
        self.admin_api_key = admin_api_key
        self.workers = []
        self.current_tab = 0  # 0: 사용자 관리, 1: 구독 요청
        self.last_update_time = None
        self._setup_ui()
        self._load_data()
        self._start_auto_refresh()

    def _get_headers(self) -> dict:
        return {
            "X-Admin-API-Key": self.admin_api_key,
            "Content-Type": "application/json",
        }

    def _start_auto_refresh(self):
        """5초마다 자동 새로고침"""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._load_data)
        self.refresh_timer.start(5000)

    def _update_last_refresh_time(self):
        """마지막 업데이트 시간 갱신"""
        self.last_update_time = datetime.now()
        time_str = self.last_update_time.strftime("%Y-%m-%d %H:%M:%S")
        self.last_update_label.setText(f"마지막 업데이트: {time_str}")

    def _setup_ui(self):
        self.setWindowTitle("관리자 대시보드")
        self.setFixedSize(1600, 900)
        self.setStyleSheet(f"background-color: {DARK['bg']};")

        # 중앙 위젯
        self.central = QWidget(self)
        self.setCentralWidget(self.central)

        # 타이틀
        title = QLabel("관리자 대시보드", self.central)
        title.setGeometry(40, 20, 400, 40)
        title.setFont(QFont(FONT_FAMILY, 22, QFont.Bold))
        title.setStyleSheet(f"color: {DARK['text']};")

        # 마지막 업데이트 시간 라벨
        self.last_update_label = QLabel("마지막 업데이트: -", self.central)
        self.last_update_label.setGeometry(900, 25, 300, 30)
        self.last_update_label.setFont(QFont(FONT_FAMILY, 10))
        self.last_update_label.setStyleSheet(f"color: {DARK['text_dim']};")
        self.last_update_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # 새로고침 버튼
        refresh_btn = QPushButton("새로고침", self.central)
        refresh_btn.setGeometry(1220, 20, 120, 40)
        refresh_btn.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK["primary"]};
                color: white;
                border: none;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: {DARK["primary_hover"]};
            }}
        """)
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self._load_data)

        # 연결 상태 표시
        self.connection_label = QLabel("", self.central)
        self.connection_label.setGeometry(1360, 25, 200, 30)
        self.connection_label.setFont(QFont(FONT_FAMILY, 10))
        self.connection_label.setStyleSheet(f"color: {DARK['success']};")

        # 통계 카드들 (Y: 75)
        self._create_stat_cards()

        # 탭 버튼들 (Y: 180)
        self._create_tab_buttons()

        # 필터/검색 영역 (Y: 240)
        self._create_filter_area()

        # 테이블 (Y: 290)
        self._create_tables()

    def _create_stat_cards(self):
        """통계 카드 생성 - 절대 좌표"""
        card_y = 75
        card_h = 85
        card_w = 240
        gap = 20
        start_x = 40

        # 구독요청 대기 중
        self._create_card(
            start_x, card_y, card_w, card_h, "구독요청 대기", DARK["warning"]
        )
        self.pending_label = self._get_value_label(start_x, card_y, card_w, card_h)

        # 구독요청 승인됨
        self._create_card(
            start_x + (card_w + gap),
            card_y,
            card_w,
            card_h,
            "구독요청 승인",
            DARK["success"],
        )
        self.approved_label = self._get_value_label(
            start_x + (card_w + gap), card_y, card_w, card_h
        )

        # 구독요청 거부됨
        self._create_card(
            start_x + (card_w + gap) * 2,
            card_y,
            card_w,
            card_h,
            "구독요청 거부",
            DARK["danger"],
        )
        self.rejected_label = self._get_value_label(
            start_x + (card_w + gap) * 2, card_y, card_w, card_h
        )

        # 전체 사용자
        self._create_card(
            start_x + (card_w + gap) * 3,
            card_y,
            card_w,
            card_h,
            "전체 사용자",
            DARK["info"],
        )
        self.users_label = self._get_value_label(
            start_x + (card_w + gap) * 3, card_y, card_w, card_h
        )

        # 온라인 사용자
        self._create_card(
            start_x + (card_w + gap) * 4,
            card_y,
            card_w,
            card_h,
            "온라인 사용자",
            DARK["online"],
        )
        self.online_label = self._get_value_label(
            start_x + (card_w + gap) * 4, card_y, card_w, card_h
        )

        # 활성 구독자
        self._create_card(
            start_x + (card_w + gap) * 5,
            card_y,
            card_w,
            card_h,
            "활성 구독자",
            DARK["primary"],
        )
        self.active_sub_label = self._get_value_label(
            start_x + (card_w + gap) * 5, card_y, card_w, card_h
        )

    def _create_card(self, x, y, w, h, title, color):
        """카드 생성"""
        card = QWidget(self.central)
        card.setGeometry(x, y, w, h)
        card.setStyleSheet(f"""
            background-color: {DARK["card"]};
            border-radius: 10px;
            border-left: 4px solid {color};
        """)

        title_lbl = QLabel(title, card)
        title_lbl.setGeometry(15, 10, w - 30, 20)
        title_lbl.setFont(QFont(FONT_FAMILY, 10))
        title_lbl.setStyleSheet(f"color: {DARK['text_dim']}; background: transparent;")

    def _get_value_label(self, x, y, w, h) -> QLabel:
        """값 라벨 생성 및 반환"""
        lbl = QLabel("0", self.central)
        lbl.setGeometry(x + 15, y + 35, w - 30, 40)
        lbl.setFont(QFont(FONT_FAMILY, 24, QFont.Bold))
        lbl.setStyleSheet(f"color: {DARK['text']}; background: transparent;")
        return lbl

    def _create_tab_buttons(self):
        """탭 버튼 생성 (회원가입 요청 탭 제거 - 자동 승인됨)"""
        self.tab_users = QPushButton("사용자 관리", self.central)
        self.tab_users.setGeometry(40, 180, 130, 42)
        self.tab_users.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        self.tab_users.setCursor(Qt.PointingHandCursor)
        self.tab_users.clicked.connect(lambda: self._switch_tab(0))

        self.tab_subscriptions = QPushButton("구독 요청", self.central)
        self.tab_subscriptions.setGeometry(180, 180, 130, 42)
        self.tab_subscriptions.setFont(QFont(FONT_FAMILY, 12))
        self.tab_subscriptions.setCursor(Qt.PointingHandCursor)
        self.tab_subscriptions.clicked.connect(lambda: self._switch_tab(1))

        self._update_tab_styles()

    def _update_tab_styles(self):
        """탭 스타일 업데이트 (2개 탭: 사용자 관리, 구독 요청)"""
        active = f"""
            QPushButton {{
                background-color: {DARK["card"]};
                color: {DARK["primary"]};
                border: none;
                border-bottom: 3px solid {DARK["primary"]};
                border-radius: 0px;
            }}
        """
        inactive = f"""
            QPushButton {{
                background-color: transparent;
                color: {DARK["text_dim"]};
                border: none;
                border-bottom: 3px solid transparent;
                border-radius: 0px;
            }}
            QPushButton:hover {{
                color: {DARK["text"]};
            }}
        """
        self.tab_users.setStyleSheet(active if self.current_tab == 0 else inactive)
        self.tab_subscriptions.setStyleSheet(
            active if self.current_tab == 1 else inactive
        )
        self.tab_users.setFont(
            QFont(
                FONT_FAMILY, 12, QFont.Bold if self.current_tab == 0 else QFont.Normal
            )
        )
        self.tab_subscriptions.setFont(
            QFont(
                FONT_FAMILY, 12, QFont.Bold if self.current_tab == 1 else QFont.Normal
            )
        )

    def _switch_tab(self, tab_index):
        """탭 전환 (0: 사용자 관리, 1: 구독 요청)"""
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
        self.search_label.setFont(QFont(FONT_FAMILY, 11))
        self.search_label.setStyleSheet(f"color: {DARK['text']};")

        self.search_edit = QLineEdit(self.central)
        self.search_edit.setGeometry(135, 242, 200, 36)
        self.search_edit.setFont(QFont(FONT_FAMILY, 11))
        self.search_edit.setPlaceholderText("검색어 입력...")
        self.search_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {DARK["card"]};
                color: {DARK["text"]};
                border: 1px solid {DARK["border"]};
                border-radius: 6px;
                padding: 5px 15px;
            }}
            QLineEdit::placeholder {{
                color: {DARK["text_dim"]};
            }}
        """)
        self.search_edit.textChanged.connect(self._on_search_changed)

        # 구독 요청 필터
        self.sub_filter_label = QLabel("상태 필터:", self.central)
        self.sub_filter_label.setGeometry(40, 245, 80, 30)
        self.sub_filter_label.setFont(QFont(FONT_FAMILY, 11))
        self.sub_filter_label.setStyleSheet(f"color: {DARK['text']};")
        self.sub_filter_label.setVisible(False)

        self.sub_filter_combo = QComboBox(self.central)
        self.sub_filter_combo.setGeometry(125, 242, 140, 36)
        self.sub_filter_combo.setFont(QFont(FONT_FAMILY, 11))
        self.sub_filter_combo.addItems(["대기 중", "승인됨", "거부됨", "전체"])
        self.sub_filter_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {DARK["card"]};
                color: {DARK["text"]};
                border: 1px solid {DARK["border"]};
                border-radius: 6px;
                padding: 5px 15px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {DARK["card"]};
                color: {DARK["text"]};
                selection-background-color: {DARK["primary"]};
            }}
        """)
        self.sub_filter_combo.currentTextChanged.connect(self._on_sub_filter_changed)
        self.sub_filter_combo.setVisible(False)

    def _create_tables(self):
        """테이블 생성 (회원가입 요청 테이블 제거)"""
        table_x = 40
        table_y = 290
        table_w = 1520
        table_h = 580

        # 사용자 관리 테이블 (확장된 컨럼) - 기본 표시
        self.users_table = QTableWidget(self.central)
        self.users_table.setGeometry(table_x, table_y, table_w, table_h)
        self.users_table.setColumnCount(13)
        self.users_table.setHorizontalHeaderLabels(
            [
                "ID",
                "아이디",
                "유형",
                "구독시작",
                "구독만료",
                "작업횟수",
                "상태",
                "로그인",
                "마지막 로그인",
                "IP",
                "접속",
                "현재작업",
                "작업",
            ]
        )
        self._style_table(
            self.users_table, [50, 100, 70, 90, 90, 80, 60, 50, 130, 100, 50, 100, 310]
        )
        # 사용자 테이블이 기본 표시됨

        # 구독 요청 테이블
        self.subscriptions_table = QTableWidget(self.central)
        self.subscriptions_table.setGeometry(table_x, table_y, table_w, table_h)
        self.subscriptions_table.setColumnCount(7)
        self.subscriptions_table.setHorizontalHeaderLabels(
            ["ID", "사용자 ID", "아이디", "메시지", "요청일시", "상태", "작업"]
        )
        self._style_table(self.subscriptions_table, [60, 80, 150, 350, 180, 100, 200])
        self.subscriptions_table.setVisible(False)

    def _style_table(self, table: QTableWidget, widths: list):
        """테이블 스타일"""
        table.setFont(QFont(FONT_FAMILY, 10))
        table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {DARK["table_bg"]};
                color: {DARK["text"]};
                border: 1px solid {DARK["border"]};
                border-radius: 8px;
                gridline-color: {DARK["border"]};
            }}
            QTableWidget::item {{
                padding: 5px;
                border-bottom: 1px solid {DARK["border"]};
                color: {DARK["text"]};
            }}
            QTableWidget::item:selected {{
                background-color: {DARK["primary"]};
                color: {DARK["text"]};
            }}
            QHeaderView::section {{
                background-color: {DARK["table_header"]};
                color: {DARK["text"]};
                font-weight: bold;
                padding: 10px 5px;
                border: none;
                border-bottom: 2px solid {DARK["primary"]};
            }}
            QScrollBar:vertical {{
                background-color: {DARK["bg"]};
                width: 12px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {DARK["border"]};
                border-radius: 6px;
                min-height: 30px;
            }}
        """)
        # 기본 교차 색상 비활성화 (직접 행 배경색 설정)
        table.setAlternatingRowColors(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(50)

        for i, w in enumerate(widths):
            table.setColumnWidth(i, w)

    def _load_data(self):
        """데이터 로드 (회원가입 요청 제거 - 자동 승인됨)"""
        self._load_users()
        self._load_subscriptions()
        self._update_last_refresh_time()

    def _load_users(self):
        """사용자 목록 로드"""
        search = self.search_edit.text().strip()
        url = f"{self.api_base_url}/user/admin/users"
        if search:
            url += f"?search={search}"

        worker = ApiWorker("GET", url, self._get_headers())
        worker.finished.connect(self._on_users_loaded)
        worker.error.connect(self._on_error)
        self.workers.append(worker)
        worker.start()

    def _on_users_loaded(self, data: dict):
        """사용자 목록 로드 완료"""
        items = data.get("users", [])
        self.users_table.setRowCount(len(items))
        self.users_label.setText(str(len(items)))

        online_count = 0
        active_sub_count = 0
        now = datetime.utcnow()

        for row, user in enumerate(items):
            self.users_table.setRowHeight(row, 50)

            self._set_cell(self.users_table, row, 0, str(user.get("id", "")))
            self._set_cell(self.users_table, row, 1, user.get("username", ""))

            # 구독 시작일
            created = user.get("created_at", "")
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    created = dt.strftime("%Y-%m-%d")
                except:
                    pass

            # 유형 (Trial / Subscriber / Admin)
            utype = user.get("user_type", "trial")
            utype_text = {
                "trial": "체험판",
                "subscriber": "구독자",
                "admin": "관리자",
            }.get(utype, utype)
            utype_color = {
                "trial": DARK["text_dim"],
                "subscriber": DARK["primary"],
                "admin": DARK["warning"],
            }.get(utype, DARK["text"])

            self._set_cell(self.users_table, row, 2, utype_text, utype_color)
            self._set_cell(self.users_table, row, 3, created or "-")

            # 구독 만료일
            expires = user.get("subscription_expires_at", "")
            expires_dt = None
            if expires:
                try:
                    expires_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                    expires_str = expires_dt.strftime("%Y-%m-%d")
                    # 만료 임박 (7일 이내) 또는 만료됨
                    if expires_dt.replace(tzinfo=None) < now:
                        self._set_cell(
                            self.users_table, row, 4, expires_str, DARK["danger"]
                        )
                    elif (expires_dt.replace(tzinfo=None) - now).days <= 7:
                        self._set_cell(
                            self.users_table, row, 4, expires_str, DARK["warning"]
                        )
                    else:
                        self._set_cell(
                            self.users_table, row, 4, expires_str, DARK["success"]
                        )
                        active_sub_count += 1
                except:
                    self._set_cell(self.users_table, row, 4, "-")
            else:
                self._set_cell(self.users_table, row, 4, "-")

            # 작업 횟수
            work_count = user.get("work_count", -1)
            work_used = user.get("work_used", 0)
            if work_count == -1:
                work_str = "무제한"
                work_color = DARK["success"]
            else:
                remaining = max(0, work_count - work_used)
                work_str = f"{remaining}/{work_count}"
                work_color = DARK["warning"] if remaining <= 10 else DARK["text"]
            self._set_cell(self.users_table, row, 5, work_str, work_color)

            # 계정 상태 (활성/비활성)
            is_active = user.get("is_active", False)
            self._set_cell(
                self.users_table,
                row,
                6,
                "활성" if is_active else "정지",
                DARK["success"] if is_active else DARK["danger"],
            )

            # 로그인 횟수
            self._set_cell(self.users_table, row, 7, str(user.get("login_count", 0)))

            # 마지막 로그인
            last_login = user.get("last_login_at", "")
            if last_login:
                try:
                    dt = datetime.fromisoformat(last_login.replace("Z", "+00:00"))
                    last_login = dt.strftime("%H:%M")  # 시간을 좀더 짧게
                    # 오늘인지 확인
                    if dt.date() == now.date():
                        last_login_str = f"오늘 {last_login}"
                    else:
                        last_login_str = dt.strftime("%m-%d %H:%M")
                except:
                    last_login_str = last_login
            else:
                last_login_str = "-"

            self._set_cell(self.users_table, row, 8, last_login_str)

            # IP
            self._set_cell(self.users_table, row, 9, user.get("last_login_ip", "-"))

            # 접속 상태 (마지막 로그인이 5분 이내면 온라인으로 간주)
            is_online = False
            if last_login and user.get("last_login_at"):
                try:
                    last_dt = datetime.fromisoformat(
                        user.get("last_login_at").replace("Z", "+00:00")
                    )
                    if (now - last_dt.replace(tzinfo=None)).total_seconds() < 300:
                        is_online = True
                        online_count += 1
                except:
                    pass
            online_text = "ON" if is_online else "OFF"
            online_color = DARK["online"] if is_online else DARK["offline"]
            self._set_cell(self.users_table, row, 10, online_text, online_color)

            # 현재 작업 (세션 정보에서 가져올 수 있음 - 현재는 미구현)
            current_task = user.get("current_task", "-")
            self._set_cell(self.users_table, row, 11, current_task)

            # 작업 버튼
            widget = self._create_user_actions(
                user.get("id"),
                user.get("username"),
                row,
                user.get("hashed_password"),  # 비밀번호 해시 전달
            )
            self.users_table.setCellWidget(row, 12, widget)

        self.online_label.setText(str(online_count))
        self.active_sub_label.setText(str(active_sub_count))

    def _set_cell(self, table, row, col, text, color=None):
        """셀 설정"""
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setTextAlignment(Qt.AlignCenter)
        # 항상 텍스트 색상 설정 (기본: 흰색)
        item.setForeground(QBrush(QColor(color if color else DARK["text"])))
        # 행 번호에 따른 배경색 설정 (교차 색상)
        bg_color = DARK["table_alt"] if row % 2 == 1 else DARK["table_bg"]
        item.setBackground(QBrush(QColor(bg_color)))
        table.setItem(row, col, item)

    def _create_user_actions(
        self, user_id, username, row: int = 0, hashed_password: str = None
    ) -> QWidget:
        """사용자 작업 버튼 - 절대 좌표로 정확히 배치"""
        widget = QWidget()
        widget.setMinimumSize(350, 50)  # 버튼 추가로 넓힘
        bg_color = DARK["table_alt"] if row % 2 == 1 else DARK["table_bg"]
        widget.setStyleSheet(f"background-color: {bg_color};")

        btn_y = 10
        btn_h = 30
        btn_w = 55

        # 비밀번호 보기
        pw_btn = QPushButton("PW", widget)
        pw_btn.setGeometry(5, btn_y, 40, btn_h)
        pw_btn.setFont(QFont(FONT_FAMILY, 9))
        pw_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK["text_dim"]};
                color: white;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #a0a8b8;
            }}
        """)
        pw_btn.setCursor(Qt.PointingHandCursor)
        pw_btn.clicked.connect(
            lambda: self._show_password_info(username, hashed_password)
        )

        # 구독 연장
        extend_btn = QPushButton("연장", widget)
        extend_btn.setGeometry(50, btn_y, btn_w, btn_h)
        extend_btn.setFont(QFont(FONT_FAMILY, 9))
        extend_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK["info"]};
                color: white;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #82b1ff;
            }}
        """)
        extend_btn.setCursor(Qt.PointingHandCursor)
        extend_btn.clicked.connect(lambda: self._extend_subscription(user_id, username))

        # 상태 변경
        toggle_btn = QPushButton("상태", widget)
        toggle_btn.setGeometry(110, btn_y, btn_w, btn_h)
        toggle_btn.setFont(QFont(FONT_FAMILY, 9))
        toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK["warning"]};
                color: black;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #ffecb3;
            }}
        """)
        toggle_btn.setCursor(Qt.PointingHandCursor)
        toggle_btn.clicked.connect(lambda: self._toggle_user(user_id, username))

        # 이력 보기
        history_btn = QPushButton("이력", widget)
        history_btn.setGeometry(170, btn_y, btn_w, btn_h)
        history_btn.setFont(QFont(FONT_FAMILY, 9))
        history_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK["card"]};
                color: {DARK["text"]};
                border: 1px solid {DARK["border"]};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {DARK["border"]};
            }}
        """)
        history_btn.setCursor(Qt.PointingHandCursor)
        history_btn.clicked.connect(lambda: self._show_login_history(user_id, username))

        # 삭제
        delete_btn = QPushButton("삭제", widget)
        delete_btn.setGeometry(230, btn_y, btn_w, btn_h)
        delete_btn.setFont(QFont(FONT_FAMILY, 9))
        delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK["danger"]};
                color: white;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #ff8a80;
            }}
        """)
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.clicked.connect(lambda: self._delete_user(user_id, username))

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
        dialog.setStyleSheet(f"background-color: {DARK['card']};")

        title_lbl = QLabel(f"'{username}' 비밀번호 해시 정보:", dialog)
        title_lbl.setGeometry(30, 25, 440, 25)
        title_lbl.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        title_lbl.setStyleSheet(f"color: {DARK['text']};")

        # 보안 경고 메시지 강화
        warning_lbl = QLabel("⚠️ 보안 경고: 비밀번호 해시는 민감한 정보입니다.", dialog)
        warning_lbl.setGeometry(30, 55, 440, 20)
        warning_lbl.setFont(QFont(FONT_FAMILY, 10, QFont.Bold))
        warning_lbl.setStyleSheet(f"color: {DARK['warning']};")

        warning2_lbl = QLabel("이 정보는 관리자 권한으로만 확인 가능합니다.", dialog)
        warning2_lbl.setGeometry(30, 75, 440, 20)
        warning2_lbl.setFont(QFont(FONT_FAMILY, 9))
        warning2_lbl.setStyleSheet(f"color: {DARK['danger']};")

        info_lbl = QLabel("필요한 경우에만 확인하고, 무단 공유를 금지합니다.", dialog)
        info_lbl.setGeometry(30, 95, 440, 20)
        info_lbl.setFont(QFont(FONT_FAMILY, 9))
        info_lbl.setStyleSheet(f"color: {DARK['text_dim']};")

        hash_edit = QLineEdit(dialog)
        hash_edit.setGeometry(30, 125, 440, 40)
        hash_edit.setText(masked_hash)
        hash_edit.setReadOnly(True)
        hash_edit.setFont(QFont("Consolas", 9))
        hash_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {DARK["bg"]};
                color: {DARK["text"]};
                border: 1px solid {DARK["border"]};
                border-radius: 6px;
                padding: 8px;
            }}
        """)

        note_lbl = QLabel(
            "※ 보안상 비밀번호는 해시 형태로만 저장됩니다.\n   원본 비밀번호는 복구할 수 없습니다.",
            dialog,
        )
        note_lbl.setGeometry(30, 175, 440, 40)
        note_lbl.setFont(QFont(FONT_FAMILY, 9))
        note_lbl.setStyleSheet(f"color: {DARK['text_dim']};")

        # 추가 보안 정보
        security_lbl = QLabel(
            "※ 해시 알고리즘: bcrypt (안전한 비밀번호 저장)\n※ 마스킹 처리: 보안상 전체 해시 표시 제한",
            dialog,
        )
        security_lbl.setGeometry(30, 215, 440, 40)
        security_lbl.setFont(QFont(FONT_FAMILY, 9))
        security_lbl.setStyleSheet(f"color: {DARK['info']};")

        close_btn = QPushButton("닫기", dialog)
        close_btn.setGeometry(370, 265, 100, 35)
        close_btn.setFont(QFont(FONT_FAMILY, 10))
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK["bg"]};
                color: {DARK["text"]};
                border: 1px solid {DARK["border"]};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {DARK["border"]};
            }}
        """)
        close_btn.clicked.connect(dialog.accept)

        dialog.exec_()

    def _on_search_changed(self, text):
        self._load_users()

    def _on_sub_filter_changed(self, text):
        self._load_subscriptions()

    def _load_subscriptions(self):
        """구독 요청 로드"""
        status_filter = self.sub_filter_combo.currentText()
        url = f"{self.api_base_url}/user/subscription/requests"
        if status_filter != "전체":
            status_map = {
                "대기 중": "PENDING",
                "승인됨": "APPROVED",
                "거부됨": "REJECTED",
            }
            url += f"?status={status_map.get(status_filter, '')}"

        worker = ApiWorker("GET", url, self._get_headers())
        worker.finished.connect(self._on_subscriptions_loaded)
        worker.error.connect(self._on_error)
        self.workers.append(worker)
        worker.start()

    def _on_subscriptions_loaded(self, data: dict):
        """구독 요청 목록 로드 완료"""
        items = data.get("requests", [])
        self.subscriptions_table.setRowCount(len(items))

        for row, req in enumerate(items):
            self.subscriptions_table.setRowHeight(row, 50)

            self._set_cell(self.subscriptions_table, row, 0, str(req.get("id", "")))
            self._set_cell(
                self.subscriptions_table, row, 1, str(req.get("user_id", ""))
            )
            self._set_cell(self.subscriptions_table, row, 2, req.get("username", ""))
            self._set_cell(
                self.subscriptions_table, row, 3, req.get("message", "") or "-"
            )

            # 요청 일시
            created = req.get("created_at", "")
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    created = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    pass
            self._set_cell(self.subscriptions_table, row, 4, created or "-")

            # 상태
            status = req.get("status", "")
            status_text = {
                "PENDING": "대기 중",
                "APPROVED": "승인됨",
                "REJECTED": "거부됨",
            }.get(status, status)
            status_color = {
                "PENDING": DARK["warning"],
                "APPROVED": DARK["success"],
                "REJECTED": DARK["danger"],
            }.get(status, DARK["text"])
            self._set_cell(self.subscriptions_table, row, 5, status_text, status_color)

            # 작업 버튼
            if status == "PENDING":
                widget = self._create_subscription_actions(req.get("id"), row)
                self.subscriptions_table.setCellWidget(row, 6, widget)
            else:
                self._set_cell(self.subscriptions_table, row, 6, "-")

    def _create_subscription_actions(self, request_id, row: int = 0) -> QWidget:
        """구독 요청 작업 버튼"""
        widget = QWidget()
        widget.setMinimumSize(200, 50)
        bg_color = DARK["table_alt"] if row % 2 == 1 else DARK["table_bg"]
        widget.setStyleSheet(f"background-color: {bg_color};")

        approve_btn = QPushButton("승인", widget)
        approve_btn.setGeometry(10, 10, 80, 30)
        approve_btn.setFont(QFont(FONT_FAMILY, 10))
        approve_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK["success"]};
                color: white;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #00e676;
            }}
        """)
        approve_btn.setCursor(Qt.PointingHandCursor)
        approve_btn.clicked.connect(lambda: self._approve_subscription(request_id))

        reject_btn = QPushButton("거부", widget)
        reject_btn.setGeometry(100, 10, 80, 30)
        reject_btn.setFont(QFont(FONT_FAMILY, 10))
        reject_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK["danger"]};
                color: white;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #ff8a80;
            }}
        """)
        reject_btn.setCursor(Qt.PointingHandCursor)
        reject_btn.clicked.connect(lambda: self._reject_subscription(request_id))

        return widget

    def _approve_subscription(self, request_id):
        """구독 승인 다이얼로그"""
        dialog = ApproveDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            days = dialog.get_days()
            work_count = dialog.get_work_count()
            url = f"{self.api_base_url}/user/subscription/approve"
            data = {
                "request_id": request_id,
                "subscription_days": days,
                "work_count": work_count,
            }
            worker = ApiWorker("POST", url, self._get_headers(), data)
            worker.finished.connect(lambda d: self._on_action_done("구독 승인", d))
            worker.error.connect(self._on_error)
            self.workers.append(worker)
            worker.start()

    def _reject_subscription(self, request_id):
        """구독 거부 다이얼로그"""
        dialog = RejectDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            reason = dialog.get_reason()
            url = f"{self.api_base_url}/user/subscription/reject"
            data = {"request_id": request_id, "admin_response": reason}
            worker = ApiWorker("POST", url, self._get_headers(), data)
            worker.finished.connect(lambda d: self._on_action_done("구독 거부", d))
            worker.error.connect(self._on_error)
            self.workers.append(worker)
            worker.start()

    def _extend_subscription(self, user_id, username):
        """구독 연장"""
        dialog = ExtendDialog(username, self)
        if dialog.exec_() == QDialog.Accepted:
            days = dialog.get_days()
            url = f"{self.api_base_url}/user/admin/users/{user_id}/extend"
            data = {"days": days}
            worker = ApiWorker("POST", url, self._get_headers(), data)
            worker.finished.connect(lambda d: self._on_action_done("구독 연장", d))
            worker.error.connect(self._on_error)
            self.workers.append(worker)
            worker.start()

    def _toggle_user(self, user_id, username):
        """사용자 상태 토글"""
        if not _styled_question_box(
            self, "상태 변경", f"'{username}' 사용자의 상태를 변경하시겠습니까?"
        ):
            return

        url = f"{self.api_base_url}/user/admin/users/{user_id}/toggle-active"
        worker = ApiWorker("POST", url, self._get_headers(), {})
        worker.finished.connect(lambda d: self._on_action_done("상태 변경", d))
        worker.error.connect(self._on_error)
        self.workers.append(worker)
        worker.start()

    def _show_login_history(self, user_id, username):
        """로그인 이력 보기"""
        dialog = LoginHistoryDialog(
            username, user_id, self.api_base_url, self._get_headers(), self
        )
        dialog.exec_()

    def _delete_user(self, user_id, username):
        """사용자 삭제"""
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
        self.workers.append(worker)
        worker.start()

    def _on_action_error(self, action, error):
        """작업 실패 시 에러 메시지 표시"""
        self._on_error(error)
        msg = _styled_msg_box(self, "오류", f"{action} 실패: {error}", "error")
        msg.exec_()
        self._load_data()

    def _on_action_done(self, action, data):
        if data.get("success"):
            msg = _styled_msg_box(
                self, "완료", f"{action} 처리가 완료되었습니다.", "info"
            )
            msg.exec_()
            self._load_data()
        else:
            msg = _styled_msg_box(
                self,
                "오류",
                data.get("message", "처리 중 오류가 발생했습니다."),
                "warning",
            )
            msg.exec_()

    def _on_error(self, error):
        self.connection_label.setText("연결 오류")
        self.connection_label.setStyleSheet(f"color: {DARK['danger']};")


class ApproveDialog(QDialog):
    """승인 다이얼로그 - 구독 기간 + 작업 횟수 설정"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("구독 승인")
        self.setFixedSize(420, 300)
        self.setStyleSheet(f"background-color: {DARK['card']};")
        self._setup_ui()

    def _setup_ui(self):
        # 구독 기간
        lbl = QLabel("구독 기간:", self)
        lbl.setGeometry(30, 25, 120, 25)
        lbl.setFont(QFont(FONT_FAMILY, 12))
        lbl.setStyleSheet(f"color: {DARK['text']};")

        self.days_spin = QSpinBox(self)
        self.days_spin.setGeometry(30, 55, 120, 40)
        self.days_spin.setFont(QFont(FONT_FAMILY, 14))
        self.days_spin.setRange(1, 365)
        self.days_spin.setValue(30)
        self.days_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: {DARK["bg"]};
                color: {DARK["text"]};
                border: 1px solid {DARK["border"]};
                border-radius: 6px;
                padding: 8px;
            }}
        """)

        day_lbl = QLabel("일", self)
        day_lbl.setGeometry(160, 63, 30, 25)
        day_lbl.setFont(QFont(FONT_FAMILY, 12))
        day_lbl.setStyleSheet(f"color: {DARK['text']};")

        # 작업 횟수
        work_lbl = QLabel("작업 횟수:", self)
        work_lbl.setGeometry(30, 110, 120, 25)
        work_lbl.setFont(QFont(FONT_FAMILY, 12))
        work_lbl.setStyleSheet(f"color: {DARK['text']};")

        self.unlimited_check = QPushButton("무제한", self)
        self.unlimited_check.setGeometry(230, 140, 80, 40)
        self.unlimited_check.setFont(QFont(FONT_FAMILY, 10))
        self.unlimited_check.setCheckable(True)
        self.unlimited_check.setChecked(True)
        self.unlimited_check.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK["success"]};
                color: white;
                border: none;
                border-radius: 6px;
            }}
            QPushButton:checked {{
                background-color: {DARK["success"]};
            }}
            QPushButton:!checked {{
                background-color: {DARK["bg"]};
                color: {DARK["text"]};
                border: 1px solid {DARK["border"]};
            }}
        """)
        self.unlimited_check.clicked.connect(self._toggle_unlimited)

        self.work_count_spin = QSpinBox(self)
        self.work_count_spin.setGeometry(30, 140, 120, 40)
        self.work_count_spin.setFont(QFont(FONT_FAMILY, 14))
        self.work_count_spin.setRange(1, 99999)
        self.work_count_spin.setValue(100)
        self.work_count_spin.setEnabled(False)
        self.work_count_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: {DARK["bg"]};
                color: {DARK["text"]};
                border: 1px solid {DARK["border"]};
                border-radius: 6px;
                padding: 8px;
            }}
            QSpinBox:disabled {{
                color: {DARK["text_dim"]};
            }}
        """)

        work_unit_lbl = QLabel("회", self)
        work_unit_lbl.setGeometry(160, 148, 30, 25)
        work_unit_lbl.setFont(QFont(FONT_FAMILY, 12))
        work_unit_lbl.setStyleSheet(f"color: {DARK['text']};")

        # 버튼
        cancel_btn = QPushButton("취소", self)
        cancel_btn.setGeometry(180, 240, 100, 40)
        cancel_btn.setFont(QFont(FONT_FAMILY, 11))
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK["bg"]};
                color: {DARK["text"]};
                border: 1px solid {DARK["border"]};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {DARK["border"]};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("승인", self)
        ok_btn.setGeometry(290, 240, 100, 40)
        ok_btn.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK["success"]};
                color: white;
                border: none;
                border-radius: 6px;
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
        self.setStyleSheet(f"background-color: {DARK['card']};")
        self._setup_ui()

    def _setup_ui(self):
        lbl = QLabel("거부 사유를 입력하세요 (선택사항):", self)
        lbl.setGeometry(30, 25, 360, 25)
        lbl.setFont(QFont(FONT_FAMILY, 12))
        lbl.setStyleSheet(f"color: {DARK['text']};")

        self.reason_edit = QTextEdit(self)
        self.reason_edit.setGeometry(30, 60, 360, 130)
        self.reason_edit.setFont(QFont(FONT_FAMILY, 11))
        self.reason_edit.setPlaceholderText("거부 사유 입력...")
        self.reason_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {DARK["bg"]};
                color: {DARK["text"]};
                border: 1px solid {DARK["border"]};
                border-radius: 6px;
                padding: 10px;
            }}
        """)

        cancel_btn = QPushButton("취소", self)
        cancel_btn.setGeometry(190, 210, 100, 40)
        cancel_btn.setFont(QFont(FONT_FAMILY, 11))
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK["bg"]};
                color: {DARK["text"]};
                border: 1px solid {DARK["border"]};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {DARK["border"]};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("거부", self)
        ok_btn.setGeometry(300, 210, 100, 40)
        ok_btn.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK["danger"]};
                color: white;
                border: none;
                border-radius: 6px;
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
        self.setStyleSheet(f"background-color: {DARK['card']};")
        self._setup_ui()

    def _setup_ui(self):
        lbl = QLabel(f"'{self.username}' 구독 연장 기간:", self)
        lbl.setGeometry(30, 30, 320, 25)
        lbl.setFont(QFont(FONT_FAMILY, 12))
        lbl.setStyleSheet(f"color: {DARK['text']};")

        self.days_spin = QSpinBox(self)
        self.days_spin.setGeometry(30, 70, 120, 40)
        self.days_spin.setFont(QFont(FONT_FAMILY, 14))
        self.days_spin.setRange(1, 365)
        self.days_spin.setValue(30)
        self.days_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: {DARK["bg"]};
                color: {DARK["text"]};
                border: 1px solid {DARK["border"]};
                border-radius: 6px;
                padding: 8px;
            }}
        """)

        day_lbl = QLabel("일 추가", self)
        day_lbl.setGeometry(160, 78, 60, 25)
        day_lbl.setFont(QFont(FONT_FAMILY, 12))
        day_lbl.setStyleSheet(f"color: {DARK['text']};")

        cancel_btn = QPushButton("취소", self)
        cancel_btn.setGeometry(150, 140, 100, 40)
        cancel_btn.setFont(QFont(FONT_FAMILY, 11))
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK["bg"]};
                color: {DARK["text"]};
                border: 1px solid {DARK["border"]};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {DARK["border"]};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("연장", self)
        ok_btn.setGeometry(260, 140, 100, 40)
        ok_btn.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK["info"]};
                color: white;
                border: none;
                border-radius: 6px;
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
        self.setStyleSheet(f"background-color: {DARK['card']};")
        self._setup_ui()
        self._load_history()

    def _setup_ui(self):
        title_lbl = QLabel(f"'{self.username}' 로그인 이력", self)
        title_lbl.setGeometry(30, 20, 640, 30)
        title_lbl.setFont(QFont(FONT_FAMILY, 14, QFont.Bold))
        title_lbl.setStyleSheet(f"color: {DARK['text']};")

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
        self.history_table.setFont(QFont(FONT_FAMILY, 10))
        self.history_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {DARK["table_bg"]};
                color: {DARK["text"]};
                border: 1px solid {DARK["border"]};
                border-radius: 6px;
                gridline-color: {DARK["border"]};
            }}
            QTableWidget::item {{
                padding: 8px;
                color: {DARK["text"]};
                background-color: {DARK["table_bg"]};
            }}
            QHeaderView::section {{
                background-color: {DARK["table_header"]};
                color: {DARK["text"]};
                font-weight: bold;
                padding: 10px;
                border: none;
            }}
        """)
        self.history_table.verticalHeader().setVisible(False)

        # 닫기 버튼
        close_btn = QPushButton("닫기", self)
        close_btn.setGeometry(560, 450, 100, 40)
        close_btn.setFont(QFont(FONT_FAMILY, 11))
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK["bg"]};
                color: {DARK["text"]};
                border: 1px solid {DARK["border"]};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {DARK["border"]};
            }}
        """)
        close_btn.clicked.connect(self.accept)

    def _load_history(self):
        """로그인 이력 로드 (현재는 세션 테이블에서 가져옴)"""
        # 실제로는 API에서 로그인 이력을 가져와야 함
        # 현재는 샘플 데이터 표시
        try:
            url = f"{self.api_base_url}/user/admin/users/{self.user_id}"
            resp = requests.get(url, headers=self.headers, timeout=30)
            if resp.status_code == 200:
                user = resp.json()
                # 단일 사용자 정보만 있으므로 마지막 로그인 정보만 표시
                self.history_table.setRowCount(1)
                last_login = user.get("last_login_at", "-")
                if last_login and last_login != "-":
                    try:
                        dt = datetime.fromisoformat(last_login.replace("Z", "+00:00"))
                        last_login = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        pass

                self._set_history_cell(0, 0, last_login)
                self._set_history_cell(0, 1, user.get("last_login_ip", "-"))
                self._set_history_cell(0, 2, "-")
                self._set_history_cell(0, 3, "성공", DARK["success"])
        except Exception as e:
            self.history_table.setRowCount(1)
            self._set_history_cell(0, 0, f"로드 실패: {str(e)[:50]}", DARK["danger"])

    def _set_history_cell(self, row, col, text, color=None):
        """히스토리 테이블 셀 설정"""
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        item.setForeground(QBrush(QColor(color if color else DARK["text"])))
        item.setBackground(QBrush(QColor(DARK["table_bg"])))
        self.history_table.setItem(row, col, item)
