"""
고정 레이아웃 설정 모듈
Fixed Layout Configuration Module

모든 해상도에서 일관된 UI를 위한 고정 크기 설정
Fixed size settings for consistent UI across all resolutions
"""


class FixedLayoutConfig:
    """
    고정 레이아웃 설정 클래스
    Fixed Layout Configuration Class

    이 클래스는 모든 해상도에서 동일한 UI를 보장하기 위한
    고정 크기 및 위치 값을 제공합니다.

    This class provides fixed size and position values
    to ensure consistent UI across all resolutions.
    """

    # ===== 윈도우 설정 =====
    # Window Settings
    WINDOW_WIDTH = 1300
    WINDOW_HEIGHT = 950
    WINDOW_MIN_WIDTH = 1000
    WINDOW_MIN_HEIGHT = 700
    WINDOW_MAX_WIDTH = 1920
    WINDOW_MAX_HEIGHT = 1200

    # ===== 헤더 영역 =====
    # Header Area
    HEADER_HEIGHT = 60
    HEADER_PADDING_X = 20
    HEADER_PADDING_Y = 10

    # ===== 사이드바 =====
    # Sidebar
    SIDEBAR_WIDTH = 240
    SIDEBAR_ITEM_HEIGHT = 56
    SIDEBAR_ITEM_PADDING = 8
    SIDEBAR_STEP_CIRCLE_RADIUS = 14

    # ===== 컨텐츠 영역 =====
    # Content Area
    CONTENT_PADDING = 20
    CARD_PADDING = 16
    CARD_BORDER_RADIUS = 12

    # ===== 폰트 크기 (고정) =====
    # Font Sizes (Fixed)
    FONT_TITLE = 16
    FONT_SUBTITLE = 12
    FONT_BODY = 11
    FONT_SMALL = 10
    FONT_TINY = 9
    FONT_CAPTION = 8

    # ===== 버튼 크기 =====
    # Button Sizes
    BUTTON_HEIGHT_LARGE = 44
    BUTTON_HEIGHT_MEDIUM = 36
    BUTTON_HEIGHT_SMALL = 28
    BUTTON_PADDING_X = 20
    BUTTON_PADDING_Y = 8

    # ===== 입력 필드 =====
    # Input Fields
    INPUT_HEIGHT = 40
    INPUT_PADDING_X = 12
    INPUT_PADDING_Y = 8

    # ===== 간격 =====
    # Spacing
    SPACING_XS = 4
    SPACING_SM = 8
    SPACING_MD = 12
    SPACING_LG = 16
    SPACING_XL = 20
    SPACING_XXL = 24

    # ===== 진행 패널 =====
    # Progress Panel
    PROGRESS_BAR_HEIGHT = 8
    PROGRESS_ITEM_HEIGHT = 40

    # ===== 테마 토글 =====
    # Theme Toggle
    TOGGLE_WIDTH = 52
    TOGGLE_HEIGHT = 28
    TOGGLE_CIRCLE_RADIUS = 10

    # ===== 체크박스/라디오 =====
    # Checkbox/Radio
    CHECKBOX_SIZE = 20
    RADIO_SIZE = 20

    # ===== 음성 선택 카드 =====
    # Voice Selection Card
    VOICE_CARD_HEIGHT = 72
    VOICE_CARD_WIDTH = 200
    VOICE_CARD_PADDING = 12

    # ===== 스크롤 영역 =====
    # Scroll Areas
    SCROLLBAR_WIDTH = 8
    SCROLL_CONTENT_PADDING = 12

    @classmethod
    def get_font(cls, name: str = "body", weight: str = "normal") -> tuple:
        """
        폰트 튜플 반환
        Returns font tuple

        Args:
            name: 폰트 크기 이름 (title, subtitle, body, small, tiny, caption)
            weight: 폰트 굵기 (normal, bold)

        Returns:
            (font_family, size, weight) 튜플
        """
        size_map = {
            "title": cls.FONT_TITLE,
            "subtitle": cls.FONT_SUBTITLE,
            "body": cls.FONT_BODY,
            "small": cls.FONT_SMALL,
            "tiny": cls.FONT_TINY,
            "caption": cls.FONT_CAPTION,
        }
        size = size_map.get(name, cls.FONT_BODY)
        return ("맑은 고딕", size, weight)

    @classmethod
    def get_padding(cls, size: str = "md") -> int:
        """
        패딩 값 반환
        Returns padding value

        Args:
            size: 패딩 크기 (xs, sm, md, lg, xl, xxl)

        Returns:
            패딩 픽셀 값
        """
        padding_map = {
            "xs": cls.SPACING_XS,
            "sm": cls.SPACING_SM,
            "md": cls.SPACING_MD,
            "lg": cls.SPACING_LG,
            "xl": cls.SPACING_XL,
            "xxl": cls.SPACING_XXL,
        }
        return padding_map.get(size, cls.SPACING_MD)


# 전역 인스턴스 (편의용)
# Global instance for convenience
LAYOUT = FixedLayoutConfig()
