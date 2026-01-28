"""
CTA (Call to Action) selection panel for choosing ending messages
세련된 비주얼 카드 선택 UI
"""
import os
import tkinter as tk
from tkinter import ttk
from typing import Optional

from managers.settings_manager import get_settings_manager


# CTA 옵션 정의 (10개)
CTA_OPTIONS = [
    {
        "name": "댓글형",
        "id": "default",
        "description": "고정댓글로 유도하는 깔끔한 멘트",
        "lines": ["영상 속 제품 정보는", "아래 고정댓글에서", "확인해 보세요!"]
    },
    {
        "name": "캡션형",
        "id": "option1",
        "description": "캡션(본문) 확인을 유도하는 직관적 멘트",
        "lines": ["궁금하신 제품 정보는", "영상 하단 캡션에", "적어두었습니다."]
    },
    {
        "name": "직진형",
        "id": "option2",
        "description": "즉시 구매 링크 클릭을 유도하는 강력한 멘트",
        "lines": ["이 제품이 마음에 든다면", "하단 제품 링크를", "지금 눌러보세요!"]
    },
    {
        "name": "링크형",
        "id": "option3",
        "description": "추가 정보를 위해 링크 클릭을 유도하는 멘트",
        "lines": ["구매 정보가 궁금할 땐", "영상 아래 링크를", "바로 클릭하세요."]
    },
    {
        "name": "버튼형",
        "id": "option4",
        "description": "제품보기 버튼 클릭을 유도하는 안내 멘트",
        "lines": ["영상 속 핫템 정보는", "왼쪽 하단 버튼에서", "확인 가능합니다!"]
    },
    # 추가 5개
    {
        "name": "할인형",
        "id": "option5",
        "description": "할인 혜택을 강조하는 멘트",
        "lines": ["지금 구매하면", "특별 할인 혜택이", "적용됩니다!"]
    },
    {
        "name": "한정형",
        "id": "option6",
        "description": "수량 한정 긴급함을 주는 멘트",
        "lines": ["수량 한정 상품!", "품절 전에", "서두르세요!"]
    },
    {
        "name": "후기형",
        "id": "option7",
        "description": "실제 후기 확인을 유도하는 멘트",
        "lines": ["실제 구매 후기가", "궁금하다면", "댓글을 확인하세요!"]
    },
    {
        "name": "질문형",
        "id": "option8",
        "description": "댓글 참여를 유도하는 멘트",
        "lines": ["이 제품 어떠세요?", "의견을 댓글로", "남겨주세요!"]
    },
    {
        "name": "팔로우형",
        "id": "option9",
        "description": "팔로우를 유도하는 멘트",
        "lines": ["더 많은 추천템은", "팔로우하고", "확인하세요!"]
    },
]


from ui.components.base_widget import ThemedMixin
from ..theme_manager import ThemeManager, get_theme_manager


class CTAPanel(tk.Frame, ThemedMixin):
    """CTA selection panel with visual CTA cards"""

    def __init__(self, parent, gui, theme_manager: Optional[ThemeManager] = None):
        """
        Initialize the CTA selection panel.

        Args:
            parent: Parent tkinter widget
            gui: VideoAnalyzerGUI instance
            theme_manager: ThemeManager instance
        """
        self.__init_themed__(theme_manager)
        super().__init__(parent, bg=self.get_color("bg_card"), bd=0, highlightthickness=0)
        self.gui = gui
        self.cta_cards = {}
        self.create_widgets()

    def create_widgets(self):
        """Create CTA selection widgets"""
        # ===== HEADER =====
        self._header = tk.Frame(self, bg=self.get_color("bg_card"))
        self._header.pack(fill=tk.X, padx=16, pady=(12, 8))

        self._title_label = tk.Label(
            self._header,
            text="CTA 선택",
            font=("맑은 고딕", 14, "bold"),
            bg=self.get_color("bg_card"),
            fg=self.get_color("text_primary")
        )
        self._title_label.pack(side=tk.LEFT)

        # 선택된 CTA 표시 라벨 (더 눈에 띄게)
        self.selected_cta_label = tk.Label(
            self._header,
            text="✓ 선택됨",
            font=("맑은 고딕", 10, "bold"),
            bg=self.get_color("primary"),
            fg="#FFFFFF",
            padx=12,
            pady=4
        )
        self.selected_cta_label.pack(side=tk.RIGHT)

        # ===== CTA CARDS CONTAINER =====
        self.container = tk.Frame(self, bg=self.get_color("bg_card"))
        self.container.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))

        # Build cards
        self._build_cta_cards()

        # Initialize selection
        if not hasattr(self.gui, 'selected_cta_id'):
            saved_cta_id = get_settings_manager().get_cta_id()
            self.gui.selected_cta_id = saved_cta_id
        
        self._update_selection_display()

    def _build_cta_cards(self):
        """Build all CTA selection cards"""
        # Clear existing
        for widget in self.container.winfo_children():
            widget.destroy()
        
        self.cta_cards.clear()
        
        # Grid layout for CTA cards (2 columns)
        for idx, option in enumerate(CTA_OPTIONS):
            row = idx // 2
            col = idx % 2
            self._create_cta_card(self.container, option, row, col)

    def _create_cta_card(self, parent, option: dict, row: int, col: int):
        """Create a single CTA selection card"""
        is_selected = getattr(self.gui, 'selected_cta_id', 'default') == option["id"]
        
        # Theme colors
        card_bg = self.get_color("bg_card")
        card_border = self.get_color("border_light")
        text_color = self.get_color("text_primary")
        secondary_text = self.get_color("text_secondary")
        
        if is_selected:
            card_bg = self.get_color("bg_selected")
            card_border = self.get_color("primary")
            border_width = 2
        else:
            border_width = 1

        card = tk.Frame(
            parent,
            bg=card_bg,
            highlightbackground=card_border,
            highlightthickness=border_width,
            cursor="hand2"
        )
        card.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
        
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)

        # Content padding
        inner = tk.Frame(card, bg=card_bg)
        inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # Name + Icon
        header_row = tk.Frame(inner, bg=card_bg)
        header_row.pack(fill=tk.X)

        icon_text = "📍" if option["id"] == "default" else "📝" if option["id"] == "option1" else "🔥" if option["id"] == "option2" else "🔗" if option["id"] == "option3" else "🖱️"
        
        tk.Label(
            header_row,
            text=f"{icon_text} {option['name']}",
            font=("맑은 고딕", 11, "bold"),
            bg=card_bg,
            fg=self.get_color("primary") if is_selected else text_color,
            cursor="hand2"
        ).pack(side=tk.LEFT)

        # Lines preview (3 lines)
        preview_bg = self.get_color("bg_secondary")
        preview_frame = tk.Frame(inner, bg=preview_bg, padx=8, pady=6)
        preview_frame.pack(fill=tk.X, pady=(8, 6))

        for line in option["lines"]:
            tk.Label(
                preview_frame,
                text=line,
                font=("맑은 고딕", 8),
                bg=preview_bg,
                fg=secondary_text,
                cursor="hand2"
            ).pack(anchor="w")

        # Description
        tk.Label(
            inner,
            text=option["description"],
            font=("맑은 고딕", 8),
            bg=card_bg,
            fg=secondary_text,
            anchor="w",
            wraplength=150,
            cursor="hand2"
        ).pack(fill=tk.X)

        # Click handlers
        def on_click(e, cid=option["id"]):
            self._select_cta(cid)
        
        for widget in [card, inner, header_row, preview_frame]:
            widget.bind("<Button-1>", on_click)
        
        for widget in preview_frame.winfo_children():
            widget.bind("<Button-1>", on_click)

        # Hover
        def on_enter(e):
            if getattr(self.gui, 'selected_cta_id', 'default') != option["id"]:
                hover_bg = self.get_color("bg_hover")
                card.configure(bg=hover_bg)
                inner.configure(bg=hover_bg)
                header_row.configure(bg=hover_bg)
                for w in header_row.winfo_children():
                    try:
                        w.configure(bg=hover_bg)  # type: ignore
                    except tk.TclError:
                        pass

        def on_leave(e):
            if getattr(self.gui, 'selected_cta_id', 'default') != option["id"]:
                card.configure(bg=card_bg)
                inner.configure(bg=card_bg)
                header_row.configure(bg=card_bg)
                for w in header_row.winfo_children():
                    try:
                        w.configure(bg=card_bg)  # type: ignore
                    except tk.TclError:
                        pass

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

        # Store reference
        self.cta_cards[option["id"]] = card

    def _select_cta(self, cta_id: str):
        """Handle CTA selection"""
        self.gui.selected_cta_id = cta_id
        get_settings_manager().set_cta_id(cta_id)
        
        # Rebuild to update visual state
        self._build_cta_cards()
        self._update_selection_display()

    def _update_selection_display(self):
        """Update selected CTA indicator with name and preview"""
        cta_id = getattr(self.gui, 'selected_cta_id', 'default')
        name = "선택 안됨"
        preview = ""

        for opt in CTA_OPTIONS:
            if opt["id"] == cta_id:
                name = opt["name"]
                # 첫 번째 라인을 미리보기로 표시
                if opt.get("lines"):
                    preview = opt["lines"][0][:12]  # 최대 12자
                    if len(opt["lines"][0]) > 12:
                        preview += "..."
                break

        # 이름 + 미리보기 표시
        display_text = f"✓ {name}"
        if preview:
            display_text += f" | {preview}"

        self.selected_cta_label.config(text=display_text)

    def apply_theme(self):
        """Apply theme colors"""
        try:
            bg_card = self.get_color("bg_card")
            text_primary = self.get_color("text_primary")
            primary = self.get_color("primary")

            self.configure(bg=bg_card)

            # 헤더 프레임 업데이트
            if hasattr(self, '_header'):
                self._header.configure(bg=bg_card)

            # 타이틀 라벨 업데이트
            if hasattr(self, '_title_label'):
                self._title_label.configure(bg=bg_card, fg=text_primary)

            # 선택된 CTA 라벨 배경색 업데이트 (테마에 맞게)
            if hasattr(self, 'selected_cta_label'):
                self.selected_cta_label.configure(bg=primary, fg="#FFFFFF")

            # 컨테이너 업데이트
            if hasattr(self, 'container'):
                self.container.configure(bg=bg_card)

            # Rebuild cards with new theme
            self._build_cta_cards()
            self._update_selection_display()

        except tk.TclError:
            pass  # 위젯이 파괴된 경우


def get_selected_cta_lines(gui) -> list:
    """Get the CTA lines for the selected CTA option"""
    selected_id = getattr(gui, 'selected_cta_id', 'default')
    for option in CTA_OPTIONS:
        if option["id"] == selected_id:
            return option["lines"]
    # Fallback to default
    return CTA_OPTIONS[0]["lines"]
