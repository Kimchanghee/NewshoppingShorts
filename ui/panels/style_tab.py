"""
Style Tab for PyQt6
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QFrame, QLabel, QHBoxLayout
)
from PyQt6.QtCore import Qt
from ui.panels.font_panel import FontPanel
from ui.panels.cta_panel import CTAPanel

class StyleTab(QWidget):
    def __init__(self, parent=None, gui=None, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        self.content_layout.setSpacing(30)
        
        # Voice Section (Placeholder or integration if needed)
        self._add_section("음성 선택", QLabel("음성 선택 패널 (통합 예정)"))
        
        # Font Section
        self.font_panel = FontPanel(self, gui=self.gui)
        self._add_section("폰트 선택", self.font_panel)
        
        # CTA Section
        self.cta_panel = CTAPanel(self, gui=self.gui)
        self._add_section("CTA 선택", self.cta_panel)
        
        self.content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _add_section(self, title, widget):
        section = QWidget()
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        
        header = QLabel(title)
        header.setStyleSheet("font-size: 14pt; font-weight: bold; color: #1b0e10; margin-bottom: 10px;")
        section_layout.addWidget(header)
        section_layout.addWidget(widget)
        
        self.content_layout.addWidget(section)

    def apply_theme(self):
        pass # Themed via QSS usually
