"""
Custom dialog components with theme support for PyQt6
Uses the design system v2 for consistent styling.
"""
import re
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QApplication, QGraphicsDropShadowEffect,
    QAbstractScrollArea, QScrollArea,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QMouseEvent

from ..design_system_v2 import get_design_system, get_color
from user_facing_errors import sanitize_user_message


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

_TYPE_META = {
    "info": ("i", "안내", "info"),
    "warning": ("!", "주의", "warning"),
    "error": ("×", "오류", "error"),
    "question": ("?", "확인", "info"),
    "success": ("✓", "완료", "success"),
}


class _DialogTitleBar(QFrame):
    """Draggable in-app title bar for the frameless alert surface."""

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None and hasattr(handle, "startSystemMove"):
                handle.startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)


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
    raw = sanitize_user_message(message, fallback="잠시 후 다시 시도해 주세요.").strip()
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
        dialog_type = dialog_type if dialog_type in _TYPE_META else "info"
        icon_char, status_text, status_color_name = _TYPE_META[dialog_type]
        icon_color = get_color(status_color_name)
        self.setObjectName("customAlertDialog")
        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAccessibleName(title)
        self.setAccessibleDescription(message)
        
        # Get colors from design system
        self.bg_color = get_color('background')
        self.card_bg = get_color('surface')
        self.text_color = get_color('text_primary')
        self.secondary_text = get_color('text_secondary')
        self.accent_color = get_color('primary')
        
        self.setStyleSheet("QDialog#customAlertDialog { background: transparent; border: none; }")
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        
        # Container frame
        container = QFrame()
        container.setObjectName("dialogSurface")
        container.setStyleSheet(f"""
            QFrame#dialogSurface {{
                background-color: {self.card_bg};
                border: 1px solid {get_color('border_medium')};
                border-radius: {self.ds.radius.lg}px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect(container)
        shadow.setBlurRadius(42)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 185))
        container.setGraphicsEffect(shadow)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, self.ds.spacing.space_6)
        container_layout.setSpacing(self.ds.spacing.space_5)

        # Branded chrome replaces the mismatched native white Windows title bar.
        title_bar = _DialogTitleBar(container)
        title_bar.setObjectName("dialogTitleBar")
        title_bar.setFixedHeight(54)
        title_bar.setStyleSheet(f"""
            QFrame#dialogTitleBar {{
                background: transparent;
                border: none;
                border-bottom: 1px solid {get_color('border_light')};
                border-top-left-radius: {self.ds.radius.lg}px;
                border-top-right-radius: {self.ds.radius.lg}px;
            }}
        """)
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(20, 0, 12, 0)
        title_bar_layout.setSpacing(10)

        brand_mark = QFrame(title_bar)
        brand_mark.setFixedSize(9, 9)
        brand_mark.setStyleSheet(
            f"background: {get_color('primary')}; border: none; border-radius: 4px;"
        )
        title_bar_layout.addWidget(brand_mark)

        brand_label = QLabel("SSMaker", title_bar)
        brand_label.setStyleSheet(f"""
            color: {self.text_color}; background: transparent; border: none;
            font-family: {self.ds.typography.font_family_primary};
            font-size: {self.ds.typography.size_sm}px;
            font-weight: {self.ds.typography.weight_bold};
        """)
        title_bar_layout.addWidget(brand_label)

        chrome_label = QLabel("알림", title_bar)
        chrome_label.setStyleSheet(f"""
            color: {get_color('text_muted')}; background: transparent; border: none;
            font-family: {self.ds.typography.font_family_primary};
            font-size: {self.ds.typography.size_xs}px;
        """)
        title_bar_layout.addWidget(chrome_label)
        title_bar_layout.addStretch()

        close_button = QPushButton("×", title_bar)
        close_button.setObjectName("dialogCloseButton")
        close_button.setAccessibleName("알림 닫기")
        close_button.setFixedSize(34, 34)
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.setStyleSheet(f"""
            QPushButton#dialogCloseButton {{
                background: transparent; color: {get_color('text_muted')};
                border: none; border-radius: {self.ds.radius.base}px;
                font-size: 22px;
            }}
            QPushButton#dialogCloseButton:hover {{
                background: {get_color('surface_variant')};
                color: {self.text_color};
            }}
        """)
        close_button.clicked.connect(self.reject)
        title_bar_layout.addWidget(close_button)
        container_layout.addWidget(title_bar)

        body = QFrame(container)
        body.setObjectName("dialogBody")
        body.setStyleSheet("QFrame#dialogBody { background: transparent; border: none; }")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(
            self.ds.spacing.space_6, 0,
            self.ds.spacing.space_6, 0,
        )
        body_layout.setSpacing(self.ds.spacing.space_5)
        
        # Header (Icon + Title)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(self.ds.spacing.space_3)
        
        icon_label = QLabel(icon_char)
        icon_label.setObjectName("dialogStatusIcon")
        icon_label.setFixedSize(40, 40)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            background-color: {get_color('surface_variant')};
            color: {icon_color};
            border: 1px solid {icon_color};
            border-radius: 20px;
            font-weight: bold;
            font-size: {self.ds.typography.size_md}px;
        """)
        header_layout.addWidget(icon_label)

        heading_copy = QVBoxLayout()
        heading_copy.setSpacing(3)
        status_label = QLabel(status_text)
        status_label.setStyleSheet(f"""
            color: {icon_color}; background: transparent; border: none;
            font-size: {self.ds.typography.size_xs}px;
            font-weight: {self.ds.typography.weight_bold};
        """)
        heading_copy.addWidget(status_label)

        title_label = QLabel(title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet(f"""
            color: {self.text_color}; background: transparent; border: none;
            font-size: {self.ds.typography.size_md}px;
            font-weight: {self.ds.typography.weight_bold};
        """)
        heading_copy.addWidget(title_label)
        header_layout.addLayout(heading_copy)
        header_layout.addStretch()
        body_layout.addLayout(header_layout)

        # Message
        message_panel = QFrame(body)
        message_panel.setObjectName("dialogMessagePanel")
        message_panel.setStyleSheet(f"""
            QFrame#dialogMessagePanel {{
                background-color: {get_color('surface_variant')};
                border: 1px solid {get_color('border_light')};
                border-radius: {self.ds.radius.base}px;
            }}
        """)
        message_layout = QVBoxLayout(message_panel)
        message_layout.setContentsMargins(16, 14, 16, 14)
        msg_label = QLabel(message, message_panel)
        msg_label.setObjectName("dialogMessageLabel")
        msg_label.setWordWrap(True)
        msg_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        msg_label.setStyleSheet(f"""
            color: {self.secondary_text}; background: transparent; border: none;
            font-size: {self.ds.typography.size_sm}px;
        """)
        message_layout.addWidget(msg_label)
        message_scroll = QScrollArea(body)
        message_scroll.setObjectName("dialogMessageScroll")
        message_scroll.setWidgetResizable(True)
        message_scroll.setFrameShape(QFrame.Shape.NoFrame)
        message_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        message_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        message_scroll.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents
        )
        screen = self.screen() or QApplication.primaryScreen()
        available_height = screen.availableGeometry().height() if screen else 720
        message_scroll.setMaximumHeight(min(320, max(140, available_height - 340)))
        message_scroll.setStyleSheet(f"""
            QScrollArea#dialogMessageScroll {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 8px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {get_color('border_medium')};
                border-radius: 4px;
                min-height: 28px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {get_color('primary')};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """)
        message_scroll.setWidget(message_panel)
        body_layout.addWidget(message_scroll)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()
        
        if buttons is None:
            buttons = [("확인", lambda: self.done_with_result(True))]
        else:
            buttons = [(_localize_button_text(text), callback) for text, callback in buttons]
            
        self._default_button = None
        for text, callback in buttons:
            btn = QPushButton(text)
            is_primary = text in {"확인", "예", "다시 시도", "계속"}
            btn.setObjectName(
                "dialogPrimaryButton" if is_primary else "dialogSecondaryButton"
            )
            
            # Get button size from design system
            btn_size = self.ds.get_button_size('md')
            btn.setMinimumSize(88, max(44, btn_size.height))
            btn.setAccessibleName(text)
            
            if is_primary:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {self.accent_color};
                        color: white;
                        border: none;
                        border-radius: {self.ds.radius.base}px;
                        padding: 0 {self.ds.spacing.space_5}px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{
                        background-color: {get_color('secondary')};
                    }}
                """)
                btn.setDefault(True)
                self._default_button = btn
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {get_color('surface_variant')};
                        color: {self.text_color};
                        border: 1px solid {get_color('border_medium')};
                        border-radius: {self.ds.radius.base}px;
                        padding: 0 {self.ds.spacing.space_5}px;
                    }}
                    QPushButton:hover {{
                        background-color: {get_color('border')};
                    }}
                """)
            
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(callback)
            button_layout.addWidget(btn)
            
        body_layout.addLayout(button_layout)
        container_layout.addWidget(body)
        layout.addWidget(container)
        
        # Resize based on content
        self.adjustSize()
        screen = self.screen() or QApplication.primaryScreen()
        available_width = screen.availableGeometry().width() if screen else 520
        self.setFixedWidth(min(520, max(390, available_width - 48)))
        if self._default_button is not None:
            self._default_button.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def done_with_result(self, result):
        self.result_value = result
        self.accept()

    def show_and_wait(self):
        self.exec()
        return self.result_value

    def keyPressEvent(self, event):  # noqa: N802 - Qt API
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._default_button is not None:
                self._default_button.click()
                event.accept()
                return
        elif event.key() == Qt.Key.Key_Escape:
            self.reject()
            event.accept()
            return
        super().keyPressEvent(event)


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
