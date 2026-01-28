# -*- coding: utf-8 -*-
"""
Admin Dashboard for Shopping Shorts Maker
관리자 대시보드 - 다크모드, 절대 좌표 배치, 5초 자동 새로고침
"""

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QComboBox, QLineEdit,
    QMessageBox, QDialog, QSpinBox, QTextEdit
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
}


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
                resp = requests.post(self.url, headers=self.headers, json=self.data, timeout=30)
            elif self.method == "DELETE":
                resp = requests.delete(self.url, headers=self.headers, timeout=30)
            else:
                self.error.emit(f"Unknown method: {self.method}")
                return

            if resp.status_code == 200:
                self.finished.emit(resp.json())
            else:
                self.error.emit(f"Error {resp.status_code}: {resp.text}")
        except Exception as e:
            self.error.emit(str(e))


class AdminDashboard(QMainWindow):
    """관리자 대시보드"""

    def __init__(self, api_base_url: str, admin_api_key: str):
        super().__init__()
        self.api_base_url = api_base_url.rstrip('/')
        self.admin_api_key = admin_api_key
        self.workers = []
        self.current_tab = 0  # 0: 회원가입 요청, 1: 사용자 관리
        self._setup_ui()
        self._load_data()
        self._start_auto_refresh()

    def _get_headers(self) -> dict:
        return {"X-Admin-API-Key": self.admin_api_key, "Content-Type": "application/json"}

    def _start_auto_refresh(self):
        """5초마다 자동 새로고침"""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._load_data)
        self.refresh_timer.start(5000)

    def _setup_ui(self):
        self.setWindowTitle("관리자 대시보드")
        self.setFixedSize(1280, 800)
        self.setStyleSheet(f"background-color: {DARK['bg']};")

        # 중앙 위젯
        self.central = QWidget(self)
        self.setCentralWidget(self.central)

        # 타이틀
        title = QLabel("관리자 대시보드", self.central)
        title.setGeometry(40, 25, 400, 40)
        title.setFont(QFont(FONT_FAMILY, 22, QFont.Bold))
        title.setStyleSheet(f"color: {DARK['text']};")

        # 새로고침 버튼
        refresh_btn = QPushButton("새로고침", self.central)
        refresh_btn.setGeometry(1120, 25, 120, 40)
        refresh_btn.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK['primary']};
                color: white;
                border: none;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: {DARK['primary_hover']};
            }}
        """)
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self._load_data)

        # 통계 카드들 (Y: 85)
        self._create_stat_cards()

        # 탭 버튼들 (Y: 200)
        self._create_tab_buttons()

        # 필터/검색 영역 (Y: 260)
        self._create_filter_area()

        # 테이블 (Y: 310)
        self._create_tables()

    def _create_stat_cards(self):
        """통계 카드 생성 - 절대 좌표"""
        card_y = 85
        card_h = 90
        card_w = 280
        gap = 25

        # 대기 중 요청
        self._create_card(40, card_y, card_w, card_h, "대기 중 요청", DARK['warning'])
        self.pending_label = self._get_value_label(40, card_y, card_w, card_h)

        # 승인된 요청
        self._create_card(40 + card_w + gap, card_y, card_w, card_h, "승인된 요청", DARK['success'])
        self.approved_label = self._get_value_label(40 + card_w + gap, card_y, card_w, card_h)

        # 거부된 요청
        self._create_card(40 + (card_w + gap) * 2, card_y, card_w, card_h, "거부된 요청", DARK['danger'])
        self.rejected_label = self._get_value_label(40 + (card_w + gap) * 2, card_y, card_w, card_h)

        # 전체 사용자
        self._create_card(40 + (card_w + gap) * 3, card_y, card_w, card_h, "전체 사용자", DARK['info'])
        self.users_label = self._get_value_label(40 + (card_w + gap) * 3, card_y, card_w, card_h)

    def _create_card(self, x, y, w, h, title, color):
        """카드 생성"""
        card = QWidget(self.central)
        card.setGeometry(x, y, w, h)
        card.setStyleSheet(f"""
            background-color: {DARK['card']};
            border-radius: 12px;
            border-left: 4px solid {color};
        """)

        title_lbl = QLabel(title, card)
        title_lbl.setGeometry(20, 12, w - 40, 20)
        title_lbl.setFont(QFont(FONT_FAMILY, 11))
        title_lbl.setStyleSheet(f"color: {DARK['text_dim']}; background: transparent;")

    def _get_value_label(self, x, y, w, h) -> QLabel:
        """값 라벨 생성 및 반환"""
        lbl = QLabel("0", self.central)
        lbl.setGeometry(x + 20, y + 38, w - 40, 40)
        lbl.setFont(QFont(FONT_FAMILY, 28, QFont.Bold))
        lbl.setStyleSheet(f"color: {DARK['text']}; background: transparent;")
        return lbl

    def _create_tab_buttons(self):
        """탭 버튼 생성"""
        self.tab_requests = QPushButton("회원가입 요청", self.central)
        self.tab_requests.setGeometry(40, 200, 150, 42)
        self.tab_requests.setFont(QFont(FONT_FAMILY, 12, QFont.Bold))
        self.tab_requests.setCursor(Qt.PointingHandCursor)
        self.tab_requests.clicked.connect(lambda: self._switch_tab(0))

        self.tab_users = QPushButton("사용자 관리", self.central)
        self.tab_users.setGeometry(200, 200, 150, 42)
        self.tab_users.setFont(QFont(FONT_FAMILY, 12))
        self.tab_users.setCursor(Qt.PointingHandCursor)
        self.tab_users.clicked.connect(lambda: self._switch_tab(1))

        self._update_tab_styles()

    def _update_tab_styles(self):
        """탭 스타일 업데이트"""
        active = f"""
            QPushButton {{
                background-color: {DARK['card']};
                color: {DARK['primary']};
                border: none;
                border-bottom: 3px solid {DARK['primary']};
                border-radius: 0px;
            }}
        """
        inactive = f"""
            QPushButton {{
                background-color: transparent;
                color: {DARK['text_dim']};
                border: none;
                border-bottom: 3px solid transparent;
                border-radius: 0px;
            }}
            QPushButton:hover {{
                color: {DARK['text']};
            }}
        """
        self.tab_requests.setStyleSheet(active if self.current_tab == 0 else inactive)
        self.tab_users.setStyleSheet(active if self.current_tab == 1 else inactive)
        self.tab_requests.setFont(QFont(FONT_FAMILY, 12, QFont.Bold if self.current_tab == 0 else QFont.Normal))
        self.tab_users.setFont(QFont(FONT_FAMILY, 12, QFont.Bold if self.current_tab == 1 else QFont.Normal))

    def _switch_tab(self, tab_index):
        """탭 전환"""
        self.current_tab = tab_index
        self._update_tab_styles()
        self.requests_table.setVisible(tab_index == 0)
        self.users_table.setVisible(tab_index == 1)
        self.filter_combo.setVisible(tab_index == 0)
        self.filter_label.setVisible(tab_index == 0)
        self.search_edit.setVisible(tab_index == 1)
        self.search_label.setVisible(tab_index == 1)

    def _create_filter_area(self):
        """필터/검색 영역 생성"""
        # 회원가입 요청 필터
        self.filter_label = QLabel("상태 필터:", self.central)
        self.filter_label.setGeometry(40, 265, 80, 30)
        self.filter_label.setFont(QFont(FONT_FAMILY, 11))
        self.filter_label.setStyleSheet(f"color: {DARK['text']};")

        self.filter_combo = QComboBox(self.central)
        self.filter_combo.setGeometry(125, 262, 140, 36)
        self.filter_combo.setFont(QFont(FONT_FAMILY, 11))
        self.filter_combo.addItems(["전체", "대기 중", "승인됨", "거부됨"])
        self.filter_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {DARK['card']};
                color: {DARK['text']};
                border: 1px solid {DARK['border']};
                border-radius: 6px;
                padding: 5px 15px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {DARK['card']};
                color: {DARK['text']};
                selection-background-color: {DARK['primary']};
            }}
        """)
        self.filter_combo.currentTextChanged.connect(self._on_filter_changed)

        # 사용자 검색
        self.search_label = QLabel("아이디 검색:", self.central)
        self.search_label.setGeometry(40, 265, 90, 30)
        self.search_label.setFont(QFont(FONT_FAMILY, 11))
        self.search_label.setStyleSheet(f"color: {DARK['text']};")
        self.search_label.setVisible(False)

        self.search_edit = QLineEdit(self.central)
        self.search_edit.setGeometry(135, 262, 200, 36)
        self.search_edit.setFont(QFont(FONT_FAMILY, 11))
        self.search_edit.setPlaceholderText("검색어 입력...")
        self.search_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {DARK['card']};
                color: {DARK['text']};
                border: 1px solid {DARK['border']};
                border-radius: 6px;
                padding: 5px 15px;
            }}
            QLineEdit::placeholder {{
                color: {DARK['text_dim']};
            }}
        """)
        self.search_edit.textChanged.connect(self._on_search_changed)
        self.search_edit.setVisible(False)

    def _create_tables(self):
        """테이블 생성"""
        table_x = 40
        table_y = 310
        table_w = 1200
        table_h = 460

        # 회원가입 요청 테이블
        self.requests_table = QTableWidget(self.central)
        self.requests_table.setGeometry(table_x, table_y, table_w, table_h)
        self.requests_table.setColumnCount(6)
        self.requests_table.setHorizontalHeaderLabels(["ID", "가입자 명", "아이디", "연락처", "상태", "작업"])
        self._style_table(self.requests_table, [60, 180, 200, 200, 120, 300])

        # 사용자 관리 테이블
        self.users_table = QTableWidget(self.central)
        self.users_table.setGeometry(table_x, table_y, table_w, table_h)
        self.users_table.setColumnCount(6)
        self.users_table.setHorizontalHeaderLabels(["ID", "아이디", "구독 만료일", "상태", "로그인 횟수", "작업"])
        self._style_table(self.users_table, [60, 200, 180, 100, 120, 400])
        self.users_table.setVisible(False)

    def _style_table(self, table: QTableWidget, widths: list):
        """테이블 스타일"""
        table.setFont(QFont(FONT_FAMILY, 10))
        table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {DARK['table_bg']};
                color: {DARK['text']};
                border: 1px solid {DARK['border']};
                border-radius: 8px;
                gridline-color: {DARK['border']};
            }}
            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {DARK['border']};
            }}
            QTableWidget::item:selected {{
                background-color: {DARK['primary']};
            }}
            QHeaderView::section {{
                background-color: {DARK['table_header']};
                color: {DARK['text']};
                font-weight: bold;
                padding: 12px;
                border: none;
                border-bottom: 2px solid {DARK['primary']};
            }}
        """)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)

        for i, w in enumerate(widths):
            table.setColumnWidth(i, w)

    def _load_data(self):
        """데이터 로드"""
        self._load_requests()
        self._load_users()

    def _load_requests(self):
        """회원가입 요청 로드"""
        status_filter = self.filter_combo.currentText()
        url = f"{self.api_base_url}/user/register/requests"
        if status_filter != "전체":
            status_map = {"대기 중": "pending", "승인됨": "approved", "거부됨": "rejected"}
            url += f"?status={status_map.get(status_filter, '')}"

        worker = ApiWorker("GET", url, self._get_headers())
        worker.finished.connect(self._on_requests_loaded)
        worker.error.connect(self._on_error)
        self.workers.append(worker)
        worker.start()

    def _on_requests_loaded(self, data: dict):
        """요청 목록 로드 완료"""
        items = data.get("requests", [])
        self.requests_table.setRowCount(len(items))

        pending = approved = rejected = 0

        for row, req in enumerate(items):
            status = req.get("status", "")
            if status == "pending":
                pending += 1
            elif status == "approved":
                approved += 1
            elif status == "rejected":
                rejected += 1

            self._set_cell(self.requests_table, row, 0, str(req.get("id", "")))
            self._set_cell(self.requests_table, row, 1, req.get("name", ""))
            self._set_cell(self.requests_table, row, 2, req.get("username", ""))
            self._set_cell(self.requests_table, row, 3, req.get("contact", ""))

            # 상태
            status_text = {"pending": "대기 중", "approved": "승인됨", "rejected": "거부됨"}.get(status, status)
            status_color = {"pending": DARK['warning'], "approved": DARK['success'], "rejected": DARK['danger']}.get(status, DARK['text'])
            self._set_cell(self.requests_table, row, 4, status_text, status_color)

            # 작업 버튼
            if status == "pending":
                widget = self._create_request_actions(req.get("id"))
                self.requests_table.setCellWidget(row, 5, widget)
            else:
                self._set_cell(self.requests_table, row, 5, "-")

        self.pending_label.setText(str(pending))
        self.approved_label.setText(str(approved))
        self.rejected_label.setText(str(rejected))

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

        for row, user in enumerate(items):
            self._set_cell(self.users_table, row, 0, str(user.get("id", "")))
            self._set_cell(self.users_table, row, 1, user.get("username", ""))

            # 구독 만료일
            expires = user.get("subscription_expires_at", "")
            if expires:
                try:
                    dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                    expires = dt.strftime("%Y-%m-%d")
                except:
                    pass
            self._set_cell(self.users_table, row, 2, expires or "-")

            # 상태
            is_active = user.get("is_active", False)
            self._set_cell(self.users_table, row, 3, "활성" if is_active else "비활성",
                          DARK['success'] if is_active else DARK['danger'])

            # 로그인 횟수
            self._set_cell(self.users_table, row, 4, str(user.get("login_count", 0)))

            # 작업 버튼
            widget = self._create_user_actions(user.get("id"), user.get("username"))
            self.users_table.setCellWidget(row, 5, widget)

    def _set_cell(self, table, row, col, text, color=None):
        """셀 설정"""
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        if color:
            item.setForeground(QBrush(QColor(color)))
        table.setItem(row, col, item)

    def _create_request_actions(self, request_id) -> QWidget:
        """요청 작업 버튼"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")

        approve_btn = QPushButton("승인", widget)
        approve_btn.setGeometry(10, 5, 70, 30)
        approve_btn.setFont(QFont(FONT_FAMILY, 10))
        approve_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK['success']};
                color: white;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #00e676;
            }}
        """)
        approve_btn.setCursor(Qt.PointingHandCursor)
        approve_btn.clicked.connect(lambda: self._approve_request(request_id))

        reject_btn = QPushButton("거부", widget)
        reject_btn.setGeometry(90, 5, 70, 30)
        reject_btn.setFont(QFont(FONT_FAMILY, 10))
        reject_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK['danger']};
                color: white;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #ff8a80;
            }}
        """)
        reject_btn.setCursor(Qt.PointingHandCursor)
        reject_btn.clicked.connect(lambda: self._reject_request(request_id))

        return widget

    def _create_user_actions(self, user_id, username) -> QWidget:
        """사용자 작업 버튼"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")

        extend_btn = QPushButton("구독 연장", widget)
        extend_btn.setGeometry(10, 5, 90, 30)
        extend_btn.setFont(QFont(FONT_FAMILY, 10))
        extend_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK['info']};
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

        toggle_btn = QPushButton("상태 변경", widget)
        toggle_btn.setGeometry(110, 5, 90, 30)
        toggle_btn.setFont(QFont(FONT_FAMILY, 10))
        toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK['warning']};
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

        delete_btn = QPushButton("삭제", widget)
        delete_btn.setGeometry(210, 5, 70, 30)
        delete_btn.setFont(QFont(FONT_FAMILY, 10))
        delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK['danger']};
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

    def _on_filter_changed(self, text):
        self._load_requests()

    def _on_search_changed(self, text):
        self._load_users()

    def _approve_request(self, request_id):
        """승인 다이얼로그"""
        dialog = ApproveDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            days = dialog.get_days()
            url = f"{self.api_base_url}/user/register/approve"
            data = {"request_id": request_id, "subscription_days": days}
            worker = ApiWorker("POST", url, self._get_headers(), data)
            worker.finished.connect(lambda d: self._on_action_done("승인", d))
            worker.error.connect(self._on_error)
            self.workers.append(worker)
            worker.start()

    def _reject_request(self, request_id):
        """거부 다이얼로그"""
        dialog = RejectDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            reason = dialog.get_reason()
            url = f"{self.api_base_url}/user/register/reject"
            data = {"request_id": request_id, "reason": reason}
            worker = ApiWorker("POST", url, self._get_headers(), data)
            worker.finished.connect(lambda d: self._on_action_done("거부", d))
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
        reply = QMessageBox.question(self, "상태 변경",
            f"'{username}' 사용자의 상태를 변경하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            url = f"{self.api_base_url}/user/admin/users/{user_id}/toggle-active"
            worker = ApiWorker("POST", url, self._get_headers(), {})
            worker.finished.connect(lambda d: self._on_action_done("상태 변경", d))
            worker.error.connect(self._on_error)
            self.workers.append(worker)
            worker.start()

    def _delete_user(self, user_id, username):
        """사용자 삭제"""
        reply = QMessageBox.warning(self, "사용자 삭제",
            f"'{username}' 사용자를 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            url = f"{self.api_base_url}/user/admin/users/{user_id}"
            worker = ApiWorker("DELETE", url, self._get_headers())
            worker.finished.connect(lambda d: self._on_action_done("삭제", d))
            worker.error.connect(self._on_error)
            self.workers.append(worker)
            worker.start()

    def _on_action_done(self, action, data):
        if data.get("success"):
            QMessageBox.information(self, "완료", f"{action} 처리가 완료되었습니다.")
            self._load_data()
        else:
            QMessageBox.warning(self, "오류", data.get("message", "처리 중 오류가 발생했습니다."))

    def _on_error(self, error):
        # 자동 새로고침 중 에러는 무시 (연결 문제 등)
        pass


class ApproveDialog(QDialog):
    """승인 다이얼로그 - 다크모드"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("회원가입 승인")
        self.setFixedSize(380, 200)
        self.setStyleSheet(f"background-color: {DARK['card']};")
        self._setup_ui()

    def _setup_ui(self):
        lbl = QLabel("승인할 구독 기간을 선택하세요:", self)
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
                background-color: {DARK['bg']};
                color: {DARK['text']};
                border: 1px solid {DARK['border']};
                border-radius: 6px;
                padding: 8px;
            }}
        """)

        day_lbl = QLabel("일", self)
        day_lbl.setGeometry(160, 78, 30, 25)
        day_lbl.setFont(QFont(FONT_FAMILY, 12))
        day_lbl.setStyleSheet(f"color: {DARK['text']};")

        cancel_btn = QPushButton("취소", self)
        cancel_btn.setGeometry(150, 140, 100, 40)
        cancel_btn.setFont(QFont(FONT_FAMILY, 11))
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK['bg']};
                color: {DARK['text']};
                border: 1px solid {DARK['border']};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {DARK['border']};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("승인", self)
        ok_btn.setGeometry(260, 140, 100, 40)
        ok_btn.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK['success']};
                color: white;
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: #00e676;
            }}
        """)
        ok_btn.clicked.connect(self.accept)

    def get_days(self):
        return self.days_spin.value()


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
                background-color: {DARK['bg']};
                color: {DARK['text']};
                border: 1px solid {DARK['border']};
                border-radius: 6px;
                padding: 10px;
            }}
        """)

        cancel_btn = QPushButton("취소", self)
        cancel_btn.setGeometry(190, 210, 100, 40)
        cancel_btn.setFont(QFont(FONT_FAMILY, 11))
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK['bg']};
                color: {DARK['text']};
                border: 1px solid {DARK['border']};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {DARK['border']};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("거부", self)
        ok_btn.setGeometry(300, 210, 100, 40)
        ok_btn.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK['danger']};
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
                background-color: {DARK['bg']};
                color: {DARK['text']};
                border: 1px solid {DARK['border']};
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
                background-color: {DARK['bg']};
                color: {DARK['text']};
                border: 1px solid {DARK['border']};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {DARK['border']};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("연장", self)
        ok_btn.setGeometry(260, 140, 100, 40)
        ok_btn.setFont(QFont(FONT_FAMILY, 11, QFont.Bold))
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK['info']};
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
