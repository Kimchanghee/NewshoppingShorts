"""
Settings tab placeholder (PyQt6).
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from ui.design_system_v2 import get_design_system, get_color

class SettingsTab(QWidget):
    def __init__(self, parent=None, gui=None, theme_manager=None):
        super().__init__(parent)
        self.ds = get_design_system()
        layout = QVBoxLayout(self)
        
        label = QLabel("설정 탭 (준비 중)", self)
        label.setStyleSheet(f"""
            font-size: {self.ds.typography.size_base}px;
            color: {get_color('text_primary')};
            font-weight: {self.ds.typography.weight_medium};
        """)
        layout.addWidget(label)
