"""
Queue panel for managing video processing queue
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional

from ui.components.rounded_widgets import RoundedButton, create_rounded_button
from ui.components.base_widget import ThemedMixin
from ui.theme_manager import ThemeManager, get_theme_manager


class QueuePanel(tk.Frame, ThemedMixin):
    """Queue panel displaying URL queue with start/stop controls"""

    def __init__(self, parent, gui, theme_manager: Optional[ThemeManager] = None):
        """
        Initialize the queue panel.

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
        self._header_labels = []  # 헤더 레이블 참조 저장
        self._frames = []  # 프레임 참조 저장
        self.create_widgets()

    def create_widgets(self):
        """Create queue panel widgets"""
        bg_card = self.get_color("bg_card")
        text_primary = self.get_color("text_primary")
        text_secondary = self.get_color("text_secondary")

        header = tk.Frame(self, bg=bg_card)
        header.pack(fill=tk.X, padx=18, pady=(16, 6))
        self._frames.append(header)
        
        title_label = tk.Label(
            header,
            text="제작 대기열",
            font=("맑은 고딕", 12, "bold"),
            bg=bg_card,
            fg=text_primary
        )
        title_label.pack(anchor=tk.W)
        self._header_labels.append(('title', title_label))
        
        subtitle_label = tk.Label(
            header,
            text="대기 | 완료 | 실패 건수를 자동으로 추적합니다.",
            font=("맑은 고딕", 9),
            bg=bg_card,
            fg=text_secondary
        )
        subtitle_label.pack(anchor=tk.W, pady=(2, 0))
        self._header_labels.append(('subtitle', subtitle_label))

        control_row = tk.Frame(self, bg=bg_card)
        control_row.pack(fill=tk.X, padx=18, pady=(0, 10))
        self._frames.append(control_row)

        # 작업 시작 버튼 - 둥근 쿠팡 레드
        self.gui.start_batch_button = create_rounded_button(
            control_row,
            text="▶ 작업 시작",
            command=self.gui.start_batch_processing,
            style="primary",
            gui=self.gui,
            font=("맑은 고딕", 10, "bold"),
            padx=18,
            pady=8
        )
        self.gui.start_batch_button.pack(side=tk.LEFT, padx=(0, 12))

        # 작업 중지 버튼 - 둥근 회색 (비활성화 상태)
        self.gui.stop_batch_button = create_rounded_button(
            control_row,
            text="■ 작업 중지",
            command=self.gui.stop_batch_processing,
            style="gray",
            gui=self.gui,
            font=("맑은 고딕", 10, "bold"),
            padx=18,
            pady=8
        )
        self.gui.stop_batch_button.configure(state="disabled")
        self.gui.stop_batch_button.pack(side=tk.LEFT)

        # 대기중 삭제 버튼 - 둥근 연한 회색
        clear_waiting_btn = create_rounded_button(
            control_row,
            text="대기중 삭제",
            command=self.gui.clear_waiting_only,
            style="secondary",
            gui=self.gui
        )
        clear_waiting_btn.pack(side=tk.LEFT, padx=(12, 0))

        table_frame = tk.Frame(self, bg=bg_card)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 10))
        self._frames.append(table_frame)

        columns = ("order", "url", "status", "remarks")
        self.gui.url_listbox = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=6,
            selectmode="browse",
            style="Queue.Treeview"
        )
        # 헤더 설정
        self.gui.url_listbox.heading("order", text="구분")
        self.gui.url_listbox.heading("url", text="URL")
        self.gui.url_listbox.heading("status", text="상태")
        self.gui.url_listbox.heading("remarks", text="비고")
        self.gui.url_listbox.column("order", width=68, anchor=tk.CENTER, stretch=False)
        self.gui.url_listbox.column("url", width=400, minwidth=300, anchor=tk.W, stretch=True)
        self.gui.url_listbox.column("status", width=102, anchor=tk.CENTER, stretch=False)
        self.gui.url_listbox.column("remarks", width=300, minwidth=200, anchor=tk.CENTER, stretch=False)

        scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.gui.url_listbox.yview, style="Queue.Vertical.TScrollbar")
        self.gui.url_listbox.configure(yscrollcommand=scroll.set)
        self.gui.url_listbox.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # 상태 태그 및 스타일 설정
        self._update_treeview_style()
        self._configure_treeview_tags()

        action_frame = tk.Frame(self, bg=bg_card)
        action_frame.pack(fill=tk.X, padx=18, pady=(0, 10), anchor="w")
        self._frames.append(action_frame)

        # 선택 삭제 버튼
        remove_button = create_rounded_button(
            action_frame,
            text="선택 삭제",
            command=self.gui.remove_selected_url,
            style="danger",
            gui=self.gui,
            pady=5
        )
        remove_button.pack(side=tk.LEFT)

        # 전체 삭제 버튼
        clear_button = create_rounded_button(
            action_frame,
            text="전체 삭제",
            command=self.gui.clear_url_queue,
            style="secondary",
            gui=self.gui,
            pady=5
        )
        clear_button.pack(side=tk.LEFT, padx=(10, 0))

        # 상태별 카운트를 개별 레이블로 표시
        count_frame = tk.Frame(self, bg=bg_card)
        count_frame.pack(fill=tk.X, padx=18, pady=(8, 12))
        self._frames.append(count_frame)
        self._count_frame = count_frame

        # 진행 중 카운트 (빨간 배경)
        self.gui.count_processing = tk.Label(
            count_frame,
            text="🔄 진행 0",
            font=("맑은 고딕", 9, "bold"),
            bg="#DC2626",
            fg="#FFFFFF",
            padx=8,
            pady=3
        )
        self.gui.count_processing.pack(side=tk.LEFT, padx=(0, 6))

        # 대기 카운트 (회색)
        self.gui.count_waiting = tk.Label(
            count_frame,
            text="⏸ 대기 0",
            font=("맑은 고딕", 9),
            bg="#4B5563",
            fg="#FFFFFF",
            padx=8,
            pady=3
        )
        self.gui.count_waiting.pack(side=tk.LEFT, padx=(0, 6))

        # 완료 카운트 (초록 배경)
        self.gui.count_completed = tk.Label(
            count_frame,
            text="✅ 완료 0",
            font=("맑은 고딕", 9, "bold"),
            bg="#059669",
            fg="#FFFFFF",
            padx=8,
            pady=3
        )
        self.gui.count_completed.pack(side=tk.LEFT, padx=(0, 6))

        # 건너뜀 카운트 (노란 배경)
        self.gui.count_skipped = tk.Label(
            count_frame,
            text="⏭ 건너뜀 0",
            font=("맑은 고딕", 9),
            bg="#D97706",
            fg="#FFFFFF",
            padx=8,
            pady=3
        )
        self.gui.count_skipped.pack(side=tk.LEFT, padx=(0, 6))

        # 실패 카운트 (어두운 빨간 배경)
        self.gui.count_failed = tk.Label(
            count_frame,
            text="❌ 실패 0",
            font=("맑은 고딕", 9, "bold"),
            bg="#991B1B",
            fg="#FFFFFF",
            padx=8,
            pady=3
        )
        self.gui.count_failed.pack(side=tk.LEFT)

        # 기존 queue_count_label은 호환성을 위해 숨김 처리
        self.gui.queue_count_label = tk.Label(
            self,
            text="",
            font=("맑은 고딕", 1),
            bg=bg_card,
            fg=bg_card,
            height=0
        )
        # pack하지 않음 - 숨김

        self.gui.update_queue_count()

    def _configure_treeview_tags(self):
        """Treeview 상태 태그 색상 설정 - 상태별 배경색으로 확실히 구분"""
        bg_card = self.get_color("bg_card")
        bg_secondary = self.get_color("bg_secondary")

        # 다크모드/라이트모드 색상 설정 - 훨씬 더 강렬한 색상
        if self.is_dark_mode:
            # 다크모드: 강렬한 배경색 + 대비되는 텍스트
            waiting_fg = "#9CA3AF"      # 연한 회색 텍스트
            waiting_bg = "#1F2937"      # 어두운 회색 배경

            processing_fg = "#FFFFFF"   # 흰색 텍스트
            processing_bg = "#DC2626"   # 밝은 빨강 (매우 눈에 띔)

            completed_fg = "#FFFFFF"    # 흰색 텍스트
            completed_bg = "#059669"    # 밝은 초록 배경

            failed_fg = "#FFFFFF"       # 흰색 텍스트
            failed_bg = "#991B1B"       # 어두운 빨강 배경

            skipped_fg = "#000000"      # 검은 텍스트
            skipped_bg = "#FBBF24"      # 밝은 노랑 배경
        else:
            # 라이트모드: 선명한 색상
            waiting_fg = "#6B7280"      # 회색 텍스트
            waiting_bg = "#F3F4F6"      # 연한 회색 배경

            processing_fg = "#FFFFFF"   # 흰색 텍스트
            processing_bg = "#DC2626"   # 밝은 빨강 (강조)

            completed_fg = "#FFFFFF"    # 흰색 텍스트
            completed_bg = "#10B981"    # 밝은 초록 배경

            failed_fg = "#FFFFFF"       # 흰색 텍스트
            failed_bg = "#B91C1C"       # 진한 빨강 배경

            skipped_fg = "#000000"      # 검은 텍스트
            skipped_bg = "#FCD34D"      # 밝은 노랑 배경

        # 대기 상태 - 차분한 회색
        self.gui.url_listbox.tag_configure(
            'waiting',
            foreground=waiting_fg,
            background=waiting_bg,
            font=("맑은 고딕", 9)
        )

        # 진행 중 - 가장 눈에 띄게 (빨간 배경 + 흰색 굵은 글씨)
        self.gui.url_listbox.tag_configure(
            'processing',
            foreground=processing_fg,
            background=processing_bg,
            font=("맑은 고딕", 10, "bold")
        )

        # 완료 - 초록 배경 + 흰색 글씨
        self.gui.url_listbox.tag_configure(
            'completed',
            foreground=completed_fg,
            background=completed_bg,
            font=("맑은 고딕", 9, "bold")
        )

        # 실패 - 어두운 빨강 배경
        self.gui.url_listbox.tag_configure(
            'failed',
            foreground=failed_fg,
            background=failed_bg,
            font=("맑은 고딕", 9, "bold")
        )

        # 건너뜀 - 노란 배경
        self.gui.url_listbox.tag_configure(
            'skipped',
            foreground=skipped_fg,
            background=skipped_bg,
            font=("맑은 고딕", 9, "bold")
        )

        # 줄무늬 색상 (대기 상태에서만 적용)
        self.gui.url_listbox.tag_configure('oddrow', background=bg_card)
        self.gui.url_listbox.tag_configure('evenrow', background=bg_secondary)

    def apply_theme(self) -> None:
        """테마 적용 - 다크/라이트 모드 전환 시 색상 업데이트"""
        bg_card = self.get_color("bg_card")
        border_color = self.get_color("border_light")
        text_primary = self.get_color("text_primary")
        text_secondary = self.get_color("text_secondary")

        # 패널 배경색 업데이트
        self.configure(bg=bg_card, highlightbackground=border_color)

        # 프레임 배경색 업데이트 (카운트 프레임 제외)
        for frame in self._frames:
            try:
                if frame != getattr(self, '_count_frame', None):
                    frame.configure(bg=bg_card)
            except tk.TclError:
                pass

        # 카운트 프레임 배경 업데이트
        count_frame = getattr(self, '_count_frame', None)
        if count_frame:
            try:
                count_frame.configure(bg=bg_card)
            except tk.TclError:
                pass

        # 레이블 색상 업데이트
        for label_type, label in self._header_labels:
            try:
                if label_type == 'title':
                    label.configure(bg=bg_card, fg=text_primary)
                else:
                    label.configure(bg=bg_card, fg=text_secondary)
            except tk.TclError:
                pass

        # 카운트 레이블들은 고정 색상 유지 (테마와 무관)
        # - count_processing: 빨간 배경
        # - count_waiting: 회색 배경
        # - count_completed: 초록 배경
        # - count_skipped: 노란 배경
        # - count_failed: 어두운 빨간 배경

        # Treeview 태그 색상 업데이트
        url_listbox = getattr(self.gui, 'url_listbox', None)
        if url_listbox is not None:
            self._configure_treeview_tags()

        # ttk Treeview 스타일 업데이트
        self._update_treeview_style()

    def _update_treeview_style(self):
        """Treeview ttk 스타일 업데이트 - 다크모드 완전 지원"""
        style = ttk.Style()

        # 'clam' 테마 사용 - Windows에서 배경색 등 커스터마이징 가능
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass  # 테마 사용 불가 시 기본 테마 유지

        # 테마 관리자에서 색상 가져오기
        bg_card = self.get_color("bg_card")
        bg_secondary = self.get_color("bg_secondary")
        bg_hover = self.get_color("bg_hover")
        text_primary = self.get_color("text_primary")
        text_secondary = self.get_color("text_secondary")
        bg_selected = self.get_color("bg_selected")
        scrollbar_bg = self.get_color("scrollbar_bg")
        scrollbar_thumb = self.get_color("scrollbar_thumb")
        primary = self.get_color("primary")
        heading_bg = bg_secondary

        # Treeview 본체 스타일 - 행 높이를 늘려서 상태 색상이 잘 보이게
        style.configure(
            "Queue.Treeview",
            background=bg_card,
            foreground=text_primary,
            fieldbackground=bg_card,
            borderwidth=0,
            relief="flat",
            rowheight=32
        )

        # Treeview 헤더 스타일
        style.configure(
            "Queue.Treeview.Heading",
            background=heading_bg,
            foreground=text_primary,
            borderwidth=0,
            relief="flat",
            padding=(8, 6)
        )

        # 선택 상태 맵핑
        style.map(
            "Queue.Treeview",
            background=[
                ("selected", bg_selected),
                ("!selected", bg_card)
            ],
            foreground=[
                ("selected", text_primary),
                ("!selected", text_primary)
            ]
        )

        style.map(
            "Queue.Treeview.Heading",
            background=[
                ("active", bg_hover),
                ("!active", heading_bg)
            ],
            foreground=[
                ("active", text_primary),
                ("!active", text_primary)
            ]
        )

        # 스크롤바 스타일
        style.configure(
            "Queue.Vertical.TScrollbar",
            background=scrollbar_thumb,
            troughcolor=scrollbar_bg,
            borderwidth=0,
            relief="flat",
            width=10
        )
        style.map(
            "Queue.Vertical.TScrollbar",
            background=[
                ("active", primary),
                ("!active", scrollbar_thumb)
            ]
        )

        # oddrow/evenrow 태그 색상도 업데이트
        treeview = getattr(self.gui, 'url_listbox', None)
        if treeview is not None:
            treeview.tag_configure('oddrow', background=bg_card)
            treeview.tag_configure('evenrow', background=bg_secondary)

            # Treeview 강제 새로고침 (Windows에서 ttk 스타일 변경 즉시 반영)
            try:
                # 스타일 재적용으로 강제 업데이트
                treeview.configure(style="Queue.Treeview")

                # 모든 아이템 태그 재설정
                for item in treeview.get_children():
                    current_tags = treeview.item(item, 'tags')
                    treeview.item(item, tags=current_tags)

                # 위젯 강제 갱신
                treeview.update()
            except tk.TclError:
                pass  # 위젯이 파괴된 경우
