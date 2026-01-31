"""
URL Input Panel for PyQt6
Refactored to integrity with Main Shell Design System
"""
import logging
import os
import subprocess
import sys
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, 
    QTextEdit, QWidget, QFrame
)
from PyQt6.QtCore import Qt
from ui.design_system_enhanced import get_design_system
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)

class URLInputPanel(QWidget):
    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.ds = get_design_system()
        self.create_widgets()
        
    def create_widgets(self):
        c = self.ds.colors
        t = self.ds.typography
        r = self.ds.radius
        
        # Main vertical layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(24)

        # 1. Input Area
        input_container = QVBoxLayout()
        input_container.setSpacing(8)
        
        lbl = QLabel("쇼핑몰 상품 링크 또는 영상 URL 입력")
        lbl.setFont(QFont(t.font_family_body, 14, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {c.text_primary};")
        input_container.addWidget(lbl)
        
        self.gui.url_entry = QTextEdit()
        self.gui.url_entry.setFixedHeight(120)
        self.gui.url_entry.setPlaceholderText("https://www.tiktok.com/@user/video/...\nhttps://smartstore.naver.com/...")
        self.gui.url_entry.setStyleSheet(self.ds.get_input_style())
        input_container.addWidget(self.gui.url_entry)
        
        hint = QLabel("💡 팁: 여러 개의 링크를 붙여넣으면 자동으로 분리하여 목록에 추가됩니다.")
        hint.setFont(QFont(t.font_family_body, 12))
        hint.setStyleSheet(f"color: {c.text_tertiary};")
        input_container.addWidget(hint)
        
        self.main_layout.addLayout(input_container)

        # 2. Action Area
        action_layout = QHBoxLayout()
        action_layout.setSpacing(12)
        
        from PyQt6.QtWidgets import QPushButton
        
        # Add Button
        self.add_btn = QPushButton("목록에 추가")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setStyleSheet(self.ds.get_button_style("primary", "md"))
        self.add_btn.clicked.connect(self.gui.add_url_from_entry)
        action_layout.addWidget(self.add_btn)
        
        # Clipboard Button
        self.clipboard_btn = QPushButton("클립보드에서 붙여넣기")
        self.clipboard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clipboard_btn.setStyleSheet(self.ds.get_button_style("secondary", "md"))
        self.clipboard_btn.clicked.connect(self.gui.paste_and_extract)
        action_layout.addWidget(self.clipboard_btn)
        
        action_layout.addStretch()
        
        self.main_layout.addLayout(action_layout)
        
        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {c.border_light};")
        self.main_layout.addWidget(line)
        
        # 3. Output Folder Settings
        folder_layout = QHBoxLayout()
        folder_layout.setSpacing(12)
        
        f_lbl = QLabel("저장 위치:")
        f_lbl.setFont(QFont(t.font_family_body, 13, QFont.Weight.Bold))
        f_lbl.setStyleSheet(f"color: {c.text_primary};")
        folder_layout.addWidget(f_lbl)
        
        self.folder_path_lbl = QLabel("설정되지 않음")
        self.folder_path_lbl.setFont(QFont(t.font_family_mono, 12))
        self.folder_path_lbl.setStyleSheet(f"""
            color: {c.text_secondary}; 
            background: {c.bg_input}; 
            padding: 4px 8px; 
            border-radius: 4px;
        """)
        # Link to gui for updates
        self.gui.output_folder_label = self.folder_path_lbl 
        folder_layout.addWidget(self.folder_path_lbl)
        
        chg_btn = QPushButton("변경")
        chg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        chg_btn.setStyleSheet(self.ds.get_button_style("secondary", "sm"))
        chg_btn.clicked.connect(self.gui.select_output_folder)
        folder_layout.addWidget(chg_btn)
        
        open_btn = QPushButton("폴더 열기")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setStyleSheet(self.ds.get_button_style("ghost", "sm"))
        open_btn.clicked.connect(self._open_output_folder)
        folder_layout.addWidget(open_btn)
        
        folder_layout.addStretch()
        self.main_layout.addLayout(folder_layout)
        
        self.main_layout.addStretch()

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
