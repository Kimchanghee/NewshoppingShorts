# -*- coding: utf-8 -*-
"""
Shopping Shorts Maker - Enhanced Design System
콘텐츠 크리에이터 스튜디오 테마 (Content Creator's Studio Theme)

UI/UX Refactored with:
- Industrial-Creative Hybrid aesthetic
- Motion-first interactions
- Distinctive typography (Outfit + Manrope)
- Enhanced red theme with personality
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
from enum import Enum


class ColorMode(Enum):
    """색상 모드 / Color mode enumeration"""
    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True)
class ColorPalette:
    """
    Enhanced Color Palette - Content Creator's Studio Theme
    Refined from STITCH base with bolder, more memorable colors
    """

    # Primary Colors - PUNCHY RED (Matched to Login UI)
    primary: str = "#e31639"           # Main Red from Login
    primary_hover: str = "#c41231"     # Darker Red from Login hover
    primary_light: str = "#fce8eb"     # Soft red background
    primary_dark: str = "#a01028"      # Deep red from Login pressed

    # Accent Colors - CORAL PINK
    accent: str = "#ff4d6a"            # Gradient End from Login
    accent_light: str = "#fff0f3"      # Light pink
    accent_hover: str = "#ff6b84"      # Lighter accent

    # Background Colors - CLEAN STUDIO
    bg_main: str = "#FAFAFA"           # Almost white, clean studio feel
    bg_card: str = "#FFFFFF"           # Pure white cards
    bg_sidebar: str = "#F5F5F5"        # Subtle gray sidebar
    bg_input: str = "#F8F8F8"          # Light input backgrounds
    bg_hover: str = "#F0F0F0"          # Hover state
    bg_selected: str = "#FFE8EC"       # Selected with red tint
    bg_secondary: str = "#F5F5F5"      # Secondary backgrounds
    bg_header: str = "#FFFFFF"         # Clean white header

    # Text Colors - HIGH CONTRAST
    text_primary: str = "#0A0A0A"      # Near black for maximum readability
    text_secondary: str = "#6B7280"    # Gray-600 for secondary text
    text_tertiary: str = "#9CA3AF"     # Gray-400 for hints
    text_disabled: str = "#D1D5DB"     # Gray-300 for disabled
    text_on_primary: str = "#FFFFFF"   # White on red backgrounds
    text_on_dark: str = "#F9FAFB"      # Soft white on dark

    # Border Colors - REFINED EDGES
    border_light: str = "#E5E7EB"      # Gray-200 - subtle borders
    border_medium: str = "#D1D5DB"     # Gray-300 - visible borders
    border_focus: str = "#FF1744"      # Red focus indicator
    border_card: str = "#F0F0F0"       # Very subtle card borders

    # Status Colors - VIBRANT & CLEAR
    success: str = "#10B981"           # Emerald-500 - fresh green
    success_light: str = "#D1FAE5"     # Light green background
    success_border: str = "#6EE7B7"    # Green border

    error: str = "#EF4444"             # Red-500 - clear error
    error_light: str = "#FEE2E2"       # Light red background
    error_border: str = "#FCA5A5"      # Red border

    warning: str = "#F59E0B"           # Amber-500 - attention
    warning_light: str = "#FEF3C7"     # Light amber background
    warning_border: str = "#FCD34D"    # Amber border

    info: str = "#3B82F6"              # Blue-500 - information
    info_light: str = "#DBEAFE"        # Light blue background
    info_border: str = "#93C5FD"       # Blue border

    # Gradient Colors - DYNAMIC DIAGONALS
    gradient_start: str = "#e31639"    # Primary red
    gradient_mid: str = "#f03252"      # Transition
    gradient_end: str = "#ff4d6a"      # Coral pink

    # Special Effects
    overlay_light: str = "rgba(255, 255, 255, 0.9)"     # Light overlay
    overlay_dark: str = "rgba(0, 0, 0, 0.4)"            # Dark overlay
    shadow_color: str = "rgba(0, 0, 0, 0.1)"            # Shadow base color
    glow_primary: str = "rgba(227, 22, 57, 0.4)"        # Red glow
    glow_accent: str = "rgba(255, 77, 106, 0.3)"        # Coral glow

    # Scrollbar Colors
    scrollbar_bg: str = "#F5F5F5"      # Scrollbar background
    scrollbar_thumb: str = "#D1D5DB"   # Scrollbar thumb
    scrollbar_hover: str = "#e31639"   # Scrollbar on hover (brand color)


@dataclass(frozen=True)
class DarkColorPalette(ColorPalette):
    """
    Dark Mode Palette - Content Creator's Studio (Night Edition)
    Deep charcoal with glowing accents
    """

    # Primary Colors - GLOWING RED in dark
    primary: str = "#ff4d6a"           # Brighter red for dark backgrounds
    primary_hover: str = "#ff6b84"     # Even brighter on hover
    primary_light: str = "#3d1a1e"     # Very dark red background
    primary_dark: str = "#e31639"      # Original red for contrast

    # Accent Colors
    accent: str = "#ff8599"            # Lighter coral for visibility
    accent_light: str = "#4d2a2e"      # Dark coral background
    accent_hover: str = "#FFA3C1"      # Bright coral hover

    # Background Colors - DEEP CHARCOAL STUDIO
    bg_main: str = "#211113"           # Deep black (not pure black)
    bg_card: str = "#2d1a1c"           # Charcoal cards
    bg_sidebar: str = "#1a0d0e"        # Slightly darker sidebar
    bg_input: str = "#3d2426"          # Input backgrounds
    bg_hover: str = "#3d2426"          # Hover state
    bg_selected: str = "#4d2a2e"       # Selected with red tint
    bg_secondary: str = "#2d1a1c"      # Secondary backgrounds
    bg_header: str = "#1a0d0e"         # Dark header

    # Text Colors - SOFT FOR DARK MODE
    text_primary: str = "#F9FAFB"      # Soft white
    text_secondary: str = "#a0a0a0"    # Gray-400
    text_tertiary: str = "#666666"     # Gray-500
    text_disabled: str = "#4B5563"     # Gray-600
    text_on_primary: str = "#FFFFFF"   # Pure white
    text_on_dark: str = "#F9FAFB"      # Soft white

    # Border Colors
    border_light: str = "#3d2426"      # Subtle dark borders
    border_medium: str = "#4d2a2e"     # Visible dark borders
    border_focus: str = "#ff4d6a"      # Bright red focus
    border_card: str = "#3d2426"       # Card borders

    # Status Colors - BRIGHTER for visibility
    success: str = "#34D399"           # Emerald-400
    success_light: str = "#1A2E1A"     # Dark green background
    success_border: str = "#059669"    # Green border

    error: str = "#F87171"             # Red-400
    error_light: str = "#2E1A1A"       # Dark red background
    error_border: str = "#DC2626"      # Red border

    warning: str = "#FBBF24"           # Amber-400
    warning_light: str = "#2E2A1A"     # Dark amber background
    warning_border: str = "#D97706"    # Amber border

    info: str = "#60A5FA"              # Blue-400
    info_light: str = "#1E3A5F"        # Dark blue background
    info_border: str = "#2563EB"       # Blue border

    # Gradient Colors
    gradient_start: str = "#e31639"
    gradient_mid: str = "#ff4d6a"
    gradient_end: str = "#ff8599"

    # Special Effects
    overlay_light: str = "rgba(255, 255, 255, 0.05)"    # Subtle light overlay
    overlay_dark: str = "rgba(0, 0, 0, 0.6)"            # Strong dark overlay
    shadow_color: str = "rgba(227, 22, 57, 0.2)"        # Darker shadows
    glow_primary: str = "rgba(255, 77, 106, 0.6)"       # Stronger red glow
    glow_accent: str = "rgba(255, 133, 153, 0.5)"       # Stronger coral glow

    # Scrollbar Colors
    scrollbar_bg: str = "#2d1a1c"
    scrollbar_thumb: str = "#4d2a2e"
    scrollbar_hover: str = "#ff4d6a"   # Glowing red on hover


@dataclass
class Typography:
    """
    Typography - Content Creator's Studio
    DISTINCTIVE FONTS - NO generic Inter/Roboto
    """

    # Font Families
    font_family_heading: str = "'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif"
    font_family_body: str = "'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif"
    font_family_primary: str = "'Malgun Gothic', 'Pretendard', sans-serif"
    font_family_mono: str = "'Consolas', 'Monaco', monospace"

    # Font Sizes (px) - REFINED SCALE
    font_size_xs: int = 10
    font_size_sm: int = 12
    font_size_base: int = 14        # Increased for better readability
    font_size_md: int = 16
    font_size_lg: int = 18
    font_size_xl: int = 22
    font_size_2xl: int = 26
    font_size_3xl: int = 32
    font_size_4xl: int = 40         # For hero text
    font_size_5xl: int = 48         # Extra large headers

    # Font Weights - EXPRESSIVE RANGE
    font_weight_light: int = 300
    font_weight_normal: int = 400
    font_weight_medium: int = 500
    font_weight_semibold: int = 600
    font_weight_bold: int = 700
    font_weight_extrabold: int = 800
    font_weight_black: int = 900    # For impact

    # Line Heights - CONTEXT-AWARE
    line_height_tight: float = 1.2      # Headlines
    line_height_snug: float = 1.375     # Subheadings
    line_height_normal: float = 1.5     # Body text
    line_height_relaxed: float = 1.75   # Comfortable reading
    line_height_loose: float = 2.0      # Spaced headers

    # Letter Spacing (for headings)
    letter_spacing_tight: str = "-0.02em"
    letter_spacing_normal: str = "0"
    letter_spacing_wide: str = "0.05em"
    letter_spacing_wider: str = "0.1em"


@dataclass
class Spacing:
    """Spacing System - 4px base unit"""

    # Base spacing scale (4px increments)
    none: int = 0
    xs: int = 4      # 0.25rem
    sm: int = 8      # 0.5rem
    md: int = 12     # 0.75rem
    lg: int = 16     # 1rem
    xl: int = 20     # 1.25rem
    xl2: int = 24    # 1.5rem
    xl3: int = 32    # 2rem
    xl4: int = 40    # 2.5rem
    xl5: int = 48    # 3rem
    xl6: int = 64    # 4rem

    # Component-specific spacing
    card_padding: int = 20
    card_margin: int = 12
    button_padding_x: int = 20
    button_padding_y: int = 10
    input_padding: int = 12
    section_gap: int = 32
    panel_gap: int = 24


@dataclass
class BorderRadius:
    """Border Radius - Refined corners"""

    none: int = 0
    sm: int = 6       # Subtle rounding
    md: int = 10      # Standard cards
    lg: int = 14      # Prominent elements
    xl: int = 18      # Large cards
    xl2: int = 24     # Hero elements
    full: int = 9999  # Pills/circles


@dataclass
class Shadow:
    """Shadow System - Depth & Elevation"""

    # Standard shadows (CSS format for PyQt)
    none: str = "none"
    xs: str = "0 1px 2px 0 rgba(0, 0, 0, 0.05)"
    sm: str = "0 2px 4px -1px rgba(0, 0, 0, 0.06)"
    md: str = "0 4px 6px -1px rgba(0, 0, 0, 0.1)"
    lg: str = "0 10px 15px -3px rgba(0, 0, 0, 0.1)"
    xl: str = "0 20px 25px -5px rgba(0, 0, 0, 0.1)"
    xl2: str = "0 25px 50px -12px rgba(0, 0, 0, 0.25)"

    # Glow effects for dark mode
    glow_primary: str = "0 0 20px rgba(255, 23, 68, 0.5)"
    glow_accent: str = "0 0 20px rgba(255, 107, 157, 0.4)"
    glow_success: str = "0 0 15px rgba(16, 185, 129, 0.4)"

    # Inner shadows
    inner: str = "inset 0 2px 4px 0 rgba(0, 0, 0, 0.06)"


@dataclass
class Animation:
    """Animation System - Motion-first interactions"""

    # Duration (ms)
    duration_instant: int = 100      # Instant feedback
    duration_fast: int = 200         # Quick transitions
    duration_normal: int = 300       # Standard animations
    duration_slow: int = 500         # Deliberate animations
    duration_slower: int = 700       # Dramatic entrances

    # Easing functions
    easing_linear: str = "linear"
    easing_ease: str = "ease"
    easing_ease_in: str = "ease-in"
    easing_ease_out: str = "ease-out"
    easing_ease_in_out: str = "ease-in-out"

    # Custom easing (CSS cubic-bezier)
    easing_bounce: str = "cubic-bezier(0.68, -0.55, 0.265, 1.55)"
    easing_smooth: str = "cubic-bezier(0.4, 0, 0.2, 1)"
    easing_snappy: str = "cubic-bezier(0.4, 0, 0.6, 1)"

    # Scale transforms for micro-interactions
    scale_hover: float = 1.02
    scale_active: float = 0.98
    scale_focus: float = 1.05


class DesignSystem:
    """
    Unified Design System - Content Creator's Studio

    Industrial-Creative Hybrid theme with:
    - Distinctive typography (Outfit + Manrope)
    - Enhanced red/coral palette
    - Motion-first interactions
    - Professional yet approachable
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
        """현재 색상 모드에 따른 색상 반환"""
        if self._color_mode == ColorMode.DARK:
            return self._dark_colors
        return self._colors

    @property
    def is_dark_mode(self) -> bool:
        """다크 모드 여부"""
        return self._color_mode == ColorMode.DARK

    def set_color_mode(self, mode: ColorMode) -> None:
        """색상 모드 설정"""
        self._color_mode = mode

    def toggle_color_mode(self) -> ColorMode:
        """색상 모드 토글"""
        if self._color_mode == ColorMode.LIGHT:
            self._color_mode = ColorMode.DARK
        else:
            self._color_mode = ColorMode.LIGHT
        return self._color_mode

    def get_color(self, name: str) -> str:
        """색상 이름으로 색상값 반환"""
        return getattr(self.colors, name, self.colors.text_primary)

    # ==================== ENHANCED COMPONENT STYLES ====================

    def get_button_style(self, style: str = "primary", size: str = "md") -> str:
        """
        Enhanced button styles with micro-interactions

        Styles: primary, secondary, outline, danger, ghost, accent
        Sizes: sm, md, lg
        """
        c = self.colors
        r = self.radius
        s = self.spacing
        t = self.typography
        a = self.animation

        # Size presets
        sizes = {
            "sm": {"padding": f"{s.sm}px {s.lg}px", "font_size": f"{t.font_size_sm}px"},
            "md": {"padding": f"{s.md}px {s.xl}px", "font_size": f"{t.font_size_base}px"},
            "lg": {"padding": f"{s.lg}px {s.xl2}px", "font_size": f"{t.font_size_lg}px"},
        }
        size_config = sizes.get(size, sizes["md"])

        base_style = f"""
            QPushButton {{
                border: none;
                border-radius: {r.lg}px;
                padding: {size_config['padding']};
                font-family: {t.font_family_body};
                font-size: {size_config['font_size']};
                font-weight: {t.font_weight_semibold};
            }}
            QPushButton:disabled {{
            }}
        """

        if style == "primary":
            return base_style + f"""
                QPushButton {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 {c.gradient_start},
                        stop:0.5 {c.gradient_mid},
                        stop:1 {c.gradient_end}
                    );
                    color: {c.text_on_primary};
                }}
                QPushButton:hover {{
                    background: {c.primary_hover};
                }}
                QPushButton:pressed {{
                    background: {c.primary_dark};
                }}
            """

        elif style == "accent":
            return base_style + f"""
                QPushButton {{
                    background-color: {c.accent};
                    color: {c.text_on_primary};
                }}
                QPushButton:hover {{
                    background-color: {c.accent_hover};
                }}
            """

        elif style == "secondary":
            return base_style + f"""
                QPushButton {{
                    background-color: {c.bg_secondary};
                    color: {c.text_primary};
                    border: 1px solid {c.border_light};
                }}
                QPushButton:hover {{
                    background-color: {c.bg_hover};
                    border-color: {c.primary};
                }}
            """

        elif style == "outline":
            return base_style + f"""
                QPushButton {{
                    background-color: transparent;
                    color: {c.primary};
                    border: 2px solid {c.primary};
                }}
                QPushButton:hover {{
                    background-color: {c.primary_light};
                    border-color: {c.primary_hover};
                }}
            """

        elif style == "danger":
            return base_style + f"""
                QPushButton {{
                    background-color: {c.error};
                    color: {c.text_on_primary};
                }}
                QPushButton:hover {{
                    background-color: #DC2626;
                }}
            """

        elif style == "ghost":
            return base_style + f"""
                QPushButton {{
                    background-color: transparent;
                    color: {c.text_primary};
                }}
                QPushButton:hover {{
                    background-color: {c.bg_hover};
                }}
            """

        return base_style

    def get_input_style(self) -> str:
        """Enhanced input field styles"""
        c = self.colors
        r = self.radius
        s = self.spacing
        t = self.typography

        return f"""
            QLineEdit, QTextEdit {{
                background-color: {c.bg_input};
                color: {c.text_primary};
                border: 2px solid {c.border_light};
                border-radius: {r.md}px;
                padding: {s.md}px {s.lg}px;
                font-family: {t.font_family_body};
                font-size: {t.font_size_base}px;
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border-color: {c.primary};
                background-color: {c.bg_card};
            }}
            QLineEdit:hover, QTextEdit:hover {{
                border-color: {c.border_medium};
            }}
            QLineEdit:disabled, QTextEdit:disabled {{
                background-color: {c.bg_secondary};
                color: {c.text_disabled};
                border-color: {c.border_light};
            }}
        """

    def get_card_style(self, elevation: str = "md") -> str:
        """Enhanced card styles with depth"""
        c = self.colors
        r = self.radius
        s = self.spacing

        shadows = {
            "sm": self.shadow.sm,
            "md": self.shadow.md,
            "lg": self.shadow.lg,
            "xl": self.shadow.xl,
        }
        shadow_value = shadows.get(elevation, self.shadow.md)

        return f"""
            QFrame {{
                background-color: {c.bg_card};
                border: 1px solid {c.border_card};
                border-radius: {r.xl}px;
                padding: {s.card_padding}px;
            }}
        """

    def get_progressbar_style(self) -> str:
        """Video timeline-inspired progress bar"""
        c = self.colors
        r = self.radius
        t = self.typography

        return f"""
            QProgressBar {{
                border: none;
                border-radius: {r.md}px;
                background-color: {c.primary_light};
                text-align: center;
                color: {c.text_primary};
                font-family: {t.font_family_mono};
                font-size: {t.font_size_sm}px;
                font-weight: {t.font_weight_bold};
                height: 24px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {c.gradient_start},
                    stop:0.6 {c.gradient_mid},
                    stop:1 {c.gradient_end}
                );
                border-radius: {r.md}px;
            }}
        """

    def get_scrollbar_style(self) -> str:
        """Refined scrollbar with brand color hover"""
        c = self.colors

        return f"""
            QScrollBar:vertical {{
                background-color: {c.scrollbar_bg};
                width: 12px;
                border-radius: 6px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {c.scrollbar_thumb};
                border-radius: 6px;
                min-height: 40px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {c.scrollbar_hover};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0;
                background: none;
            }}
            QScrollBar:horizontal {{
                background-color: {c.scrollbar_bg};
                height: 12px;
                border-radius: 6px;
                margin: 2px;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {c.scrollbar_thumb};
                border-radius: 6px;
                min-width: 40px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: {c.scrollbar_hover};
            }}
        """

    def get_label_style(self, variant: str = "primary") -> str:
        """Enhanced label styles"""
        c = self.colors
        t = self.typography

        variants = {
            "primary": f"color: {c.text_primary}; font-size: {t.font_size_base}px;",
            "secondary": f"color: {c.text_secondary}; font-size: {t.font_size_sm}px;",
            "tertiary": f"color: {c.text_tertiary}; font-size: {t.font_size_xs}px;",
            "title": f"""
                color: {c.text_primary};
                font-family: {t.font_family_heading};
                font-weight: {t.font_weight_bold};
                font-size: {t.font_size_xl}px;
                letter-spacing: {t.letter_spacing_tight};
            """,
            "heading": f"""
                color: {c.text_primary};
                font-family: {t.font_family_heading};
                font-weight: {t.font_weight_extrabold};
                font-size: {t.font_size_3xl}px;
                letter-spacing: {t.letter_spacing_tight};
            """,
            "badge_success": f"""
                color: {c.success};
                background-color: {c.success_light};
                border-radius: 6px;
                padding: 4px 10px;
                font-weight: {t.font_weight_medium};
                font-size: {t.font_size_sm}px;
            """,
            "badge_error": f"""
                color: {c.error};
                background-color: {c.error_light};
                border-radius: 6px;
                padding: 4px 10px;
                font-weight: {t.font_weight_medium};
                font-size: {t.font_size_sm}px;
            """,
            "badge_primary": f"""
                color: {c.text_on_primary};
                background-color: {c.primary};
                border-radius: 6px;
                padding: 4px 10px;
                font-weight: {t.font_weight_semibold};
                font-size: {t.font_size_sm}px;
            """,
        }

        return variants.get(variant, variants["primary"])


# ==================== SINGLETON INSTANCE ====================

_design_system: Optional[DesignSystem] = None


def get_design_system() -> DesignSystem:
    """디자인 시스템 싱글톤 인스턴스 반환"""
    global _design_system
    if _design_system is None:
        _design_system = DesignSystem()
    return _design_system


# ==================== CONVENIENCE FUNCTIONS ====================

def get_color(name: str) -> str:
    """색상값 간편 반환"""
    return get_design_system().get_color(name)


def is_dark_mode() -> bool:
    """다크 모드 여부 확인"""
    return get_design_system().is_dark_mode


def set_dark_mode(enabled: bool) -> None:
    """다크 모드 설정"""
    mode = ColorMode.DARK if enabled else ColorMode.LIGHT
    get_design_system().set_color_mode(mode)
