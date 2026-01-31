# -*- coding: utf-8 -*-
"""
Shopping Shorts Maker Design System
?¼í•‘ ?í¼ ë©”ì´ì»??”ì???œìŠ¤??
STITCH MCPë¥??µí•´ ?ì„±???”ì?¸ì„ ê¸°ë°˜?¼ë¡œ ???µí•© ?”ì???œìŠ¤??
PyQt5 ë°?PyQt6?ì„œ ê³µí†µ?¼ë¡œ ?¬ìš©?????ˆëŠ” ?‰ìƒ, ?°íŠ¸, ?¤í????•ì˜.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
from enum import Enum


class ColorMode(Enum):
    """?‰ìƒ ëª¨ë“œ / Color mode enumeration"""
    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True)
class ColorPalette:
    """
    ?‰ìƒ ?”ë ˆ???•ì˜ / Color palette definition
    STITCH MCP ?”ì??ê¸°ë°˜ - ?ˆë“œ/ì½”ë„ ?Œë§ˆ
    """

    # Primary Colors (STITCH ?ˆë“œ ê³„ì—´)
    primary: str = "#e31639"           # ë©”ì¸ ?ˆë“œ (STITCH ê¸°ì?)
    primary_hover: str = "#c41231"     # ?¸ë²„ ???´ë‘???ˆë“œ
    primary_light: str = "#fce8eb"     # ?°í•œ ?ˆë“œ (ë°°ê²½??
    primary_dark: str = "#a01028"      # ì§„í•œ ?ˆë“œ

    # Secondary Colors
    secondary: str = "#ff4d6a"         # ë³´ì¡° ?‘í¬/?ˆë“œ
    secondary_light: str = "#ffb3c1"   # ?°í•œ ë³´ì¡°??
    # Background Colors (STITCH ê¸°ì?)
    bg_main: str = "#f8f6f6"           # ë©”ì¸ ë°°ê²½ (STITCH light)
    bg_card: str = "#FFFFFF"           # ì¹´ë“œ ë°°ê²½
    bg_sidebar: str = "#FFFFFF"        # ?¬ì´?œë°” ë°°ê²½ (light)
    bg_input: str = "#F3F4F6"          # ?…ë ¥ ?„ë“œ ë°°ê²½
    bg_hover: str = "#F3F4F6"          # ?¸ë²„ ë°°ê²½
    bg_selected: str = "#fce8eb"       # ? íƒ????ª© ë°°ê²½
    bg_secondary: str = "#F3F4F6"      # ë³´ì¡° ë°°ê²½
    bg_header: str = "#FFFFFF"         # ?¤ë” ë°°ê²½

    # Text Colors (STITCH slate ê³„ì—´)
    text_primary: str = "#1b0e10"      # ì£¼ìš” ?ìŠ¤??(ê±°ì˜ ê²€??
    text_secondary: str = "#64748b"    # ë³´ì¡° ?ìŠ¤??(slate-500)
    text_disabled: str = "#94a3b8"     # ë¹„í™œ???ìŠ¤??(slate-400)
    text_on_primary: str = "#FFFFFF"   # primary ë°°ê²½ ???ìŠ¤??
    # Border Colors
    border_light: str = "#e2e8f0"      # ?°í•œ ?Œë‘ë¦?(slate-200)
    border_focus: str = "#e31639"      # ?¬ì»¤???Œë‘ë¦?(primary)
    border_card: str = "#e2e8f0"       # ì¹´ë“œ ?Œë‘ë¦?
    # Status Colors
    success: str = "#22C55E"           # ?±ê³µ/?„ë£Œ
    success_light: str = "#F0FDF4"     # ?±ê³µ ë°°ê²½
    success_border: str = "#BBF7D0"    # ?±ê³µ ?Œë‘ë¦?
    error: str = "#EF4444"             # ?¤ë¥˜/?¤íŒ¨
    error_light: str = "#FEF2F2"       # ?¤ë¥˜ ë°°ê²½
    error_border: str = "#FECACA"      # ?¤ë¥˜ ?Œë‘ë¦?
    warning: str = "#F59E0B"           # ê²½ê³ 
    warning_light: str = "#FFFBEB"     # ê²½ê³  ë°°ê²½
    warning_border: str = "#FDE68A"    # ê²½ê³  ?Œë‘ë¦?
    info: str = "#3B82F6"              # ?•ë³´
    info_light: str = "#EFF6FF"        # ?•ë³´ ë°°ê²½

    # Gradient Colors (STITCH red gradient)
    gradient_start: str = "#e31639"    # ê·¸ë¼?°ì´???œì‘
    gradient_end: str = "#ff4d6a"      # ê·¸ë¼?°ì´????
    # Scrollbar Colors
    scrollbar_bg: str = "#F3F4F6"      # ?¤í¬ë¡¤ë°” ë°°ê²½
    scrollbar_thumb: str = "#D1D5DB"   # ?¤í¬ë¡¤ë°” ??

@dataclass(frozen=True)
class DarkColorPalette(ColorPalette):
    """
    ?¤í¬ ëª¨ë“œ ?‰ìƒ ?”ë ˆ??/ Dark mode color palette
    STITCH MCP ?”ì??ê¸°ë°˜ - ?ˆë“œ/ì½”ë„ ?¤í¬ ?Œë§ˆ
    """

    # Primary Colors (STITCH red - ?¤í¬ëª¨ë“œ?ì„œ ë°ê²Œ)
    primary: str = "#ff4d6a"           # ë°ì? ?ˆë“œ/?‘í¬
    primary_hover: str = "#ff6b84"     # ??ë°ì? ?ˆë“œ
    primary_light: str = "#3d1a1e"     # ?´ë‘???ˆë“œ ë°°ê²½
    primary_dark: str = "#e31639"

    # Secondary Colors
    secondary: str = "#ff6b84"
    secondary_light: str = "#4d2a2e"

    # Background Colors (STITCH dark - #211113 ê¸°ë°˜)
    bg_main: str = "#211113"           # ë©”ì¸ ë°°ê²½ (STITCH dark)
    bg_card: str = "#2d1a1c"           # ì¹´ë“œ ë°°ê²½ (zinc-900 ?ë‚Œ)
    bg_sidebar: str = "#1a0d0e"        # ?¬ì´?œë°” (???´ë‘¡ê²?
    bg_input: str = "#3d2426"          # ?…ë ¥ ?„ë“œ ë°°ê²½
    bg_hover: str = "#3d2426"          # ?¸ë²„ ë°°ê²½
    bg_selected: str = "#4d2a2e"       # ? íƒ????ª© ë°°ê²½
    bg_secondary: str = "#2d1a1c"      # ë³´ì¡° ë°°ê²½
    bg_header: str = "#1a0d0e"         # ?¤ë” ë°°ê²½

    # Text Colors
    text_primary: str = "#FFFFFF"      # ì£¼ìš” ?ìŠ¤??    text_secondary: str = "#a0a0a0"    # ë³´ì¡° ?ìŠ¤??    text_disabled: str = "#666666"     # ë¹„í™œ???ìŠ¤??
    # Border Colors
    border_light: str = "#3d2426"      # ?°í•œ ?Œë‘ë¦?    border_focus: str = "#ff4d6a"      # ?¬ì»¤???Œë‘ë¦?    border_card: str = "#3d2426"       # ì¹´ë“œ ?Œë‘ë¦?
    # Status Colors (?¤í¬ëª¨ë“œ?ì„œ ë°ê²Œ)
    success: str = "#34D399"
    success_light: str = "#1a2e1a"
    error: str = "#F87171"
    error_light: str = "#2e1a1a"
    warning: str = "#FBBF24"
    warning_light: str = "#2e2a1a"

    # Gradient Colors
    gradient_start: str = "#e31639"
    gradient_end: str = "#ff4d6a"

    # Scrollbar Colors
    scrollbar_bg: str = "#2d1a1c"
    scrollbar_thumb: str = "#4d2a2e"


@dataclass
class Typography:
    """?€?´í¬ê·¸ë˜???•ì˜ / Typography definition (STITCH ê¸°ë°˜)"""

    # Font Families (STITCH - Inter ?°íŠ¸ ?¬ìš©)
    font_family_primary: str = "Inter"
    font_family_fallback: str = "Inter, Pretendard, Malgun Gothic, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    font_family_mono: str = "JetBrains Mono, Consolas, Monaco, monospace"

    # Font Sizes (px)
    font_size_xs: int = 10
    font_size_sm: int = 11
    font_size_base: int = 12
    font_size_md: int = 13
    font_size_lg: int = 14
    font_size_xl: int = 16
    font_size_2xl: int = 18
    font_size_3xl: int = 20
    font_size_4xl: int = 24

    # Font Weights
    font_weight_normal: str = "normal"
    font_weight_medium: str = "medium"
    font_weight_bold: str = "bold"

    # Line Heights
    line_height_tight: float = 1.25
    line_height_normal: float = 1.5
    line_height_relaxed: float = 1.75


@dataclass
class Spacing:
    """ê°„ê²© ?•ì˜ / Spacing definition"""

    # Base unit: 4px
    xs: int = 4      # 0.25rem
    sm: int = 8      # 0.5rem
    md: int = 12     # 0.75rem
    lg: int = 16     # 1rem
    xl: int = 20     # 1.25rem
    xxl: int = 24    # 1.5rem
    xxxl: int = 32   # 2rem

    # Component-specific spacing
    card_padding: int = 16
    card_margin: int = 8
    button_padding_x: int = 16
    button_padding_y: int = 8
    input_padding: int = 10
    section_gap: int = 24


@dataclass
class BorderRadius:
    """ëª¨ì„œë¦??¥ê?ê¸??•ì˜ / Border radius definition"""

    none: int = 0
    sm: int = 4
    md: int = 8
    lg: int = 12
    xl: int = 16
    full: int = 9999  # ?„ì „ ?¥ê?ê²?

@dataclass
class Shadow:
    """ê·¸ë¦¼???•ì˜ / Shadow definition"""

    # PyQt5 ?¤í???ë¬¸ì?´ì´ ?„ë‹Œ ë°•ìŠ¤ ?€?„ìš° ê°?    none: str = "none"
    sm: str = "0 1px 2px rgba(0, 0, 0, 0.05)"
    md: str = "0 4px 6px -1px rgba(0, 0, 0, 0.1)"
    lg: str = "0 10px 15px -3px rgba(0, 0, 0, 0.1)"
    xl: str = "0 20px 25px -5px rgba(0, 0, 0, 0.1)"

    # Glow effects for dark mode
    glow_primary: str = "0 0 20px rgba(124, 58, 237, 0.3)"
    glow_success: str = "0 0 10px rgba(34, 197, 94, 0.3)"


@dataclass
class Animation:
    """? ë‹ˆë©”ì´???•ì˜ / Animation definition"""

    duration_fast: int = 150      # ms
    duration_normal: int = 300    # ms
    duration_slow: int = 500      # ms

    easing_default: str = "ease-out"
    easing_bounce: str = "cubic-bezier(0.68, -0.55, 0.265, 1.55)"


class DesignSystem:
    """
    ?µí•© ?”ì???œìŠ¤???´ë˜??    Unified Design System class

    STITCH?ì„œ ?ì„±???”ì?¸ì„ ê¸°ë°˜?¼ë¡œ ??ëª¨ë“  UI ?¤í??¼ì„ ê´€ë¦¬í•©?ˆë‹¤.
    """

    _instance: Optional['DesignSystem'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._color_mode = ColorMode.LIGHT
        self._colors = ColorPalette()
        self._dark_colors = DarkColorPalette()
        self.typography = Typography()
        self.spacing = Spacing()
        self.radius = BorderRadius()
        self.shadow = Shadow()
        self.animation = Animation()

        self._initialized = True

    @property
    def colors(self) -> ColorPalette:
        """?„ì¬ ?‰ìƒ ëª¨ë“œ???°ë¥¸ ?‰ìƒ ë°˜í™˜"""
        if self._color_mode == ColorMode.DARK:
            return self._dark_colors
        return self._colors

    @property
    def is_dark_mode(self) -> bool:
        """?¤í¬ ëª¨ë“œ ?¬ë?"""
        return self._color_mode == ColorMode.DARK

    def set_color_mode(self, mode: ColorMode) -> None:
        """?‰ìƒ ëª¨ë“œ ?¤ì •"""
        self._color_mode = mode

    def toggle_color_mode(self) -> ColorMode:
        """?‰ìƒ ëª¨ë“œ ? ê?"""
        if self._color_mode == ColorMode.LIGHT:
            self._color_mode = ColorMode.DARK
        else:
            self._color_mode = ColorMode.LIGHT
        return self._color_mode

    def get_color(self, name: str) -> str:
        """?‰ìƒ ?´ë¦„?¼ë¡œ ?‰ìƒê°?ë°˜í™˜"""
        return getattr(self.colors, name, self.colors.text_primary)

    # PyQt5 StyleSheet Generators
    def get_button_style(self, style: str = "primary") -> str:
        """ë²„íŠ¼ ?¤í??¼ì‹œ???ì„±"""
        c = self.colors
        r = self.radius

        if style == "primary":
            return f"""
                QPushButton {{
                    background-color: {c.primary};
                    color: {c.text_on_primary};
                    border: none;
                    border-radius: {r.lg}px;
                    padding: 8px 16px;
                    font-weight: bold;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: {c.primary_hover};
                }}
                QPushButton:pressed {{
                    background-color: {c.primary_dark};
                }}
                QPushButton:disabled {{
                    background-color: {c.border_light};
                    color: {c.text_disabled};
                }}
            """
        elif style == "secondary":
            return f"""
                QPushButton {{
                    background-color: {c.bg_secondary};
                    color: {c.text_primary};
                    border: 1px solid {c.border_light};
                    border-radius: {r.lg}px;
                    padding: 8px 16px;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: {c.bg_hover};
                    border-color: {c.primary};
                }}
                QPushButton:pressed {{
                    background-color: {c.bg_selected};
                }}
            """
        elif style == "outline":
            return f"""
                QPushButton {{
                    background-color: transparent;
                    color: {c.primary};
                    border: 1px solid {c.primary};
                    border-radius: {r.lg}px;
                    padding: 8px 16px;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: {c.primary_light};
                }}
                QPushButton:pressed {{
                    background-color: {c.bg_selected};
                }}
            """
        elif style == "danger":
            return f"""
                QPushButton {{
                    background-color: {c.error};
                    color: {c.text_on_primary};
                    border: none;
                    border-radius: {r.lg}px;
                    padding: 8px 16px;
                    font-weight: bold;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: #DC2626;
                }}
            """
        elif style == "gray":
            return f"""
                QPushButton {{
                    background-color: {c.bg_secondary};
                    color: {c.text_secondary};
                    border: none;
                    border-radius: {r.lg}px;
                    padding: 8px 16px;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: {c.bg_hover};
                }}
                QPushButton:disabled {{
                    background-color: {c.bg_secondary};
                    color: {c.text_disabled};
                }}
            """
        return ""

    def get_input_style(self) -> str:
        """?…ë ¥ ?„ë“œ ?¤í??¼ì‹œ??""
        c = self.colors
        r = self.radius
        return f"""
            QLineEdit, QTextEdit {{
                background-color: {c.bg_input};
                color: {c.text_primary};
                border: 1px solid {c.border_light};
                border-radius: {r.md}px;
                padding: 8px 12px;
                font-size: 12px;
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border-color: {c.primary};
                background-color: {c.bg_card};
            }}
            QLineEdit:disabled, QTextEdit:disabled {{
                background-color: {c.bg_secondary};
                color: {c.text_disabled};
            }}
        """

    def get_card_style(self) -> str:
        """ì¹´ë“œ ?¤í??¼ì‹œ??""
        c = self.colors
        r = self.radius
        return f"""
            QFrame {{
                background-color: {c.bg_card};
                border: 1px solid {c.border_card};
                border-radius: {r.xl}px;
            }}
        """

    def get_checkbox_style(self) -> str:
        """ì²´í¬ë°•ìŠ¤ ?¤í??¼ì‹œ??""
        c = self.colors
        return f"""
            QCheckBox {{
                color: {c.text_primary};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid {c.border_light};
                background-color: {c.bg_card};
            }}
            QCheckBox::indicator:checked {{
                background-color: {c.primary};
                border-color: {c.primary};
            }}
            QCheckBox::indicator:hover {{
                border-color: {c.primary};
            }}
        """

    def get_progressbar_style(self) -> str:
        """?„ë¡œê·¸ë ˆ?¤ë°” ?¤í??¼ì‹œ??""
        c = self.colors
        r = self.radius
        return f"""
            QProgressBar {{
                border: none;
                border-radius: {r.md}px;
                background-color: {c.primary_light};
                text-align: center;
                color: {c.text_primary};
                font-weight: bold;
            }}
            QProgressBar::chunk {{
                background-color: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {c.gradient_start},
                    stop:1 {c.gradient_end}
                );
                border-radius: {r.md}px;
            }}
        """

    def get_scrollbar_style(self) -> str:
        """?¤í¬ë¡¤ë°” ?¤í??¼ì‹œ??""
        c = self.colors
        return f"""
            QScrollBar:vertical {{
                background-color: {c.scrollbar_bg};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {c.scrollbar_thumb};
                border-radius: 5px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {c.primary};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """

    def get_label_style(self, variant: str = "primary") -> str:
        """?ˆì´ë¸??¤í??¼ì‹œ??""
        c = self.colors

        if variant == "primary":
            return f"color: {c.text_primary}; background: transparent;"
        elif variant == "secondary":
            return f"color: {c.text_secondary}; background: transparent;"
        elif variant == "title":
            return f"color: {c.text_primary}; font-weight: bold; font-size: 14px; background: transparent;"
        elif variant == "badge_success":
            return f"color: {c.success}; background-color: {c.success_light}; border-radius: 4px; padding: 2px 8px;"
        elif variant == "badge_error":
            return f"color: {c.error}; background-color: {c.error_light}; border-radius: 4px; padding: 2px 8px;"
        elif variant == "badge_primary":
            return f"color: {c.text_on_primary}; background-color: {c.primary}; border-radius: 4px; padding: 2px 8px;"
        return ""


# Singleton instance
_design_system: Optional[DesignSystem] = None


def get_design_system() -> DesignSystem:
    """?”ì???œìŠ¤???±ê????¸ìŠ¤?´ìŠ¤ ë°˜í™˜"""
    global _design_system
    if _design_system is None:
        _design_system = DesignSystem()
    return _design_system


# Convenience functions
def get_color(name: str) -> str:
    """?‰ìƒ ê°?ê°„í¸ ë°˜í™˜"""
    return get_design_system().get_color(name)


def is_dark_mode() -> bool:
    """?¤í¬ ëª¨ë“œ ?¬ë? ?•ì¸"""
    return get_design_system().is_dark_mode


def set_dark_mode(enabled: bool) -> None:
    """?¤í¬ ëª¨ë“œ ?¤ì •"""
    mode = ColorMode.DARK if enabled else ColorMode.LIGHT
    get_design_system().set_color_mode(mode)
