"""
테마 관리 모듈
모던 블루/퍼플 그라데이션 테마 - 완전히 새로운 디자인
"""

from typing import Dict, Callable, List, Optional


# ============================================================
# 새로운 모던 라이트 테마 (STITCH 디자인 기반 레드 테마)
# ============================================================
LIGHT_THEME: Dict[str, str] = {
    # Primary Colors - STITCH 레드 (#e31639)
    "primary": "#e31639",  # 메인 레드
    "primary_hover": "#c41231",  # 호버 시 어두운 레드
    "primary_light": "#fce8eb",  # 연한 레드 배경
    "primary_text": "#FFFFFF",  # 버튼 텍스트
    # Accent Colors - 그라데이션 효과용
    "accent": "#ff4d6a",  # 밝은 핑크/레드
    "accent_hover": "#ff6b84",  # 밝은 코랄
    "accent_light": "#fff0f3",  # 연한 핑크
    # Gradient Colors (STITCH 디자인)
    "gradient_start": "#e31639",  # 그라데이션 시작
    "gradient_end": "#ff4d6a",  # 그라데이션 끝
    # Background Colors - STITCH 스타일
    "bg_main": "#f8f6f6",  # 메인 배경 (STITCH light)
    "bg_card": "#FFFFFF",  # 카드 배경
    "bg_header": "#FFFFFF",  # 헤더 배경
    "bg_secondary": "#F3F4F6",  # 보조 배경
    "bg_input": "#f9fafb",  # 입력 필드 배경 (slate-50)
    "bg_hover": "#f1f5f9",  # 호버 배경 (slate-100)
    "bg_selected": "#fce8eb",  # 선택된 항목 배경
    "bg_sidebar": "#FFFFFF",  # 사이드바 (라이트 모드)
    # Text Colors - STITCH slate 계열
    "text_primary": "#1b0e10",  # 주요 텍스트
    "text_secondary": "#64748b",  # 보조 텍스트 (slate-500)
    "text_disabled": "#94a3b8",  # 비활성 텍스트 (slate-400)
    "text_placeholder": "#94a3b8",  # 플레이스홀더
    "text_on_primary": "#FFFFFF",  # primary 배경 위 텍스트
    # Border Colors - STITCH slate 계열
    "border_light": "#e2e8f0",  # 연한 테두리 (slate-200)
    "border_medium": "#cbd5e1",  # 중간 테두리 (slate-300)
    "border_focus": "#e31639",  # 포커스 테두리
    "border_card": "#e2e8f0",  # 카드 테두리
    # Status Colors - 모던 컬러 (STITCH 디자인)
    "success": "#22C55E",  # 성공/완료
    "success_bg": "#F0FDF4",  # 성공 배경
    "success_border": "#BBF7D0",  # 성공 테두리
    "warning": "#F59E0B",  # 경고
    "warning_bg": "#FFFBEB",  # 경고 배경
    "warning_border": "#FDE68A",  # 경고 테두리
    "error": "#EF4444",  # 오류/실패
    "error_bg": "#FEF2F2",  # 오류 배경
    "error_border": "#FECACA",  # 오류 테두리
    "info": "#3B82F6",  # 정보
    "info_bg": "#EFF6FF",  # 정보 배경
    # Progress Colors
    "progress_bg": "#fce8eb",  # 진행바 배경
    "progress_fill": "#e31639",  # 진행바 채움
    # Tab Colors
    "tab_active": "#e31639",  # 활성 탭
    "tab_inactive": "#64748b",  # 비활성 탭
    "tab_indicator": "#e31639",  # 탭 인디케이터
    # Scrollbar Colors
    "scrollbar_bg": "#F3F4F6",  # 스크롤바 배경
    "scrollbar_thumb": "#D1D5DB",  # 스크롤바 썸
    # Sidebar Colors (STITCH 라이트 스타일)
    "sidebar_bg": "#FFFFFF",  # 사이드바 배경
    "sidebar_item_active": "#fce8eb",  # 활성 메뉴 배경
    "sidebar_item_hover": "#f1f5f9",  # 호버 메뉴 배경
    "sidebar_indicator": "#e31639",  # 활성 인디케이터
    "sidebar_step_number": "#e31639",  # 단계 번호 색상
    "sidebar_step_completed": "#22C55E",  # 완료된 단계
    # Button Specific
    "btn_secondary": "#F3F4F6",  # 세컨더리 버튼 배경
    "btn_secondary_hover": "#E5E7EB",
    "btn_secondary_text": "#374151",
    "btn_danger": "#EF4444",  # 위험 버튼
    "btn_danger_hover": "#DC2626",
    # Shadow
    "shadow": "rgba(0, 0, 0, 0.08)",
}


# ============================================================
# 새로운 모던 다크 테마 (STITCH 디자인 기반 레드 다크)
# ============================================================
DARK_THEME: Dict[str, str] = {
    # Primary Colors - STITCH 레드 (다크에서 더 밝게)
    "primary": "#ff4d6a",  # 밝은 레드/핑크
    "primary_hover": "#ff6b84",  # 더 밝은 코랄
    "primary_light": "#3d1a1e",  # 어두운 레드 배경
    "primary_text": "#FFFFFF",  # 버튼 텍스트
    # Accent Colors
    "accent": "#ff6b84",  # 밝은 코랄
    "accent_hover": "#ff8599",  # 더 밝은 핑크
    "accent_light": "#4d2a2e",  # 어두운 레드
    # Gradient Colors (STITCH 디자인)
    "gradient_start": "#e31639",  # 그라데이션 시작
    "gradient_end": "#ff4d6a",  # 그라데이션 끝
    # Background Colors - STITCH 다크 (#211113 기반)
    "bg_main": "#211113",  # 메인 배경 (STITCH dark)
    "bg_card": "#2d1a1c",  # 카드 배경 (zinc-900 느낌)
    "bg_header": "#1a0d0e",  # 헤더 배경
    "bg_secondary": "#2d1a1c",  # 보조 배경
    "bg_input": "#3d2426",  # 입력 필드 배경
    "bg_hover": "#3d2426",  # 호버 배경
    "bg_selected": "#4d2a2e",  # 선택된 항목 배경
    "bg_sidebar": "#1a0d0e",  # 사이드바 (더 어두운)
    # Text Colors
    "text_primary": "#FFFFFF",  # 주요 텍스트
    "text_secondary": "#a0a0a0",  # 보조 텍스트
    "text_disabled": "#666666",  # 비활성 텍스트
    "text_placeholder": "#666666",  # 플레이스홀더
    "text_on_primary": "#FFFFFF",  # primary 배경 위 텍스트
    # Border Colors
    "border_light": "#3d2426",  # 연한 테두리
    "border_medium": "#4d2a2e",  # 중간 테두리
    "border_focus": "#ff4d6a",  # 포커스 테두리
    "border_card": "#3d2426",  # 카드 테두리
    # Status Colors (다크 모드에서 더 밝게)
    "success": "#34D399",  # 성공/완료
    "success_bg": "#1A2E1A",  # 성공 배경
    "success_border": "#166534",  # 성공 테두리
    "warning": "#FBBF24",  # 경고
    "warning_bg": "#2E2A1A",  # 경고 배경
    "warning_border": "#92400E",  # 경고 테두리
    "error": "#F87171",  # 오류/실패
    "error_bg": "#2E1A1A",  # 오류 배경
    "error_border": "#991B1B",  # 오류 테두리
    "info": "#60A5FA",  # 정보
    "info_bg": "#1E3A5F",  # 정보 배경
    # Progress Colors
    "progress_bg": "#3d2426",  # 진행바 배경
    "progress_fill": "#ff4d6a",  # 진행바 채움
    # Tab Colors
    "tab_active": "#ff4d6a",  # 활성 탭
    "tab_inactive": "#666666",  # 비활성 탭
    "tab_indicator": "#ff4d6a",  # 탭 인디케이터
    # Scrollbar Colors
    "scrollbar_bg": "#2d1a1c",  # 스크롤바 배경
    "scrollbar_thumb": "#4d2a2e",  # 스크롤바 썸
    # Sidebar Colors (STITCH 다크 스타일)
    "sidebar_bg": "#1a0d0e",  # 사이드바 배경
    "sidebar_item_active": "#3d1a1e",  # 활성 메뉴 배경
    "sidebar_item_hover": "#2d1a1c",  # 호버 메뉴 배경
    "sidebar_indicator": "#ff4d6a",  # 활성 인디케이터
    "sidebar_step_number": "#ff4d6a",  # 단계 번호 색상
    "sidebar_step_completed": "#34D399",  # 완료된 단계
    # Button Specific
    "btn_secondary": "#2d1a1c",  # 세컨더리 버튼 배경
    "btn_secondary_hover": "#3d2426",
    "btn_secondary_text": "#E5E5E5",
    "btn_danger": "#F87171",  # 위험 버튼
    "btn_danger_hover": "#FCA5A5",
    # Shadow (다크 모드에서는 글로우 효과)
    "shadow": "rgba(227, 22, 57, 0.2)",
}


# ============================================================
# 폰트 설정 - STITCH 디자인 기반 (Inter 폰트)
# ============================================================
FONT_SETTINGS = {
    # 메인 폰트 (STITCH - Inter, Windows/Mac/Linux 호환)
    "family": "Inter, Pretendard, Malgun Gothic, Apple SD Gothic Neo, sans-serif",
    "family_mono": "JetBrains Mono, D2Coding, Consolas, monospace",
    # 폰트 사이즈
    "size_xs": 10,
    "size_sm": 11,
    "size_base": 12,
    "size_md": 13,
    "size_lg": 14,
    "size_xl": 16,
    "size_2xl": 18,
    "size_3xl": 24,
    "size_4xl": 32,
    # 폰트 굵기
    "weight_normal": "normal",
    "weight_medium": "bold",
    "weight_bold": "bold",
}


# ============================================================
# 버튼 스타일 설정 - 둥근 모던 버튼
# ============================================================
BUTTON_STYLES = {
    # 기본 버튼 설정
    "border_radius": 8,  # 둥근 모서리
    "padding_x": 16,  # 좌우 패딩
    "padding_y": 10,  # 상하 패딩
    "min_width": 80,  # 최소 너비
    "min_height": 36,  # 최소 높이
    # 아이콘 버튼
    "icon_size": 20,
    "icon_padding": 8,
    # 버튼 변형
    "variants": {
        "primary": {
            "bg": "primary",
            "fg": "primary_text",
            "hover_bg": "primary_hover",
            "border": None,
        },
        "secondary": {
            "bg": "btn_secondary",
            "fg": "btn_secondary_text",
            "hover_bg": "btn_secondary_hover",
            "border": "border_light",
        },
        "outline": {
            "bg": "transparent",
            "fg": "primary",
            "hover_bg": "primary_light",
            "border": "primary",
        },
        "ghost": {
            "bg": "transparent",
            "fg": "text_primary",
            "hover_bg": "bg_hover",
            "border": None,
        },
        "danger": {
            "bg": "btn_danger",
            "fg": "primary_text",
            "hover_bg": "btn_danger_hover",
            "border": None,
        },
    },
}


# ============================================================
# 입력 필드 스타일
# ============================================================
INPUT_STYLES = {
    "border_radius": 8,
    "padding_x": 12,
    "padding_y": 10,
    "border_width": 1,
    "focus_ring_width": 2,
}


# ============================================================
# 카드 스타일
# ============================================================
CARD_STYLES = {
    "border_radius": 12,
    "padding": 16,
    "shadow": "0 1px 3px rgba(0, 0, 0, 0.1)",
}


class ThemeManager:
    """
    테마 관리 싱글톤 클래스
    라이트/다크 모드 전환 및 색상 관리
    """

    _instance: Optional["ThemeManager"] = None

    LIGHT = "light"
    DARK = "dark"

    def __new__(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._current_theme: str = self.LIGHT  # 라이트 모드 고정
        self._themes: Dict[str, Dict[str, str]] = {
            self.LIGHT: LIGHT_THEME,
            self.DARK: DARK_THEME,
        }
        self._observers: List[Callable[[str], None]] = []

    @property
    def current_theme(self) -> str:
        """현재 테마 반환"""
        return self._current_theme

    @current_theme.setter
    def current_theme(self, value: str):
        """현재 테마 설정"""
        if value not in (self.LIGHT, self.DARK):
            raise ValueError(f"Invalid theme: {value}")
        self._current_theme = value

    @property
    def is_dark_mode(self) -> bool:
        """다크 모드 여부 반환"""
        return self._current_theme == self.DARK

    def get_color(self, key: str) -> str:
        """
        현재 테마의 색상 반환

        Args:
            key: 색상 키 (예: "primary", "bg_main")

        Returns:
            색상 코드 (예: "#6366F1")
        """
        return self._themes[self._current_theme].get(key, "#000000")

    def get_all_colors(self) -> Dict[str, str]:
        """현재 테마의 모든 색상 반환"""
        return self._themes[self._current_theme].copy()

    def get_font(self, key: str):
        """폰트 설정 반환"""
        return FONT_SETTINGS.get(key)

    def get_button_style(self, variant: str = "primary") -> dict:
        """버튼 스타일 반환"""
        base = BUTTON_STYLES.copy()
        variant_style = BUTTON_STYLES["variants"].get(
            variant, BUTTON_STYLES["variants"]["primary"]
        )

        # 색상 값으로 변환
        result = {
            "border_radius": base["border_radius"],
            "padding_x": base["padding_x"],
            "padding_y": base["padding_y"],
            "bg": self.get_color(variant_style["bg"])
            if variant_style["bg"] != "transparent"
            else "transparent",
            "fg": self.get_color(variant_style["fg"]),
            "hover_bg": self.get_color(variant_style["hover_bg"])
            if variant_style["hover_bg"]
            else None,
            "border": self.get_color(variant_style["border"])
            if variant_style["border"]
            else None,
        }
        return result

    def toggle_theme(self) -> str:
        """
        테마 토글 비활성화 (라이트 모드 고정)

        Returns:
            현재 테마 이름 (항상 LIGHT)
        """
        # self._current_theme = self.DARK if self._current_theme == self.LIGHT else self.LIGHT
        # self._notify_observers()
        return self._current_theme

    def set_theme(self, theme: str) -> None:
        """
        특정 테마로 설정

        Args:
            theme: 테마 이름 ("light" 또는 "dark")
        """
        if theme not in (self.LIGHT, self.DARK):
            raise ValueError(f"Invalid theme: {theme}. Use 'light' or 'dark'.")

        if self._current_theme != theme:
            self._current_theme = theme
            self._notify_observers()

    def register_observer(self, callback: Callable[[str], None]) -> None:
        """
        테마 변경 시 호출될 콜백 등록

        Args:
            callback: 테마 변경 시 호출될 함수 (인자: 새 테마 이름)
        """
        if callback not in self._observers:
            self._observers.append(callback)

    def unregister_observer(self, callback: Callable[[str], None]) -> None:
        """
        등록된 콜백 제거

        Args:
            callback: 제거할 콜백 함수
        """
        if callback in self._observers:
            self._observers.remove(callback)

    def _notify_observers(self) -> None:
        """등록된 모든 옵저버에 테마 변경 알림"""
        import logging

        logger = logging.getLogger(__name__)
        for callback in self._observers:
            try:
                callback(self._current_theme)
            except Exception as e:
                logger.error(f"Error notifying theme observer: {e}")


# 전역 테마 관리자 인스턴스
_theme_manager: Optional[ThemeManager] = None


def get_theme_manager() -> ThemeManager:
    """
    전역 테마 관리자 인스턴스 반환

    Returns:
        ThemeManager 싱글톤 인스턴스
    """
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager


def get_color(key: str) -> str:
    """
    현재 테마의 색상을 빠르게 가져오는 헬퍼 함수

    Args:
        key: 색상 키

    Returns:
        색상 코드
    """
    return get_theme_manager().get_color(key)


def get_font(key: str):
    """폰트 설정을 빠르게 가져오는 헬퍼 함수"""
    return FONT_SETTINGS.get(key)


def get_button_style(variant: str = "primary") -> dict:
    """버튼 스타일을 빠르게 가져오는 헬퍼 함수"""
    return get_theme_manager().get_button_style(variant)
