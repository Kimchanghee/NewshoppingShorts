"""
Style Tab for PyQt6
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QFrame, QLabel, QHBoxLayout
)
from PyQt6.QtCore import Qt
from ui.panels.font_panel import FontPanel
from ui.panels.cta_panel import CTAPanel
from ui.design_system_v2 import get_design_system, get_color

class StyleTab(QWidget):
    def __init__(self, parent=None, gui=None, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.ds = get_design_system()
        self._setup_ui()

    def _setup_ui(self):
        ds = self.ds
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(ds.spacing.space_5, ds.spacing.space_5, ds.spacing.space_5, ds.spacing.space_5)
        self.content_layout.setSpacing(ds.spacing.space_6)
        
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
        ds = self.ds
        section = QWidget()
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        
        header = QLabel(title)
        header.setStyleSheet(f"""
            font-size: {ds.typography.size_base}px; 
            font-weight: {ds.typography.weight_bold}; 
            color: {get_color('text_primary')}; 
            margin-bottom: {ds.spacing.space_2}px;
        """)
        section_layout.addWidget(header)
        section_layout.addWidget(widget)
        
        self.content_layout.addWidget(section)

    def apply_theme(self):
        pass # Themed via QSS usually
