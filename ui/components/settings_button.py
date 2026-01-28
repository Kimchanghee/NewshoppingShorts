"""
설정 버튼 모듈
톱니바퀴 아이콘 버튼 + 설정 모달 트리거
"""
import tkinter as tk
import math
from typing import Optional, Callable
from .base_widget import ThemedMixin
from ..theme_manager import ThemeManager, get_theme_manager


class SettingsButton(tk.Canvas, ThemedMixin):
    """톱니바퀴 설정 버튼"""

    def __init__(
        self,
        parent: tk.Widget,
        theme_manager: Optional[ThemeManager] = None,
        size: int = 36,
        on_click: Optional[Callable] = None
    ):
        self._size = size
        self._on_click = on_click
        self._hover = False

        self.__init_themed__(theme_manager)

        tk.Canvas.__init__(
            self, parent,
            width=size, height=size,
            highlightthickness=0,
            bg=self.get_color("bg_header")
        )

        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<Button-1>', self._handle_click)

        self._draw()

    def _draw(self) -> None:
        """버튼 그리기"""
        self.delete("all")

        cx = self._size // 2
        cy = self._size // 2

        # 배경 원 (호버 시)
        if self._hover:
            self.create_oval(
                4, 4, self._size - 4, self._size - 4,
                fill=self.get_color("bg_hover"),
                outline=""
            )

        # 톱니바퀴 아이콘 색상
        color = self.get_color("text_primary") if self._hover else self.get_color("text_secondary")

        # 톱니바퀴 그리기
        self._draw_gear(cx, cy, 10, color)

    def _draw_gear(self, cx: float, cy: float, radius: float, color: str) -> None:
        """톱니바퀴 아이콘 그리기"""
        # 외곽 톱니바퀴 형태
        num_teeth = 8
        outer_radius = radius
        inner_radius = radius * 0.65
        tooth_depth = radius * 0.25

        points = []
        for i in range(num_teeth * 2):
            angle = (i * math.pi) / num_teeth - math.pi / 2
            if i % 2 == 0:
                r = outer_radius + tooth_depth
            else:
                r = outer_radius

            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            points.extend([x, y])

        # 외곽 톱니
        self.create_polygon(points, fill=color, outline=color, smooth=True)

        # 중앙 원 (배경색으로 뚫기)
        center_radius = inner_radius * 0.5
        bg_color = self.get_color("bg_hover") if self._hover else self.get_color("bg_header")
        self.create_oval(
            cx - center_radius, cy - center_radius,
            cx + center_radius, cy + center_radius,
            fill=bg_color, outline=""
        )

    def _on_enter(self, event=None) -> None:
        self._hover = True
        self._draw()
        self.configure(cursor="hand2")

    def _on_leave(self, event=None) -> None:
        self._hover = False
        self._draw()

    def _handle_click(self, event=None) -> None:
        if self._on_click:
            self._on_click()

    def apply_theme(self) -> None:
        """테마 적용"""
        self.configure(bg=self.get_color("bg_header"))
        self._draw()

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()
