# -*- coding: utf-8 -*-
"""
Admin Dashboard Dialogs
관리자 대시보드 다이얼로그 컴포넌트

분리된 다이얼로그 클래스들:
- ApproveDialog: 구독 승인 다이얼로그
- RejectDialog: 구독 거부 다이얼로그
- ExtendDialog: 구독 연장 다이얼로그
- LoginHistoryDialog: 로그인 이력 다이얼로그
"""

import logging
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
)
from PyQt6.QtGui import QFont, QColor, QBrush
import requests

from ui.design_system_v2 import get_design_system, get_color

ds = get_design_system()
FONT_FAMILY = "Noto Sans KR"
API_TIMEOUT = 30

logger = logging.getLogger(__name__)


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
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Login history datetime parsing failed: {e}")

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
