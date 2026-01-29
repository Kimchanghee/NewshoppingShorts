"""
Subscription prompt popup dialog
체험판 소진 시 표시되는 구독 안내 팝업
"""
import tkinter as tk
from typing import Optional, Callable

from ui.theme_manager import ThemeManager, get_theme_manager


class SubscriptionPromptDialog:
    """
    Popup dialog shown when trial is exhausted.
    체험판 횟수 소진 시 표시되는 구독 안내 다이얼로그.

    Features:
    - Shows current usage (e.g., 3/3 used)
    - Lists subscription benefits
    - "구독 신청" button with message input
    - Cancel button
    """

    def __init__(
        self,
        parent,
        work_count: int,
        work_used: int,
        on_submit: Optional[Callable[[str], None]] = None,
        theme_manager: Optional[ThemeManager] = None
    ):
        """
        Initialize the subscription prompt dialog.

        Args:
            parent: Parent window
            work_count: Total work count
            work_used: Number of works used
            on_submit: Callback with message when subscription is requested
            theme_manager: ThemeManager instance
        """
        self.result = None
        self._on_submit = on_submit
        self._theme_manager = theme_manager or get_theme_manager()

        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("구독 안내")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Get colors
        self._setup_colors()
        self.dialog.configure(bg=self.bg_color)

        # Build UI
        self._create_content(work_count, work_used)

        # Center dialog
        self.dialog.update_idletasks()
        width = 400
        height = self.dialog.winfo_height()
        x = (self.dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (height // 2)
        self.dialog.geometry(f'{width}x{height}+{x}+{y}')
        self.dialog.resizable(False, False)

        # Bind escape key
        self.dialog.bind("<Escape>", lambda e: self.close(False))

    def _setup_colors(self):
        """Setup colors based on current theme"""
        tm = self._theme_manager

        self.bg_color = tm.get_color("bg_main")
        self.card_bg = tm.get_color("bg_card")
        self.text_color = tm.get_color("text_primary")
        self.secondary_text = tm.get_color("text_secondary")
        self.accent_color = tm.get_color("primary")
        self.accent_hover = tm.get_color("primary_hover")
        self.warning_color = tm.get_color("warning")
        self.error_color = tm.get_color("error")
        self.success_color = tm.get_color("success")
        self.input_bg = tm.get_color("bg_input")
        self.border_color = tm.get_color("border_light")
        self.secondary_btn_bg = tm.get_color("bg_secondary")
        self.secondary_btn_fg = tm.get_color("text_primary")

    def _create_content(self, work_count: int, work_used: int):
        """Create dialog content"""
        # Main container
        main_frame = tk.Frame(self.dialog, bg=self.card_bg, padx=24, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Header with warning icon
        header_frame = tk.Frame(main_frame, bg=self.card_bg)
        header_frame.pack(fill=tk.X, pady=(0, 16))

        # Warning icon
        icon_bg = tk.Frame(header_frame, bg=self.warning_color, width=28, height=28)
        icon_bg.pack(side=tk.LEFT, padx=(0, 12))
        icon_bg.pack_propagate(False)
        tk.Label(
            icon_bg,
            text="!",
            font=("맑은 고딕", 14, "bold"),
            bg=self.warning_color,
            fg="#ffffff"
        ).place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Title
        tk.Label(
            header_frame,
            text="체험판 횟수가 소진되었습니다",
            font=("맑은 고딕", 12, "bold"),
            bg=self.card_bg,
            fg=self.text_color,
            anchor=tk.W
        ).pack(side=tk.LEFT, fill=tk.X)

        # Usage info
        usage_frame = tk.Frame(main_frame, bg=self.input_bg, padx=16, pady=12)
        usage_frame.pack(fill=tk.X, pady=(0, 16))

        tk.Label(
            usage_frame,
            text=f"사용량: {work_used}/{work_count}회 (소진)",
            font=("맑은 고딕", 10),
            bg=self.input_bg,
            fg=self.error_color
        ).pack(anchor=tk.W)

        # Benefits section
        benefits_label = tk.Label(
            main_frame,
            text="구독 혜택",
            font=("맑은 고딕", 10, "bold"),
            bg=self.card_bg,
            fg=self.text_color,
            anchor=tk.W
        )
        benefits_label.pack(fill=tk.X, pady=(0, 8))

        benefits = [
            "무제한 숏폼 생성",
            "모든 템플릿 사용 가능",
            "우선 지원 서비스",
            "새로운 기능 우선 이용"
        ]

        for benefit in benefits:
            benefit_frame = tk.Frame(main_frame, bg=self.card_bg)
            benefit_frame.pack(fill=tk.X, pady=2)

            tk.Label(
                benefit_frame,
                text="v",
                font=("맑은 고딕", 9),
                bg=self.card_bg,
                fg=self.success_color
            ).pack(side=tk.LEFT, padx=(0, 8))

            tk.Label(
                benefit_frame,
                text=benefit,
                font=("맑은 고딕", 9),
                bg=self.card_bg,
                fg=self.secondary_text,
                anchor=tk.W
            ).pack(side=tk.LEFT, fill=tk.X)

        # Message input section
        message_label = tk.Label(
            main_frame,
            text="메시지 (선택사항)",
            font=("맑은 고딕", 9),
            bg=self.card_bg,
            fg=self.secondary_text,
            anchor=tk.W
        )
        message_label.pack(fill=tk.X, pady=(16, 4))

        self._message_entry = tk.Text(
            main_frame,
            height=3,
            font=("맑은 고딕", 9),
            bg=self.input_bg,
            fg=self.text_color,
            relief=tk.FLAT,
            padx=8,
            pady=8,
            highlightthickness=1,
            highlightbackground=self.border_color,
            highlightcolor=self.accent_color
        )
        self._message_entry.pack(fill=tk.X, pady=(0, 16))
        self._message_entry.insert("1.0", "구독을 신청합니다.")

        # Buttons
        button_frame = tk.Frame(main_frame, bg=self.card_bg)
        button_frame.pack(fill=tk.X)

        # Cancel button
        cancel_btn = tk.Button(
            button_frame,
            text="취소",
            font=("맑은 고딕", 9),
            bg=self.secondary_btn_bg,
            fg=self.secondary_btn_fg,
            activebackground=self.input_bg,
            activeforeground=self.text_color,
            relief=tk.FLAT,
            padx=20,
            pady=8,
            cursor="hand2",
            bd=0,
            command=lambda: self.close(False)
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(8, 0))

        # Submit button
        submit_btn = tk.Button(
            button_frame,
            text="구독 신청",
            font=("맑은 고딕", 9, "bold"),
            bg=self.accent_color,
            fg="#ffffff",
            activebackground=self.accent_hover,
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=20,
            pady=8,
            cursor="hand2",
            bd=0,
            command=self._on_submit_click
        )
        submit_btn.pack(side=tk.RIGHT)

    def _on_submit_click(self):
        """Handle submit button click"""
        message = self._message_entry.get("1.0", tk.END).strip()
        if self._on_submit:
            self._on_submit(message)
        self.close(True)

    def close(self, result):
        """Close dialog with result"""
        self.result = result
        self.dialog.destroy()

    def show(self):
        """Show dialog and wait for result"""
        self.dialog.wait_window()
        return self.result


def show_subscription_prompt(
    parent,
    work_count: int,
    work_used: int,
    on_submit: Optional[Callable[[str], None]] = None,
    theme_manager: Optional[ThemeManager] = None
) -> bool:
    """
    Show subscription prompt dialog.

    Args:
        parent: Parent window
        work_count: Total work count
        work_used: Number of works used
        on_submit: Callback when subscription is requested
        theme_manager: ThemeManager instance

    Returns:
        True if user requested subscription, False if cancelled
    """
    dialog = SubscriptionPromptDialog(
        parent,
        work_count,
        work_used,
        on_submit,
        theme_manager
    )
    return dialog.show()
