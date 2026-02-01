"""
쇼핑 숏츠 메이커 애플리케이션을 위한 디자인 시스템 V2

이 모듈은 애플리케이션 전체에서 일관된 UI/UX를 제공하기 위한 디자인 시스템을 정의합니다.
색상, 타이포그래피, 여백, 그림자 등의 시각적 요소를 중앙 집중식으로 관리합니다.

사용 예시:
    >>> from ui.design_system_v2 import get_design_system, get_color
    >>> ds = get_design_system()
    >>> print(ds.colors.primary)  # #E31639
    >>> print(get_color('primary'))  # #E31639
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Union
import sys


@dataclass(frozen=True)
class ColorPalette:
    """
    라이트 모드 색상 팔레트
    
    쇼핑 숏츠 메이커의 브랜드 아이덴티티를 반영한 색상 체계입니다.
    빨간색 계열의 프라이머리 컬러는 에너지와 활력을 나타냅니다.
    
    Attributes:
        primary: 주요 브랜드 색상 (빨간색)
        secondary: 보조 브랜드 색상 (코랄)
        background: 배경색
        surface: 표면 색상 (카드, 판넬 등)
        text_primary: 주요 텍스트 색상
        text_secondary: 보조 텍스트 색상
        text_muted: 비활성/힌트 텍스트 색상
        border: 경계선 색상
        error: 오류 상태 색상
        success: 성공 상태 색상
        warning: 경고 상태 색상
        info: 정보 상태 색상
    """
    primary: str = "#E31639"
    secondary: str = "#FF4D6A"
    background: str = "#FAFAFA"
    surface: str = "#FFFFFF"
    surface_variant: str = "#F5F5F5"
    text_primary: str = "#1A1A1A"
    text_secondary: str = "#4A4A4A"
    text_muted: str = "#9A9A9A"
    border: str = "#E5E5E5"
    border_light: str = "#F0F0F0"
    error: str = "#DC2626"
    success: str = "#16A34A"
    warning: str = "#F59E0B"
    info: str = "#3B82F6"
    overlay: str = "rgba(0, 0, 0, 0.5)"
    overlay_light: str = "rgba(0, 0, 0, 0.25)"


@dataclass(frozen=True)
class DarkColorPalette:
    """
    다크 모드 색상 팔레트
    
    어두운 환경에서의 사용성을 최적화한 색상 체계입니다.
    대비 비율을 유지하여 가독성을 보장합니다.
    
    Attributes:
        primary: 주요 브랜드 색상 (라이트 모드와 동일)
        secondary: 보조 브랜드 색상 (라이트 모드와 동일)
        background: 어두운 배경색
        surface: 어두운 표면 색상
        text_primary: 밝은 주요 텍스트 색상
        text_secondary: 밝은 보조 텍스트 색상
        text_muted: 어두운 환경의 비활성 텍스트
        border: 어두운 테마의 경계선
        error: 오류 색상 (약간 밝게 조정)
        success: 성공 색상 (약간 밝게 조정)
        warning: 경고 색상 (약간 밝게 조정)
        info: 정보 색상 (약간 밝게 조정)
    """
    primary: str = "#E31639"
    secondary: str = "#FF4D6A"
    background: str = "#1A1A1A"
    surface: str = "#2A2A2A"
    surface_variant: str = "#3A3A3A"
    text_primary: str = "#FFFFFF"
    text_secondary: str = "#E0E0E0"
    text_muted: str = "#888888"
    border: str = "#404040"
    border_light: str = "#505050"
    error: str = "#EF4444"
    success: str = "#22C55E"
    warning: str = "#FBBF24"
    info: str = "#60A5FA"
    overlay: str = "rgba(0, 0, 0, 0.7)"
    overlay_light: str = "rgba(0, 0, 0, 0.4)"


@dataclass(frozen=True)
class Typography:
    """
    타이포그래피 시스템
    
    일관된 텍스트 스타일을 위한 폰트 크기, 두께, 줄 높이를 정의합니다.
    8px 그리드 시스템을 기반으로 하며, 픽셀 퍼펙트 디자인을 지원합니다.
    
    Attributes:
        size_*: 다양한 크기의 폰트 (10px ~ 40px)
        weight_*: 폰트 두께 (normal ~ bold)
        line_height_*: 줄 높이 배율 (tight ~ relaxed)
        letter_spacing_*: 자간 조정값
        font_family_primary: 주요 폰트 패밀리
        font_family_mono: 고정폭 폰트 패밀리
    """
    # Font sizes (px)
    size_2xs: int = 10
    size_xs: int = 12
    size_sm: int = 14
    size_base: int = 16
    size_md: int = 18
    size_lg: int = 20
    size_xl: int = 24
    size_2xl: int = 32
    size_3xl: int = 40
    
    # Font weights
    weight_normal: int = 400
    weight_medium: int = 500
    weight_semibold: int = 600
    weight_bold: int = 700
    weight_extrabold: int = 800
    
    # Line heights (multiplier)
    line_height_tight: float = 1.25
    line_height_normal: float = 1.5
    line_height_relaxed: float = 1.75
    line_height_loose: float = 2.0
    
    # Letter spacing
    letter_spacing_tight: str = "-0.025em"
    letter_spacing_normal: str = "0"
    letter_spacing_wide: str = "0.025em"
    letter_spacing_wider: str = "0.05em"
    
    # Font families
    font_family_primary: str = "'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    font_family_mono: str = "'JetBrains Mono', 'Fira Code', 'Consolas', monospace"


@dataclass(frozen=True)
class Spacing:
    """
    여백 시스템
    
    8px 기반 그리드 시스템으로 일관된 레이아웃 간격을 제공합니다.
    모든 간격 값은 4의 배수로 구성되어 있습니다.
    
    Attributes:
        space_*: 다양한 크기의 여백 값 (4px ~ 128px)
        gutter: 그리드 거터 간격
        section: 섹션 간 기본 간격
    """
    space_0: int = 0
    space_1: int = 4
    space_2: int = 8
    space_3: int = 12
    space_4: int = 16
    space_5: int = 24
    space_6: int = 32
    space_7: int = 48
    space_8: int = 64
    space_9: int = 96
    space_10: int = 128
    
    # Common spacing aliases
    gutter: int = 24
    section: int = 48
    container_padding: int = 24
    card_padding: int = 16


@dataclass(frozen=True)
class BorderRadius:
    """
    테두리 반경 시스템
    
    컴포넌트의 모서리 둥글기를 일관되게 적용하기 위한 값들입니다.
    0부터 완전한 원형(9999px)까지 다양한 옵션을 제공합니다.
    
    Attributes:
        none, sm, base, md, lg, xl, xxl, full: 다양한 반경 값 (0px ~ 9999px)
    """
    none: int = 0
    sm: int = 4
    base: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 20
    xxl: int = 24
    full: int = 9999


@dataclass(frozen=True)
class ButtonSize:
    """
    버튼 크기 정의
    
    다양한 컨텍스트에서 사용할 수 있는 표준 버튼 크기입니다.
    각 크기는 높이, 패딩, 폰트 크기를 포함합니다.
    
    Attributes:
        height: 버튼 높이 (픽셀)
        padding_x: 수평 패딩
        font_size: 폰트 크기
        icon_size: 아이콘 크기
    
    사용 가능한 사이즈:
        - xs: 28px (extra small)
        - sm: 32px (small)
        - md: 40px (medium, default)
        - lg: 48px (large)
        - xl: 56px (extra large)
    """
    height: int
    padding_x: int
    font_size: int
    icon_size: int

    @classmethod
    def get_sizes(cls) -> Dict[str, 'ButtonSize']:
        """모든 버튼 크기 정의를 반환합니다."""
        return {
            'xs': cls(height=28, padding_x=12, font_size=12, icon_size=14),
            'sm': cls(height=32, padding_x=16, font_size=12, icon_size=16),
            'md': cls(height=40, padding_x=20, font_size=14, icon_size=18),
            'lg': cls(height=48, padding_x=24, font_size=16, icon_size=20),
            'xl': cls(height=56, padding_x=32, font_size=18, icon_size=24),
        }


@dataclass(frozen=True)
class Shadow:
    """
    그림자 시스템
    
    깊이와 계층 구조를 표현하기 위한 그림자 스타일입니다.
    CSS box-shadow 값을 문자열로 제공합니다.
    
    Attributes:
        none, xs, sm, base, md, lg, xl, 2xl: 다양한 깊이의 그림자 값
    """
    none: str = "none"
    xs: str = "0 1px 2px 0 rgba(0, 0, 0, 0.05)"
    sm: str = "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)"
    base: str = "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)"
    md: str = "0 6px 8px -1px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)"
    lg: str = "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)"
    xl: str = "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)"
    xxl: str = "0 25px 50px -12px rgba(0, 0, 0, 0.25)"
    inner: str = "inset 0 2px 4px 0 rgba(0, 0, 0, 0.05)"
    focus: str = "0 0 0 3px rgba(227, 22, 57, 0.3)"


@dataclass(frozen=True)
class Transition:
    """
    전환 애니메이션 시스템
    
    부드러운 상호작용을 위한 CSS transition 값입니다.
    
    Attributes:
        duration_*: 다양한 지속 시간 (빠름 ~ 느림)
        easing_*: 다양한 이징 함수
    """
    duration_fast: int = 150  # ms
    duration_normal: int = 250  # ms
    duration_slow: int = 350  # ms
    duration_slower: int = 500  # ms
    
    easing_default: str = "cubic-bezier(0.4, 0, 0.2, 1)"
    easing_in: str = "cubic-bezier(0.4, 0, 1, 1)"
    easing_out: str = "cubic-bezier(0, 0, 0.2, 1)"
    easing_bounce: str = "cubic-bezier(0.68, -0.55, 0.265, 1.55)"


@dataclass(frozen=True)
class ZIndex:
    """
    Z-인덱스 시스템
    
    계층 구조와 겹침 순서를 관리하기 위한 z-index 값입니다.
    
    Attributes:
        z_*: 다양한 계층의 z-index 값
    """
    z_base: int = 0
    z_dropdown: int = 100
    z_sticky: int = 200
    z_fixed: int = 300
    z_drawer: int = 400
    z_modal: int = 500
    z_popover: int = 600
    z_tooltip: int = 700
    z_toast: int = 800
    z_max: int = 9999


@dataclass
class DesignSystem:
    """
    메인 디자인 시스템 클래스
    
    모든 디자인 토큰을 통합 관리하는 싱글톤 클래스입니다.
    라이트/다크 모드를 지원하며, 현재 테마에 맞는 값을 제공합니다.
    
    Attributes:
        _instance: 싱글톤 인스턴스 저장소
        colors_light: 라이트 모드 색상 팔레트
        colors_dark: 다크 모드 색상 팔레트
        typography: 타이포그래피 시스템
        spacing: 여백 시스템
        border_radius: 테두리 반경 시스템
        shadow: 그림자 시스템
        transition: 전환 애니메이션 시스템
        z_index: Z-인덱스 시스템
        _is_dark_mode: 현재 다크 모드 상태
    
    사용 예시:
        >>> ds = DesignSystem.get_instance()
        >>> print(ds.colors.primary)
        >>> ds.set_dark_mode(True)
        >>> print(ds.colors.background)  # 다크 모드 배경색
    """
    _instance: Optional['DesignSystem'] = None
    
    colors_light: ColorPalette = field(default_factory=ColorPalette)
    colors_dark: DarkColorPalette = field(default_factory=DarkColorPalette)
    typography: Typography = field(default_factory=Typography)
    spacing: Spacing = field(default_factory=Spacing)
    border_radius: BorderRadius = field(default_factory=BorderRadius)
    shadow: Shadow = field(default_factory=Shadow)
    transition: Transition = field(default_factory=Transition)
    z_index: ZIndex = field(default_factory=ZIndex)
    
    _is_dark_mode: bool = False
    
    def __post_init__(self):
        """초기화 후 버튼 사이즈 딕셔너리를 생성합니다."""
        object.__setattr__(self, '_button_sizes', ButtonSize.get_sizes())
    
    @classmethod
    def get_instance(cls) -> 'DesignSystem':
        """
        디자인 시스템 싱글톤 인스턴스를 반환합니다.
        
        Returns:
            DesignSystem: 디자인 시스템 인스턴스
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @property
    def colors(self) -> Union[ColorPalette, DarkColorPalette]:
        """
        현재 테마에 맞는 색상 팔레트를 반환합니다.
        
        Returns:
            ColorPalette 또는 DarkColorPalette: 현재 테마의 색상 팔레트
        """
        return self.colors_dark if self._is_dark_mode else self.colors_light
    
    def set_dark_mode(self, enabled: bool) -> None:
        """
        다크 모드를 설정합니다.
        
        Args:
            enabled: True이면 다크 모드 활성화, False이면 라이트 모드
        """
        self._is_dark_mode = enabled
    
    def is_dark_mode(self) -> bool:
        """
        현재 다크 모드 상태를 확인합니다.
        
        Returns:
            bool: 다크 모드가 활성화되어 있으면 True
        """
        return self._is_dark_mode
    
    @property
    def radius(self) -> BorderRadius:
        """
        테두리 반경 시스템에 대한 단축 접근자입니다.
        
        Returns:
            BorderRadius: 테두리 반경 정의
        
        사용 예시:
            >>> ds = get_design_system()
            >>> ds.radius.md  # 12
            >>> ds.radius.xl  # 16
        """
        return self.border_radius
    
    @property
    def button_sizes(self) -> Dict[str, ButtonSize]:
        """
        모든 버튼 크기 정의를 딕셔너리로 반환합니다.
        
        Returns:
            Dict[str, ButtonSize]: 버튼 크기 이름과 ButtonSize 객체의 매핑
        
        사용 예시:
            >>> ds = get_design_system()
            >>> ds.button_sizes['md'].height  # 40
            >>> ds.button_sizes['lg'].font_size  # 16
        """
        return self._button_sizes
    
    def get_button_size(self, size: str) -> ButtonSize:
        """
        지정된 이름의 버튼 크기를 반환합니다.
        
        Args:
            size: 버튼 크기 이름 ('xs', 'sm', 'md', 'lg', 'xl')
        
        Returns:
            ButtonSize: 해당 크기의 버튼 사양
        
        Raises:
            KeyError: 존재하지 않는 크기 이름을 지정한 경우
        """
        return self._button_sizes[size]
    
    def get_color(self, name: str) -> str:
        """
        현재 테마에서 지정된 이름의 색상을 반환합니다.
        
        Args:
            name: 색상 이름 (예: 'primary', 'background', 'text_primary')
        
        Returns:
            str: 색상 HEX 코드
        
        Raises:
            AttributeError: 존재하지 않는 색상 이름을 지정한 경우
        """
        return getattr(self.colors, name)


# =============================================================================
# 헬퍼 함수
# =============================================================================

# 디자인 시스템 인스턴스 캐시
_design_system_instance: Optional[DesignSystem] = None


def get_design_system() -> DesignSystem:
    """
    디자인 시스템 인스턴스를 반환합니다.
    
    싱글톤 패턴을 사용하여 애플리케이션 전체에서 하나의 인스턴스를 공유합니다.
    
    Returns:
        DesignSystem: 디자인 시스템 인스턴스
    
    사용 예시:
        >>> ds = get_design_system()
        >>> print(ds.colors.primary)
    """
    global _design_system_instance
    if _design_system_instance is None:
        _design_system_instance = DesignSystem.get_instance()
    return _design_system_instance


def get_color(name: str) -> str:
    """
    현재 테마에서 지정된 이름의 색상을 반환합니다.
    
    Args:
        name: 색상 이름 (예: 'primary', 'background', 'text_primary')
    
    Returns:
        str: 색상 HEX 코드
    
    사용 예시:
        >>> primary_color = get_color('primary')  # '#E31639'
        >>> bg_color = get_color('background')    # 테마에 따라 다름
    """
    return get_design_system().get_color(name)


def is_dark_mode() -> bool:
    """
    현재 다크 모드가 활성화되어 있는지 확인합니다.
    
    Returns:
        bool: 다크 모드가 활성화되어 있으면 True, 아니면 False
    
    사용 예시:
        >>> if is_dark_mode():
        ...     print("다크 모드가 활성화됨")
    """
    return get_design_system().is_dark_mode()


def set_dark_mode(enabled: bool) -> None:
    """
    다크 모드를 설정합니다.
    
    Args:
        enabled: True이면 다크 모드 활성화, False이면 라이트 모드
    
    사용 예시:
        >>> set_dark_mode(True)   # 다크 모드 활성화
        >>> set_dark_mode(False)  # 라이트 모드로 전환
    """
    get_design_system().set_dark_mode(enabled)


# =============================================================================
# 모듈 레벨 상수 (편의성 제공)
# =============================================================================

# 기본 인스턴스 생성
ds = get_design_system()

# 색상 팔레트
COLORS_LIGHT = ColorPalette()
COLORS_DARK = DarkColorPalette()

# 타이포그래피
TYPOGRAPHY = Typography()

# 여백
SPACING = Spacing()

# 테두리 반경
BORDER_RADIUS = BorderRadius()

# 그림자
SHADOW = Shadow()

# 전환
TRANSITION = Transition()

# Z-인덱스
Z_INDEX = ZIndex()

# 버튼 크기
BUTTON_SIZES = ButtonSize.get_sizes()


# =============================================================================
# __all__ 정의
# =============================================================================

__all__ = [
    # 클래스
    'ColorPalette',
    'DarkColorPalette',
    'Typography',
    'Spacing',
    'BorderRadius',
    'ButtonSize',
    'Shadow',
    'Transition',
    'ZIndex',
    'DesignSystem',
    
    # 함수
    'get_design_system',
    'get_color',
    'is_dark_mode',
    'set_dark_mode',
    
    # 상수
    'ds',
    'COLORS_LIGHT',
    'COLORS_DARK',
    'TYPOGRAPHY',
    'SPACING',
    'BORDER_RADIUS',
    'SHADOW',
    'TRANSITION',
    'Z_INDEX',
    'BUTTON_SIZES',
]
