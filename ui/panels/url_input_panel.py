"""
URL input panel for entering and managing video URLs
"""
import logging
import tkinter as tk
from tkinter import ttk
from typing import Optional

from ui.components.rounded_widgets import RoundedButton, create_rounded_button
from ui.components.base_widget import ThemedMixin
from ui.theme_manager import ThemeManager, get_theme_manager

logger = logging.getLogger(__name__)


class URLInputPanel(tk.Frame, ThemedMixin):
    """URL input panel with URL text area and folder selection"""

    def __init__(self, parent, gui, theme_manager: Optional[ThemeManager] = None):
        """
        Initialize the URL input panel.

        Args:
            parent: Parent tkinter widget
            gui: VideoAnalyzerGUI instance
            theme_manager: ThemeManager instance
        """
        self.__init_themed__(theme_manager)
        super().__init__(
            parent,
            bg=self.get_color("bg_card"),
            bd=0,
            highlightbackground=self.get_color("border_light"),
            highlightthickness=1
        )
        self.gui = gui
        self._frames = []  # 프레임 참조 저장
        self._labels = []  # 레이블 참조 저장
        self.create_widgets()

    def create_widgets(self):
        """Create URL input widgets"""
        bg_card = self.get_color("bg_card")
        bg_input = self.get_color("bg_input")
        text_primary = self.get_color("text_primary")
        text_secondary = self.get_color("text_secondary")
        border_light = self.get_color("border_light")
        primary = self.get_color("primary")

        header = tk.Frame(self, bg=bg_card)
        header.pack(fill=tk.X, padx=16, pady=(10, 4))
        self._frames.append(header)

        # 헤더 좌측: 제목
        header_left = tk.Frame(header, bg=bg_card)
        header_left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._frames.append(header_left)

        title_label = tk.Label(
            header_left,
            text="URL 입력 및 설정",
            font=("맑은 고딕", 12, "bold"),
            bg=bg_card,
            fg=text_primary
        )
        title_label.pack(anchor=tk.W)
        self._labels.append(('title', title_label))
        
        subtitle_label = tk.Label(
            header_left,
            text="텍스트 붙여넣기 시 자동으로 링크 추출됩니다. Enter 키로 추가할 수 있습니다.",
            font=("맑은 고딕", 9),
            bg=bg_card,
            fg=text_secondary
        )
        subtitle_label.pack(anchor=tk.W, pady=(1, 0))
        self._labels.append(('subtitle', subtitle_label))

        # 헤더 우측: API 버튼들
        header_right = tk.Frame(header, bg=bg_card)
        header_right.pack(side=tk.RIGHT, anchor=tk.NE)
        self._frames.append(header_right)

        # API 관리 버튼
        api_btn = create_rounded_button(
            header_right,
            text="API 키 관리",
            command=self.gui.show_api_key_manager,
            style="primary",
            gui=self.gui
        )
        api_btn.pack(side=tk.LEFT)

        # API 상태 버튼
        status_btn = create_rounded_button(
            header_right,
            text="API 상태 확인",
            command=self.gui.show_api_status,
            style="outline",
            gui=self.gui
        )
        status_btn.pack(side=tk.LEFT, padx=(8, 0))

        input_wrap = tk.Frame(self, bg=bg_card)
        input_wrap.pack(fill=tk.X, padx=16, pady=(0, 6))
        self._frames.append(input_wrap)

        self.gui.url_entry = tk.Text(
            input_wrap,
            height=2,
            wrap=tk.WORD,
            font=("맑은 고딕", 10),
            bg=bg_input,
            fg=text_primary,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=border_light,
            highlightcolor=primary,
            insertbackground=primary
        )
        self.gui.url_entry.pack(fill=tk.X)
        self.gui.url_entry.bind("<Return>", self.gui.add_url_from_entry)
        self.gui.url_entry.bind("<Control-Return>", self.gui.add_url_from_entry)
        self.gui.url_entry.bind("<Control-v>", self.gui.paste_and_extract)

        example_label = tk.Label(
            input_wrap,
            text="예: https://www.tiktok.com/@...",
            font=("맑은 고딕", 9),
            bg=bg_card,
            fg=text_secondary
        )
        example_label.pack(anchor=tk.W, pady=(4, 0))
        self._labels.append(('example', example_label))

        action_bar = tk.Frame(input_wrap, bg=bg_card)
        action_bar.pack(fill=tk.X, pady=(6, 0))
        self._frames.append(action_bar)

        # URL 추가 버튼
        url_add_btn = create_rounded_button(
            action_bar,
            text="URL 추가",
            command=self.gui.add_url_from_entry,
            style="primary",
            gui=self.gui
        )
        url_add_btn.pack(side=tk.LEFT)

        # 클립보드 추가 버튼
        clipboard_btn = create_rounded_button(
            action_bar,
            text="클립보드 추가",
            command=lambda: self.gui.paste_and_extract(),
            style="secondary",
            gui=self.gui
        )
        clipboard_btn.pack(side=tk.LEFT, padx=(8, 0))

        # 저장 폴더 열기 버튼
        folder_open_btn = create_rounded_button(
            action_bar,
            text="📁 저장 폴더 열기",
            command=self._open_output_folder,
            style="secondary",
            gui=self.gui,
            padx=12
        )
        folder_open_btn.pack(side=tk.LEFT, padx=(8, 0))

        folder_inline = tk.Frame(action_bar, bg=bg_card)
        folder_inline.pack(side=tk.LEFT, padx=(0, 0), fill=tk.X, expand=True)
        folder_inline.grid_columnconfigure(2, weight=1)
        self._frames.append(folder_inline)

        self.gui.output_folder_button = create_rounded_button(
            folder_inline,
            text="저장폴더 선택",
            command=self.gui.select_output_folder,
            style="primary",
            gui=self.gui,
            pady=5
        )
        self.gui.output_folder_button.grid(row=0, column=1, padx=(8, 0))

        self.gui.output_folder_label = tk.Label(
            folder_inline,
            textvariable=self.gui.output_folder_var,
            font=("맑은 고딕", 9),
            bg=bg_card,
            fg=text_secondary,
            anchor="w",
            justify=tk.LEFT
        )
        self.gui.output_folder_label.grid(row=0, column=2, padx=(8, 0), sticky="we")
        self._labels.append(('folder', self.gui.output_folder_label))

    def _open_output_folder(self):
        """저장 폴더를 파일 탐색기에서 열기"""
        import os
        import subprocess
        import sys

        output_path = getattr(self.gui, 'output_folder_path', None)
        if not output_path:
            output_path = os.path.join(os.getcwd(), "outputs")

        os.makedirs(output_path, exist_ok=True)

        try:
            if sys.platform == 'win32':
                os.startfile(output_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.run(['open', output_path])
            else:  # Linux
                subprocess.run(['xdg-open', output_path])
        except Exception as e:
            logger.error(f"폴더 열기 오류: {e}")

    def apply_theme(self) -> None:
        """테마 적용 - 다크/라이트 모드 전환 시 색상 업데이트"""
        bg_card = self.get_color("bg_card")
        bg_input = self.get_color("bg_input")
        border_color = self.get_color("border_light")
        text_primary = self.get_color("text_primary")
        text_secondary = self.get_color("text_secondary")
        primary = self.get_color("primary")
        
        # 패널 배경색 업데이트
        self.configure(bg=bg_card, highlightbackground=border_color)
        
        # 프레임 배경색 업데이트
        for frame in self._frames:
            try:
                frame.configure(bg=bg_card)
            except Exception as e:
                logger.debug(f"프레임 테마 적용 실패: {e}")
        
        # 레이블 색상 업데이트
        for label_type, label in self._labels:
            try:
                if label_type == 'title':
                    label.configure(bg=bg_card, fg=text_primary)
                else:
                    label.configure(bg=bg_card, fg=text_secondary)
            except Exception as e:
                logger.debug(f"레이블 테마 적용 실패 ({label_type}): {e}")
        
        # URL 입력 필드 테마 적용
        if hasattr(self.gui, 'url_entry'):
            try:
                self.gui.url_entry.configure(
                    bg=bg_input,
                    fg=text_primary,
                    highlightbackground=border_color,
                    highlightcolor=primary,
                    insertbackground=primary
                )
            except Exception as e:
                logger.debug(f"URL 입력 필드 테마 적용 실패: {e}")
