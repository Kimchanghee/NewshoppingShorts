"""
베이스 위젯 모듈
테마 지원 위젯을 위한 기본 클래스 및 믹스인
"""
import logging
import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, Any, Callable
from ..theme_manager import ThemeManager, get_theme_manager

logger = logging.getLogger(__name__)


class ThemedMixin:
    """
    테마 지원 믹스인 클래스
    Tkinter 위젯과 함께 사용하여 테마 기능 추가
    """

    def __init_themed__(self, theme_manager: Optional[ThemeManager] = None):
        """
        테마 믹스인 초기화

        Args:
            theme_manager: 테마 관리자 (None이면 전역 인스턴스 사용)
        """
        self._theme_manager = theme_manager or get_theme_manager()
        self._theme_manager.register_observer(self._on_theme_changed)
        self._themed_children: list = []

    def get_color(self, key: str) -> str:
        """
        현재 테마의 색상 가져오기

        Args:
            key: 색상 키 (예: "primary", "bg_main")

        Returns:
            색상 코드
        """
        return self._theme_manager.get_color(key)

    @property
    def theme_manager(self) -> ThemeManager:
        """테마 관리자 반환"""
        return self._theme_manager

    @property
    def is_dark_mode(self) -> bool:
        """다크 모드 여부"""
        return self._theme_manager.is_dark_mode

    def _on_theme_changed(self, new_theme: str) -> None:
        """
        테마 변경 시 호출됨
        서브클래스에서 오버라이드하여 UI 업데이트

        Args:
            new_theme: 새 테마 이름 ("light" 또는 "dark")
        """
        self.apply_theme()

    def apply_theme(self) -> None:
        """
        테마 적용
        서브클래스에서 오버라이드하여 구현
        """
        pass

    def register_themed_child(self, child: 'ThemedMixin') -> None:
        """
        테마 변경을 전파받을 자식 위젯 등록

        Args:
            child: 테마 지원 자식 위젯
        """
        if child not in self._themed_children:
            self._themed_children.append(child)

    def unregister_themed_child(self, child: 'ThemedMixin') -> None:
        """
        자식 위젯 등록 해제

        Args:
            child: 해제할 자식 위젯
        """
        if child in self._themed_children:
            self._themed_children.remove(child)

    def cleanup_theme(self) -> None:
        """
        테마 관련 리소스 정리
        위젯 파괴 시 호출
        """
        try:
            self._theme_manager.unregister_observer(self._on_theme_changed)
        except (AttributeError, ValueError):
            pass


class ThemedFrame(tk.Frame, ThemedMixin):
    """테마 지원 프레임"""

    def __init__(
        self,
        parent: tk.Widget,
        theme_manager: Optional[ThemeManager] = None,
        bg_key: str = "bg_card",
        **kwargs
    ):
        """
        Args:
            parent: 부모 위젯
            theme_manager: 테마 관리자
            bg_key: 배경색 키
            **kwargs: Frame에 전달할 추가 인자
        """
        self._bg_key = bg_key
        self.__init_themed__(theme_manager)

        # 배경색 설정
        kwargs['bg'] = self.get_color(bg_key)
        tk.Frame.__init__(self, parent, **kwargs)

    def apply_theme(self) -> None:
        """테마 적용"""
        self.configure(bg=self.get_color(self._bg_key))

        # 자식 위젯들에게 전파
        for child in self._themed_children:
            try:
                child.apply_theme()
            except (tk.TclError, AttributeError) as e:
                logger.debug("Failed to apply theme to child widget: %s", e)

    def destroy(self) -> None:
        """위젯 파괴 시 정리"""
        self.cleanup_theme()
        super().destroy()


class ThemedLabel(tk.Label, ThemedMixin):
    """테마 지원 레이블"""

    def __init__(
        self,
        parent: tk.Widget,
        theme_manager: Optional[ThemeManager] = None,
        bg_key: str = "bg_card",
        fg_key: str = "text_primary",
        **kwargs
    ):
        """
        Args:
            parent: 부모 위젯
            theme_manager: 테마 관리자
            bg_key: 배경색 키
            fg_key: 전경색(텍스트) 키
            **kwargs: Label에 전달할 추가 인자
        """
        self._bg_key = bg_key
        self._fg_key = fg_key
        self.__init_themed__(theme_manager)

        kwargs['bg'] = self.get_color(bg_key)
        kwargs['fg'] = self.get_color(fg_key)
        tk.Label.__init__(self, parent, **kwargs)

    def apply_theme(self) -> None:
        """테마 적용"""
        self.configure(
            bg=self.get_color(self._bg_key),
            fg=self.get_color(self._fg_key)
        )

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()


class ThemedButton(tk.Button, ThemedMixin):
    """테마 지원 버튼"""

    def __init__(
        self,
        parent: tk.Widget,
        theme_manager: Optional[ThemeManager] = None,
        style: str = "primary",  # "primary", "secondary", "text"
        **kwargs
    ):
        """
        Args:
            parent: 부모 위젯
            theme_manager: 테마 관리자
            style: 버튼 스타일
            **kwargs: Button에 전달할 추가 인자
        """
        self._style = style
        self.__init_themed__(theme_manager)

        self._apply_style(kwargs)
        tk.Button.__init__(self, parent, **kwargs)

        # 호버 이벤트 바인딩
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)

    def _apply_style(self, kwargs: Dict[str, Any]) -> None:
        """스타일에 따른 색상 적용"""
        if self._style == "primary":
            kwargs['bg'] = self.get_color("primary")
            kwargs['fg'] = self.get_color("primary_text")
            kwargs['activebackground'] = self.get_color("primary_hover")
            kwargs['activeforeground'] = self.get_color("primary_text")
        elif self._style == "secondary":
            kwargs['bg'] = self.get_color("bg_secondary")
            kwargs['fg'] = self.get_color("text_primary")
            kwargs['activebackground'] = self.get_color("bg_hover")
            kwargs['activeforeground'] = self.get_color("text_primary")
        else:  # text
            kwargs['bg'] = self.get_color("bg_card")
            kwargs['fg'] = self.get_color("primary")
            kwargs['activebackground'] = self.get_color("bg_hover")
            kwargs['activeforeground'] = self.get_color("primary")

        kwargs.setdefault('relief', 'flat')
        kwargs.setdefault('borderwidth', 0)
        kwargs.setdefault('cursor', 'hand2')

    def _on_enter(self, event=None):
        """마우스 진입 시"""
        if self._style == "primary":
            self.configure(bg=self.get_color("primary_hover"))
        else:
            self.configure(bg=self.get_color("bg_hover"))

    def _on_leave(self, event=None):
        """마우스 이탈 시"""
        if self._style == "primary":
            self.configure(bg=self.get_color("primary"))
        elif self._style == "secondary":
            self.configure(bg=self.get_color("bg_secondary"))
        else:
            self.configure(bg=self.get_color("bg_card"))

    def apply_theme(self) -> None:
        """테마 적용"""
        if self._style == "primary":
            self.configure(
                bg=self.get_color("primary"),
                fg=self.get_color("primary_text"),
                activebackground=self.get_color("primary_hover"),
                activeforeground=self.get_color("primary_text")
            )
        elif self._style == "secondary":
            self.configure(
                bg=self.get_color("bg_secondary"),
                fg=self.get_color("text_primary"),
                activebackground=self.get_color("bg_hover"),
                activeforeground=self.get_color("text_primary")
            )
        else:
            self.configure(
                bg=self.get_color("bg_card"),
                fg=self.get_color("primary"),
                activebackground=self.get_color("bg_hover"),
                activeforeground=self.get_color("primary")
            )

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()


class ThemedEntry(tk.Entry, ThemedMixin):
    """테마 지원 입력 필드"""

    def __init__(
        self,
        parent: tk.Widget,
        theme_manager: Optional[ThemeManager] = None,
        **kwargs
    ):
        self.__init_themed__(theme_manager)

        kwargs['bg'] = self.get_color("bg_input")
        kwargs['fg'] = self.get_color("text_primary")
        kwargs['insertbackground'] = self.get_color("text_primary")
        kwargs.setdefault('relief', 'flat')
        kwargs.setdefault('highlightthickness', 1)
        kwargs['highlightbackground'] = self.get_color("border_light")
        kwargs['highlightcolor'] = self.get_color("border_focus")

        tk.Entry.__init__(self, parent, **kwargs)

    def apply_theme(self) -> None:
        self.configure(
            bg=self.get_color("bg_input"),
            fg=self.get_color("text_primary"),
            insertbackground=self.get_color("text_primary"),
            highlightbackground=self.get_color("border_light"),
            highlightcolor=self.get_color("border_focus")
        )

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()


class ThemedText(tk.Text, ThemedMixin):
    """테마 지원 텍스트 영역"""

    def __init__(
        self,
        parent: tk.Widget,
        theme_manager: Optional[ThemeManager] = None,
        **kwargs
    ):
        self.__init_themed__(theme_manager)

        kwargs['bg'] = self.get_color("bg_input")
        kwargs['fg'] = self.get_color("text_primary")
        kwargs['insertbackground'] = self.get_color("text_primary")
        kwargs.setdefault('relief', 'flat')
        kwargs.setdefault('highlightthickness', 1)
        kwargs['highlightbackground'] = self.get_color("border_light")
        kwargs['highlightcolor'] = self.get_color("border_focus")

        tk.Text.__init__(self, parent, **kwargs)

    def apply_theme(self) -> None:
        self.configure(
            bg=self.get_color("bg_input"),
            fg=self.get_color("text_primary"),
            insertbackground=self.get_color("text_primary"),
            highlightbackground=self.get_color("border_light"),
            highlightcolor=self.get_color("border_focus")
        )

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()


class ThemedCanvas(tk.Canvas, ThemedMixin):
    """테마 지원 캔버스"""

    def __init__(
        self,
        parent: tk.Widget,
        theme_manager: Optional[ThemeManager] = None,
        bg_key: str = "bg_card",
        **kwargs
    ):
        self._bg_key = bg_key
        self.__init_themed__(theme_manager)

        kwargs['bg'] = self.get_color(bg_key)
        kwargs.setdefault('highlightthickness', 0)

        tk.Canvas.__init__(self, parent, **kwargs)

    def apply_theme(self) -> None:
        self.configure(bg=self.get_color(self._bg_key))

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()


class ThemedCheckbutton(tk.Checkbutton, ThemedMixin):
    """테마 지원 체크박스"""

    def __init__(
        self,
        parent: tk.Widget,
        theme_manager: Optional[ThemeManager] = None,
        bg_key: str = "bg_card",
        **kwargs
    ):
        self._bg_key = bg_key
        self.__init_themed__(theme_manager)

        kwargs['bg'] = self.get_color(bg_key)
        kwargs['fg'] = self.get_color("text_primary")
        kwargs['activebackground'] = self.get_color(bg_key)
        kwargs['activeforeground'] = self.get_color("text_primary")
        kwargs['selectcolor'] = self.get_color("bg_input")
        kwargs.setdefault('relief', 'flat')
        kwargs.setdefault('borderwidth', 0)

        tk.Checkbutton.__init__(self, parent, **kwargs)

    def apply_theme(self) -> None:
        self.configure(
            bg=self.get_color(self._bg_key),
            fg=self.get_color("text_primary"),
            activebackground=self.get_color(self._bg_key),
            activeforeground=self.get_color("text_primary"),
            selectcolor=self.get_color("bg_input")
        )

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()


class ThemedRadiobutton(tk.Radiobutton, ThemedMixin):
    """테마 지원 라디오 버튼"""

    def __init__(
        self,
        parent: tk.Widget,
        theme_manager: Optional[ThemeManager] = None,
        bg_key: str = "bg_card",
        **kwargs
    ):
        self._bg_key = bg_key
        self.__init_themed__(theme_manager)

        kwargs['bg'] = self.get_color(bg_key)
        kwargs['fg'] = self.get_color("text_primary")
        kwargs['activebackground'] = self.get_color(bg_key)
        kwargs['activeforeground'] = self.get_color("text_primary")
        kwargs['selectcolor'] = self.get_color("primary")
        kwargs.setdefault('relief', 'flat')
        kwargs.setdefault('borderwidth', 0)

        tk.Radiobutton.__init__(self, parent, **kwargs)

    def apply_theme(self) -> None:
        self.configure(
            bg=self.get_color(self._bg_key),
            fg=self.get_color("text_primary"),
            activebackground=self.get_color(self._bg_key),
            activeforeground=self.get_color("text_primary"),
            selectcolor=self.get_color("primary")
        )

    def destroy(self) -> None:
        self.cleanup_theme()
        super().destroy()


def configure_ttk_styles(theme_manager: Optional[ThemeManager] = None) -> None:
    """
    ttk 위젯 스타일 설정

    Args:
        theme_manager: 테마 관리자
    """
    tm = theme_manager or get_theme_manager()
    style = ttk.Style()

    # Treeview 스타일
    style.configure(
        "Themed.Treeview",
        background=tm.get_color("bg_card"),
        foreground=tm.get_color("text_primary"),
        fieldbackground=tm.get_color("bg_card"),
        borderwidth=0
    )
    style.configure(
        "Themed.Treeview.Heading",
        background=tm.get_color("bg_secondary"),
        foreground=tm.get_color("text_primary"),
        borderwidth=0
    )
    style.map(
        "Themed.Treeview",
        background=[("selected", tm.get_color("bg_selected"))],
        foreground=[("selected", tm.get_color("text_primary"))]
    )

    # Scrollbar 스타일
    style.configure(
        "Themed.Vertical.TScrollbar",
        background=tm.get_color("scrollbar_thumb"),
        troughcolor=tm.get_color("scrollbar_bg"),
        borderwidth=0,
        arrowsize=0
    )
    style.configure(
        "Themed.Horizontal.TScrollbar",
        background=tm.get_color("scrollbar_thumb"),
        troughcolor=tm.get_color("scrollbar_bg"),
        borderwidth=0,
        arrowsize=0
    )

    # Progressbar 스타일
    style.configure(
        "Themed.Horizontal.TProgressbar",
        background=tm.get_color("progress_fill"),
        troughcolor=tm.get_color("progress_bg"),
        borderwidth=0,
        thickness=8
    )

    # Combobox 스타일
    style.configure(
        "Themed.TCombobox",
        fieldbackground=tm.get_color("bg_input"),
        background=tm.get_color("bg_input"),
        foreground=tm.get_color("text_primary"),
        arrowcolor=tm.get_color("text_secondary"),
        borderwidth=1,
        relief="flat"
    )
    style.map(
        "Themed.TCombobox",
        fieldbackground=[("readonly", tm.get_color("bg_input"))],
        background=[("readonly", tm.get_color("bg_input"))]
    )
