"""
Queue Tab for PyQt6
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from PyQt6.QtCore import Qt
from ui.panels.queue_panel import QueuePanel

class QueueTab(QWidget):
    def __init__(self, parent=None, gui=None, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        
        # Header (Optional duplication or move to panel)
        # In the original, QueueTab has its own header.
        self.header_frame = QFrame()
        self.header_frame.setStyleSheet("background-color: #f3f4f6; border-radius: 8px;")
        header_layout = QHBoxLayout(self.header_frame)
        
        self.title_label = QLabel("제작 대기열")
        self.title_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #1b0e10;")
        header_layout.addWidget(self.title_label)
        
        header_layout.addStretch()
        
        self.stats_label = QLabel("대기 0 | 완료 0 | 실패 0")
        self.stats_label.setStyleSheet("color: #64748b; font-size: 9pt;")
        header_layout.addWidget(self.stats_label)
        
        layout.addWidget(self.header_frame)
        
        # Queue Panel
        self.queue_panel = QueuePanel(self, self.gui)
        layout.addWidget(self.queue_panel)

    def update_queue_stats(self, waiting: int, completed: int, failed: int):
        self.stats_label.setText(f"대기 {waiting} | 완료 {completed} | 실패 {failed}")

    def apply_theme(self):
        pass # Themed via QSS or delegate
