"""
Subscription status widget for displaying user's subscription information
구독 상태 표시 위젯
"""
import tkinter as tk
from typing import Optional, Callable

from ui.components.base_widget import ThemedMixin
from ui.theme_manager import ThemeManager, get_theme_manager


class SubscriptionStatusWidget(tk.Frame, ThemedMixin):
    """
    Widget displaying subscription status in the main UI.
    메인 UI에 표시되는 구독 상태 위젯.

    Shows:
    - Remaining work count (X/Y or "무제한")
    - Subscription type (체험판/구독)
    - "구독 신청" button for trial users
    """

    def __init__(
        self,
        parent,
        on_request_subscription: Optional[Callable] = None,
        theme_manager: Optional[ThemeManager] = None
    ):
        """
        Initialize the subscription status widget.

        Args:
            parent: Parent tkinter widget
            on_request_subscription: Callback when "구독 신청" button is clicked
            theme_manager: ThemeManager instance
        """
        self.__init_themed__(theme_manager)
        super().__init__(parent, bg=self.get_color("bg_card"))

        self._on_request_subscription = on_request_subscription

        # State
        self._is_trial = True
        self._work_count = 3
        self._work_used = 0
        self._can_work = True
        self._has_pending_request = False

        self._create_widgets()
        self._update_display()

    def _create_widgets(self):
        """Create all widgets"""
        # Container frame with padding
        container = tk.Frame(self, bg=self.get_color("bg_card"), padx=10, pady=8)
        container.pack(fill=tk.X, expand=True)

        # Left side: Status info
        info_frame = tk.Frame(container, bg=self.get_color("bg_card"))
        info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Subscription type label
        self._type_label = tk.Label(
            info_frame,
            text="체험판",
            font=("맑은 고딕", 9, "bold"),
            bg=self.get_color("bg_card"),
            fg=self.get_color("warning"),
            anchor=tk.W
        )
        self._type_label.pack(side=tk.LEFT, padx=(0, 10))

        # Work count display
        self._count_frame = tk.Frame(info_frame, bg=self.get_color("bg_card"))
        self._count_frame.pack(side=tk.LEFT, fill=tk.X)

        self._count_label = tk.Label(
            self._count_frame,
            text="남은 횟수:",
            font=("맑은 고딕", 9),
            bg=self.get_color("bg_card"),
            fg=self.get_color("text_secondary"),
            anchor=tk.W
        )
        self._count_label.pack(side=tk.LEFT)

        self._count_value = tk.Label(
            self._count_frame,
            text="3/3",
            font=("맑은 고딕", 9, "bold"),
            bg=self.get_color("bg_card"),
            fg=self.get_color("primary"),
            anchor=tk.W
        )
        self._count_value.pack(side=tk.LEFT, padx=(4, 0))

        # Right side: Request button (only for trial users)
        self._request_btn = tk.Button(
            container,
            text="구독 신청",
            font=("맑은 고딕", 8),
            bg=self.get_color("primary"),
            fg="#ffffff",
            activebackground=self.get_color("primary_hover"),
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="hand2",
            bd=0,
            command=self._on_request_click
        )
        self._request_btn.pack(side=tk.RIGHT, padx=(10, 0))

        # Pending request indicator
        self._pending_label = tk.Label(
            container,
            text="신청 대기중",
            font=("맑은 고딕", 8),
            bg=self.get_color("bg_card"),
            fg=self.get_color("info"),
            anchor=tk.E
        )

    def _on_request_click(self):
        """Handle request button click"""
        if self._on_request_subscription:
            self._on_request_subscription()

    def update_status(
        self,
        is_trial: bool = True,
        work_count: int = 3,
        work_used: int = 0,
        can_work: bool = True,
        has_pending_request: bool = False
    ):
        """
        Update the subscription status display.

        Args:
            is_trial: Whether user is on trial
            work_count: Total work count (-1 for unlimited)
            work_used: Number of works used
            can_work: Whether user can perform work
            has_pending_request: Whether there's a pending subscription request
        """
        self._is_trial = is_trial
        self._work_count = work_count
        self._work_used = work_used
        self._can_work = can_work
        self._has_pending_request = has_pending_request
        self._update_display()

    def _update_display(self):
        """Update the display based on current state"""
        is_unlimited = self._work_count == -1

        # Update type label
        if is_unlimited:
            self._type_label.configure(
                text="구독",
                fg=self.get_color("success")
            )
        else:
            self._type_label.configure(
                text="체험판",
                fg=self.get_color("warning")
            )

        # Update count display
        if is_unlimited:
            self._count_value.configure(
                text="무제한",
                fg=self.get_color("success")
            )
        else:
            remaining = max(0, self._work_count - self._work_used)
            self._count_value.configure(
                text=f"{remaining}/{self._work_count}",
                fg=self.get_color("primary") if remaining > 0 else self.get_color("error")
            )

        # Show/hide request button and pending label
        if is_unlimited:
            # Subscriber: hide both
            self._request_btn.pack_forget()
            self._pending_label.pack_forget()
        elif self._has_pending_request:
            # Has pending request: show pending label, hide button
            self._request_btn.pack_forget()
            self._pending_label.pack(side=tk.RIGHT, padx=(10, 0))
        else:
            # Trial without pending: show button, hide label
            self._pending_label.pack_forget()
            self._request_btn.pack(side=tk.RIGHT, padx=(10, 0))

    def apply_theme(self) -> None:
        """Apply theme colors"""
        self.configure(bg=self.get_color("bg_card"))

        # Update all widget colors
        for widget in self.winfo_children():
            if isinstance(widget, tk.Frame):
                widget.configure(bg=self.get_color("bg_card"))
                for child in widget.winfo_children():
                    if isinstance(child, (tk.Frame, tk.Label)):
                        child.configure(bg=self.get_color("bg_card"))

        self._update_display()
