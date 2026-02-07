# -*- coding: utf-8 -*-
"""
API Key Error Dialog - Shows when all Gemini API keys are exhausted.

Pauses batch processing and allows users to:
1. Add a new API key in settings
2. Retry with available keys
3. Stop processing entirely
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
)
from PyQt6.QtGui import QFont

from utils.logging_config import get_logger

logger = get_logger(__name__)


class ApiKeyErrorDialog(QDialog):
    """
    API Key 오류 발생 시 일시정지 팝업.

    Signals:
        action_selected(str): "retry" | "settings" | "stop"
    """

    action_selected = pyqtSignal(str)

    def __init__(
        self,
        parent=None,
        step_name: str = "",
        key_name: str = "",
        error_msg: str = "",
        error_type: str = "quota",
    ):
        super().__init__(parent)
        self._result_action = "stop"
        self.setWindowTitle("API Key 오류 - 작업 일시정지")
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedWidth(480)
        # Modeless dialog: user must be able to interact with Settings to add keys.
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self._build_ui(step_name, key_name, error_msg, error_type)

    def _build_ui(self, step_name, key_name, error_msg, error_type):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header icon + title
        header = QHBoxLayout()
        icon_label = QLabel("⚠️")
        icon_label.setFont(QFont("Segoe UI Emoji", 28))
        icon_label.setFixedWidth(48)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)

        if error_type == "quota":
            title_text = "API 할당량 초과 (429)"
        elif error_type == "permission":
            title_text = "API 권한 오류 (403)"
        else:
            title_text = "API Key 오류"

        title = QLabel(title_text)
        title.setFont(QFont("Pretendard", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #DC2626;")

        subtitle = QLabel("작업이 일시정지 되었습니다")
        subtitle.setFont(QFont("Pretendard", 11))
        subtitle.setStyleSheet("color: #6B7280;")

        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        header.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
        header.addLayout(title_layout, 1)
        layout.addLayout(header)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #E5E7EB;")
        layout.addWidget(sep)

        # Error details
        details_layout = QVBoxLayout()
        details_layout.setSpacing(8)

        if step_name:
            step_row = self._info_row("작업 단계", step_name)
            details_layout.addLayout(step_row)

        if key_name and key_name != "unknown":
            key_row = self._info_row("오류 발생 키", key_name)
            details_layout.addLayout(key_row)

        if error_msg:
            display_msg = error_msg[:150] + "..." if len(error_msg) > 150 else error_msg
            err_row = self._info_row("오류 내용", display_msg)
            details_layout.addLayout(err_row)

        layout.addLayout(details_layout)

        # Info message
        info_frame = QFrame()
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(12, 12, 12, 12)

        # Check if it's a Google Drive permission error
        is_gdrive_error = False
        if error_type == "permission" and error_msg:
            lowered = error_msg.lower()
            if any(x in lowered for x in ["you do not have permission to access the file", "file not found", "permission denied"]):
                is_gdrive_error = True

        if is_gdrive_error:
            # Google Drive specific message
            info_frame.setStyleSheet(
                "background-color: #FFF7ED; border: 1px solid #FDBA74; border-radius: 8px; padding: 12px;"
            )
            info_text = QLabel(
                "⚠️ 구글 드라이브 파일 권한 오류\n\n"
                "이 오류는 API 키 문제가 아니라 파일 공유 설정 문제입니다.\n\n"
                "해결 방법:\n"
                "1. 구글 드라이브에서 해당 파일을 '링크가 있는 모든 사용자'로 공유\n"
                "2. 또는 OAuth 인증 방식으로 전환\n"
                "3. 또는 '작업 중지'를 눌러 해당 URL을 건너뛰기"
            )
            info_text.setStyleSheet("color: #9A3412; background: transparent; border: none;")
        else:
            # Standard message for quota errors
            info_frame.setStyleSheet(
                "background-color: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 8px; padding: 12px;"
            )
            info_text = QLabel(
                "설정에서 새 API 키를 추가한 후 '작업 계속하기'를 누르면\n"
                "남은 작업을 이어서 진행할 수 있습니다."
            )
            info_text.setStyleSheet("color: #1E40AF; background: transparent; border: none;")

        info_text.setFont(QFont("Pretendard", 10))
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)
        layout.addWidget(info_frame)

        layout.addSpacing(8)

        # Buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        # Primary: 작업 계속하기
        self.retry_btn = QPushButton("▶  작업 계속하기 (API 키 확인 후 재시도)")
        self.retry_btn.setFont(QFont("Pretendard", 12, QFont.Weight.Bold))
        self.retry_btn.setFixedHeight(44)
        self.retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retry_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 16px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
            QPushButton:pressed { background-color: #1E40AF; }
        """)
        self.retry_btn.clicked.connect(self._on_retry)
        btn_layout.addWidget(self.retry_btn)

        # Secondary row
        secondary_row = QHBoxLayout()
        secondary_row.setSpacing(8)

        # 설정 열기
        self.settings_btn = QPushButton("⚙  설정에서 API 키 추가")
        self.settings_btn.setFont(QFont("Pretendard", 11))
        self.settings_btn.setFixedHeight(40)
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                color: #374151;
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                padding: 0 16px;
            }
            QPushButton:hover { background-color: #E5E7EB; }
        """)
        self.settings_btn.clicked.connect(self._on_settings)
        secondary_row.addWidget(self.settings_btn)

        # 작업 중지
        self.stop_btn = QPushButton("■  작업 중지")
        self.stop_btn.setFont(QFont("Pretendard", 11))
        self.stop_btn.setFixedHeight(40)
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #FEF2F2;
                color: #DC2626;
                border: 1px solid #FECACA;
                border-radius: 8px;
                padding: 0 16px;
            }
            QPushButton:hover { background-color: #FEE2E2; }
        """)
        self.stop_btn.clicked.connect(self._on_stop)
        secondary_row.addWidget(self.stop_btn)

        btn_layout.addLayout(secondary_row)
        layout.addLayout(btn_layout)

    def _info_row(self, label_text, value_text):
        row = QHBoxLayout()
        label = QLabel(f"{label_text}:")
        label.setFont(QFont("Pretendard", 10, QFont.Weight.Bold))
        label.setStyleSheet("color: #374151;")
        label.setFixedWidth(90)

        value = QLabel(value_text)
        value.setFont(QFont("Pretendard", 10))
        value.setStyleSheet("color: #6B7280;")
        value.setWordWrap(True)

        row.addWidget(label, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(value, 1)
        return row

    def _on_retry(self):
        self._result_action = "retry"
        self.accept()

    def _on_settings(self):
        # Open settings page without closing dialog
        gui = self.parent()
        if gui and hasattr(gui, "_on_step_selected"):
            gui._on_step_selected("settings")
        else:
            logger.warning("[ApiKeyErrorDialog] Cannot navigate to settings - parent not available")

    def _on_stop(self):
        self._result_action = "stop"
        self.reject()

    @property
    def result_action(self) -> str:
        return self._result_action
