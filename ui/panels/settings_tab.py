"""
설정 탭 패널
URL 입력, API 관리, 저장 폴더 설정을 포함
"""
import logging
import tkinter as tk
from tkinter import ttk
import os
import subprocess
import sys
from typing import Optional
from ..components.base_widget import ThemedMixin
from ..components.rounded_widgets import create_rounded_button
from ..components.tab_container import TabContent
from ..theme_manager import ThemeManager, get_theme_manager

logger = logging.getLogger(__name__)


class SettingsTab(TabContent):
    """설정 탭 - URL 입력, API 관리, 저장 폴더"""

    def __init__(self, parent: tk.Widget, gui, theme_manager: Optional[ThemeManager] = None):
        """
        Args:
            parent: 부모 위젯 (TabContainer의 컨텐츠 영역)
            gui: VideoAnalyzerGUI 인스턴스
            theme_manager: 테마 관리자
        """
        self.gui = gui
        super().__init__(parent, theme_manager=theme_manager, padding=(20, 16))

        self._create_widgets()

    def _create_widgets(self) -> None:
        """위젯 생성"""
        # 스크롤 가능한 컨테이너
        canvas = tk.Canvas(
            self.inner,
            bg=self.get_color("bg_main"),
            highlightthickness=0
        )
        scrollbar = ttk.Scrollbar(
            self.inner,
            orient="vertical",
            command=canvas.yview,
            style="Themed.Vertical.TScrollbar"
        )
        self._scrollable_frame = tk.Frame(canvas, bg=self.get_color("bg_main"))

        self._scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self._scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 마우스 휠 스크롤
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # URL 입력 섹션
        self._create_url_section()

        # API 관리 섹션
        self._create_api_section()

        # 저장 폴더 섹션
        self._create_folder_section()

    def _create_url_section(self) -> None:
        """URL 입력 섹션"""
        section = tk.Frame(self._scrollable_frame, bg=self.get_color("bg_card"))
        section.pack(fill=tk.X, pady=(0, 16))

        # 섹션 헤더
        header = tk.Frame(section, bg=self.get_color("bg_secondary"))
        header.pack(fill=tk.X)

        tk.Label(
            header,
            text="URL 입력",
            font=("맑은 고딕", 12, "bold"),
            bg=self.get_color("bg_secondary"),
            fg=self.get_color("text_primary"),
            padx=16,
            pady=12
        ).pack(side=tk.LEFT)

        # 컨텐츠
        content = tk.Frame(section, bg=self.get_color("bg_card"))
        content.pack(fill=tk.X, padx=16, pady=16)

        # 설명
        tk.Label(
            content,
            text="TikTok/Douyin URL을 입력하세요. 여러 개의 URL을 한 번에 붙여넣을 수 있습니다.",
            font=("맑은 고딕", 9),
            bg=self.get_color("bg_card"),
            fg=self.get_color("text_secondary"),
            anchor="w"
        ).pack(fill=tk.X, pady=(0, 8))

        # URL 입력 텍스트 영역
        text_frame = tk.Frame(content, bg=self.get_color("bg_card"))
        text_frame.pack(fill=tk.X, pady=(0, 12))

        self.url_entry = tk.Text(
            text_frame,
            height=3,
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
        self.url_entry.pack(fill=tk.X)
        # 호환성을 위해 gui에도 참조 설정
        self.gui.url_entry = self.url_entry
        self.url_entry.bind("<Return>", self.gui.add_url_from_entry)
        self.url_entry.bind("<Control-Return>", self.gui.add_url_from_entry)
        self.url_entry.bind("<Control-v>", self.gui.paste_and_extract)

        # 예시 텍스트
        tk.Label(
            content,
            text="예: https://www.tiktok.com/@user/video/... 또는 https://v.douyin.com/...",
            font=("맑은 고딕", 9),
            bg=self.get_color("bg_card"),
            fg=self.get_color("text_disabled"),
            anchor="w"
        ).pack(fill=tk.X, pady=(0, 12))

        # 버튼 영역
        btn_frame = tk.Frame(content, bg=self.get_color("bg_card"))
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

    def _create_api_section(self) -> None:
        """API 관리 섹션"""
        section = tk.Frame(self._scrollable_frame, bg=self.get_color("bg_card"))
        section.pack(fill=tk.X, pady=(0, 16))

        # 섹션 헤더
        header = tk.Frame(section, bg=self.get_color("bg_secondary"))
        header.pack(fill=tk.X)

        tk.Label(
            header,
            text="API 설정",
            font=("맑은 고딕", 12, "bold"),
            bg=self.get_color("bg_secondary"),
            fg=self.get_color("text_primary"),
            padx=16,
            pady=12
        ).pack(side=tk.LEFT)

        # 컨텐츠
        content = tk.Frame(section, bg=self.get_color("bg_card"))
        content.pack(fill=tk.X, padx=16, pady=16)

        # 설명
        tk.Label(
            content,
            text="Google Gemini API 키가 필요합니다. 여러 개의 API 키를 등록하면 부하가 분산됩니다.",
            font=("맑은 고딕", 9),
            bg=self.get_color("bg_card"),
            fg=self.get_color("text_secondary"),
            anchor="w"
        ).pack(fill=tk.X, pady=(0, 12))

        # 버튼 영역
        btn_frame = tk.Frame(content, bg=self.get_color("bg_card"))
        btn_frame.pack(fill=tk.X)

        # API 키 관리 버튼
        api_btn = create_rounded_button(
            btn_frame,
            text="API 키 관리",
            command=self.gui.show_api_key_manager,
            style="primary",
            theme_manager=self._theme_manager
        )
        api_btn.pack(side=tk.LEFT)

        # API 상태 확인 버튼
        status_btn = create_rounded_button(
            btn_frame,
            text="API 상태 확인",
            command=self.gui.show_api_status,
            style="outline",
            theme_manager=self._theme_manager
        )
        status_btn.pack(side=tk.LEFT, padx=(8, 0))

        # API 상태 표시
        self._api_status_label = tk.Label(
            btn_frame,
            text="",
            font=("맑은 고딕", 9),
            bg=self.get_color("bg_card"),
            fg=self.get_color("success")
        )
        self._api_status_label.pack(side=tk.RIGHT)

    def _create_folder_section(self) -> None:
        """저장 폴더 섹션"""
        section = tk.Frame(self._scrollable_frame, bg=self.get_color("bg_card"))
        section.pack(fill=tk.X, pady=(0, 16))

        # 섹션 헤더
        header = tk.Frame(section, bg=self.get_color("bg_secondary"))
        header.pack(fill=tk.X)

        tk.Label(
            header,
            text="저장 위치",
            font=("맑은 고딕", 12, "bold"),
            bg=self.get_color("bg_secondary"),
            fg=self.get_color("text_primary"),
            padx=16,
            pady=12
        ).pack(side=tk.LEFT)

        # 컨텐츠
        content = tk.Frame(section, bg=self.get_color("bg_card"))
        content.pack(fill=tk.X, padx=16, pady=16)

        # 현재 경로 표시
        path_frame = tk.Frame(content, bg=self.get_color("bg_card"))
        path_frame.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            path_frame,
            text="현재 저장 폴더:",
            font=("맑은 고딕", 9, "bold"),
            bg=self.get_color("bg_card"),
            fg=self.get_color("text_primary")
        ).pack(side=tk.LEFT)

        self.gui.output_folder_label = tk.Label(
            path_frame,
            textvariable=self.gui.output_folder_var,
            font=("맑은 고딕", 9),
            bg=self.get_color("bg_card"),
            fg=self.get_color("text_secondary"),
            anchor="w"
        )
        self.gui.output_folder_label.pack(side=tk.LEFT, padx=(8, 0), fill=tk.X, expand=True)

        # 버튼 영역
        btn_frame = tk.Frame(content, bg=self.get_color("bg_card"))
        btn_frame.pack(fill=tk.X)

        # 폴더 선택 버튼
        self.gui.output_folder_button = create_rounded_button(
            btn_frame,
            text="폴더 선택",
            command=self.gui.select_output_folder,
            style="primary",
            theme_manager=self._theme_manager
        )
        self.gui.output_folder_button.pack(side=tk.LEFT)

        # 폴더 열기 버튼
        open_btn = create_rounded_button(
            btn_frame,
            text="폴더 열기",
            command=self._open_output_folder,
            style="secondary",
            theme_manager=self._theme_manager
        )
        open_btn.pack(side=tk.LEFT, padx=(8, 0))

    def _open_output_folder(self) -> None:
        """저장 폴더를 파일 탐색기에서 열기"""
        output_path = getattr(self.gui, 'output_folder_path', None)
        if not output_path:
            output_path = os.path.join(os.getcwd(), "outputs")

        os.makedirs(output_path, exist_ok=True)

        try:
            if sys.platform == 'win32':
                os.startfile(output_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', output_path], timeout=10)
            else:
                subprocess.run(['xdg-open', output_path], timeout=10)
        except subprocess.TimeoutExpired:
            logger.warning("Folder open command timed out")
        except Exception as e:
            logger.error(f"Failed to open folder: {e}")

    def update_url_count(self, count: int) -> None:
        """URL 개수 업데이트"""
        self._url_count_label.configure(text=f"URL: {count}/30")

    def update_api_status(self, status: str, is_ok: bool = True) -> None:
        """API 상태 업데이트"""
        color = self.get_color("success") if is_ok else self.get_color("error")
        self._api_status_label.configure(text=status, fg=color)

    def apply_theme(self) -> None:
        """테마 적용"""
        super().apply_theme()
        self._scrollable_frame.configure(bg=self.get_color("bg_main"))

        # URL 입력 필드 테마 적용
        if hasattr(self, 'url_entry'):
            try:
                self.url_entry.configure(
                    bg=self.get_color("bg_input"),
                    fg=self.get_color("text_primary"),
                    highlightbackground=self.get_color("border_light"),
                    highlightcolor=self.get_color("border_focus"),
                    insertbackground=self.get_color("primary")
                )
            except Exception as e:
                logger.debug("Failed to apply theme to URL entry: %s", e)

        # URL 개수 레이블 테마 적용
        if hasattr(self, '_url_count_label'):
            try:
                self._url_count_label.configure(
                    bg=self.get_color("bg_card"),
                    fg=self.get_color("text_secondary")
                )
            except Exception as e:
                logger.debug("Failed to apply theme to URL count label: %s", e)

        # API 상태 레이블 테마 적용
        if hasattr(self, '_api_status_label'):
            try:
                self._api_status_label.configure(bg=self.get_color("bg_card"))
            except Exception as e:
                logger.debug("Failed to apply theme to API status label: %s", e)

    def destroy(self) -> None:
        """위젯 정리 및 파괴"""
        # 마우스 휠 바인딩 해제
        try:
            self.unbind_all("<MouseWheel>")
        except Exception as e:
            logger.debug("Failed to unbind mousewheel in SettingsTab: %s", e)
        super().destroy()
