"""
Status bar component for displaying application status
"""
import tkinter as tk
from typing import Optional

from ui.components.base_widget import ThemedMixin
from ui.theme_manager import ThemeManager, get_theme_manager


class StatusBar(tk.Label, ThemedMixin):
    """Bottom status bar displaying current application status"""

    def __init__(self, parent, gui, theme_manager: Optional[ThemeManager] = None):
        """
        Initialize the status bar.

        Args:
            parent: Parent tkinter widget
            gui: VideoAnalyzerGUI instance
            theme_manager: ThemeManager instance
        """
        self.__init_themed__(theme_manager)
        super().__init__(
            parent,
            text="준비 완료",
            bg=self.get_color("bg_header"),
            fg=self.get_color("text_secondary"),
            font=("맑은 고딕", 8),
            anchor=tk.W,
            padx=10
        )
        self.gui = gui

        # Store reference in GUI instance
        self.gui.status_bar = self

        # Pack the status bar at the bottom
        self.pack(side=tk.BOTTOM, fill=tk.X)

        # Refresh voice status display
        self.gui.refresh_voice_status_display()

    def apply_theme(self) -> None:
        """테마 적용 - 다크/라이트 모드 전환 시 색상 업데이트"""
        self.configure(
            bg=self.get_color("bg_header"),
            fg=self.get_color("text_secondary")
        )
