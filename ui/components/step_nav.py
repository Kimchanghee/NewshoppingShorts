"""
Step navigation bar for the main shell (PyQt6).
Modernized with Design System V2 - Clean icon-based design.
"""
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QPushButton, QSizePolicy, 
    QLabel, QHBoxLayout, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QFont, QColor

from ui.design_system_v2 import get_design_system, get_color


# Icon mapping: step_id -> Unicode symbol (clean, minimal style)
STEP_ICONS = {
    "mode": "◐",        # Mode selection
    "source": "◎",      # Target/source
    "voice": "♪",       # Music/voice
    "cta": "▶",         # Play/action
    "font": "A",        # Font
    "watermark": "◈",   # Watermark
    "queue": "≡",       # List/queue
    "settings": "⚙",   # Settings gear
}


class StepButton(QPushButton):
    """Custom styled navigation button - STITCH 디자인 적용"""
    def __init__(self, step_id, label, icon_key, parent=None):
        super().__init__(parent)
        self.step_id = step_id
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(48)  # STITCH: 48px 유지

        # Design System
        self.ds = get_design_system()

        # Layout - STITCH: 간격 최적화
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            self.ds.spacing.space_4,  # 16px (STITCH 디자인)
            self.ds.spacing.space_3,  # 12px
            self.ds.spacing.space_4,  # 16px
            self.ds.spacing.space_3   # 12px
        )
        layout.setSpacing(self.ds.spacing.space_3)  # 12px 간격

        # Icon - STITCH: 크기 증가
        icon_char = STEP_ICONS.get(icon_key, "•")
        self.icon_label = QLabel(icon_char)
        self.icon_label.setFont(QFont("Segoe UI Symbol", 16))  # 14 → 16 (STITCH)
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        self.icon_label.setFixedWidth(24)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Text - STITCH: 폰트 크기 증가
        self.text_label = QLabel(label)
        self.text_label.setFont(QFont(
            self.ds.typography.font_family_body,  # Manrope 사용
            self.ds.typography.size_sm,           # 14px (STITCH)
            QFont.Weight.Medium
        ))
        self.text_label.setStyleSheet("background: transparent; border: none;")
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        layout.addStretch()
        
        # Initial Style
        self.update_style(False)

    def setChecked(self, checked):
        super().setChecked(checked)
        self.update_style(checked)

    def update_style(self, checked):
        """STITCH 디자인 스타일 적용"""
        if checked:
            # Active state - STITCH: 배경 + 왼쪽 보더 + Primary 색상
            bg = f"rgba(227, 22, 57, 0.1)"  # primary with 10% opacity
            text_color = get_color('text_primary')  # White text
            icon_color = get_color('primary')  # Red icon
            border = f"4px solid {get_color('primary')}"  # 3px → 4px (STITCH)
            font_weight = QFont.Weight.Bold
            border_radius = self.ds.radius.md  # 8px rounded (STITCH)
        else:
            # Inactive state - STITCH: 투명 배경, 회색 텍스트
            bg = "transparent"
            text_color = get_color('text_secondary')  # #A0A0A0
            icon_color = get_color('text_muted')      # #6B7280
            border = "4px solid transparent"
            font_weight = QFont.Weight.Medium
            border_radius = self.ds.radius.md

        self.setStyleSheet(f"""
            StepButton {{
                background-color: {bg};
                border: none;
                border-left: {border};
                border-radius: {border_radius}px;
                text-align: left;
                padding-left: 0px;
            }}
            StepButton:hover {{
                background-color: rgba(255, 255, 255, 0.03);
            }}
        """)
        
        self.text_label.setStyleSheet(f"color: {text_color}; background: transparent; border: none;")
        self.icon_label.setStyleSheet(f"color: {icon_color}; background: transparent; border: none;")
        
        f = self.text_label.font()
        f.setWeight(font_weight)
        self.text_label.setFont(f)


class StepNav(QFrame):
    """Left sidebar navigation - STITCH 디자인 적용"""
    step_selected = pyqtSignal(str)

    def __init__(self, steps, parent=None):
        super().__init__(parent)
        self.ds = get_design_system()
        self._buttons = {}

        self.setObjectName("StepNav")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setFixedWidth(280)  # STITCH: 280px (240px → 280px)
        
        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            0,
            self.ds.spacing.space_6,
            0,
            self.ds.spacing.space_6
        )
        layout.setSpacing(self.ds.spacing.space_1)
        
        # Styling
        self.setStyleSheet(f"""
            #StepNav {{
                background-color: {get_color('surface')};
                border-right: 1px solid {get_color('border_light')};
            }}
        """)

        # Add buttons
        for step_id, label, icon_key in steps:
            btn = StepButton(step_id, label, icon_key, self)
            btn.clicked.connect(lambda _, sid=step_id: self._on_click(sid))
            layout.addWidget(btn)
            self._buttons[step_id] = btn

        layout.addStretch()
        
        if steps:
            self.set_active(steps[0][0])

    def _on_click(self, step_id: str):
        self.set_active(step_id)
        self.step_selected.emit(step_id)

    def set_active(self, step_id: str):
        for sid, btn in self._buttons.items():
            btn.setChecked(sid == step_id)

    def get_button(self, step_id: str) -> StepButton | None:
        """step_id에 해당하는 버튼 위젯 반환 (튜토리얼 하이라이트용)"""
        return self._buttons.get(step_id)
