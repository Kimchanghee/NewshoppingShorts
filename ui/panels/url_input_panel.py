"""
URL Input Panel for PyQt6
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
from ui.components.rounded_widgets import RoundedButton, create_rounded_button
from ui.components.base_widget import ThemedMixin

logger = logging.getLogger(__name__)

class URLInputPanel(QFrame, ThemedMixin):
    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.__init_themed__(theme_manager)
        self.create_widgets()
        self.apply_theme()

    def create_widgets(self):
        # Main vertical layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 12, 16, 12)
        self.main_layout.setSpacing(10)

        # Header: Title + Buttons
        header_layout = QHBoxLayout()
        
        # Title area
        title_area = QVBoxLayout()
        self.title_label = QLabel("URL 입력 및 설정")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_area.addWidget(self.title_label)
        
        self.subtitle_label = QLabel("텍스트 붙여넣기 시 자동으로 링크 추출됩니다. Enter 키로 추가할 수 있습니다.")
        self.subtitle_label.setStyleSheet("font-size: 12px;")
        title_area.addWidget(self.subtitle_label)
        header_layout.addLayout(title_area)
        
        # API Buttons
        api_layout = QHBoxLayout()
        self.api_btn = create_rounded_button(self, "API 키 관리", self.gui.show_api_key_manager)
        api_layout.addWidget(self.api_btn)
        
        self.status_btn = create_rounded_button(self, "API 상태 확인", self.gui.show_api_status, style="secondary")
        api_layout.addWidget(self.status_btn)
        
        header_layout.addLayout(api_layout)
        self.main_layout.addLayout(header_layout)

        # URL Entry
        self.gui.url_entry = QTextEdit()
        self.gui.url_entry.setFixedHeight(60)
        self.gui.url_entry.setPlaceholderText("예: https://www.tiktok.com/@...")
        self.main_layout.addWidget(self.gui.url_entry)
        
        # Example label
        self.example_label = QLabel("예: https://www.tiktok.com/@...")
        self.example_label.setStyleSheet("font-size: 11px;")
        self.main_layout.addWidget(self.example_label)

        # Action Bar
        action_bar = QHBoxLayout()
        
        self.add_btn = create_rounded_button(self, "URL 추가", self.gui.add_url_from_entry)
        action_bar.addWidget(self.add_btn)
        
        self.clipboard_btn = create_rounded_button(self, "클립보드 추가", self.gui.paste_and_extract, style="secondary")
        action_bar.addWidget(self.clipboard_btn)
        
        self.folder_open_btn = create_rounded_button(self, "📁 저장 폴더 열기", self._open_output_folder, style="secondary")
        action_bar.addWidget(self.folder_open_btn)
        
        action_bar.addSpacing(20)
        
        self.gui.output_folder_button = create_rounded_button(self, "저장폴더 선택", self.gui.select_output_folder)
        action_bar.addWidget(self.gui.output_folder_button)
        
        self.gui.output_folder_label = QLabel("폴더를 선택해주세요")
        self.gui.output_folder_label.setStyleSheet("font-size: 11px;")
        # Link label to sync with gui logic (though gui logic will need updating too)
        action_bar.addWidget(self.gui.output_folder_label, 1)
        
        self.main_layout.addLayout(action_bar)

    def _open_output_folder(self):
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
        bg_card = self.get_color("bg_card")
        bg_input = self.get_color("bg_input")
        text_primary = self.get_color("text_primary")
        text_secondary = self.get_color("text_secondary")
        border = self.get_color("border_light")
        
        self.setStyleSheet(f"background-color: {bg_card}; border: 1px solid {border}; border-radius: 8px;")
        self.title_label.setStyleSheet(f"color: {text_primary}; font-weight: bold; border: none;")
        self.subtitle_label.setStyleSheet(f"color: {text_secondary}; border: none;")
        self.example_label.setStyleSheet(f"color: {text_secondary}; border: none;")
        self.gui.output_folder_label.setStyleSheet(f"color: {text_secondary}; border: none;")
        
        self.gui.url_entry.setStyleSheet(f"""
            QTextEdit {{
                background-color: {bg_input};
                color: {text_primary};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 4px;
            }}
        """)
