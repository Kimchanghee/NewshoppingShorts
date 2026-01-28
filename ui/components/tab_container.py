"""
탭 컨테이너 모듈
탭 기반 네비게이션 및 컨텐츠 전환 관리
"""
import tkinter as tk
from typing import Dict, Optional, Callable, List, Tuple
from .base_widget import ThemedMixin, ThemedFrame, ThemedLabel, ThemedCanvas
from ..theme_manager import ThemeManager, get_theme_manager
from ..animation import TabTransition


class TabButton(tk.Canvas, ThemedMixin):
    """탭 버튼 (커스텀 캔버스 기반)"""

    def __init__(
        self,
        parent: tk.Widget,
        text: str,
        icon: str = "",
        theme_manager: Optional[ThemeManager] = None,
        command: Optional[Callable] = None,
        width: int = 120,
        height: int = 44
    ):
        self._text = text
        self._icon = icon
        self._command = command
        self._active = False
        self._hover = False
        self._width = width
        self._height = height

        self.__init_themed__(theme_manager)

        tk.Canvas.__init__(
            self, parent,
            width=width, height=height,
            highlightthickness=0,
            bg=self.get_color("bg_header")
        )

        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<Button-1>', self._on_click)

        self._draw()

    def _draw(self) -> None:
        """탭 버튼 그리기"""
        self.delete("all")

        # 배경색 결정
        if self._active:
            bg_color = self.get_color("bg_card")
        elif self._hover:
            bg_color = self.get_color("bg_hover")
        else:
            bg_color = self.get_color("bg_header")

        # 배경 그리기 (상단 둥근 모서리)
        radius = 8
        self._draw_rounded_rect(0, 0, self._width, self._height + radius, radius, bg_color)

        # 텍스트 색상
        if self._active:
            text_color = self.get_color("tab_active")
        else:
            text_color = self.get_color("tab_inactive")

        # 아이콘 + 텍스트
        display_text = f"{self._icon} {self._text}" if self._icon else self._text
        self.create_text(
            self._width // 2,
            self._height // 2,
            text=display_text,
            fill=text_color,
            font=("맑은 고딕", 11, "bold" if self._active else "normal"),
            anchor="center"
        )

        # 활성 인디케이터 (하단 선)
        if self._active:
            indicator_height = 3
            self.create_rectangle(
                10, self._height - indicator_height,
                self._width - 10, self._height,
                fill=self.get_color("tab_indicator"),
                outline=""
            )

    def _draw_rounded_rect(
        self,
        x1: int, y1: int,
        x2: int, y2: int,
        radius: int,
        color: str
    ) -> None:
        """둥근 사각형 그리기 (상단만 둥글게)"""
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2,
            x1, y2,
            x1, y1 + radius,
            x1, y1,
            x1 + radius, y1
        ]
        self.create_polygon(points, fill=color, outline="", smooth=True)

    def _on_enter(self, event=None) -> None:
        self._hover = True
        self._draw()
        self.configure(cursor="hand2")

    def _on_leave(self, event=None) -> None:
        self._hover = False
        self._draw()

    def _on_click(self, event=None) -> None:
        if self._command:
            self._command()

    def set_active(self, active: bool) -> None:
        """활성 상태 설정"""
        self._active = active
        self._draw()

    def apply_theme(self) -> None:
        """테마 적용"""
        self.configure(bg=self.get_color("bg_header"))
        self._draw()

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()


class TabContainer(tk.Frame, ThemedMixin):
    """
    탭 컨테이너 위젯
    탭 헤더와 컨텐츠 영역 관리
    """

    def __init__(
        self,
        parent: tk.Widget,
        theme_manager: Optional[ThemeManager] = None,
        animation_duration: int = 250,
        **kwargs
    ):
        self.__init_themed__(theme_manager)
        self._animation_duration = animation_duration

        kwargs['bg'] = self.get_color("bg_main")
        tk.Frame.__init__(self, parent, **kwargs)

        # 탭 데이터
        self._tabs: Dict[str, Dict] = {}
        self._tab_order: List[str] = []
        self._current_tab: Optional[str] = None
        self._tab_buttons: Dict[str, TabButton] = {}

        # 레이아웃 구성
        self._create_layout()

        # 탭 전환 애니메이션
        self._transition = TabTransition(self._content_frame, animation_duration)

    def _create_layout(self) -> None:
        """레이아웃 생성"""
        # 헤더 영역 (탭 버튼들)
        self._header_frame = tk.Frame(self, bg=self.get_color("bg_header"), height=50)
        self._header_frame.pack(fill=tk.X, side=tk.TOP)
        self._header_frame.pack_propagate(False)

        # 탭 버튼 컨테이너
        self._tab_buttons_frame = tk.Frame(self._header_frame, bg=self.get_color("bg_header"))
        self._tab_buttons_frame.pack(side=tk.LEFT, padx=16, pady=3)

        # 우측 영역 (테마 토글 등을 위한 공간)
        self._header_right = tk.Frame(self._header_frame, bg=self.get_color("bg_header"))
        self._header_right.pack(side=tk.RIGHT, padx=16, pady=3)

        # 구분선
        self._separator = tk.Frame(self, bg=self.get_color("border_light"), height=1)
        self._separator.pack(fill=tk.X, side=tk.TOP)

        # 컨텐츠 영역
        self._content_frame = tk.Frame(self, bg=self.get_color("bg_main"))
        self._content_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP)

    def add_tab(
        self,
        name: str,
        label: str,
        content_frame: tk.Frame,
        icon: str = "",
        select: bool = False
    ) -> None:
        """
        탭 추가

        Args:
            name: 탭 식별자
            label: 표시 레이블
            content_frame: 탭 컨텐츠 프레임
            icon: 아이콘 (이모지 또는 유니코드)
            select: 추가 후 선택 여부
        """
        if name in self._tabs:
            return

        # 탭 데이터 저장
        self._tabs[name] = {
            "label": label,
            "icon": icon,
            "content": content_frame
        }
        self._tab_order.append(name)

        # 탭 버튼 생성
        button = TabButton(
            self._tab_buttons_frame,
            text=label,
            icon=icon,
            theme_manager=self._theme_manager,
            command=lambda n=name: self.select_tab(n)
        )
        button.pack(side=tk.LEFT, padx=2)
        self._tab_buttons[name] = button

        # 첫 번째 탭이거나 select=True인 경우 선택
        if len(self._tabs) == 1 or select:
            self.select_tab(name, animate=False)

    def remove_tab(self, name: str) -> None:
        """탭 제거"""
        if name not in self._tabs:
            return

        # 현재 탭이면 다른 탭으로 전환
        if self._current_tab == name:
            idx = self._tab_order.index(name)
            new_idx = idx - 1 if idx > 0 else (idx + 1 if idx < len(self._tab_order) - 1 else None)
            if new_idx is not None:
                self.select_tab(self._tab_order[new_idx], animate=False)

        # 정리
        self._tab_buttons[name].destroy()
        del self._tab_buttons[name]
        self._tabs[name]["content"].place_forget()
        del self._tabs[name]
        self._tab_order.remove(name)

    def select_tab(self, name: str, animate: bool = False) -> None:
        """
        탭 선택 (애니메이션 없이 즉시 전환)

        Args:
            name: 탭 식별자
            animate: 애니메이션 적용 여부 (기본값 False - 즉시 전환)
        """
        if name not in self._tabs or name == self._current_tab:
            return

        old_frame = self._tabs[self._current_tab]["content"] if self._current_tab else None
        new_frame = self._tabs[name]["content"]

        # 탭 버튼 상태 업데이트
        for tab_name, button in self._tab_buttons.items():
            button.set_active(tab_name == name)

        # 컨텐츠 즉시 전환 (애니메이션 없음)
        self._transition.instant_switch(old_frame, new_frame)

        self._current_tab = name

    @property
    def current_tab(self) -> Optional[str]:
        """현재 선택된 탭"""
        return self._current_tab

    @property
    def header_right(self) -> tk.Frame:
        """헤더 우측 영역 (위젯 추가용)"""
        return self._header_right

    @property
    def tab_names(self) -> List[str]:
        """탭 이름 목록"""
        return self._tab_order.copy()

    @property
    def content_frame(self) -> tk.Frame:
        """컨텐츠 프레임 (탭 컨텐츠의 부모)"""
        return self._content_frame

    def apply_theme(self) -> None:
        """테마 적용"""
        self.configure(bg=self.get_color("bg_main"))
        self._header_frame.configure(bg=self.get_color("bg_header"))
        self._tab_buttons_frame.configure(bg=self.get_color("bg_header"))
        self._header_right.configure(bg=self.get_color("bg_header"))
        self._separator.configure(bg=self.get_color("border_light"))
        self._content_frame.configure(bg=self.get_color("bg_main"))

        # 탭 버튼 테마 적용
        for button in self._tab_buttons.values():
            button.apply_theme()

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()


class TabContent(tk.Frame, ThemedMixin):
    """
    탭 컨텐츠 베이스 클래스
    각 탭의 컨텐츠 프레임 기본 클래스
    """

    def __init__(
        self,
        parent: tk.Widget,
        theme_manager: Optional[ThemeManager] = None,
        padding: Tuple[int, int] = (20, 16),
        **kwargs
    ):
        self._padding = padding
        self.__init_themed__(theme_manager)

        kwargs['bg'] = self.get_color("bg_main")
        tk.Frame.__init__(self, parent, **kwargs)

        # 내부 컨테이너 (패딩 적용)
        self._inner = tk.Frame(self, bg=self.get_color("bg_main"))
        self._inner.pack(fill=tk.BOTH, expand=True, padx=padding[0], pady=padding[1])

    @property
    def inner(self) -> tk.Frame:
        """내부 컨테이너 프레임"""
        return self._inner

    def create_section(
        self,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> tk.Frame:
        """
        섹션 생성

        Args:
            title: 섹션 제목
            description: 섹션 설명

        Returns:
            섹션 프레임
        """
        section = tk.Frame(self._inner, bg=self.get_color("bg_card"))
        section.pack(fill=tk.X, pady=(0, 12))

        # 섹션 내부 패딩
        inner = tk.Frame(section, bg=self.get_color("bg_card"))
        inner.pack(fill=tk.X, padx=16, pady=12)

        if title:
            title_label = tk.Label(
                inner,
                text=title,
                font=("맑은 고딕", 12, "bold"),
                bg=self.get_color("bg_card"),
                fg=self.get_color("text_primary"),
                anchor="w"
            )
            title_label.pack(fill=tk.X)

        if description:
            desc_label = tk.Label(
                inner,
                text=description,
                font=("맑은 고딕", 9),
                bg=self.get_color("bg_card"),
                fg=self.get_color("text_secondary"),
                anchor="w"
            )
            desc_label.pack(fill=tk.X, pady=(2, 0))

        # 컨텐츠 영역
        content = tk.Frame(inner, bg=self.get_color("bg_card"))
        content.pack(fill=tk.X, pady=(8, 0))

        return content

    def create_card(
        self,
        title: Optional[str] = None,
        expand: bool = False
    ) -> tk.Frame:
        """
        카드 스타일 컨테이너 생성

        Args:
            title: 카드 제목
            expand: 세로 확장 여부

        Returns:
            카드 컨텐츠 프레임
        """
        card = tk.Frame(
            self._inner,
            bg=self.get_color("bg_card"),
            highlightbackground=self.get_color("border_light"),
            highlightthickness=1
        )
        if expand:
            card.pack(fill=tk.BOTH, expand=True, pady=(0, 12))
        else:
            card.pack(fill=tk.X, pady=(0, 12))

        if title:
            header = tk.Frame(card, bg=self.get_color("bg_secondary"))
            header.pack(fill=tk.X)

            title_label = tk.Label(
                header,
                text=title,
                font=("맑은 고딕", 11, "bold"),
                bg=self.get_color("bg_secondary"),
                fg=self.get_color("text_primary"),
                anchor="w",
                padx=16,
                pady=10
            )
            title_label.pack(fill=tk.X)

        content = tk.Frame(card, bg=self.get_color("bg_card"))
        content.pack(fill=tk.BOTH, expand=expand, padx=16, pady=12)

        return content

    def apply_theme(self) -> None:
        """테마 적용"""
        self.configure(bg=self.get_color("bg_main"))
        self._inner.configure(bg=self.get_color("bg_main"))

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()
