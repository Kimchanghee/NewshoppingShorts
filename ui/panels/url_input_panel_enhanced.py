# -*- coding: utf-8 -*-
"""
Enhanced URL Input Panel - Content Creator's Studio Theme

Features:
- EnhancedInput with focus animations
- Professional button styles
- Better visual hierarchy
- Improved spacing
"""

import logging
import os
import subprocess
import sys
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTextEdit, QFileDialog, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ui.components.base_widget_enhanced import (
    ThemedMixin, EnhancedLabel, EnhancedTextEdit,
    create_button, create_label, create_card
)

logger = logging.getLogger(__name__)


class EnhancedURLInputPanel(QFrame, ThemedMixin):
    """
    Enhanced URL input panel with professional styling

    Features:
    - Enhanced text input with focus states
    - Styled buttons with hover effects
    - Clear visual hierarchy
    - Better spacing and layout
    """

    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.__init_themed__(theme_manager)
        self.create_widgets()
        self.apply_theme()

    def create_widgets(self):
        # Main vertical layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(
            self.spacing.xl2,
            self.spacing.lg,
            self.spacing.xl2,
            self.spacing.lg
        )
        self.main_layout.setSpacing(self.spacing.lg)

        # Header: Title + Buttons
        header_layout = self._create_header()
        self.main_layout.addLayout(header_layout)

        # URL Entry Area
        self._create_url_input()

        # Example hint
        self.example_label = create_label(
            "예: https://www.tiktok.com/@username/video/...",
            variant="tertiary"
        )
        self.main_layout.addWidget(self.example_label)

        # Action Bar
        action_bar = self._create_action_bar()
        self.main_layout.addLayout(action_bar)

    def _create_header(self) -> QHBoxLayout:
        """Create header with title and API buttons"""
        header_layout = QHBoxLayout()
        header_layout.setSpacing(self.spacing.xl)

        # Title area
        title_area = QVBoxLayout()
        title_area.setSpacing(self.spacing.xs)

        self.title_label = QLabel("URL 입력 및 설정")
        title_area.addWidget(self.title_label)

        self.subtitle_label = QLabel(
            "텍스트 붙여넣기 시 자동으로 링크 추출됩니다. Enter 키로 추가할 수 있습니다."
        )
        title_area.addWidget(self.subtitle_label)

        header_layout.addLayout(title_area)
        header_layout.addStretch()

        # API Buttons
        api_layout = QHBoxLayout()
        api_layout.setSpacing(self.spacing.sm)

        self.api_btn = create_button(
            "API 키 관리",
            style="secondary",
            size="md",
            parent=self,
            on_click=self.gui.show_api_key_manager
        )
        api_layout.addWidget(self.api_btn)

        self.status_btn = create_button(
            "API 상태 확인",
            style="outline",
            size="md",
            parent=self,
            on_click=self.gui.show_api_status
        )
        api_layout.addWidget(self.status_btn)

        header_layout.addLayout(api_layout)

        return header_layout

    def _create_url_input(self):
        """Create URL text input area"""
        # Use QTextEdit for multi-line URL support
        self.gui.url_entry = QTextEdit()
        self.gui.url_entry.setFixedHeight(80)  # Increased from 60
        self.gui.url_entry.setPlaceholderText(
            "URL을 입력하거나 붙여넣으세요...\n\n예: https://www.tiktok.com/@..."
        )
        self.main_layout.addWidget(self.gui.url_entry)

    def _create_action_bar(self) -> QHBoxLayout:
        """Create action buttons bar"""
        action_bar = QHBoxLayout()
        action_bar.setSpacing(self.spacing.md)

        # Primary actions
        self.add_btn = create_button(
            "URL 추가",
            style="primary",
            size="lg",
            parent=self,
            on_click=self.gui.add_url_from_entry
        )
        action_bar.addWidget(self.add_btn)

        self.clipboard_btn = create_button(
            "클립보드에서 추가",
            style="accent",
            size="lg",
            parent=self,
            on_click=self.gui.paste_and_extract
        )
        action_bar.addWidget(self.clipboard_btn)

        # Spacer
        action_bar.addSpacing(self.spacing.xl2)

        # Folder actions
        self.folder_open_btn = create_button(
            "📁 저장 폴더 열기",
            style="secondary",
            size="md",
            parent=self,
            on_click=self._open_output_folder
        )
        action_bar.addWidget(self.folder_open_btn)

        self.gui.output_folder_button = create_button(
            "저장 폴더 선택",
            style="secondary",
            size="md",
            parent=self,
            on_click=self.gui.select_output_folder
        )
        action_bar.addWidget(self.gui.output_folder_button)

        # Folder path label
        self.gui.output_folder_label = create_label(
            "폴더를 선택해주세요",
            variant="secondary"
        )
        action_bar.addWidget(self.gui.output_folder_label, 1)

        return action_bar

    def _open_output_folder(self):
        """Open output folder in file explorer"""
        output_path = getattr(self.gui, 'output_folder_path', None)
        if not output_path:
            output_path = os.path.join(os.getcwd(), "outputs")

        os.makedirs(output_path, exist_ok=True)

        try:
            if sys.platform == 'win32':
                os.startfile(output_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', output_path])
            else:
                subprocess.run(['xdg-open', output_path])
        except Exception as e:
            logger.error(f"폴더 열기 오류: {e}")

    def apply_theme(self):
        """Apply enhanced panel styling"""
        c = self.colors
        t = self.typography
        r = self.ds.radius

        # Panel background (card style)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {c.bg_card};
                border: 1px solid {c.border_card};
                border-radius: {r.xl}px;
            }}
        """)

        # Title with heading font
        self.title_label.setStyleSheet(f"""
            QLabel {{
                color: {c.text_primary};
                font-family: {t.font_family_heading};
                font-size: {t.font_size_xl}px;
                font-weight: {t.font_weight_bold};
                background: transparent;
                border: none;
            }}
        """)

        # Subtitle
        self.subtitle_label.setStyleSheet(f"""
            QLabel {{
                color: {c.text_secondary};
                font-family: {t.font_family_body};
                font-size: {t.font_size_sm}px;
                background: transparent;
                border: none;
            }}
        """)

        # URL Entry (enhanced text edit style)
        self.gui.url_entry.setStyleSheet(f"""
            QTextEdit {{
                background-color: {c.bg_input};
                color: {c.text_primary};
                border: 2px solid {c.border_light};
                border-radius: {r.md}px;
                padding: {self.spacing.md}px;
                font-family: {t.font_family_body};
                font-size: {t.font_size_base}px;
                line-height: {int(t.font_size_base * t.line_height_relaxed)}px;
            }}
            QTextEdit:focus {{
                border-color: {c.primary};
                background-color: {c.bg_card};
            }}
            QTextEdit:hover {{
                border-color: {c.border_medium};
            }}
        """)

        # Set font for text edit
        font = QFont(t.font_family_body)
        font.setPointSize(t.font_size_base)
        self.gui.url_entry.setFont(font)
