"""
Voice selection panel for choosing TTS voices
세련된 카드 그리드 레이아웃 + 성별 탭 필터
"""
import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, Optional, List

from ui.components.base_widget import ThemedMixin
from ..theme_manager import ThemeManager, get_theme_manager

logger = logging.getLogger(__name__)


class VoicePanel(tk.Frame, ThemedMixin):
    """Voice selection panel with card grid layout and gender tab filter"""

    def __init__(self, parent, gui, theme_manager: Optional[ThemeManager] = None):
        """
        Initialize the voice selection panel.

        Args:
            parent: Parent tkinter widget
            gui: VideoAnalyzerGUI instance
            theme_manager: ThemeManager instance
        """
        self.__init_themed__(theme_manager)
        super().__init__(parent, bg=self.get_color("bg_card"), bd=0, highlightthickness=0)
        self.gui = gui
        self.gender_filter = "all"  # all, female, male
        self.voice_cards = {}
        self.tab_buttons = {}
        self.create_widgets()

    def create_widgets(self):
        """Create voice selection widgets with card grid and gender tabs"""
        # ===== HEADER =====
        header = tk.Frame(self, bg=self.get_color("bg_card"))
        header.pack(fill=tk.X, padx=16, pady=(12, 8))

        # Title row
        title_frame = tk.Frame(header, bg=self.get_color("bg_card"))
        title_frame.pack(fill=tk.X)

        tk.Label(
            title_frame,
            text="음성 선택",
            font=("맑은 고딕", 14, "bold"),
            bg=self.get_color("bg_card"),
            fg=self.get_color("text_primary")
        ).pack(side=tk.LEFT)

        # 선택 카운트 badge
        self.count_badge = tk.Label(
            title_frame,
            text="0개 선택",
            font=("맑은 고딕", 9),
            bg=self.get_color("primary"),
            fg="#FFFFFF",
            padx=8,
            pady=2
        )
        self.count_badge.pack(side=tk.RIGHT)

        # ===== GENDER TAB FILTER =====
        tab_frame = tk.Frame(self, bg=self.get_color("bg_card"))
        tab_frame.pack(fill=tk.X, padx=16, pady=(0, 12))

        tabs = [
            ("all", "전체"),
            ("female", "여성"),
            ("male", "남성")
        ]

        for tab_id, tab_label in tabs:
            is_active = (tab_id == self.gender_filter)
            btn = tk.Label(
                tab_frame,
                text=tab_label,
                font=("맑은 고딕", 10, "bold" if is_active else "normal"),
                bg=self.get_color("primary") if is_active else self.get_color("bg_card"),
                fg="#FFFFFF" if is_active else self.get_color("text_secondary"),
                padx=16,
                pady=6,
                cursor="hand2"
            )
            btn.pack(side=tk.LEFT, padx=(0, 4))
            btn.bind("<Button-1>", lambda e, tid=tab_id: self._on_tab_click(tid))
            self.tab_buttons[tab_id] = btn

        # 전체 선택/해제 버튼
        btn_frame = tk.Frame(tab_frame, bg=self.get_color("bg_card"))
        btn_frame.pack(side=tk.RIGHT)

        self.deselect_btn = tk.Label(
            btn_frame,
            text="전체해제",
            font=("맑은 고딕", 9),
            bg=self.get_color("bg_card"),
            fg=self.get_color("text_secondary"),
            cursor="hand2",
            padx=8
        )
        self.deselect_btn.pack(side=tk.RIGHT)
        self.deselect_btn.bind("<Button-1>", lambda e: self._deselect_all_visible())

        self.select_btn = tk.Label(
            btn_frame,
            text="전체선택",
            font=("맑은 고딕", 9),
            bg=self.get_color("bg_card"),
            fg=self.get_color("primary"),
            cursor="hand2",
            padx=8
        )
        self.select_btn.pack(side=tk.RIGHT)
        self.select_btn.bind("<Button-1>", lambda e: self._select_all_visible())

        # ===== VOICE GRID =====
        self.grid_container = tk.Frame(self, bg=self.get_color("bg_card"))
        self.grid_container.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))

        # Canvas for scrolling
        self.canvas = tk.Canvas(
            self.grid_container,
            bg=self.get_color("bg_card"),
            highlightthickness=0,
            bd=0
        )
        
        # Scrollbar (thin style)
        self.scrollbar = ttk.Scrollbar(
            self.grid_container,
            orient="vertical",
            command=self.canvas.yview,
            style="Themed.Vertical.TScrollbar"
        )
        
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollable frame
        self.scrollable_frame = tk.Frame(self.canvas, bg=self.get_color("bg_card"))
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        # Bind events
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.scrollable_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.scrollable_frame.bind("<MouseWheel>", self._on_mousewheel)

        # Initialize containers
        self.gui.voice_card_frames = {}
        self.gui.voice_play_buttons = {}

        # Build voice cards
        self._build_voice_cards()

        # Load saved selections
        voice_manager = getattr(self.gui, 'voice_manager', None)
        if voice_manager is not None:
            load_saved_voices = getattr(voice_manager, 'load_saved_voices', None)
            if load_saved_voices is not None:
                load_saved_voices()

        # Update displays
        self.refresh_voice_cards()

    def _build_voice_cards(self):
        """Build voice cards grid"""
        # Clear existing cards
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.voice_cards.clear()
        
        # Filter profiles by gender
        profiles = self.gui.voice_profiles
        if self.gender_filter == "female":
            profiles = [p for p in profiles if p.get("gender") == "female"]
        elif self.gender_filter == "male":
            profiles = [p for p in profiles if p.get("gender") == "male"]
        
        # Create cards in 2-column grid
        for i, profile in enumerate(profiles):
            row = i // 2
            col = i % 2
            self._create_voice_card(profile, row, col)

    def _create_voice_card(self, profile: Dict, row: int, col: int):
        """Create a single voice card"""
        # Get theme colors
        card_bg = self.get_color("bg_card")
        card_border = self.get_color("border_light")
        text_color = self.get_color("text_primary")
        secondary_text = self.get_color("text_secondary")
        
        # Card frame
        card = tk.Frame(
            self.scrollable_frame,
            bg=card_bg,
            highlightbackground=card_border,
            highlightthickness=1,
            cursor="hand2"
        )
        card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
        
        # Configure grid weights
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        self.scrollable_frame.grid_columnconfigure(1, weight=1)

        # Check if selected
        var = self.gui.voice_vars.get(profile["id"])
        if var is None:
            var = tk.BooleanVar(value=False)
            self.gui.voice_vars[profile["id"]] = var
        
        is_selected = var.get()
        
        # Selected state styling
        if is_selected:
            selected_bg = self.get_color("bg_selected")
            selected_border = self.get_color("primary")
            card.configure(bg=selected_bg, highlightbackground=selected_border, highlightthickness=2)
            card_bg = selected_bg

        # Inner padding frame
        inner = tk.Frame(card, bg=card_bg)
        inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # Top row: checkbox + name
        top_row = tk.Frame(inner, bg=card_bg)
        top_row.pack(fill=tk.X)

        # Checkbox
        check_text = "✓" if is_selected else ""
        check_bg = self.get_color("primary") if is_selected else self.get_color("bg_secondary")
        check_fg = "#FFFFFF" if is_selected else card_bg
        
        check_label = tk.Label(
            top_row,
            text=check_text,
            font=("맑은 고딕", 9, "bold"),
            bg=check_bg,
            fg=check_fg,
            width=2,
            height=1,
            cursor="hand2"
        )
        check_label.pack(side=tk.LEFT, padx=(0, 8))

        # Gender icon + Name
        gender_icon = "♀" if profile.get("gender") == "female" else "♂"
        icon_color = "#FF6B81" if profile.get("gender") == "female" else "#5B9BD5"
        
        tk.Label(
            top_row,
            text=gender_icon,
            font=("맑은 고딕", 12),
            bg=card_bg,
            fg=icon_color
        ).pack(side=tk.LEFT, padx=(0, 4))

        name_label = tk.Label(
            top_row,
            text=profile["label"],
            font=("맑은 고딕", 12, "bold"),
            bg=card_bg,
            fg=text_color,
            cursor="hand2"
        )
        name_label.pack(side=tk.LEFT)

        # Play button
        play_btn = tk.Label(
            top_row,
            text="▶",
            font=("맑은 고딕", 10),
            bg="#FF6B81" if profile.get("gender") == "female" else "#5B9BD5",
            fg="#FFFFFF",
            padx=8,
            pady=2,
            cursor="hand2"
        )
        play_btn.pack(side=tk.RIGHT)
        play_btn.bind("<Button-1>", lambda e, vid=profile["id"]: self.gui.play_voice_sample(vid))

        # Description
        desc_label = tk.Label(
            inner,
            text=profile["description"],
            font=("맑은 고딕", 9),
            bg=card_bg,
            fg=secondary_text,
            anchor="w",
            cursor="hand2"
        )
        desc_label.pack(fill=tk.X, pady=(6, 0))

        # Click handlers
        def on_click(e):
            self._toggle_voice(profile["id"])
        
        for widget in [card, inner, top_row, check_label, name_label, desc_label]:
            widget.bind("<Button-1>", on_click)
            widget.bind("<MouseWheel>", self._on_mousewheel)

        # Hover effects
        def on_enter(e):
            if not var.get():
                hover_bg = self.get_color("bg_hover")
                card.configure(bg=hover_bg)
                inner.configure(bg=hover_bg)
                for w in [top_row, check_label, name_label, desc_label]:
                    try:
                        if w != check_label or not var.get():
                            w.configure(bg=hover_bg)
                    except tk.TclError:
                        pass

        def on_leave(e):
            if not var.get():
                original_bg = self.get_color("bg_card")
                card.configure(bg=original_bg)
                inner.configure(bg=original_bg)
                for w in [top_row, name_label, desc_label]:
                    try:
                        w.configure(bg=original_bg)
                    except tk.TclError:
                        pass

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

        # Store references
        self.voice_cards[profile["id"]] = {
            'card': card,
            'inner': inner,
            'check_label': check_label,
            'name_label': name_label,
            'desc_label': desc_label,
            'top_row': top_row,
            'play_btn': play_btn,
            'profile': profile
        }
        self.gui.voice_card_frames[profile["id"]] = card
        self.gui.voice_play_buttons[profile["id"]] = play_btn

    def _toggle_voice(self, voice_id: str):
        """Toggle voice selection"""
        var = self.gui.voice_vars.get(voice_id)
        if var:
            new_value = not var.get()

            # Check max selection count
            if new_value:
                selected_ids = [vid for vid, state in self.gui.voice_vars.items() if state.get()]
                max_voices = getattr(self.gui, 'max_voice_selection', 10)
                if len(selected_ids) >= max_voices:
                    from ui.components.custom_dialog import show_info
                    show_info(self.gui.root, "알림", f"최대 {max_voices}개까지 선택할 수 있습니다.")
                    return

            var.set(new_value)
            self._update_card_style(voice_id)
            self._update_voice_summary()

            # Save selection
            voice_manager = getattr(self.gui, 'voice_manager', None)
            if voice_manager is not None:
                save_fn = getattr(voice_manager, 'save_voice_selections', None)
                if save_fn is not None:
                    save_fn()

    def _update_card_style(self, voice_id: str):
        """Update card visual state"""
        if voice_id not in self.voice_cards:
            return
        
        card_data = self.voice_cards[voice_id]
        var = self.gui.voice_vars.get(voice_id)
        if not var:
            return
        
        is_selected = var.get()
        
        # Colors based on selection and theme
        if is_selected:
            card_bg = self.get_color("bg_selected")
            border_color = self.get_color("primary")
            border_width = 2
            check_bg = self.get_color("primary")
            check_text = "✓"
            check_fg = "#FFFFFF"
        else:
            card_bg = self.get_color("bg_card")
            border_color = self.get_color("border_light")
            border_width = 1
            check_bg = self.get_color("bg_secondary")
            check_text = ""
            check_fg = card_bg
        
        text_color = self.get_color("text_primary")
        secondary_text = self.get_color("text_secondary")

        try:
            card_data['card'].configure(bg=card_bg, highlightbackground=border_color, highlightthickness=border_width)
            card_data['inner'].configure(bg=card_bg)
            card_data['top_row'].configure(bg=card_bg)
            card_data['check_label'].configure(bg=check_bg, text=check_text, fg=check_fg)
            card_data['name_label'].configure(bg=card_bg, fg=text_color)
            card_data['desc_label'].configure(bg=card_bg, fg=secondary_text)
        except tk.TclError:
            pass

    def _select_all_visible(self):
        """Select all visible voices"""
        profiles = self.gui.voice_profiles
        
        if self.gender_filter == "female":
            profiles = [p for p in profiles if p.get("gender") == "female"]
        elif self.gender_filter == "male":
            profiles = [p for p in profiles if p.get("gender") == "male"]

        max_voices = getattr(self.gui, 'max_voice_selection', 10)
        current_selected = sum(1 for var in self.gui.voice_vars.values() if var.get())
        available_slots = max_voices - current_selected

        if available_slots <= 0:
            from ui.components.custom_dialog import show_info
            show_info(self.gui.root, "알림", f"이미 {max_voices}개가 선택되어 있습니다.")
            return

        selected_count = 0
        for profile in profiles:
            var = self.gui.voice_vars.get(profile["id"])
            if var and not var.get():
                if selected_count >= available_slots:
                    break
                var.set(True)
                self._update_card_style(profile["id"])
                selected_count += 1

        self._update_voice_summary()

        voice_manager = getattr(self.gui, 'voice_manager', None)
        if voice_manager is not None:
            save_fn = getattr(voice_manager, 'save_voice_selections', None)
            if save_fn is not None:
                save_fn()

    def _deselect_all_visible(self):
        """Deselect all visible voices"""
        profiles = self.gui.voice_profiles

        if self.gender_filter == "female":
            profiles = [p for p in profiles if p.get("gender") == "female"]
        elif self.gender_filter == "male":
            profiles = [p for p in profiles if p.get("gender") == "male"]

        for profile in profiles:
            var = self.gui.voice_vars.get(profile["id"])
            if var:
                var.set(False)
                self._update_card_style(profile["id"])

        self._update_voice_summary()

        voice_manager = getattr(self.gui, 'voice_manager', None)
        if voice_manager is not None:
            save_fn = getattr(voice_manager, 'save_voice_selections', None)
            if save_fn is not None:
                save_fn()

    def _update_voice_summary(self):
        """Update the selected voice count badge"""
        selected_voices = []
        for profile in self.gui.voice_profiles:
            var = self.gui.voice_vars.get(profile["id"])
            if var and var.get():
                selected_voices.append(profile["label"])

        count = len(selected_voices)
        
        if count > 0:
            self.count_badge.config(
                text=f"{count}개 선택",
                bg=self.get_color("primary"),
                fg="#FFFFFF"
            )
        else:
            self.count_badge.config(
                text="0개 선택",
                bg=self.get_color("error"),
                fg="#FFFFFF"
            )

        update_voice_summary_fn = getattr(self.gui, 'update_voice_summary', None)
        if update_voice_summary_fn is not None:
            update_voice_summary_fn()

    def refresh_voice_cards(self):
        """Refresh voice card styles after loading saved selections"""
        for voice_id in self.voice_cards.keys():
            self._update_card_style(voice_id)
        self._update_voice_summary()

    def _on_tab_click(self, tab_id: str):
        """Handle gender tab click"""
        if tab_id == self.gender_filter:
            return
        
        # Update active tab
        self.gender_filter = tab_id
        
        # Update tab button styles
        for tid, btn in self.tab_buttons.items():
            if tid == tab_id:
                btn.configure(bg=self.get_color("primary"), fg="#FFFFFF", font=("맑은 고딕", 10, "bold"))
            else:
                btn.configure(bg=self.get_color("bg_card"), fg=self.get_color("text_secondary"), font=("맑은 고딕", 10, "normal"))
        
        # Rebuild cards with new filter
        self._build_voice_cards()
        self.refresh_voice_cards()

    def _on_canvas_configure(self, event):
        """Handle canvas resize"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        # Update canvas window width
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_frame_configure(self, event):
        """Handle frame resize"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling"""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def apply_theme(self):
        """Apply theme - rebuild panel with new colors"""
        try:
            # Update main frame
            self.configure(bg=self.get_color("bg_card"))
            
            # Update header and tab frames
            for child in self.winfo_children():
                if isinstance(child, tk.Frame):
                    child.configure(bg=self.get_color("bg_card"))
                    for subchild in child.winfo_children():
                        if isinstance(subchild, tk.Label):
                            # Skip tab buttons and count badge
                            if subchild not in self.tab_buttons.values() and subchild != self.count_badge:
                                subchild.configure(bg=self.get_color("bg_card"), fg=self.get_color("text_primary"))
                        elif isinstance(subchild, tk.Frame):
                            subchild.configure(bg=self.get_color("bg_card"))

            # Update canvas
            if hasattr(self, 'canvas'):
                self.canvas.configure(bg=self.get_color("bg_card"))
            if hasattr(self, 'scrollable_frame'):
                self.scrollable_frame.configure(bg=self.get_color("bg_card"))

            # Update tab buttons
            for tid, btn in self.tab_buttons.items():
                if tid == self.gender_filter:
                    btn.configure(bg=self.get_color("primary"), fg="#FFFFFF")
                else:
                    btn.configure(bg=self.get_color("bg_card"), fg=self.get_color("text_secondary"))

            # Update select/deselect buttons
            self.select_btn.configure(bg=self.get_color("bg_card"), fg=self.get_color("primary"))
            self.deselect_btn.configure(bg=self.get_color("bg_card"), fg=self.get_color("text_secondary"))

            # Rebuild voice cards with new theme
            self._build_voice_cards()
            self.refresh_voice_cards()

        except tk.TclError:
            pass
