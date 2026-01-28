# -*- coding: utf-8 -*-
"""
Shopping Shorts Maker Design System
쇼핑 숏폼 메이커 디자인 시스템

STITCH MCP를 통해 생성된 디자인을 기반으로 한 통합 디자인 시스템.
PyQt5 및 tkinter에서 공통으로 사용할 수 있는 색상, 폰트, 스타일 정의.
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
    색상 팔레트 정의 / Color palette definition
    STITCH MCP 디자인 기반 - 레드/코랄 테마
    """

    # Primary Colors (STITCH 레드 계열)
    primary: str = "#e31639"           # 메인 레드 (STITCH 기준)
    primary_hover: str = "#c41231"     # 호버 시 어두운 레드
    primary_light: str = "#fce8eb"     # 연한 레드 (배경용)
    primary_dark: str = "#a01028"      # 진한 레드

    # Secondary Colors
    secondary: str = "#ff4d6a"         # 보조 핑크/레드
    secondary_light: str = "#ffb3c1"   # 연한 보조색

    # Background Colors (STITCH 기준)
    bg_main: str = "#f8f6f6"           # 메인 배경 (STITCH light)
    bg_card: str = "#FFFFFF"           # 카드 배경
    bg_sidebar: str = "#FFFFFF"        # 사이드바 배경 (light)
    bg_input: str = "#F3F4F6"          # 입력 필드 배경
    bg_hover: str = "#F3F4F6"          # 호버 배경
    bg_selected: str = "#fce8eb"       # 선택된 항목 배경
    bg_secondary: str = "#F3F4F6"      # 보조 배경
    bg_header: str = "#FFFFFF"         # 헤더 배경

    # Text Colors (STITCH slate 계열)
    text_primary: str = "#1b0e10"      # 주요 텍스트 (거의 검정)
    text_secondary: str = "#64748b"    # 보조 텍스트 (slate-500)
    text_disabled: str = "#94a3b8"     # 비활성 텍스트 (slate-400)
    text_on_primary: str = "#FFFFFF"   # primary 배경 위 텍스트

    # Border Colors
    border_light: str = "#e2e8f0"      # 연한 테두리 (slate-200)
    border_focus: str = "#e31639"      # 포커스 테두리 (primary)
    border_card: str = "#e2e8f0"       # 카드 테두리

    # Status Colors
    success: str = "#22C55E"           # 성공/완료
    success_light: str = "#F0FDF4"     # 성공 배경
    success_border: str = "#BBF7D0"    # 성공 테두리

    error: str = "#EF4444"             # 오류/실패
    error_light: str = "#FEF2F2"       # 오류 배경
    error_border: str = "#FECACA"      # 오류 테두리

    warning: str = "#F59E0B"           # 경고
    warning_light: str = "#FFFBEB"     # 경고 배경
    warning_border: str = "#FDE68A"    # 경고 테두리

    info: str = "#3B82F6"              # 정보
    info_light: str = "#EFF6FF"        # 정보 배경

    # Gradient Colors (STITCH red gradient)
    gradient_start: str = "#e31639"    # 그라데이션 시작
    gradient_end: str = "#ff4d6a"      # 그라데이션 끝

    # Scrollbar Colors
    scrollbar_bg: str = "#F3F4F6"      # 스크롤바 배경
    scrollbar_thumb: str = "#D1D5DB"   # 스크롤바 썸


@dataclass(frozen=True)
class DarkColorPalette(ColorPalette):
    """
    다크 모드 색상 팔레트 / Dark mode color palette
    STITCH MCP 디자인 기반 - 레드/코랄 다크 테마
    """

    # Primary Colors (STITCH red - 다크모드에서 밝게)
    primary: str = "#ff4d6a"           # 밝은 레드/핑크
    primary_hover: str = "#ff6b84"     # 더 밝은 레드
    primary_light: str = "#3d1a1e"     # 어두운 레드 배경
    primary_dark: str = "#e31639"

    # Secondary Colors
    secondary: str = "#ff6b84"
    secondary_light: str = "#4d2a2e"

    # Background Colors (STITCH dark - #211113 기반)
    bg_main: str = "#211113"           # 메인 배경 (STITCH dark)
    bg_card: str = "#2d1a1c"           # 카드 배경 (zinc-900 느낌)
    bg_sidebar: str = "#1a0d0e"        # 사이드바 (더 어둡게)
    bg_input: str = "#3d2426"          # 입력 필드 배경
    bg_hover: str = "#3d2426"          # 호버 배경
    bg_selected: str = "#4d2a2e"       # 선택된 항목 배경
    bg_secondary: str = "#2d1a1c"      # 보조 배경
    bg_header: str = "#1a0d0e"         # 헤더 배경

    # Text Colors
    text_primary: str = "#FFFFFF"      # 주요 텍스트
    text_secondary: str = "#a0a0a0"    # 보조 텍스트
    text_disabled: str = "#666666"     # 비활성 텍스트

    # Border Colors
    border_light: str = "#3d2426"      # 연한 테두리
    border_focus: str = "#ff4d6a"      # 포커스 테두리
    border_card: str = "#3d2426"       # 카드 테두리

    # Status Colors (다크모드에서 밝게)
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
    """타이포그래피 정의 / Typography definition (STITCH 기반)"""

    # Font Families (STITCH - Inter 폰트 사용)
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
    """간격 정의 / Spacing definition"""

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
    """모서리 둥글기 정의 / Border radius definition"""

    none: int = 0
    sm: int = 4
    md: int = 8
    lg: int = 12
    xl: int = 16
    full: int = 9999  # 완전 둥글게


@dataclass
class Shadow:
    """그림자 정의 / Shadow definition"""

    # PyQt5 스타일 문자열이 아닌 박스 섀도우 값
    none: str = "none"
    sm: str = "0 1px 2px rgba(0, 0, 0, 0.05)"
    md: str = "0 4px 6px -1px rgba(0, 0, 0, 0.1)"
    lg: str = "0 10px 15px -3px rgba(0, 0, 0, 0.1)"
    xl: str = "0 20px 25px -5px rgba(0, 0, 0, 0.1)"

    # Glow effects for dark mode
    glow_primary: str = "0 0 20px rgba(124, 58, 237, 0.3)"
    glow_success: str = "0 0 10px rgba(34, 197, 94, 0.3)"


@dataclass
class Animation:
    """애니메이션 정의 / Animation definition"""

    duration_fast: int = 150      # ms
    duration_normal: int = 300    # ms
    duration_slow: int = 500      # ms

    easing_default: str = "ease-out"
    easing_bounce: str = "cubic-bezier(0.68, -0.55, 0.265, 1.55)"


class DesignSystem:
    """
    통합 디자인 시스템 클래스
    Unified Design System class

    STITCH에서 생성된 디자인을 기반으로 한 모든 UI 스타일을 관리합니다.
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

    # PyQt5 StyleSheet Generators
    def get_button_style(self, style: str = "primary") -> str:
        """버튼 스타일시트 생성"""
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
        """입력 필드 스타일시트"""
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
        """카드 스타일시트"""
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
        """체크박스 스타일시트"""
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
        """프로그레스바 스타일시트"""
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
        """스크롤바 스타일시트"""
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
        """레이블 스타일시트"""
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
    """디자인 시스템 싱글톤 인스턴스 반환"""
    global _design_system
    if _design_system is None:
        _design_system = DesignSystem()
    return _design_system


# Convenience functions
def get_color(name: str) -> str:
    """색상 값 간편 반환"""
    return get_design_system().get_color(name)


def is_dark_mode() -> bool:
    """다크 모드 여부 확인"""
    return get_design_system().is_dark_mode


def set_dark_mode(enabled: bool) -> None:
    """다크 모드 설정"""
    mode = ColorMode.DARK if enabled else ColorMode.LIGHT
    get_design_system().set_color_mode(mode)
