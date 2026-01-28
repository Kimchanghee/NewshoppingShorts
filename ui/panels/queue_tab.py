"""
작업 탭 패널
큐 관리만 포함 (제작 진행 상황은 사이드바 하단에 표시)
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional
from ..components.base_widget import ThemedMixin
from ..components.tab_container import TabContent
from ..theme_manager import ThemeManager, get_theme_manager

# 기존 패널 임포트
from .queue_panel import QueuePanel


class QueueTab(TabContent):
    """작업 탭 - 큐 관리 (진행 상황은 사이드바에 표시)"""

    def __init__(self, parent: tk.Widget, gui, theme_manager: Optional[ThemeManager] = None):
        """
        Args:
            parent: 부모 위젯 (TabContainer의 컨텐츠 영역)
            gui: VideoAnalyzerGUI 인스턴스
            theme_manager: 테마 관리자
        """
        self.gui = gui
        super().__init__(parent, theme_manager=theme_manager, padding=(16, 12))

        self._create_widgets()

    def _create_widgets(self) -> None:
        """위젯 생성 - 큐 패널만 전체 너비로 표시"""
        # 전체 너비 사용
        self.inner.columnconfigure(0, weight=1)
        self.inner.rowconfigure(0, weight=1)

        # 큐 관리 섹션
        self._queue_section = tk.Frame(self.inner, bg=self.get_color("bg_main"))
        self._queue_section.grid(row=0, column=0, sticky="nsew")

        # 큐 헤더
        self._queue_header = tk.Frame(self._queue_section, bg=self.get_color("bg_secondary"))
        self._queue_header.pack(fill=tk.X)

        self._queue_title = tk.Label(
            self._queue_header,
            text="제작 대기열",
            font=("맑은 고딕", 12, "bold"),
            bg=self.get_color("bg_secondary"),
            fg=self.get_color("text_primary"),
            padx=16,
            pady=10
        )
        self._queue_title.pack(side=tk.LEFT)

        # 대기열 통계
        self._queue_stats = tk.Label(
            self._queue_header,
            text="대기 0 | 완료 0 | 실패 0",
            font=("맑은 고딕", 9),
            bg=self.get_color("bg_secondary"),
            fg=self.get_color("text_secondary"),
            padx=16
        )
        self._queue_stats.pack(side=tk.RIGHT)

        # 큐 패널 컨테이너
        self._queue_container = tk.Frame(self._queue_section, bg=self.get_color("bg_card"))
        self._queue_container.pack(fill=tk.BOTH, expand=True)

        self.queue_panel = QueuePanel(self._queue_container, self.gui, theme_manager=self._theme_manager)
        self.queue_panel.pack(fill=tk.BOTH, expand=True)

        # progress_panel 참조 (호환성 유지 - 실제로는 사이드바에서 표시)
        self.progress_panel = None

    def update_queue_stats(self, waiting: int, completed: int, failed: int) -> None:
        """
        대기열 통계 업데이트

        Args:
            waiting: 대기 중인 작업 수
            completed: 완료된 작업 수
            failed: 실패한 작업 수
        """
        self._queue_stats.configure(
            text=f"대기 {waiting} | 완료 {completed} | 실패 {failed}"
        )

    def apply_theme(self) -> None:
        """테마 적용 - 하위 패널들에 테마 전파"""
        super().apply_theme()

        # 현재 테마 색상 가져오기
        bg_main = self.get_color("bg_main")
        bg_secondary = self.get_color("bg_secondary")
        bg_card = self.get_color("bg_card")
        text_primary = self.get_color("text_primary")
        text_secondary = self.get_color("text_secondary")

        # 큐 섹션 배경색 업데이트
        if hasattr(self, '_queue_section'):
            try:
                self._queue_section.configure(bg=bg_main)
            except tk.TclError:
                pass  # 위젯이 파괴된 경우

        # 큐 헤더 배경색 업데이트
        if hasattr(self, '_queue_header'):
            try:
                self._queue_header.configure(bg=bg_secondary)
            except tk.TclError:
                pass

        # 큐 타이틀 레이블 업데이트
        if hasattr(self, '_queue_title'):
            try:
                self._queue_title.configure(bg=bg_secondary, fg=text_primary)
            except tk.TclError:
                pass

        # 대기열 통계 레이블 업데이트
        if hasattr(self, '_queue_stats'):
            try:
                self._queue_stats.configure(bg=bg_secondary, fg=text_secondary)
            except tk.TclError:
                pass

        # 큐 컨테이너 배경색 업데이트 (중요: bg_card 사용)
        if hasattr(self, '_queue_container'):
            try:
                self._queue_container.configure(bg=bg_card)
            except tk.TclError:
                pass

        # 하위 패널들에 테마 전파
        if hasattr(self, 'queue_panel') and hasattr(self.queue_panel, 'apply_theme'):
            self.queue_panel.apply_theme()
