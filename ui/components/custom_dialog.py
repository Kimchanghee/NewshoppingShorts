"""
Custom dialog components with theme support for PyQt6
Uses the design system v2 for consistent styling.
"""
import re
from typing import Optional, List, Tuple, Callable
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QWidget, QApplication
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QIcon

from ..design_system_v2 import get_design_system, get_color


_TITLE_MAP = {
    "done": "완료",
    "success": "완료",
    "error": "오류",
    "warning": "경고",
    "info": "안내",
    "confirm": "확인",
    "confirmation": "확인",
}

_BUTTON_MAP = {
    "ok": "확인",
    "yes": "예",
    "no": "아니오",
    "cancel": "취소",
}

_INPUT_ADDED_PATTERN = re.compile(r"^\s*Input added\s+(\d+)\s+URL\(s\)\.?\s*$", re.IGNORECASE)


def _localize_title(title: str) -> str:
    raw = (title or "").strip()
    if not raw:
        return "안내"
    return _TITLE_MAP.get(raw.lower(), raw)


def _localize_button_text(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return raw
    return _BUTTON_MAP.get(raw.lower(), raw)


def _localize_message(message: str) -> str:
    raw = (message or "").strip()
    if not raw:
        return raw

    match = _INPUT_ADDED_PATTERN.match(raw)
    if match:
        return f"입력한 링크 {match.group(1)}개를 추가했습니다."

    for eng, kor in (
        ("waiting", "대기"),
        ("processing", "진행 중"),
        ("completed", "완료"),
        ("done", "완료"),
        ("disabled", "사용 안 함"),
        ("enabled", "사용"),
        ("connected", "연결됨"),
    ):
        raw = re.sub(rf"\b{re.escape(eng)}\b", kor, raw, flags=re.IGNORECASE)
    return raw


class CustomDialog(QDialog):
    """Custom dialog with theme support for PyQt6"""

    def __init__(self, parent, title, message, dialog_type="info", buttons=None, theme_manager=None):
        super().__init__(parent)
        self.result_value = None
        self.ds = get_design_system()
        title = _localize_title(title)
        message = _localize_message(message)
        self.setWindowTitle(title)
        self.setModal(True)
        
        # Get colors from design system
        self.bg_color = get_color('background')
        self.card_bg = get_color('surface')
        self.text_color = get_color('text_primary')
        self.secondary_text = get_color('text_secondary')
        self.accent_color = get_color('primary')
        
        self.setStyleSheet(f"background-color: {self.bg_color}; border: none;")
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Container frame
        container = QFrame()
        container.setStyleSheet(f"background-color: {self.card_bg}; margin: 2px; border-radius: {self.ds.radius.base}px;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(self.ds.spacing.space_6, self.ds.spacing.space_6, self.ds.spacing.space_6, self.ds.spacing.space_6)
        container_layout.setSpacing(self.ds.spacing.space_4)
        
        # Header (Icon + Title)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(self.ds.spacing.space_3)
        
        # Type-specific icon/color
        icon_map = {
            "info": ("i", get_color('info')),
            "warning": ("!", get_color('warning')),
            "error": ("x", get_color('error')),
            "question": ("?", get_color('info')),
            "success": ("v", get_color('success'))
        }
        icon_char, icon_color = icon_map.get(dialog_type, ("i", self.accent_color))
        
        icon_label = QLabel(icon_char)
        icon_label.setFixedSize(28, 28)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            background-color: {icon_color};
            color: white;
            border-radius: 14px;
            font-weight: bold;
            font-size: {self.ds.typography.size_base}px;
        """)
        header_layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {self.text_color}; font-size: {self.ds.typography.size_base}px; font-weight: bold;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        container_layout.addLayout(header_layout)
        
        # Message
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet(f"color: {self.secondary_text}; font-size: {self.ds.typography.size_sm}px;")
        container_layout.addWidget(msg_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        if buttons is None:
            buttons = [("확인", lambda: self.done_with_result(True))]
        else:
            buttons = [(_localize_button_text(text), callback) for text, callback in buttons]
            
        for text, callback in buttons:
            btn = QPushButton(text)
            is_primary = text in ["확인", "예"]
            
            # Get button size from design system
            btn_size = self.ds.get_button_size('md')
            
            if is_primary:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {self.accent_color};
                        color: white;
                        border-radius: {self.ds.radius.sm}px;
                        padding: {self.ds.spacing.space_2}px {self.ds.spacing.space_5}px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{
                        background-color: {get_color('secondary')};
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {get_color('surface_variant')};
                        color: {self.text_color};
                        border-radius: {self.ds.radius.sm}px;
                        padding: {self.ds.spacing.space_2}px {self.ds.spacing.space_5}px;
                    }}
                    QPushButton:hover {{
                        background-color: {get_color('border')};
                    }}
                """)
            
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(callback)
            button_layout.addWidget(btn)
            
        container_layout.addLayout(button_layout)
        layout.addWidget(container)
        
        # Resize based on content
        self.adjustSize()
        if self.width() < 350:
            self.setFixedWidth(350)

    def done_with_result(self, result):
        self.result_value = result
        self.accept()

    def show_and_wait(self):
        self.exec()
        return self.result_value


def show_info(parent, title, message):
    return CustomDialog(parent, title, message, "info").show_and_wait()

def show_warning(parent, title, message):
    return CustomDialog(parent, title, message, "warning").show_and_wait()

def show_error(parent, title, message):
    return CustomDialog(parent, title, message, "error").show_and_wait()

def show_question(parent, title, message):
    # Lambda closures are late-binding: dialog is resolved at click time, not creation time
    dialog = CustomDialog(
        parent, title, message, "question",
        buttons=[
            ("아니오", lambda: dialog.done_with_result(False)),
            ("예", lambda: dialog.done_with_result(True)),
        ]
    )
    return dialog.show_and_wait()

def show_success(parent, title, message):
    return CustomDialog(parent, title, message, "success").show_and_wait()
