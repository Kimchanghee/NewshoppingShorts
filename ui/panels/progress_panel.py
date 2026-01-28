"""
Progress panel for tracking video processing progress
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional

from ui.components.base_widget import ThemedMixin
from ui.theme_manager import ThemeManager, get_theme_manager


class ProgressPanel(tk.Frame, ThemedMixin):
    """Progress panel displaying current processing steps and progress"""

    def __init__(self, parent, gui, theme_manager: Optional[ThemeManager] = None):
        """
        Initialize the progress panel.

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
        """Create progress panel widgets"""
        bg_card = self.get_color("bg_card")
        bg_secondary = self.get_color("bg_secondary")
        text_primary = self.get_color("text_primary")
        text_secondary = self.get_color("text_secondary")
        primary = self.get_color("primary")

        header = tk.Frame(self, bg=bg_card)
        header.pack(fill=tk.X, padx=14, pady=(16, 8))
        self._frames.append(header)

        header_title = tk.Label(
            header,
            text="제작 진행",
            font=("맑은 고딕", 14, "bold"),
            bg=bg_card,
            fg=text_primary
        )
        header_title.pack(anchor=tk.W)
        self._labels.append(('title', header_title))

        # 현재 작업 상태 컨테이너 (배경색으로 강조)
        status_container = tk.Frame(
            self,
            bg="#DC2626",  # 빨간 배경
            padx=2,
            pady=2
        )
        status_container.pack(fill=tk.X, padx=14, pady=(0, 10))
        self._frames.append(status_container)
        self._status_container = status_container

        status_inner = tk.Frame(status_container, bg="#1F2937")
        status_inner.pack(fill=tk.X, padx=1, pady=1)
        self._status_inner = status_inner

        # 현재 작업 표시 - 더 크고 눈에 띄게
        self.gui.current_task_label = tk.Label(
            status_inner,
            textvariable=self.gui.current_task_var,
            font=("맑은 고딕", 11, "bold"),
            bg="#1F2937",
            fg="#F87171",  # 밝은 빨강
            anchor=tk.W,
            wraplength=320,
            justify=tk.LEFT,
            padx=10,
            pady=8
        )
        self.gui.current_task_label.pack(fill=tk.X)

        overall = tk.Frame(self, bg=bg_card)
        overall.pack(fill=tk.X, padx=14, pady=(4, 8))
        self._frames.append(overall)

        overall_title = tk.Label(
            overall,
            text="📊 현재 영상 진행률",
            font=("맑은 고딕", 11, "bold"),
            bg=bg_card,
            fg=text_primary
        )
        overall_title.pack(anchor=tk.W)
        self._labels.append(('overall_title', overall_title))

        self.gui.overall_numeric_label = tk.Label(
            overall,
            text="0/0 (0%)",
            font=("맑은 고딕", 12, "bold"),
            bg=bg_card,
            fg=primary,
            anchor=tk.W
        )
        self.gui.overall_numeric_label.pack(anchor=tk.W, pady=(4, 0))

        self.gui.overall_witty_label = tk.Label(
            overall,
            text="큐를 채우면 신나는 제작 퍼레이드가 시작됩니다!",
            font=("맑은 고딕", 9),
            bg=bg_card,
            fg=text_secondary,
            wraplength=320,
            justify=tk.LEFT
        )
        self.gui.overall_witty_label.pack(anchor=tk.W, pady=(2, 0))

        # 스텝 컨테이너
        steps_frame = tk.Frame(self, bg=bg_card)
        steps_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))
        self._frames.append(steps_frame)
        self._steps_frame = steps_frame

        # 실제 처리 순서에 맞게 정렬
        step_definitions = [
            ("📥 다운로드", 'download'),
            ("🤖 AI 분석", 'analysis'),
            ("🔍 자막 분석", 'ocr_analysis'),
            ("🌐 번역", 'translation'),
            ("🎤 TTS", 'tts'),
            ("🎨 블러", 'subtitle'),
            ("🔊 싱크", 'audio_analysis'),
            ("📝 자막", 'subtitle_overlay'),
            ("🎵 합성", 'video'),
            ("✨ 완료", 'finalize'),
        ]

        # 깜빡임 효과를 위한 변수
        self.gui.blink_job = None
        self.gui.blink_state = True
        self.gui.current_step_key = None

        self.gui.step_indicators = {}
        self.gui.step_titles = {}

        # 상태별 색상
        self._step_colors = self._get_step_colors()

        for idx, (title, key) in enumerate(step_definitions):
            row_bg = bg_secondary if idx % 2 == 0 else bg_card
            row = tk.Frame(
                steps_frame,
                bg=row_bg,
                height=32
            )
            row.pack(fill=tk.X, pady=0)
            row.pack_propagate(False)

            row.grid_columnconfigure(0, weight=0, minsize=28)
            row.grid_columnconfigure(1, weight=1)
            row.grid_columnconfigure(2, weight=0, minsize=55)

            # 상태 아이콘 (대기/진행/완료)
            status_label = tk.Label(
                row,
                text="⏸",
                font=("맑은 고딕", 11),
                bg=row_bg,
                fg=text_secondary,
                anchor="center"
            )
            status_label.grid(row=0, column=0, padx=(6, 2), sticky="w")

            # 단계 제목
            title_label = tk.Label(
                row,
                text=title,
                font=("맑은 고딕", 9),
                bg=row_bg,
                fg=text_primary,
                anchor="w"
            )
            title_label.grid(row=0, column=1, padx=(0, 4), sticky="w")

            # 진행률
            progress_label = tk.Label(
                row,
                text="",
                font=("맑은 고딕", 9, "bold"),
                bg=row_bg,
                fg=text_secondary,
                anchor="e"
            )
            progress_label.grid(row=0, column=2, padx=(4, 8), sticky="e")

            self.gui.step_titles[key] = title
            self.gui.step_indicators[key] = {
                'status_label': status_label,
                'progress_label': progress_label,
                'row_frame': row,
                'title_label': title_label,
                'index': idx
            }

    def _get_row_colors(self):
        """줄무늬 행 색상 반환"""
        if self.is_dark_mode:
            return [self.get_color("bg_secondary"), self.get_color("bg_card")]
        else:
            return [self.get_color("bg_secondary"), self.get_color("bg_card")]

    def _get_step_colors(self):
        """단계별 상태 색상 반환"""
        if self.is_dark_mode:
            return {
                'pending': {'fg': '#6B7280', 'icon': '⏸'},      # 회색
                'active': {'fg': '#F87171', 'icon': '🔄'},      # 빨강 (진행 중)
                'completed': {'fg': '#34D399', 'icon': '✅'},   # 초록 (완료)
                'error': {'fg': '#F87171', 'icon': '❌'}        # 빨강 (오류)
            }
        else:
            return {
                'pending': {'fg': '#9CA3AF', 'icon': '⏸'},
                'active': {'fg': '#DC2626', 'icon': '🔄'},
                'completed': {'fg': '#059669', 'icon': '✅'},
                'error': {'fg': '#DC2626', 'icon': '❌'}
            }

    def update_step_status(self, step_key, status, progress=None):
        """단계 상태 업데이트 (외부에서 호출)"""
        if step_key not in self.gui.step_indicators:
            return

        indicator = self.gui.step_indicators[step_key]
        colors = self._get_step_colors()
        color_info = colors.get(status, colors['pending'])

        status_label = indicator.get('status_label')
        title_label = indicator.get('title_label')
        progress_label = indicator.get('progress_label')
        row_frame = indicator.get('row_frame')

        if status_label:
            status_label.config(text=color_info['icon'], fg=color_info['fg'])

        if title_label:
            if status == 'active':
                title_label.config(fg=color_info['fg'], font=("맑은 고딕", 9, "bold"))
            else:
                title_label.config(fg=self.get_color("text_primary"), font=("맑은 고딕", 9))

        if progress_label:
            if progress is not None:
                progress_label.config(text=f"{progress}%", fg=color_info['fg'])
            elif status == 'completed':
                progress_label.config(text="완료", fg=color_info['fg'])
            elif status == 'active':
                progress_label.config(text="진행중", fg=color_info['fg'])
            else:
                progress_label.config(text="", fg=self.get_color("text_secondary"))

        # 진행 중인 단계는 배경색 강조
        if row_frame:
            if status == 'active':
                if self.is_dark_mode:
                    row_frame.config(bg="#3B1A1A")  # 어두운 빨강
                else:
                    row_frame.config(bg="#FEE2E2")  # 연한 빨강
                # 자식 위젯도 업데이트
                for child in row_frame.winfo_children():
                    try:
                        child.config(bg=row_frame.cget('bg'))
                    except Exception:
                        pass
            else:
                idx = indicator.get('index', 0)
                row_bg = self.get_color("bg_secondary") if idx % 2 == 0 else self.get_color("bg_card")
                row_frame.config(bg=row_bg)
                for child in row_frame.winfo_children():
                    try:
                        child.config(bg=row_bg)
                    except Exception:
                        pass

    def start_blink(self, step_key):
        """현재 작업 중인 단계 깜빡임 시작"""
        self.stop_blink()
        self.gui.current_step_key = step_key
        self.gui.blink_state = True
        self._do_blink()

    def stop_blink(self):
        """깜빡임 중지"""
        if self.gui.blink_job:
            try:
                self.after_cancel(self.gui.blink_job)
            except tk.TclError:
                pass
            self.gui.blink_job = None

        if self.gui.current_step_key and self.gui.current_step_key in self.gui.step_indicators:
            indicator = self.gui.step_indicators[self.gui.current_step_key]
            if 'title_label' in indicator:
                indicator['title_label'].config(fg=self.get_color("text_primary"))
        self.gui.current_step_key = None

    def _do_blink(self):
        """깜빡임 효과 실행"""
        if not self.gui.current_step_key:
            return

        if self.gui.current_step_key not in self.gui.step_indicators:
            return

        indicator = self.gui.step_indicators[self.gui.current_step_key]
        title_label = indicator.get('title_label')

        if title_label:
            if self.gui.blink_state:
                title_label.config(fg=self.get_color("primary"))
            else:
                title_label.config(fg=self.get_color("text_disabled"))

            self.gui.blink_state = not self.gui.blink_state

        self.gui.blink_job = self.after(500, self._do_blink)

    def apply_theme(self) -> None:
        """테마 적용 - 다크/라이트 모드 전환 시 색상 업데이트"""
        bg_card = self.get_color("bg_card")
        bg_secondary = self.get_color("bg_secondary")
        border_color = self.get_color("border_light")
        text_primary = self.get_color("text_primary")
        text_secondary = self.get_color("text_secondary")
        primary = self.get_color("primary")

        # 패널 배경색 업데이트
        self.configure(bg=bg_card, highlightbackground=border_color)

        # 일반 프레임 배경색 업데이트 (status_container 제외)
        for frame in self._frames:
            try:
                if frame == getattr(self, '_status_container', None):
                    frame.configure(bg="#DC2626")  # 항상 빨간 테두리
                elif frame == getattr(self, '_status_inner', None):
                    inner_bg = "#1F2937" if self.is_dark_mode else "#FEF2F2"
                    frame.configure(bg=inner_bg)
                else:
                    frame.configure(bg=bg_card)
            except Exception:
                pass

        # 레이블 색상 업데이트
        for label_type, label in self._labels:
            try:
                if label_type in ('title', 'overall_title'):
                    label.configure(bg=bg_card, fg=text_primary)
                else:
                    label.configure(bg=bg_card, fg=text_secondary)
            except Exception:
                pass

        # 현재 작업 레이블 업데이트 - 강조 색상
        current_task_label = getattr(self.gui, 'current_task_label', None)
        if current_task_label is not None:
            try:
                inner_bg = "#1F2937" if self.is_dark_mode else "#FEF2F2"
                task_fg = "#F87171" if self.is_dark_mode else "#DC2626"
                current_task_label.configure(bg=inner_bg, fg=task_fg)
            except Exception:
                pass

        # 전체 진행률 레이블들 업데이트
        overall_numeric_label = getattr(self.gui, 'overall_numeric_label', None)
        if overall_numeric_label is not None:
            try:
                overall_numeric_label.configure(bg=bg_card, fg=primary)
            except Exception:
                pass

        overall_witty_label = getattr(self.gui, 'overall_witty_label', None)
        if overall_witty_label is not None:
            try:
                overall_witty_label.configure(bg=bg_card, fg=text_secondary)
            except Exception:
                pass

        # 스텝 인디케이터 색상 업데이트
        step_indicators = getattr(self.gui, 'step_indicators', None)
        if step_indicators is not None:
            self._step_colors = self._get_step_colors()

            for key, indicator in step_indicators.items():
                try:
                    idx = indicator.get('index', 0)
                    row_bg = bg_secondary if idx % 2 == 0 else bg_card
                    row_frame = indicator.get('row_frame')
                    if row_frame:
                        row_frame.configure(bg=row_bg)

                    title_label = indicator.get('title_label')
                    if title_label:
                        title_label.configure(bg=row_bg, fg=text_primary)

                    status_label = indicator.get('status_label')
                    if status_label:
                        status_label.configure(bg=row_bg, fg=text_secondary)

                    progress_label = indicator.get('progress_label')
                    if progress_label:
                        progress_label.configure(bg=row_bg, fg=text_secondary)
                except Exception:
                    pass
