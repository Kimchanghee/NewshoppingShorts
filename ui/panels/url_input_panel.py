"""
URL Input Panel for PyQt6
Refactored to integrity with Main Shell Design System
"""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QWidget
)
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QFont
from ui.design_system_v2 import get_design_system, get_color

class URLInputPanel(QWidget):
    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.ds = get_design_system()
        self.create_widgets()
        
    def create_widgets(self):
        ds = self.ds
        
        # Main vertical layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(ds.spacing.space_5)

        # 1. Input Area
        input_container = QVBoxLayout()
        input_container.setSpacing(ds.spacing.space_2)
        
        lbl = QLabel("쇼핑몰 상품 링크 또는 영상 URL 입력")
        lbl.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_sm, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {get_color('text_primary')};")
        input_container.addWidget(lbl)
        
        self.gui.url_entry = QTextEdit()
        self.gui.url_entry.setFixedHeight(120)
        self.gui.url_entry.setPlaceholderText("https://www.tiktok.com/@user/video/...\nhttps://smartstore.naver.com/...")
        self.gui.url_entry.setStyleSheet(self._get_input_style())
        input_container.addWidget(self.gui.url_entry)
        
        hint = QLabel("💡 팁: 여러 개의 링크를 붙여넣으면 자동으로 분리하여 목록에 추가됩니다.")
        hint.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        hint.setStyleSheet(f"color: {get_color('text_muted')};")
        input_container.addWidget(hint)
        
        self.main_layout.addLayout(input_container)

        # 2. Action Area
        action_layout = QHBoxLayout()
        action_layout.setSpacing(ds.spacing.space_3)
        
        from PyQt6.QtWidgets import QPushButton
        
        # Add Button
        self.add_btn = QPushButton("목록에 추가")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setStyleSheet(self._get_button_style("primary", "md"))
        self.add_btn.clicked.connect(self.gui.add_url_from_entry)
        action_layout.addWidget(self.add_btn)
        
        # Clipboard Button
        self.clipboard_btn = QPushButton("클립보드에서 붙여넣기")
        self.clipboard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clipboard_btn.setStyleSheet(self._get_button_style("secondary", "md"))
        self.clipboard_btn.clicked.connect(self.gui.paste_and_extract)
        action_layout.addWidget(self.clipboard_btn)
        
        action_layout.addStretch()
        
        self.main_layout.addLayout(action_layout)
        
        self.main_layout.addStretch()

        # Enter key to add URL
        self.gui.url_entry.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Enter key triggers URL add (Shift+Enter for newline)"""
        if obj is self.gui.url_entry and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                    self.gui.add_url_from_entry()
                    return True
        return super().eventFilter(obj, event)

    def _get_input_style(self) -> str:
        """Get input style using design system v2."""
        ds = self.ds
        return f"""
            QTextEdit {{
                background-color: {get_color('surface_variant')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border')};
                border-radius: {ds.radius.base}px;
                padding: {ds.spacing.space_2}px;
                font-family: {ds.typography.font_family_primary};
                font-size: {ds.typography.size_sm}px;
            }}
            QTextEdit:focus {{
                border: 2px solid {get_color('primary')};
            }}
            QTextEdit::placeholder {{
                color: {get_color('text_muted')};
            }}
        """

    def _get_button_style(self, variant: str = "primary", size: str = "md") -> str:
        """Get button style using design system v2."""
        ds = self.ds
        btn_size = ds.get_button_size(size)
        
        if variant == "primary":
            bg_color = get_color('primary')
            text_color = "white"
            hover_bg = "#C41230"  # Darker shade of primary
        elif variant == "secondary":
            bg_color = get_color('surface_variant')
            text_color = get_color('text_primary')
            hover_bg = get_color('border_light')
        else:  # ghost
            bg_color = "transparent"
            text_color = get_color('text_secondary')
            hover_bg = get_color('surface_variant')
        
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: none;
                border-radius: {ds.radius.base}px;
                padding: 0 {btn_size.padding_x}px;
                height: {btn_size.height}px;
                font-family: {ds.typography.font_family_primary};
                font-size: {btn_size.font_size}px;
                font-weight: {ds.typography.weight_medium};
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
            }}
        """

