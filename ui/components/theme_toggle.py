"""
테마 토글 버튼 모듈
라이트/다크 모드 전환 버튼
(수정됨: 렌더링 왜곡 문제 해결)
"""
import tkinter as tk
import math
from typing import Optional, Callable
from .base_widget import ThemedMixin
from ..theme_manager import ThemeManager, get_theme_manager
from ..animation import TkAnimation, ease_out_quad


class ThemeToggle(tk.Canvas, ThemedMixin):
    """
    테마 토글 스위치 버튼
    슬라이더 형태의 라이트/다크 모드 전환 버튼
    """

    def __init__(
        self,
        parent: tk.Widget,
        theme_manager: Optional[ThemeManager] = None,
        width: int = 60,
        height: int = 30,
        on_toggle: Optional[Callable[[str], None]] = None
    ):
        """
        Args:
            parent: 부모 위젯
            theme_manager: 테마 관리자
            width: 버튼 너비
            height: 버튼 높이
            on_toggle: 토글 시 호출될 콜백 (인자: 새 테마)
        """
        self._width = width
        self._height = height
        self._on_toggle = on_toggle
        self._animating = False

        self.__init_themed__(theme_manager)

        tk.Canvas.__init__(
            self, parent,
            width=width,
            height=height,
            highlightthickness=0,
            bg=self.get_color("bg_header")
        )

        # 슬라이더 위치 (0.0 = 왼쪽/라이트, 1.0 = 오른쪽/다크)
        self._slider_pos = 0.0 if not self._theme_manager.is_dark_mode else 1.0

        self.bind('<Button-1>', self._on_click)
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)

        self._draw()

    def _draw(self) -> None:
        """토글 버튼 그리기"""
        self.delete("all")

        padding = 3
        track_height = self._height - padding * 2
        knob_size = track_height - 4

        # 트랙 색상 (다크 모드 시 primary 색상)
        if self._slider_pos > 0.5:
            track_color = self.get_color("primary")
        else:
            track_color = self.get_color("border_medium")

        # 트랙 그리기 (둥근 사각형)
        self._draw_pill(
            padding, padding,
            self._width - padding, self._height - padding,
            track_color
        )

        # 슬라이더 위치 계산 (정수로 변환하여 떨림 방지)
        track_width = self._width - padding * 2 - knob_size - 4
        knob_x = int(padding + 2 + (track_width * self._slider_pos))
        knob_y = int(padding + 2)

        # 슬라이더 (흰색 원) - 중심 좌표로 전달
        knob_cx = knob_x + knob_size // 2
        knob_cy = knob_y + knob_size // 2
        self._draw_circle(knob_cx, knob_cy, knob_size, "#FFFFFF")

        # 아이콘 그리기
        if self._slider_pos > 0.5:
            # 달 아이콘 (다크 모드)
            self._draw_moon(knob_cx, knob_cy, int(knob_size * 0.4))
        else:
            # 해 아이콘 (라이트 모드)
            self._draw_sun(knob_cx, knob_cy, int(knob_size * 0.4))

    def _draw_pill(self, x1: float, y1: float, x2: float, y2: float, color: str) -> None:
        """알약 형태 그리기 (polygon으로 정확한 반원)"""
        # 정수로 변환
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        height = y2 - y1
        radius = height // 2
        cy = y1 + radius  # 중심 Y

        # 왼쪽 반원 포인트
        left_points = []
        for i in range(90, 271, 5):  # 90도~270도 (왼쪽 반원)
            angle = math.radians(i)
            px = int(x1 + radius + radius * math.cos(angle))
            py = int(cy + radius * math.sin(angle))
            left_points.append((px, py))

        # 오른쪽 반원 포인트
        right_points = []
        for i in range(-90, 91, 5):  # -90도~90도 (오른쪽 반원)
            angle = math.radians(i)
            px = int(x2 - radius + radius * math.cos(angle))
            py = int(cy + radius * math.sin(angle))
            right_points.append((px, py))

        # 전체 폴리곤 (왼쪽 반원 + 오른쪽 반원)
        all_points = left_points + right_points
        if len(all_points) >= 3:
            self.create_polygon(all_points, fill=color, outline="", smooth=True)

    def _draw_circle(self, cx: int, cy: int, size: int, color: str) -> None:
        """원 그리기 (중심 좌표 기준)"""
        radius = size // 2
        self.create_oval(
            cx - radius, cy - radius,
            cx + radius, cy + radius,
            fill=color, outline=""
        )

    def _draw_sun(self, cx: int, cy: int, radius: int) -> None:
        """해 아이콘 그리기"""
        sun_color = "#FFB300"

        # 중앙 원
        inner_radius = max(1, int(radius * 0.5))
        self.create_oval(
            cx - inner_radius, cy - inner_radius,
            cx + inner_radius, cy + inner_radius,
            fill=sun_color, outline=""
        )

        # 광선 (8방향)
        ray_length = max(1, int(radius * 0.3))
        ray_start = max(1, int(radius * 0.6))
        for i in range(8):
            angle = math.radians(i * 45)
            x1 = int(cx + math.cos(angle) * ray_start)
            y1 = int(cy + math.sin(angle) * ray_start)
            x2 = int(cx + math.cos(angle) * (ray_start + ray_length))
            y2 = int(cy + math.sin(angle) * (ray_start + ray_length))
            self.create_line(x1, y1, x2, y2, fill=sun_color, width=2)

    def _draw_moon(self, cx: int, cy: int, radius: int) -> None:
        """달 아이콘 그리기 (대칭적 초승달)"""
        moon_color = "#FFE082"

        # 메인 원
        self.create_oval(
            cx - radius, cy - radius,
            cx + radius, cy + radius,
            fill=moon_color, outline=""
        )

        # 그림자 (대칭적 오프셋으로 초승달 효과)
        shadow_offset_x = int(radius * 0.35)
        shadow_offset_y = int(radius * 0.15)
        shadow_radius = int(radius * 0.8)
        bg_color = self.get_color("primary")
        self.create_oval(
            cx - shadow_radius + shadow_offset_x,
            cy - shadow_radius - shadow_offset_y,
            cx + shadow_radius + shadow_offset_x,
            cy + shadow_radius - shadow_offset_y,
            fill=bg_color, outline=""
        )

    def _on_click(self, event=None) -> None:
        """클릭 시 테마 토글"""
        if self._animating:
            return

        # 애니메이션으로 슬라이더 이동
        start_pos = self._slider_pos
        end_pos = 0.0 if start_pos > 0.5 else 1.0

        self._animating = True

        def update_pos(pos: float):
            # 소수점 2자리로 제한하여 떨림 방지
            self._slider_pos = round(pos, 2)
            self._draw()

        def on_complete():
            self._animating = False
            # 테마 토글
            new_theme = self._theme_manager.toggle_theme()
            if self._on_toggle:
                self._on_toggle(new_theme)

        TkAnimation.animate_value(
            self,
            start_pos, end_pos,
            200,
            update_pos,
            ease_out_quad,
            on_complete
        )

    def _on_enter(self, event=None) -> None:
        """마우스 진입"""
        self.configure(cursor="hand2")

    def _on_leave(self, event=None) -> None:
        """마우스 이탈"""
        pass

    def sync_with_theme(self) -> None:
        """테마 상태와 슬라이더 동기화"""
        self._slider_pos = 1.0 if self._theme_manager.is_dark_mode else 0.0
        self._draw()

    def apply_theme(self) -> None:
        """테마 적용"""
        self.configure(bg=self.get_color("bg_header"))
        self.sync_with_theme()

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()


class ThemeToggleButton(tk.Frame, ThemedMixin):
    """
    테마 토글 버튼 (레이블 포함)
    토글 스위치 + 현재 테마 레이블
    """

    def __init__(
        self,
        parent: tk.Widget,
        theme_manager: Optional[ThemeManager] = None,
        show_label: bool = True,
        on_toggle: Optional[Callable[[str], None]] = None
    ):
        self._show_label = show_label
        self._on_toggle = on_toggle

        self.__init_themed__(theme_manager)

        tk.Frame.__init__(self, parent, bg=self.get_color("bg_header"))

        self._create_widgets()

    def _create_widgets(self) -> None:
        """위젯 생성"""
        # 레이블
        if self._show_label:
            self._label = tk.Label(
                self,
                text=self._get_label_text(),
                font=("맑은 고딕", 9),
                bg=self.get_color("bg_header"),
                fg=self.get_color("text_secondary")
            )
            self._label.pack(side=tk.LEFT, padx=(0, 8))

        # 토글 스위치
        self._toggle = ThemeToggle(
            self,
            theme_manager=self._theme_manager,
            on_toggle=self._handle_toggle
        )
        self._toggle.pack(side=tk.LEFT)

    def _get_label_text(self) -> str:
        """현재 테마에 따른 레이블 텍스트"""
        return "다크 모드" if self._theme_manager.is_dark_mode else "라이트 모드"

    def _handle_toggle(self, new_theme: str) -> None:
        """토글 처리"""
        if self._show_label:
            self._label.configure(text=self._get_label_text())

        if self._on_toggle:
            self._on_toggle(new_theme)

    def apply_theme(self) -> None:
        """테마 적용"""
        self.configure(bg=self.get_color("bg_header"))
        if self._show_label:
            self._label.configure(
                bg=self.get_color("bg_header"),
                fg=self.get_color("text_secondary"),
                text=self._get_label_text()
            )
        self._toggle.apply_theme()

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()


class ThemeIconButton(tk.Canvas, ThemedMixin):
    """
    간단한 테마 아이콘 버튼
    클릭 시 테마 전환 (해/달 아이콘만 표시)
    """

    def __init__(
        self,
        parent: tk.Widget,
        theme_manager: Optional[ThemeManager] = None,
        size: int = 32,
        on_toggle: Optional[Callable[[str], None]] = None
    ):
        self._size = size
        self._on_toggle = on_toggle
        self._hover = False

        self.__init_themed__(theme_manager)

        tk.Canvas.__init__(
            self, parent,
            width=size, height=size,
            highlightthickness=0,
            bg=self.get_color("bg_header")
        )

        self.bind('<Button-1>', self._on_click)
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)

        self._draw()

    def _draw(self) -> None:
        """아이콘 그리기"""
        self.delete("all")

        # 배경 원 (호버 시)
        if self._hover:
            self.create_oval(
                2, 2, self._size - 2, self._size - 2,
                fill=self.get_color("bg_hover"),
                outline=""
            )

        # 아이콘
        cx = self._size / 2
        cy = self._size / 2
        radius = self._size * 0.3

        if self._theme_manager.is_dark_mode:
            self._draw_moon(cx, cy, radius)
        else:
            self._draw_sun(cx, cy, radius)

    def _draw_sun(self, cx: float, cy: float, radius: float) -> None:
        """해 아이콘"""
        color = self.get_color("text_secondary")
        cx, cy, radius = int(cx), int(cy), int(radius)

        # 중앙 원
        inner = max(1, int(radius * 0.45))
        self.create_oval(
            cx - inner, cy - inner,
            cx + inner, cy + inner,
            fill=color, outline=""
        )

        # 광선
        for i in range(8):
            angle = math.radians(i * 45)
            x1 = int(cx + math.cos(angle) * (radius * 0.55))
            y1 = int(cy + math.sin(angle) * (radius * 0.55))
            x2 = int(cx + math.cos(angle) * radius)
            y2 = int(cy + math.sin(angle) * radius)
            self.create_line(x1, y1, x2, y2, fill=color, width=2)

    def _draw_moon(self, cx: float, cy: float, radius: float) -> None:
        """달 아이콘 (대칭적 초승달)"""
        color = self.get_color("text_secondary")
        cx, cy, radius = int(cx), int(cy), int(radius)

        # 초승달 (두 개의 원으로 표현)
        self.create_oval(
            cx - radius, cy - radius,
            cx + radius, cy + radius,
            fill=color, outline=""
        )

        # 그림자 (대칭적)
        offset_x = int(radius * 0.3)
        offset_y = int(radius * 0.15)
        bg = self.get_color("bg_hover") if self._hover else self.get_color("bg_header")
        self.create_oval(
            cx - radius + offset_x, cy - radius - offset_y,
            cx + radius + offset_x, cy + radius - offset_y,
            fill=bg, outline=""
        )

    def _on_click(self, event=None) -> None:
        """클릭 - 테마 토글"""
        new_theme = self._theme_manager.toggle_theme()
        self._draw()
        if self._on_toggle:
            self._on_toggle(new_theme)

    def _on_enter(self, event=None) -> None:
        self._hover = True
        self._draw()
        self.configure(cursor="hand2")

    def _on_leave(self, event=None) -> None:
        self._hover = False
        self._draw()

    def apply_theme(self) -> None:
        self.configure(bg=self.get_color("bg_header"))
        self._draw()

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()
