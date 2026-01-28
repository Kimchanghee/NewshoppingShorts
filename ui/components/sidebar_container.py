"""
사이드바 컨테이너 모듈
좌측 사이드바 메뉴 + 우측 컨텐츠 영역 관리
순차적 워크플로우 지원 (1->2->3)
"""
import logging
import tkinter as tk
from typing import Dict, Optional, Callable, List
from .base_widget import ThemedMixin
from ..theme_manager import ThemeManager, get_theme_manager
from ..animation import TabTransition

logger = logging.getLogger(__name__)


class SidebarMenuItem(tk.Canvas, ThemedMixin):
    """사이드바 메뉴 아이템 (캔버스 기반)"""

    def __init__(
        self,
        parent: tk.Widget,
        text: str,
        step_number: int,
        icon: str = "",
        theme_manager: Optional[ThemeManager] = None,
        command: Optional[Callable] = None,
        width: int = 220,
        height: int = 56
    ):
        self._text = text
        self._step_number = step_number
        self._icon = icon
        self._command = command
        self._active = False
        self._hover = False
        self._completed = False
        self._width = width
        self._height = height

        self.__init_themed__(theme_manager)

        tk.Canvas.__init__(
            self, parent,
            width=width, height=height,
            highlightthickness=0,
            bg=self.get_color("sidebar_bg")
        )

        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<Button-1>', self._on_click)

        self._draw()

    def _draw(self) -> None:
        """메뉴 아이템 그리기"""
        self.delete("all")

        # 배경색 결정
        if self._active:
            bg_color = self.get_color("sidebar_item_active")
        elif self._hover:
            bg_color = self.get_color("sidebar_item_hover")
        else:
            bg_color = self.get_color("sidebar_bg")

        # 배경 그리기
        self.create_rectangle(
            0, 0, self._width, self._height,
            fill=bg_color, outline=""
        )

        # 활성 인디케이터 (좌측 세로선)
        if self._active:
            self.create_rectangle(
                0, 8, 4, self._height - 8,
                fill=self.get_color("sidebar_indicator"),
                outline=""
            )

        # 단계 번호 원형 배경
        circle_x = 28
        circle_y = self._height // 2
        circle_radius = 14

        if self._completed:
            circle_color = self.get_color("sidebar_step_completed")
            number_color = "#FFFFFF"
        elif self._active:
            circle_color = self.get_color("sidebar_step_number")
            number_color = "#FFFFFF"
        else:
            circle_color = self.get_color("border_light")
            number_color = self.get_color("text_secondary")

        self.create_oval(
            circle_x - circle_radius, circle_y - circle_radius,
            circle_x + circle_radius, circle_y + circle_radius,
            fill=circle_color, outline=""
        )

        # 단계 번호 또는 체크 아이콘
        if self._completed:
            # 체크 아이콘
            self.create_text(
                circle_x, circle_y,
                text="v",
                fill=number_color,
                font=("맑은 고딕", 10, "bold"),
                anchor="center"
            )
        else:
            self.create_text(
                circle_x, circle_y,
                text=str(self._step_number),
                fill=number_color,
                font=("맑은 고딕", 11, "bold"),
                anchor="center"
            )

        # 텍스트 색상
        if self._active:
            text_color = self.get_color("text_primary")
        else:
            text_color = self.get_color("text_secondary")

        # 아이콘 + 텍스트
        text_x = 56
        if self._icon:
            self.create_text(
                text_x, circle_y,
                text=self._icon,
                fill=text_color,
                font=("맑은 고딕", 12),
                anchor="w"
            )
            text_x += 24

        self.create_text(
            text_x, circle_y,
            text=self._text,
            fill=text_color,
            font=("맑은 고딕", 11, "bold" if self._active else "normal"),
            anchor="w"
        )

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

    def set_completed(self, completed: bool) -> None:
        """완료 상태 설정"""
        self._completed = completed
        self._draw()

    def apply_theme(self) -> None:
        """테마 적용"""
        self.configure(bg=self.get_color("sidebar_bg"))
        self._draw()

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()


class SidebarProgressMini(tk.Frame, ThemedMixin):
    """사이드바 하단에 표시되는 미니 진행 상황 패널"""

    def __init__(
        self,
        parent: tk.Widget,
        gui=None,
        theme_manager: Optional[ThemeManager] = None
    ):
        self.__init_themed__(theme_manager)
        self.gui = gui

        tk.Frame.__init__(
            self, parent,
            bg=self.get_color("sidebar_bg"),
            bd=0
        )

        self._create_widgets()

    def _create_widgets(self) -> None:
        """위젯 생성"""
        bg = self.get_color("sidebar_bg")
        text_primary = self.get_color("text_primary")
        text_secondary = self.get_color("text_secondary")
        primary = self.get_color("primary")

        # 상단 구분선
        self._divider = tk.Frame(self, bg=self.get_color("border_light"), height=1)
        self._divider.pack(fill=tk.X)

        # 컨텐츠 영역
        self._content = tk.Frame(self, bg=bg)
        self._content.pack(fill=tk.X, padx=12, pady=10)

        # 헤더
        self._header = tk.Frame(self._content, bg=bg)
        self._header.pack(fill=tk.X)

        self._title_label = tk.Label(
            self._header,
            text="제작 진행",
            font=("맑은 고딕", 10, "bold"),
            bg=bg,
            fg=text_primary
        )
        self._title_label.pack(side=tk.LEFT)

        # 현재 작업 상태
        self._status_label = tk.Label(
            self._content,
            text="대기 중",
            font=("맑은 고딕", 9),
            bg=bg,
            fg=text_secondary,
            anchor="w"
        )
        self._status_label.pack(fill=tk.X, pady=(4, 0))

        # 진행 스텝 표시 (간소화)
        self._steps_frame = tk.Frame(self._content, bg=bg)
        self._steps_frame.pack(fill=tk.X, pady=(6, 0))

        # 미니 스텝 인디케이터 생성
        self._step_labels = {}
        steps = [
            ("📥", "download"),
            ("🤖", "analysis"),
            ("🔍", "ocr_analysis"),
            ("🌐", "translation"),
            ("🎤", "tts"),
            ("🎬", "video"),
        ]

        for i, (icon, key) in enumerate(steps):
            step_label = tk.Label(
                self._steps_frame,
                text=icon,
                font=("맑은 고딕", 10),
                bg=bg,
                fg=text_secondary,
                width=3
            )
            step_label.pack(side=tk.LEFT, padx=1)
            self._step_labels[key] = step_label

        # 전체 진행률 표시
        self._progress_label = tk.Label(
            self._content,
            text="0%",
            font=("맑은 고딕", 11, "bold"),
            bg=bg,
            fg=primary
        )
        self._progress_label.pack(fill=tk.X, pady=(6, 0))

    def update_status(self, status: str) -> None:
        """상태 텍스트 업데이트"""
        try:
            self._status_label.configure(text=status)
        except Exception as e:
            logger.debug(f"상태 업데이트 실패: {e}")

    def update_progress(self, progress: int) -> None:
        """진행률 업데이트"""
        try:
            self._progress_label.configure(text=f"{progress}%")
        except Exception as e:
            logger.debug(f"진행률 업데이트 실패: {e}")

    def update_step(self, step_key: str, status: str) -> None:
        """스텝 상태 업데이트 (completed, processing, waiting)"""
        if step_key not in self._step_labels:
            return

        label = self._step_labels[step_key]
        try:
            if status == "completed":
                label.configure(fg=self.get_color("success"))
            elif status == "processing":
                label.configure(fg=self.get_color("primary"))
            elif status == "failed":
                label.configure(fg=self.get_color("error"))
            else:
                label.configure(fg=self.get_color("text_secondary"))
        except Exception as e:
            logger.debug(f"스텝 상태 업데이트 실패 ({step_key}): {e}")

    def reset_steps(self) -> None:
        """모든 스텝 초기화"""
        text_secondary = self.get_color("text_secondary")
        for label in self._step_labels.values():
            try:
                label.configure(fg=text_secondary)
            except Exception as e:
                logger.debug(f"스텝 초기화 실패: {e}")
        self.update_progress(0)
        self.update_status("대기 중")

    def apply_theme(self) -> None:
        """테마 적용"""
        bg = self.get_color("sidebar_bg")
        text_primary = self.get_color("text_primary")
        text_secondary = self.get_color("text_secondary")
        primary = self.get_color("primary")
        border_light = self.get_color("border_light")

        try:
            self.configure(bg=bg)
            self._divider.configure(bg=border_light)
            self._content.configure(bg=bg)
            self._header.configure(bg=bg)
            self._title_label.configure(bg=bg, fg=text_primary)
            self._status_label.configure(bg=bg, fg=text_secondary)
            self._steps_frame.configure(bg=bg)
            self._progress_label.configure(bg=bg, fg=primary)

            # 스텝 레이블 기본 색상 업데이트 (현재 상태 유지)
            for label in self._step_labels.values():
                label.configure(bg=bg)
        except Exception as e:
            logger.debug(f"SidebarProgressMini 테마 적용 실패: {e}")

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()


class SidebarContainer(tk.Frame, ThemedMixin):
    """
    사이드바 컨테이너 위젯
    좌측 메뉴 + 우측 컨텐츠 영역
    """

    def __init__(
        self,
        parent: tk.Widget,
        theme_manager: Optional[ThemeManager] = None,
        sidebar_width: int = 240,
        animation_duration: int = 250,
        gui=None,
        **kwargs
    ):
        self.__init_themed__(theme_manager)
        self._sidebar_width = sidebar_width
        self._animation_duration = animation_duration
        self._gui = gui

        kwargs['bg'] = self.get_color("bg_main")
        tk.Frame.__init__(self, parent, **kwargs)

        # 메뉴 데이터
        self._menus: Dict[str, Dict] = {}
        self._menu_order: List[str] = []
        self._current_menu: Optional[str] = None
        self._menu_items: Dict[str, SidebarMenuItem] = {}

        # 레이아웃 구성
        self._create_layout()

        # 컨텐츠 전환 애니메이션
        self._transition = TabTransition(self._content_frame, animation_duration)

    def _create_layout(self) -> None:
        """레이아웃 생성 (좌측 사이드바 + 우측 컨텐츠)"""
        # 사이드바 (좌측)
        self._sidebar_frame = tk.Frame(
            self,
            bg=self.get_color("sidebar_bg"),
            width=self._sidebar_width
        )
        self._sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)
        self._sidebar_frame.pack_propagate(False)

        # 사이드바 내부 패딩 (메뉴용)
        self._sidebar_inner = tk.Frame(
            self._sidebar_frame,
            bg=self.get_color("sidebar_bg")
        )
        self._sidebar_inner.pack(fill=tk.X, padx=8, pady=16)

        # 사이드바 하단 미니 진행 패널
        self._progress_mini = SidebarProgressMini(
            self._sidebar_frame,
            gui=self._gui,
            theme_manager=self._theme_manager
        )
        self._progress_mini.pack(side=tk.BOTTOM, fill=tk.X)

        # 사이드바 우측 구분선
        self._sidebar_border = tk.Frame(
            self,
            bg=self.get_color("border_light"),
            width=1
        )
        self._sidebar_border.pack(side=tk.LEFT, fill=tk.Y)

        # 컨텐츠 영역 (우측)
        self._content_frame = tk.Frame(self, bg=self.get_color("bg_main"))
        self._content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def add_menu_item(
        self,
        name: str,
        label: str,
        content_frame: tk.Frame,
        step_number: int,
        icon: str = "",
        select: bool = False
    ) -> None:
        """
        메뉴 항목 추가

        Args:
            name: 메뉴 식별자
            label: 표시 레이블
            content_frame: 메뉴 컨텐츠 프레임
            step_number: 단계 번호 (1, 2, 3...)
            icon: 아이콘 (이모지 또는 유니코드)
            select: 추가 후 선택 여부
        """
        if name in self._menus:
            return

        # 메뉴 데이터 저장
        self._menus[name] = {
            "label": label,
            "icon": icon,
            "step_number": step_number,
            "content": content_frame
        }
        self._menu_order.append(name)

        # 메뉴 아이템 생성
        item = SidebarMenuItem(
            self._sidebar_inner,
            text=label,
            step_number=step_number,
            icon=icon,
            theme_manager=self._theme_manager,
            command=lambda n=name: self.select_menu(n)
        )
        item.pack(fill=tk.X, pady=2)
        self._menu_items[name] = item

        # 첫 번째 메뉴이거나 select=True인 경우 선택
        if len(self._menus) == 1 or select:
            self.select_menu(name, animate=False)

    def remove_menu_item(self, name: str) -> None:
        """메뉴 항목 제거"""
        if name not in self._menus:
            return

        # 현재 메뉴면 다른 메뉴로 전환
        if self._current_menu == name:
            idx = self._menu_order.index(name)
            new_idx = idx - 1 if idx > 0 else (idx + 1 if idx < len(self._menu_order) - 1 else None)
            if new_idx is not None:
                self.select_menu(self._menu_order[new_idx], animate=False)

        # 정리
        self._menu_items[name].destroy()
        del self._menu_items[name]
        self._menus[name]["content"].place_forget()
        del self._menus[name]
        self._menu_order.remove(name)

    def select_menu(self, name: str, animate: bool = False) -> None:
        """
        메뉴 선택 (애니메이션 없이 즉시 전환)

        Args:
            name: 메뉴 식별자
            animate: 애니메이션 적용 여부 (기본값 False - 즉시 전환)
        """
        if name not in self._menus or name == self._current_menu:
            return

        old_frame = self._menus[self._current_menu]["content"] if self._current_menu else None
        new_frame = self._menus[name]["content"]

        # 메뉴 아이템 상태 업데이트
        for menu_name, item in self._menu_items.items():
            item.set_active(menu_name == name)

        # 컨텐츠 즉시 전환 (애니메이션 없음)
        self._transition.instant_switch(old_frame, new_frame)

        self._current_menu = name

    def mark_step_completed(self, name: str, completed: bool = True) -> None:
        """단계 완료 표시"""
        if name in self._menu_items:
            self._menu_items[name].set_completed(completed)

    def go_next(self) -> bool:
        """다음 단계로 이동. 성공 여부 반환."""
        if not self._current_menu:
            return False

        idx = self._menu_order.index(self._current_menu)
        if idx < len(self._menu_order) - 1:
            self.select_menu(self._menu_order[idx + 1])
            return True
        return False

    def go_prev(self) -> bool:
        """이전 단계로 이동. 성공 여부 반환."""
        if not self._current_menu:
            return False

        idx = self._menu_order.index(self._current_menu)
        if idx > 0:
            self.select_menu(self._menu_order[idx - 1])
            return True
        return False

    @property
    def current_menu(self) -> Optional[str]:
        """현재 선택된 메뉴"""
        return self._current_menu

    @property
    def menu_names(self) -> List[str]:
        """메뉴 이름 목록"""
        return self._menu_order.copy()

    @property
    def content_frame(self) -> tk.Frame:
        """컨텐츠 프레임 (메뉴 컨텐츠의 부모)"""
        return self._content_frame

    @property
    def sidebar_frame(self) -> tk.Frame:
        """사이드바 프레임"""
        return self._sidebar_frame

    @property
    def progress_mini(self) -> SidebarProgressMini:
        """미니 진행 패널 반환"""
        return self._progress_mini

    def apply_theme(self) -> None:
        """테마 적용"""
        self.configure(bg=self.get_color("bg_main"))
        self._sidebar_frame.configure(bg=self.get_color("sidebar_bg"))
        self._sidebar_inner.configure(bg=self.get_color("sidebar_bg"))
        self._sidebar_border.configure(bg=self.get_color("border_light"))
        self._content_frame.configure(bg=self.get_color("bg_main"))

        # 메뉴 아이템 테마 적용
        for item in self._menu_items.values():
            item.apply_theme()

        # 미니 진행 패널 테마 적용
        if hasattr(self, '_progress_mini'):
            self._progress_mini.apply_theme()

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()
