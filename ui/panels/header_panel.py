"""
Header panel for PyQt6
"""
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt
from ui.components.base_widget import ThemedMixin

class HeaderPanel(QFrame, ThemedMixin):
    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.__init_themed__(theme_manager)
        self.create_widgets()
        self.apply_theme()

    def create_widgets(self):
        # We use a layout instead of pack
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(16, 8, 16, 8)
        
        # Store reference
        self.gui.header_frame = self
        
        # Header content (can be expanded later)
        # For now it just maintains a minimum height as in the original
        self.setFixedHeight(40)

    def apply_theme(self):
        bg_header = self.get_color("bg_header")
        self.setStyleSheet(f"background-color: {bg_header}; border: none;")
