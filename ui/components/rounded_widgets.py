"""
Rounded UI widgets for Coupang-style design
둥근 모서리를 가진 커스텀 위젯들 (테마 지원)
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable
from .base_widget import ThemedMixin
from ..theme_manager import ThemeManager, get_theme_manager


class RoundedButton(tk.Canvas, ThemedMixin):
    """둥근 모서리를 가진 버튼 위젯 (테마 지원)"""

    def __init__(
        self,
        parent,
        text="",
        command: Optional[Callable] = None,
        bg: Optional[str] = None,
        fg: Optional[str] = None,
        hover_bg: Optional[str] = None,
        disabled_bg: Optional[str] = None,
        font=("맑은 고딕", 9, "bold"),
        radius=8,
        padx=16,
        pady=8,
        style: str = "primary",  # "primary", "secondary", "outline", "danger", "success"
        theme_manager: Optional[ThemeManager] = None,
        **kwargs
    ):
        self.command = command
        self.radius = radius
        self.text = text
        self.font = font
        self._state = "normal"
        self._style = style

        # 테마 초기화
        self.__init_themed__(theme_manager)

        # 스타일에 따른 기본 색상
        self._init_colors(bg, fg, hover_bg, disabled_bg)

        # 텍스트 크기 계산을 위한 임시 라벨
        temp = tk.Label(parent, text=text, font=font)
        text_width = temp.winfo_reqwidth()
        text_height = temp.winfo_reqheight()
        temp.destroy()

        width = text_width + padx * 2
        height = text_height + pady * 2

        # 부모 배경색 가져오기
        try:
            parent_bg = parent.cget("bg")
        except tk.TclError:
            parent_bg = self.get_color("bg_main")

        tk.Canvas.__init__(
            self,
            parent,
            width=width,
            height=height,
            bg=parent_bg,
            highlightthickness=0,
            **kwargs
        )

        self.width = width
        self.height = height
        self._parent_bg = parent_bg

        self._draw_button(self.bg)

        # 이벤트 바인딩
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.bind("<ButtonRelease-1>", self._on_release)

        self.config(cursor="hand2")

    def _init_colors(self, bg, fg, hover_bg, disabled_bg):
        """스타일에 따른 색상 초기화"""
        if self._style == "primary":
            self.bg = bg or self.get_color("primary")
            self.fg = fg or self.get_color("primary_text")
            self.hover_bg = hover_bg or self.get_color("primary_hover")
            self.disabled_bg = disabled_bg or self.get_color("text_disabled")
        elif self._style == "secondary":
            self.bg = bg or self.get_color("bg_secondary")
            self.fg = fg or self.get_color("text_primary")
            self.hover_bg = hover_bg or self.get_color("bg_hover")
            self.disabled_bg = disabled_bg or self.get_color("text_disabled")
        elif self._style == "outline":
            self.bg = bg or self.get_color("primary_light")
            self.fg = fg or self.get_color("primary")
            self.hover_bg = hover_bg or self.get_color("bg_selected")
            self.disabled_bg = disabled_bg or self.get_color("bg_secondary")
        elif self._style == "danger":
            self.bg = bg or self.get_color("error_bg")
            self.fg = fg or self.get_color("error")
            self.hover_bg = hover_bg or self.get_color("error")
            self.disabled_bg = disabled_bg or self.get_color("text_disabled")
        elif self._style == "success":
            self.bg = bg or self.get_color("success_bg")
            self.fg = fg or self.get_color("success")
            self.hover_bg = hover_bg or self.get_color("success")
            self.disabled_bg = disabled_bg or self.get_color("text_disabled")
        else:
            # 기본값
            self.bg = bg or self.get_color("primary")
            self.fg = fg or self.get_color("primary_text")
            self.hover_bg = hover_bg or self.get_color("primary_hover")
            self.disabled_bg = disabled_bg or self.get_color("text_disabled")

    def _draw_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        """둥근 사각형 그리기"""
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _draw_button(self, color):
        """버튼 그리기"""
        self.delete("all")

        # 둥근 사각형 배경
        self._draw_rounded_rect(
            2, 2, self.width - 2, self.height - 2,
            self.radius,
            fill=color,
            outline=color
        )

        # 텍스트 색상 (호버 시 반전 가능)
        text_color = self.fg
        if self._style in ("danger", "success") and color == self.hover_bg:
            text_color = self.get_color("primary_text")

        # 텍스트
        self.create_text(
            self.width / 2,
            self.height / 2,
            text=self.text,
            fill=text_color,
            font=self.font
        )

    def _on_enter(self, event):
        if self._state == "normal":
            self._draw_button(self.hover_bg)

    def _on_leave(self, event):
        if self._state == "normal":
            self._draw_button(self.bg)

    def _on_click(self, event):
        if self._state == "normal":
            self._draw_button(self.hover_bg)

    def _on_release(self, event):
        if self._state == "normal":
            self._draw_button(self.bg)
            if self.command:
                self.command()

    def configure(self, **kwargs):
        needs_redraw = False

        if "state" in kwargs:
            self._state = kwargs.pop("state")
            if self._state == "disabled":
                self.config(cursor="arrow")
            else:
                self.config(cursor="hand2")
            needs_redraw = True
        if "text" in kwargs:
            self.text = kwargs.pop("text")
            needs_redraw = True
        if "bg" in kwargs:
            self.bg = kwargs.pop("bg")
            needs_redraw = True
        if "fg" in kwargs:
            self.fg = kwargs.pop("fg")
            needs_redraw = True
        if "hover_bg" in kwargs:
            self.hover_bg = kwargs.pop("hover_bg")
        if "disabled_bg" in kwargs:
            self.disabled_bg = kwargs.pop("disabled_bg")

        if needs_redraw:
            self._draw_button(self.bg if self._state == "normal" else self.disabled_bg)

        # Only pass valid Canvas options to parent
        if kwargs:
            super().configure(**kwargs)

    config = configure

    def apply_theme(self) -> None:
        """테마 적용"""
        self._init_colors(None, None, None, None)
        try:
            parent = self.master
            if parent:
                self._parent_bg = parent.cget("bg")
                super().configure(bg=self._parent_bg)
        except tk.TclError:
            pass
        self._draw_button(self.bg if self._state == "normal" else self.disabled_bg)

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()


class RoundedFrame(tk.Canvas, ThemedMixin):
    """둥근 모서리를 가진 프레임 위젯 (테마 지원)"""

    def __init__(
        self,
        parent,
        bg: Optional[str] = None,
        border_color: Optional[str] = None,
        radius=12,
        border_width=1,
        theme_manager: Optional[ThemeManager] = None,
        **kwargs
    ):
        self.__init_themed__(theme_manager)

        self.frame_bg = bg or self.get_color("bg_card")
        self.border_color = border_color or self.get_color("border_light")
        self.radius = radius
        self.border_width = border_width

        try:
            parent_bg = parent.cget("bg")
        except tk.TclError:
            parent_bg = self.get_color("bg_main")

        tk.Canvas.__init__(
            self,
            parent,
            bg=parent_bg,
            highlightthickness=0,
            **kwargs
        )

        # 내부 프레임 (위젯들을 담을 컨테이너)
        self.inner_frame = tk.Frame(self, bg=self.frame_bg)

        self.bind("<Configure>", self._on_configure)

    def _draw_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        """둥근 사각형 그리기"""
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _on_configure(self, event):
        """크기 변경 시 다시 그리기"""
        self.delete("rounded_bg")

        width = event.width
        height = event.height

        # 테두리
        if self.border_width > 0:
            self._draw_rounded_rect(
                1, 1, width - 1, height - 1,
                self.radius,
                fill=self.border_color,
                outline=self.border_color,
                tags="rounded_bg"
            )

        # 배경
        self._draw_rounded_rect(
            self.border_width + 1,
            self.border_width + 1,
            width - self.border_width - 1,
            height - self.border_width - 1,
            self.radius - 1,
            fill=self.frame_bg,
            outline=self.frame_bg,
            tags="rounded_bg"
        )

        # 내부 프레임 배치
        padding = self.radius // 2
        self.create_window(
            padding, padding,
            window=self.inner_frame,
            anchor="nw",
            width=width - padding * 2,
            height=height - padding * 2,
            tags="inner"
        )

    def get_inner_frame(self):
        """내부 프레임 반환 (위젯 추가용)"""
        return self.inner_frame

    def apply_theme(self) -> None:
        """테마 적용"""
        self.frame_bg = self.get_color("bg_card")
        self.border_color = self.get_color("border_light")
        self.inner_frame.configure(bg=self.frame_bg)

        try:
            parent = self.master
            if parent:
                super().configure(bg=parent.cget("bg"))
        except tk.TclError:
            pass

        # 다시 그리기
        self.event_generate("<Configure>")

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()


class RoundedEntry(tk.Frame, ThemedMixin):
    """둥근 모서리를 가진 입력 필드 (테마 지원)"""

    def __init__(
        self,
        parent,
        bg: Optional[str] = None,
        fg: Optional[str] = None,
        border_color: Optional[str] = None,
        focus_color: Optional[str] = None,
        font=("맑은 고딕", 10),
        radius=8,
        theme_manager: Optional[ThemeManager] = None,
        **kwargs
    ):
        self.__init_themed__(theme_manager)

        try:
            parent_bg = parent.cget("bg")
        except tk.TclError:
            parent_bg = self.get_color("bg_main")

        tk.Frame.__init__(self, parent, bg=parent_bg)

        self.bg = bg or self.get_color("bg_input")
        self.fg = fg or self.get_color("text_primary")
        self.border_color = border_color or self.get_color("border_light")
        self.focus_color = focus_color or self.get_color("border_focus")
        self.radius = radius
        self._focused = False

        self.canvas = tk.Canvas(
            self,
            highlightthickness=0,
            bg=parent_bg
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.entry = tk.Entry(
            self.canvas,
            bg=self.bg,
            fg=self.fg,
            font=font,
            relief=tk.FLAT,
            insertbackground=self.focus_color,
            **kwargs
        )

        self.canvas.bind("<Configure>", self._on_configure)
        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)

    def _draw_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        """둥근 사각형 그리기"""
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def _on_configure(self, event):
        """크기 변경 시 다시 그리기"""
        self._redraw()

    def _redraw(self):
        self.canvas.delete("border")

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        if width < 10 or height < 10:
            return

        border_color = self.focus_color if self._focused else self.border_color

        # 테두리
        self._draw_rounded_rect(
            1, 1, width - 1, height - 1,
            self.radius,
            fill=border_color,
            outline=border_color,
            tags="border"
        )

        # 배경
        self._draw_rounded_rect(
            2, 2, width - 2, height - 2,
            self.radius - 1,
            fill=self.bg,
            outline=self.bg,
            tags="border"
        )

        # Entry 배치
        self.canvas.create_window(
            self.radius, height // 2,
            window=self.entry,
            anchor="w",
            width=width - self.radius * 2,
            tags="entry"
        )

    def _on_focus_in(self, event):
        self._focused = True
        self._redraw()

    def _on_focus_out(self, event):
        self._focused = False
        self._redraw()

    def get(self):
        return self.entry.get()

    def delete(self, first, last=None):
        return self.entry.delete(first, last)

    def insert(self, index, string):
        return self.entry.insert(index, string)

    def bind(self, sequence, func):
        return self.entry.bind(sequence, func)

    def apply_theme(self) -> None:
        """테마 적용"""
        self.bg = self.get_color("bg_input")
        self.fg = self.get_color("text_primary")
        self.border_color = self.get_color("border_light")
        self.focus_color = self.get_color("border_focus")

        self.entry.configure(
            bg=self.bg,
            fg=self.fg,
            insertbackground=self.focus_color
        )

        try:
            parent = self.master
            if parent:
                parent_bg = parent.cget("bg")
                super().configure(bg=parent_bg)
                self.canvas.configure(bg=parent_bg)
        except tk.TclError:
            pass

        self._redraw()

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()


class ModernScrollbar(tk.Canvas, ThemedMixin):
    """
    모던 커스텀 스크롤바 - 둥근 모서리, 테마 지원
    Modern custom scrollbar with rounded corners and theme support
    """

    def __init__(
        self,
        parent,
        command=None,
        width: int = 8,
        theme_manager: Optional[ThemeManager] = None,
        **kwargs
    ):
        self.__init_themed__(theme_manager)

        self._command = command
        self._thumb_color = self.get_color("scrollbar_thumb")
        self._track_color = self.get_color("bg_secondary")
        self._hover_color = self.get_color("primary")
        self._width = width

        # 스크롤 상태
        self._thumb_pos = 0.0  # 0.0 ~ 1.0
        self._thumb_size = 0.3  # 비율
        self._is_dragging = False
        self._drag_start_y = 0
        self._drag_start_pos = 0.0
        self._is_hovered = False

        try:
            parent_bg = parent.cget("bg")
        except tk.TclError:
            parent_bg = self.get_color("bg_main")

        tk.Canvas.__init__(
            self,
            parent,
            width=width,
            bg=parent_bg,
            highlightthickness=0,
            **kwargs
        )

        self.bind("<Configure>", self._on_configure)
        self.bind("<Button-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def set(self, first: float, last: float) -> None:
        """스크롤 위치 설정 (0.0 ~ 1.0)"""
        first = float(first)
        last = float(last)
        self._thumb_pos = first
        self._thumb_size = last - first
        self._draw()

    def _draw(self) -> None:
        """스크롤바 그리기"""
        self.delete("all")

        height = self.winfo_height()
        width = self._width

        if height < 20:
            return

        # 트랙 (배경)
        self._draw_rounded_rect(
            1, 1, width - 1, height - 1,
            radius=width // 2,
            fill=self._track_color,
            outline=self._track_color
        )

        # 썸 (핸들) 크기 계산
        thumb_height = max(30, int(height * self._thumb_size))
        available_space = height - thumb_height
        thumb_y = int(available_space * self._thumb_pos)

        # 썸 색상 (호버 시 변경)
        thumb_color = self._hover_color if self._is_hovered else self._thumb_color

        # 썸 그리기
        self._draw_rounded_rect(
            2, thumb_y + 2,
            width - 2, thumb_y + thumb_height - 2,
            radius=(width - 4) // 2,
            fill=thumb_color,
            outline=thumb_color
        )

    def _draw_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        """둥근 사각형 그리기"""
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _on_configure(self, event):
        self._draw()

    def _on_click(self, event):
        height = self.winfo_height()
        thumb_height = max(30, int(height * self._thumb_size))
        available_space = height - thumb_height
        thumb_y = int(available_space * self._thumb_pos)

        # 썸 위치 확인
        if thumb_y <= event.y <= thumb_y + thumb_height:
            self._is_dragging = True
            self._drag_start_y = event.y
            self._drag_start_pos = self._thumb_pos
        else:
            # 클릭 위치로 이동
            new_pos = event.y / height
            self._scroll_to(new_pos)

    def _on_drag(self, event):
        if not self._is_dragging:
            return

        height = self.winfo_height()
        thumb_height = max(30, int(height * self._thumb_size))
        available_space = height - thumb_height

        if available_space <= 0:
            return

        delta_y = event.y - self._drag_start_y
        delta_pos = delta_y / available_space
        new_pos = max(0.0, min(1.0, self._drag_start_pos + delta_pos))

        self._scroll_to(new_pos)

    def _on_release(self, event):
        self._is_dragging = False

    def _on_enter(self, event):
        self._is_hovered = True
        self._draw()

    def _on_leave(self, event):
        self._is_hovered = False
        self._draw()

    def _scroll_to(self, pos: float) -> None:
        """특정 위치로 스크롤"""
        if self._command:
            self._command("moveto", str(pos))

    def apply_theme(self) -> None:
        """테마 적용"""
        self._thumb_color = self.get_color("scrollbar_thumb")
        self._track_color = self.get_color("bg_secondary")
        self._hover_color = self.get_color("primary")

        try:
            parent = self.master
            if parent:
                super().configure(bg=parent.cget("bg"))
        except tk.TclError:
            pass

        self._draw()

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()


class StatusBadge(tk.Canvas, ThemedMixin):
    """
    상태 표시 배지 - 둥근 모서리, 테마 지원
    Status badge with rounded corners and theme support
    """

    def __init__(
        self,
        parent,
        text: str = "",
        status: str = "default",  # "success", "warning", "error", "info", "default"
        theme_manager: Optional[ThemeManager] = None,
        **kwargs
    ):
        self.__init_themed__(theme_manager)

        self._text = text
        self._status = status
        self._font = ("맑은 고딕", 9, "bold")

        # 텍스트 크기 계산
        temp = tk.Label(parent, text=text, font=self._font)
        text_width = temp.winfo_reqwidth()
        text_height = temp.winfo_reqheight()
        temp.destroy()

        width = text_width + 16
        height = text_height + 8

        try:
            parent_bg = parent.cget("bg")
        except tk.TclError:
            parent_bg = self.get_color("bg_main")

        tk.Canvas.__init__(
            self,
            parent,
            width=width,
            height=height,
            bg=parent_bg,
            highlightthickness=0,
            **kwargs
        )

        self._width = width
        self._height = height
        self._parent_bg = parent_bg

        self._draw()

    def _get_colors(self):
        """상태에 따른 색상 반환"""
        status_colors = {
            "success": (self.get_color("success_bg"), self.get_color("success")),
            "warning": (self.get_color("warning_bg"), self.get_color("warning")),
            "error": (self.get_color("error_bg"), self.get_color("error")),
            "info": (self.get_color("info_bg"), self.get_color("info")),
            "default": (self.get_color("bg_secondary"), self.get_color("text_secondary")),
        }
        return status_colors.get(self._status, status_colors["default"])

    def _draw_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        """둥근 사각형 그리기"""
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _draw(self):
        """배지 그리기"""
        self.delete("all")

        bg_color, text_color = self._get_colors()
        radius = self._height // 2

        # 배경
        self._draw_rounded_rect(
            1, 1, self._width - 1, self._height - 1,
            radius=radius,
            fill=bg_color,
            outline=bg_color
        )

        # 텍스트
        self.create_text(
            self._width // 2,
            self._height // 2,
            text=self._text,
            fill=text_color,
            font=self._font
        )

    def set_text(self, text: str) -> None:
        """텍스트 변경"""
        self._text = text

        # 크기 재계산
        temp = tk.Label(self.master, text=text, font=self._font)
        text_width = temp.winfo_reqwidth()
        text_height = temp.winfo_reqheight()
        temp.destroy()

        self._width = text_width + 16
        self._height = text_height + 8

        self.configure(width=self._width, height=self._height)
        self._draw()

    def set_status(self, status: str) -> None:
        """상태 변경"""
        self._status = status
        self._draw()

    def apply_theme(self) -> None:
        """테마 적용"""
        try:
            parent = self.master
            if parent:
                self._parent_bg = parent.cget("bg")
                super().configure(bg=self._parent_bg)
        except tk.TclError:
            pass
        self._draw()

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()


def apply_rounded_style_to_ttk(theme_manager: Optional[ThemeManager] = None):
    """ttk 위젯에 둥근 스타일 적용"""
    tm = theme_manager or get_theme_manager()
    style = ttk.Style()

    # Combobox 스타일
    style.configure(
        "Rounded.TCombobox",
        borderwidth=0,
        relief="flat",
        padding=8,
        fieldbackground=tm.get_color("bg_input"),
        background=tm.get_color("bg_input"),
        foreground=tm.get_color("text_primary")
    )

    # Scrollbar 스타일 (둥글게)
    style.configure(
        "Rounded.Vertical.TScrollbar",
        borderwidth=0,
        relief="flat",
        troughcolor=tm.get_color("scrollbar_bg"),
        background=tm.get_color("scrollbar_thumb"),
        arrowsize=0
    )

    # Themed Scrollbar 스타일
    style.configure(
        "Themed.Vertical.TScrollbar",
        gripcount=0,
        background=tm.get_color("scrollbar_thumb"),
        troughcolor=tm.get_color("bg_secondary"),
        borderwidth=0,
        relief="flat"
    )

    style.map(
        "Themed.Vertical.TScrollbar",
        background=[
            ("active", tm.get_color("primary")),
            ("!active", tm.get_color("scrollbar_thumb"))
        ]
    )


# 전역 컬러 헬퍼 함수 (레거시 호환용 - ThemeManager 기반)
def get_coupang_color(color_name: str) -> str:
    """쿠팡 브랜드 컬러를 ThemeManager에서 가져오기"""
    tm = get_theme_manager()
    color_map = {
        "PRIMARY": "primary",
        "ACCENT": "primary_hover",
        "HOVER": "primary_hover",
        "SUCCESS": "success",
        "WARNING": "warning",
        "ERROR": "error",
        "TEXT": "text_primary",
        "SECONDARY_TEXT": "text_secondary",
        "BACKGROUND": "bg_main",
        "CARD": "bg_card",
        "BORDER": "border_light",
        "LIGHT_RED": "primary_light",
        "HIGHLIGHT": "bg_selected"
    }
    theme_key = color_map.get(color_name, "primary")
    return tm.get_color(theme_key)


# 레거시 호환용 - 정적 상수 (라이트 모드 기본값, 새 코드에서는 get_theme_manager() 사용 권장)
class CoupangColors:
    """쿠팡 브랜드 컬러 (레거시 호환용) - 새 코드에서는 ThemeManager 사용 권장"""
    PRIMARY = "#E4002B"
    ACCENT = "#D10024"
    HOVER = "#C80020"
    SUCCESS = "#00A862"
    WARNING = "#FF9500"
    ERROR = "#FF3B30"
    TEXT = "#111111"
    SECONDARY_TEXT = "#666666"
    BACKGROUND = "#F5F5F7"
    CARD = "#FFFFFF"
    BORDER = "#E5E5E5"
    LIGHT_RED = "#FFF0F0"
    HIGHLIGHT = "#FFE8E8"


def create_rounded_button(
    parent,
    text,
    command=None,
    style="primary",
    gui=None,
    padx=14,
    pady=7,
    font=("맑은 고딕", 9, "bold"),
    radius=6,
    width=None,
    theme_manager: Optional[ThemeManager] = None
):
    """
    둥근 버튼 생성 헬퍼 함수

    Args:
        parent: 부모 위젯
        text: 버튼 텍스트
        command: 클릭 시 실행할 함수
        style: "primary", "secondary", "outline", "danger", "success"
        gui: VideoAnalyzerGUI 인스턴스 (레거시 호환, 선택적)
        padx, pady: 내부 패딩
        font: 폰트
        radius: 모서리 둥글기
        width: 고정 너비 (옵션)
        theme_manager: 테마 관리자
    """
    tm = theme_manager or get_theme_manager()

    # 스타일별 색상 (테마 기반)
    styles = {
        "primary": {
            "bg": tm.get_color("primary"),
            "fg": tm.get_color("primary_text"),
            "hover": tm.get_color("primary_hover")
        },
        "secondary": {
            "bg": tm.get_color("bg_secondary"),
            "fg": tm.get_color("text_primary"),
            "hover": tm.get_color("bg_hover")
        },
        "outline": {
            "bg": tm.get_color("primary_light"),
            "fg": tm.get_color("primary"),
            "hover": tm.get_color("bg_selected")
        },
        "danger": {
            "bg": tm.get_color("error_bg"),
            "fg": tm.get_color("error"),
            "hover": tm.get_color("error")
        },
        "success": {
            "bg": tm.get_color("success_bg"),
            "fg": tm.get_color("success"),
            "hover": tm.get_color("success")
        },
        "gray": {
            "bg": tm.get_color("text_secondary"),
            "fg": tm.get_color("primary_text"),
            "hover": tm.get_color("text_disabled")
        },
    }

    # 레거시 GUI 호환: 더 이상 GUI 인스턴스에서 색상을 가져오지 않음
    # 모든 색상은 ThemeManager에서 관리됨

    s = styles.get(style, styles["primary"])

    return RoundedButton(
        parent,
        text=text,
        command=command,
        bg=s["bg"],
        fg=s["fg"],
        hover_bg=s["hover"],
        font=font,
        radius=radius,
        padx=padx,
        pady=pady,
        style=style,
        theme_manager=tm
    )
