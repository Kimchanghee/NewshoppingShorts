"""
Custom dialog components with theme support (light/dark mode)
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional
from ..theme_manager import ThemeManager, get_theme_manager


class CustomDialog:
    """Custom dialog with theme support (light/dark mode)"""

    def __init__(self, parent, title, message, dialog_type="info", buttons=None, theme_manager: Optional[ThemeManager] = None):
        """
        Create a custom dialog

        Args:
            parent: Parent window
            title: Dialog title
            message: Dialog message
            dialog_type: Type of dialog (info, warning, error, question, success)
            buttons: List of (text, callback) tuples
            theme_manager: Optional theme manager for theming
        """
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Theme manager
        self._theme_manager = theme_manager or get_theme_manager()

        # Get colors from theme
        self._setup_colors()

        self.dialog.configure(bg=self.bg_color)

        # Icon based on type
        icon_map = {
            "info": ("i", self.accent_color),
            "warning": ("!", self.warning_color),
            "error": ("x", self.error_color),
            "question": ("?", self.accent_color),
            "success": ("v", self.success_color)
        }
        icon, icon_color = icon_map.get(dialog_type, ("i", self.accent_color))

        # Main container
        main_frame = tk.Frame(self.dialog, bg=self.card_bg, padx=24, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Header (icon + title)
        header_frame = tk.Frame(main_frame, bg=self.card_bg)
        header_frame.pack(fill=tk.X, pady=(0, 12))

        # Icon (small circular background)
        icon_bg = tk.Frame(header_frame, bg=icon_color, width=24, height=24)
        icon_bg.pack(side=tk.LEFT, padx=(0, 10))
        icon_bg.pack_propagate(False)
        tk.Label(
            icon_bg,
            text=icon,
            font=("맑은 고딕", 12, "bold"),
            bg=icon_color,
            fg="#ffffff"
        ).place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Title
        tk.Label(
            header_frame,
            text=title,
            font=("맑은 고딕", 11, "bold"),
            bg=self.card_bg,
            fg=self.text_color,
            anchor=tk.W
        ).pack(side=tk.LEFT, fill=tk.X)

        # Message
        tk.Label(
            main_frame,
            text=message,
            font=("맑은 고딕", 10),
            bg=self.card_bg,
            fg=self.secondary_text,
            wraplength=320,
            justify=tk.LEFT,
            anchor=tk.W
        ).pack(fill=tk.X, pady=(0, 16))

        # Buttons (right aligned)
        button_frame = tk.Frame(main_frame, bg=self.card_bg)
        button_frame.pack(fill=tk.X)

        if buttons is None:
            buttons = [("확인", lambda: self.close(True))]

        self.primary_button = None
        # Place buttons from right (reverse order)
        for idx, (text, callback) in enumerate(reversed(buttons)):
            is_primary = idx == len(buttons) - 1  # First button is primary
            btn = tk.Button(
                button_frame,
                text=text,
                command=callback,
                font=("맑은 고딕", 9),
                bg=self.accent_color if is_primary else self.secondary_btn_bg,
                fg="#ffffff" if is_primary else self.secondary_btn_fg,
                activebackground=self.accent_hover if is_primary else self.secondary_btn_hover,
                activeforeground="#ffffff" if is_primary else self.text_color,
                relief=tk.FLAT,
                padx=16,
                pady=6,
                cursor="hand2",
                bd=0
            )
            btn.pack(side=tk.RIGHT, padx=(5, 0))
            if is_primary:
                self.primary_button = btn

        # Center dialog
        self.dialog.update_idletasks()
        width = max(300, self.dialog.winfo_width())
        height = self.dialog.winfo_height()
        x = (self.dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (height // 2)
        self.dialog.geometry(f'{width}x{height}+{x}+{y}')
        self.dialog.resizable(False, False)

        # Bind escape key
        self.dialog.bind("<Escape>", lambda e: self.close(False))

        # Bind enter key to primary button
        self.dialog.bind("<Return>", lambda e: self._on_enter_pressed())

        # Focus on primary button
        if self.primary_button:
            self.primary_button.focus_set()

    def _setup_colors(self):
        """Setup colors based on current theme"""
        tm = self._theme_manager

        # Background colors
        self.bg_color = tm.get_color("bg_main")
        self.card_bg = tm.get_color("bg_card")

        # Text colors
        self.text_color = tm.get_color("text_primary")
        self.secondary_text = tm.get_color("text_secondary")

        # Accent color (primary button)
        self.accent_color = tm.get_color("primary")
        self.accent_hover = tm.get_color("primary_hover")

        # Status colors
        self.error_color = tm.get_color("error")
        self.warning_color = tm.get_color("warning")
        self.success_color = tm.get_color("success")

        # Secondary button colors (theme-aware)
        self.secondary_btn_bg = tm.get_color("bg_secondary")
        self.secondary_btn_fg = tm.get_color("text_primary")
        self.secondary_btn_hover = tm.get_color("bg_hover")

    def _on_enter_pressed(self):
        """Handle Enter key press - invoke primary button"""
        if self.primary_button:
            self.primary_button.invoke()

    def close(self, result):
        """Close dialog with result"""
        self.result = result
        self.dialog.destroy()

    def show(self):
        """Show dialog and wait for result"""
        self.dialog.wait_window()
        return self.result


def show_info(parent, title, message, theme_manager: Optional[ThemeManager] = None):
    """Show info dialog"""
    return CustomDialog(parent, title, message, "info", theme_manager=theme_manager).show()


def show_warning(parent, title, message, theme_manager: Optional[ThemeManager] = None):
    """Show warning dialog"""
    return CustomDialog(parent, title, message, "warning", theme_manager=theme_manager).show()


def show_error(parent, title, message, theme_manager: Optional[ThemeManager] = None):
    """Show error dialog"""
    return CustomDialog(parent, title, message, "error", theme_manager=theme_manager).show()


def show_question(parent, title, message, theme_manager: Optional[ThemeManager] = None):
    """Show question dialog with Yes/No buttons"""
    dialog = CustomDialog(
        parent,
        title,
        message,
        "question",
        buttons=[
            ("예", lambda: dialog.close(True)),
            ("아니오", lambda: dialog.close(False))
        ],
        theme_manager=theme_manager
    )
    return dialog.show()


def show_success(parent, title, message, theme_manager: Optional[ThemeManager] = None):
    """Show success dialog"""
    return CustomDialog(parent, title, message, "success", theme_manager=theme_manager).show()
