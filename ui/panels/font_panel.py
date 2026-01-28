"""
Font selection panel for choosing subtitle fonts
세련된 폰트 카드 선택 UI
"""
import logging
import os
import sys
import tkinter as tk
from tkinter import ttk
from typing import Optional

from managers.settings_manager import get_settings_manager

logger = logging.getLogger(__name__)

# Windows에서 TTF 폰트를 Tkinter에서 사용할 수 있도록 등록
_REGISTERED_FONTS: dict = {}


def _register_font_for_tkinter(font_path: str) -> Optional[str]:
    """
    TTF 폰트를 Windows에 임시 등록하고 Tkinter에서 사용할 수 있는 폰트 이름 반환
    """
    if not os.path.exists(font_path):
        return None

    if font_path in _REGISTERED_FONTS:
        return _REGISTERED_FONTS[font_path]

    try:
        if sys.platform == 'win32':
            import ctypes
            from ctypes import wintypes

            # Windows GDI를 사용하여 폰트 등록
            gdi32 = ctypes.WinDLL('gdi32')
            AddFontResourceEx = gdi32.AddFontResourceExW
            AddFontResourceEx.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPVOID]
            AddFontResourceEx.restype = wintypes.INT

            FR_PRIVATE = 0x10  # 현재 프로세스에서만 사용

            result = AddFontResourceEx(font_path, FR_PRIVATE, None)
            if result > 0:
                # 폰트 파일에서 폰트 이름 추출
                font_name = _get_font_name_from_file(font_path)
                if font_name:
                    _REGISTERED_FONTS[font_path] = font_name
                    return font_name
    except Exception as e:
        logger.warning("[FontPanel] 폰트 등록 실패: %s", e)

    return None


def _get_font_name_from_file(font_path: str) -> Optional[str]:
    """TTF 파일에서 폰트 이름 추출"""
    try:
        from fontTools.ttLib import TTFont
        font = TTFont(font_path)
        name_table = font['name']

        # 폰트 패밀리 이름 찾기 (nameID 1 또는 4)
        for record in name_table.names:
            if record.nameID == 1:  # Font Family
                try:
                    return record.toUnicode()
                except (UnicodeDecodeError, AttributeError):
                    pass

        # fallback: 파일명에서 추출
        return os.path.splitext(os.path.basename(font_path))[0]
    except ImportError:
        # fontTools가 없으면 파일명 사용
        basename = os.path.splitext(os.path.basename(font_path))[0]
        # 일반적인 폰트 이름 매핑
        name_map = {
            "SeoulHangangB": "서울한강 장체 B",
            "SeoulHangangEB": "서울한강 장체 EB",
            "SeoulHangangM": "서울한강 장체 M",
            "SeoulHangangL": "서울한강 장체 L",
            "UnPeople": "유앤피플 고딕",
            "Pretendard-Black": "Pretendard Black",
            "Pretendard-Bold": "Pretendard Bold",
            "Pretendard-ExtraBold": "Pretendard ExtraBold",
            "Paperlogy-9Black": "Paperlogy 9Black",
            "Paperlogy-8ExtraBold": "Paperlogy 8ExtraBold",
            "Paperlogy-7Bold": "Paperlogy 7Bold",
            "GmarketSansTTFBold": "GmarketSans TTF Bold",
            "GmarketSansTTFMedium": "GmarketSans TTF Medium",
            "Pretendard-ExtraBold": "Pretendard ExtraBold",
            "Pretendard-Bold": "Pretendard Bold",
            "Pretendard-SemiBold": "Pretendard SemiBold",
        }
        return name_map.get(basename, basename)
    except (OSError, KeyError, ValueError) as e:
        logger.debug("폰트 이름 추출 실패, 파일명 사용: %s", e)
        return os.path.splitext(os.path.basename(font_path))[0]


from ui.components.base_widget import ThemedMixin
from ..theme_manager import ThemeManager, get_theme_manager


class FontPanel(tk.Frame, ThemedMixin):
    """Font selection panel with visual font cards"""

    def __init__(self, parent, gui, theme_manager: Optional[ThemeManager] = None):
        """
        Initialize the font selection panel.

        Args:
            parent: Parent tkinter widget
            gui: VideoAnalyzerGUI instance
            theme_manager: ThemeManager instance
        """
        self.__init_themed__(theme_manager)
        super().__init__(parent, bg=self.get_color("bg_card"), bd=0, highlightthickness=0)
        self.gui = gui
        self.font_cards = {}
        self.create_widgets()

    def create_widgets(self):
        """Create font selection widgets"""
        # ===== HEADER =====
        header = tk.Frame(self, bg=self.get_color("bg_card"))
        header.pack(fill=tk.X, padx=16, pady=(12, 8))

        tk.Label(
            header,
            text="폰트 선택",
            font=("맑은 고딕", 14, "bold"),
            bg=self.get_color("bg_card"),
            fg=self.get_color("text_primary")
        ).pack(side=tk.LEFT)

        # Selected font indicator
        self.selected_label = tk.Label(
            header,
            text="",
            font=("맑은 고딕", 9),
            bg=self.get_color("primary"),
            fg="#FFFFFF",
            padx=8,
            pady=2
        )
        self.selected_label.pack(side=tk.RIGHT)

        # ===== FONT CARDS CONTAINER =====
        self.cards_container = tk.Frame(self, bg=self.get_color("bg_card"))
        self.cards_container.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))

        # Build cards
        self._rebuild_cards()

        # Initialize selection from saved settings
        if not hasattr(self.gui, 'selected_font_id'):
            saved_font_id = get_settings_manager().get_font_id()
            self.gui.selected_font_id = saved_font_id

        self._update_selection_display()

    def _create_font_card(self, parent, option: dict, idx: int):
        """Create a single font card"""
        # Check if font exists
        font_paths = option.get("font_paths", [])
        font_exists = any(os.path.exists(fp) for fp in font_paths)
        
        # Theme colors
        card_bg = self.get_color("bg_card")
        card_border = self.get_color("border_light")
        text_color = self.get_color("text_primary")
        secondary_text = self.get_color("text_secondary")
        disabled_bg = self.get_color("bg_main")
        
        if not font_exists:
            card_bg = disabled_bg
            text_color = secondary_text

        # Card frame
        card = tk.Frame(
            parent,
            bg=card_bg,
            highlightbackground=card_border,
            highlightthickness=1,
            cursor="hand2" if font_exists else "arrow"
        )
        card.pack(fill=tk.X, pady=4)

        # Check if selected
        is_selected = getattr(self.gui, 'selected_font_id', 'seoul_hangang') == option["id"]
        
        if is_selected and font_exists:
            selected_bg = self.get_color("bg_selected")
            card.configure(bg=selected_bg, highlightbackground=self.get_color("primary"), highlightthickness=2)
            card_bg = selected_bg

        # Inner content
        inner = tk.Frame(card, bg=card_bg)
        inner.pack(fill=tk.X, padx=12, pady=10)

        # Left: Radio + Font name
        left_frame = tk.Frame(inner, bg=card_bg)
        left_frame.pack(side=tk.LEFT, fill=tk.Y)

        # Radio indicator
        if not font_exists:
            radio_text = "✕"
            radio_fg = secondary_text
        else:
            radio_text = "●" if is_selected else "○"
            radio_fg = self.get_color("primary") if is_selected else secondary_text

        radio_label = tk.Label(
            left_frame,
            text=radio_text,
            font=("맑은 고딕", 12),
            bg=card_bg,
            fg=radio_fg,
            cursor="hand2" if font_exists else "arrow"
        )
        radio_label.pack(side=tk.LEFT, padx=(0, 10))

        # Font info frame
        info_frame = tk.Frame(left_frame, bg=card_bg)
        info_frame.pack(side=tk.LEFT)

        # Font name
        name_text = option["name"] if font_exists else f"{option['name']} (없음)"
        name_label = tk.Label(
            info_frame,
            text=name_text,
            font=("맑은 고딕", 11, "bold"),
            bg=card_bg,
            fg=text_color,
            anchor="w",
            cursor="hand2" if font_exists else "arrow"
        )
        name_label.pack(anchor="w")

        # Description
        desc_label = tk.Label(
            info_frame,
            text=option["description"] if font_exists else "폰트 파일이 없습니다",
            font=("맑은 고딕", 9),
            bg=card_bg,
            fg=secondary_text,
            anchor="w",
            cursor="hand2" if font_exists else "arrow"
        )
        desc_label.pack(anchor="w")

        # Right: Font preview
        preview_label = None
        if font_exists:
            # Register font and get name
            custom_font_name = None
            for font_path in font_paths:
                if os.path.exists(font_path):
                    registered_name = _register_font_for_tkinter(font_path)
                    if registered_name:
                        custom_font_name = registered_name
                        break

            preview_font = (custom_font_name, 14) if custom_font_name else ("맑은 고딕", 14, "bold")
            
            preview_label = tk.Label(
                inner,
                text=option["preview"],
                font=preview_font,
                bg=card_bg,
                fg=self.get_color("primary") if is_selected else text_color,
                cursor="hand2"
            )
            preview_label.pack(side=tk.RIGHT, padx=(10, 0))

        # Click handlers (only if font exists)
        if font_exists:
            def on_click(e, fid=option["id"]):
                self._select_font(fid)

            for widget in [card, inner, left_frame, info_frame, radio_label, name_label, desc_label]:
                widget.bind("<Button-1>", on_click)
            
            if preview_label:
                preview_label.bind("<Button-1>", on_click)

            # Hover effects
            def on_enter(e):
                if getattr(self.gui, 'selected_font_id', 'seoul_hangang') != option["id"]:
                    hover_bg = self.get_color("bg_hover")
                    card.configure(bg=hover_bg)
                    inner.configure(bg=hover_bg)
                    for w in [left_frame, info_frame, radio_label, name_label, desc_label]:
                        try:
                            w.configure(bg=hover_bg)
                        except tk.TclError:
                            pass
                    if preview_label:
                        try:
                            preview_label.configure(bg=hover_bg)
                        except tk.TclError:
                            pass

            def on_leave(e):
                if getattr(self.gui, 'selected_font_id', 'seoul_hangang') != option["id"]:
                    card.configure(bg=card_bg)
                    inner.configure(bg=card_bg)
                    for w in [left_frame, info_frame, radio_label, name_label, desc_label]:
                        try:
                            w.configure(bg=card_bg)
                        except tk.TclError:
                            pass
                    if preview_label:
                        try:
                            preview_label.configure(bg=card_bg)
                        except tk.TclError:
                            pass

            card.bind("<Enter>", on_enter)
            card.bind("<Leave>", on_leave)

        # Store reference
        self.font_cards[option["id"]] = {
            'card': card,
            'inner': inner,
            'radio_label': radio_label,
            'name_label': name_label,
            'desc_label': desc_label,
            'left_frame': left_frame,
            'info_frame': info_frame,
            'font_exists': font_exists,
            'option': option
        }

        if not hasattr(self.gui, 'font_option_widgets'):
            self.gui.font_option_widgets = {}
        self.gui.font_option_widgets[option["id"]] = {
            'row_frame': card,
            'radio_label': radio_label,
            'bg_color': card_bg,
            'font_exists': font_exists
        }

    def _select_font(self, font_id: str):
        """Handle font selection"""
        self.gui.selected_font_id = font_id
        get_settings_manager().set_font_id(font_id)
        
        # Update UI state without full rebuild
        self._update_selection_display()
        for fid, card_data in self.font_cards.items():
            self._update_card_visual(fid)

    def _update_card_visual(self, font_id: str):
        """Update a single card's visual state based on selection"""
        if font_id not in self.font_cards:
            return
        
        card_data = self.font_cards[font_id]
        option = card_data['option']
        font_exists = card_data['font_exists']
        
        is_selected = getattr(self.gui, 'selected_font_id', 'seoul_hangang') == font_id
        
        card_bg = self.get_color("bg_card")
        text_color = self.get_color("text_primary")
        secondary_text = self.get_color("text_secondary")
        
        if not font_exists:
            card_bg = self.get_color("bg_main")
            text_color = secondary_text
        elif is_selected:
            card_bg = self.get_color("bg_selected")
        
        radio_text = "●" if is_selected else "○" if font_exists else "✕"
        radio_fg = self.get_color("primary") if is_selected else secondary_text
        border_color = self.get_color("primary") if is_selected else self.get_color("border_light")
        border_width = 2 if is_selected else 1

        card_data['card'].configure(bg=card_bg, highlightbackground=border_color, highlightthickness=border_width)
        card_data['inner'].configure(bg=card_bg)
        card_data['left_frame'].configure(bg=card_bg)
        card_data['info_frame'].configure(bg=card_bg)
        card_data['radio_label'].configure(bg=card_bg, fg=radio_fg, text=radio_text)
        card_data['name_label'].configure(bg=card_bg, fg=text_color)
        card_data['desc_label'].configure(bg=card_bg, fg=secondary_text)

    def _rebuild_cards(self):
        """Rebuild all font cards"""
        # Clear existing
        for widget in self.cards_container.winfo_children():
            widget.destroy()
        
        self.font_cards.clear()
        
        project_fonts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "fonts")
        
        font_options = [
            {
                "name": "서울 한강체",
                "id": "seoul_hangang",
                "preview": "쇼핑 숏폼 자막",
                "description": "모던하고 깔끔한 서울시 공식 폰트",
                "font_paths": [os.path.join(project_fonts_dir, "SeoulHangangB.ttf")]
            },
            {
                "name": "프리텐다드",
                "id": "pretendard",
                "preview": "쇼핑 숏폼 자막",
                "description": "세련된 현대적 고딕체",
                "font_paths": [os.path.join(project_fonts_dir, "Pretendard-ExtraBold.ttf")]
            },
            {
                "name": "G마켓 산스",
                "id": "gmarketsans",
                "preview": "쇼핑 숏폼 자막",
                "description": "인기 있는 고품질 무료 폰트",
                "font_paths": [os.path.join(project_fonts_dir, "GmarketSansTTFBold.ttf")]
            },
            {
                "name": "페이퍼로지",
                "id": "paperlogy",
                "preview": "쇼핑 숏폼 자막",
                "description": "부드러운 곡선이 매력적인 폰트",
                "font_paths": [os.path.join(project_fonts_dir, "Paperlogy-9Black.ttf")]
            },
            {
                "name": "유앤피플",
                "id": "unpeople_gothic",
                "preview": "쇼핑 숏폼 자막",
                "description": "부드럽고 가독성 좋은 고딕체",
                "font_paths": [os.path.join(project_fonts_dir, "UnPeople.ttf")]
            }
        ]
        
        for idx, option in enumerate(font_options):
            self._create_font_card(self.cards_container, option, idx)

    def _update_selection_display(self):
        """Update the selected font indicator"""
        selected_font_id = getattr(self.gui, 'selected_font_id', 'seoul_hangang')
        
        # Find selected font name
        font_options = [
            {"id": "seoul_hangang", "name": "서울 한강체"},
            {"id": "pretendard", "name": "프리텐다드"},
            {"id": "gmarketsans", "name": "G마켓 산스"},
            {"id": "paperlogy", "name": "페이퍼로지"},
            {"id": "unpeople_gothic", "name": "유앤피플"}
        ]
        
        selected_font_name = "선택 안됨"
        for option in font_options:
            if option["id"] == selected_font_id:
                selected_font_name = option["name"]
                break
        
        self.selected_label.config(
            text=selected_font_name,
            bg=self.get_color("primary"),
            fg="#FFFFFF"
        )
    
    def apply_theme(self):
        """Apply theme - rebuild panel with new colors"""
        try:
            self.configure(bg=self.get_color("bg_card"))
            
            # Update header
            for child in self.winfo_children():
                if isinstance(child, tk.Frame):
                    child.configure(bg=self.get_color("bg_card"))
                    for subchild in child.winfo_children():
                        if isinstance(subchild, tk.Label) and subchild != self.selected_label:
                            subchild.configure(bg=self.get_color("bg_card"), fg=self.get_color("text_primary"))

            # Rebuild font cards
            self._rebuild_cards()
            self._update_selection_display()

        except tk.TclError:
            pass
