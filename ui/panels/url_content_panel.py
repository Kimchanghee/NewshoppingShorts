"""
URL 입력 컨텐츠 패널 (1단계)
URL 입력 영역만 포함 (API/폴더 설정은 모달로 분리)
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional
from ..components.base_widget import ThemedMixin
from ..components.tab_container import TabContent
from ..components.rounded_widgets import create_rounded_button
from ..theme_manager import ThemeManager, get_theme_manager


class URLContentPanel(TabContent):
    """URL 입력 패널 - 1단계"""

    def __init__(self, parent: tk.Widget, gui, theme_manager: Optional[ThemeManager] = None):
        """
        Args:
            parent: 부모 위젯
            gui: VideoAnalyzerGUI 인스턴스
            theme_manager: 테마 관리자
        """
        self.gui = gui
        super().__init__(parent, theme_manager=theme_manager, padding=(24, 20))

        self._create_widgets()

    def _create_widgets(self) -> None:
        """위젯 생성"""
        # 단계 헤더
        self._create_step_header()

        # URL 입력 카드
        self._create_url_card()

        # 안내 카드
        self._create_guide_card()

    def _create_step_header(self) -> None:
        """단계 헤더 생성"""
        header_frame = tk.Frame(self.inner, bg=self.get_color("bg_main"))
        header_frame.pack(fill=tk.X, pady=(0, 20))

        # 단계 배지
        badge = tk.Frame(header_frame, bg=self.get_color("primary"), padx=12, pady=4)
        badge.pack(side=tk.LEFT)

        tk.Label(
            badge,
            text="STEP 1",
            font=("맑은 고딕", 9, "bold"),
            bg=self.get_color("primary"),
            fg=self.get_color("primary_text")
        ).pack()

        # 제목
        tk.Label(
            header_frame,
            text="URL 입력",
            font=("맑은 고딕", 18, "bold"),
            bg=self.get_color("bg_main"),
            fg=self.get_color("text_primary")
        ).pack(side=tk.LEFT, padx=(12, 0))

    def _create_url_card(self) -> None:
        """URL 입력 카드 생성"""
        card = tk.Frame(
            self.inner,
            bg=self.get_color("bg_card"),
            highlightbackground=self.get_color("border_light"),
            highlightthickness=1
        )
        card.pack(fill=tk.BOTH, expand=True, pady=(0, 16))

        # 카드 내부 패딩
        card_inner = tk.Frame(card, bg=self.get_color("bg_card"))
        card_inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 설명
        tk.Label(
            card_inner,
            text="TikTok / Douyin URL을 입력하세요",
            font=("맑은 고딕", 11, "bold"),
            bg=self.get_color("bg_card"),
            fg=self.get_color("text_primary"),
            anchor="w"
        ).pack(fill=tk.X)

        tk.Label(
            card_inner,
            text="여러 개의 URL을 한 번에 붙여넣을 수 있습니다. (최대 30개)",
            font=("맑은 고딕", 9),
            bg=self.get_color("bg_card"),
            fg=self.get_color("text_secondary"),
            anchor="w"
        ).pack(fill=tk.X, pady=(4, 12))

        # URL 입력 텍스트 영역
        text_frame = tk.Frame(card_inner, bg=self.get_color("bg_card"))
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        self.url_entry = tk.Text(
            text_frame,
            height=6,
            wrap=tk.WORD,
            font=("맑은 고딕", 10),
            bg=self.get_color("bg_input"),
            fg=self.get_color("text_primary"),
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.get_color("border_light"),
            highlightcolor=self.get_color("border_focus"),
            insertbackground=self.get_color("primary")
        )
        self.url_entry.pack(fill=tk.BOTH, expand=True)

        # 호환성을 위해 gui에도 참조 설정
        self.gui.url_entry = self.url_entry
        add_url_method = getattr(self.gui, 'add_url_from_entry', None)
        if add_url_method is not None:
            self.url_entry.bind("<Return>", add_url_method)
            self.url_entry.bind("<Control-Return>", add_url_method)
        paste_method = getattr(self.gui, 'paste_and_extract', None)
        if paste_method is not None:
            self.url_entry.bind("<Control-v>", paste_method)

        # 예시 텍스트
        tk.Label(
            card_inner,
            text="예: https://v.douyin.com/xxxxx/ 또는 https://vm.tiktok.com/xxxxx/",
            font=("맑은 고딕", 9),
            bg=self.get_color("bg_card"),
            fg=self.get_color("text_disabled"),
            anchor="w"
        ).pack(fill=tk.X, pady=(0, 16))

        # 버튼 영역
        btn_frame = tk.Frame(card_inner, bg=self.get_color("bg_card"))
        btn_frame.pack(fill=tk.X)

        # URL 추가 버튼
        url_add_btn = create_rounded_button(
            btn_frame,
            text="URL 추가",
            command=self.gui.add_url_from_entry,
            style="primary",
            theme_manager=self._theme_manager
        )
        url_add_btn.pack(side=tk.LEFT)

        # 클립보드 추가 버튼
        clipboard_btn = create_rounded_button(
            btn_frame,
            text="클립보드에서 추가",
            command=lambda: self.gui.paste_and_extract(),
            style="secondary",
            theme_manager=self._theme_manager
        )
        clipboard_btn.pack(side=tk.LEFT, padx=(8, 0))

        # URL 개수 표시
        self._url_count_label = tk.Label(
            btn_frame,
            text="URL: 0/30",
            font=("맑은 고딕", 9),
            bg=self.get_color("bg_card"),
            fg=self.get_color("text_secondary")
        )
        self._url_count_label.pack(side=tk.RIGHT)

    def _create_guide_card(self) -> None:
        """안내 카드 생성"""
        card = tk.Frame(
            self.inner,
            bg=self.get_color("info_bg"),
            highlightbackground=self.get_color("info"),
            highlightthickness=1
        )
        card.pack(fill=tk.X)

        card_inner = tk.Frame(card, bg=self.get_color("info_bg"))
        card_inner.pack(fill=tk.X, padx=16, pady=12)

        # 아이콘 + 텍스트
        info_frame = tk.Frame(card_inner, bg=self.get_color("info_bg"))
        info_frame.pack(fill=tk.X)

        tk.Label(
            info_frame,
            text="i",
            font=("맑은 고딕", 11, "bold"),
            bg=self.get_color("info"),
            fg="#FFFFFF",
            width=2,
            height=1
        ).pack(side=tk.LEFT)

        tk.Label(
            info_frame,
            text="URL 추가 후 '스타일' 단계에서 음성과 폰트를 선택하세요",
            font=("맑은 고딕", 10),
            bg=self.get_color("info_bg"),
            fg=self.get_color("info"),
            anchor="w"
        ).pack(side=tk.LEFT, padx=(10, 0))

        # 다음 단계 버튼
        next_btn = create_rounded_button(
            info_frame,
            text="다음: 스타일 선택",
            command=self._go_next_step,
            style="outline",
            theme_manager=self._theme_manager
        )
        next_btn.pack(side=tk.RIGHT)

    def _go_next_step(self) -> None:
        """다음 단계로 이동"""
        sidebar = getattr(self.gui, 'sidebar_container', None)
        if sidebar is not None:
            sidebar.go_next()

    def update_url_count(self, count: int) -> None:
        """URL 개수 업데이트"""
        self._url_count_label.configure(text=f"URL: {count}/30")

    def apply_theme(self) -> None:
        """테마 적용"""
        super().apply_theme()

        # URL 입력 필드 테마 적용
        if hasattr(self, 'url_entry'):
            self.url_entry.configure(
                bg=self.get_color("bg_input"),
                fg=self.get_color("text_primary"),
                highlightbackground=self.get_color("border_light"),
                highlightcolor=self.get_color("border_focus"),
                insertbackground=self.get_color("primary")
            )
