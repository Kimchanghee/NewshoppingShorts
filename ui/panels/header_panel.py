"""
Header panel with API status display
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional

from ui.components.base_widget import ThemedMixin
from ui.theme_manager import ThemeManager, get_theme_manager


class HeaderPanel(tk.Frame, ThemedMixin):
    """Header panel with API status display"""

    def __init__(self, parent, gui, theme_manager: Optional[ThemeManager] = None):
        """
        Initialize the header panel.

        Args:
            parent: Parent tkinter widget
            gui: VideoAnalyzerGUI instance
            theme_manager: ThemeManager instance
        """
        self.__init_themed__(theme_manager)
        super().__init__(
            parent,
            bg=self.get_color("bg_header"),
            bd=0,
            relief=tk.FLAT
        )
        self.gui = gui
        self.create_widgets()

    def create_widgets(self):
        """Create header widgets"""
        # Store reference to header frame in GUI instance
        self.gui.header_frame = self
        # HeaderPanel uses pack for positioning from root
        # API 버튼들은 URLInputPanel로 이동됨 - 헤더는 최소 높이만 유지
        self.pack(fill=tk.X, pady=(0, 4))

    def apply_theme(self) -> None:
        """테마 적용 - 다크/라이트 모드 전환 시 색상 업데이트"""
        self.configure(bg=self.get_color("bg_header"))
