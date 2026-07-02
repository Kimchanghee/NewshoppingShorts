"""
Queue Panel for PyQt6
"""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QTreeWidget, QTreeWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, QTimer
from ui.components.rounded_widgets import create_rounded_button
from ui.components.base_widget import ThemedMixin

class QueuePanel(QFrame, ThemedMixin):
    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.__init_themed__(theme_manager)
        self.create_widgets()
        self.apply_theme()
        self._start_auto_refresh()

    def create_widgets(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(18, 16, 18, 16)
        
        # Header
        self.title_label = QLabel("제작 대기열")
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.main_layout.addWidget(self.title_label)
        
        self.subtitle_label = QLabel("대기 | 완료 | 실패 건수를 자동으로 추적합니다.")
        self.subtitle_label.setStyleSheet("font-size: 11px;")
        self.main_layout.addWidget(self.subtitle_label)

        self.title_label.setText("제작 대기열")
        self.subtitle_label.setText("풀자동화 예약, YouTube 연결, 다음 업로드 시간을 실제 큐 기준으로 표시합니다.")

        status_layout = QHBoxLayout()
        status_layout.setSpacing(8)
        self.gui.summer_status_interval = QLabel("자동 업로드\n확인 중")
        self.gui.summer_status_youtube = QLabel("YouTube\n확인 중")
        self.gui.summer_status_queue = QLabel("작업 큐\n확인 중")
        self.gui.summer_status_next = QLabel("다음 업로드\n확인 중")
        self._status_chips = [
            self.gui.summer_status_interval,
            self.gui.summer_status_youtube,
            self.gui.summer_status_queue,
            self.gui.summer_status_next,
        ]
        for label in self._status_chips:
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            label.setMinimumHeight(54)
            status_layout.addWidget(label, 1)
        self.main_layout.addLayout(status_layout)
        
        # Control Buttons
        control_layout = QHBoxLayout()
        self.gui.start_batch_button = create_rounded_button(self, "▶ 작업 시작", self.gui.start_batch_processing)
        control_layout.addWidget(self.gui.start_batch_button)
        
        self.gui.stop_batch_button = create_rounded_button(self, "■ 작업 중지", self.gui.stop_batch_processing, style="secondary")
        self.gui.stop_batch_button.setEnabled(False)
        control_layout.addWidget(self.gui.stop_batch_button)
        
        self.clear_waiting_btn = create_rounded_button(self, "대기중 삭제", self.gui.clear_waiting_only, style="secondary")
        control_layout.addWidget(self.clear_waiting_btn)

        self.clear_completed_btn = create_rounded_button(self, "완료 삭제", self.gui.clear_completed_only, style="secondary")
        control_layout.addWidget(self.clear_completed_btn)

        control_layout.addStretch()
        self.main_layout.addLayout(control_layout)

        run_status_layout = QVBoxLayout()
        run_status_layout.setSpacing(3)
        self.gui.start_run_status_label = QLabel("작업 시작 전")
        self.gui.start_run_status_label.setWordWrap(True)
        self.gui.start_run_status_label.setMinimumHeight(22)
        self.gui.start_run_detail_label = QLabel(
            "작업 시작을 누르면 실행 요청, 실제 실행, 완료 또는 차단 사유가 여기에 표시됩니다."
        )
        self.gui.start_run_detail_label.setWordWrap(True)
        self.gui.start_run_detail_label.setMinimumHeight(28)
        run_status_layout.addWidget(self.gui.start_run_status_label)
        run_status_layout.addWidget(self.gui.start_run_detail_label)
        self.main_layout.addLayout(run_status_layout)
        
        # TreeWidget (Replacement for Treeview)
        self.gui.url_listbox = QTreeWidget()
        self.gui.url_listbox.setColumnCount(5)
        self.gui.url_listbox.setHeaderLabels(["구분", "URL", "상태", "자동 업로드", "비고"])
        self._configure_queue_table_columns()
        self.main_layout.addWidget(self.gui.url_listbox)
        
        # Action Buttons
        action_layout = QHBoxLayout()
        self.remove_btn = create_rounded_button(self, "선택 삭제", self.gui.remove_selected_url, style="danger")
        action_layout.addWidget(self.remove_btn)
        
        self.clear_btn = create_rounded_button(self, "전체 삭제", self.gui.clear_url_queue, style="secondary")
        action_layout.addWidget(self.clear_btn)
        
        action_layout.addStretch()
        self.main_layout.addLayout(action_layout)
        
        # Status Counts
        count_layout = QHBoxLayout()
        self.gui.count_processing = QLabel("🔄 진행 0")
        self.gui.count_waiting = QLabel("⏸ 대기 0")
        self.gui.count_completed = QLabel("✅ 완료 0")
        self.gui.count_skipped = QLabel("⏭ 건너뜀 0")
        self.gui.count_failed = QLabel("❌ 실패 0")
        
        for label in [self.gui.count_processing, self.gui.count_waiting, self.gui.count_completed, self.gui.count_skipped, self.gui.count_failed]:
            label.setStyleSheet("padding: 4px 8px; border-radius: 4px; color: white; font-weight: bold;")
            count_layout.addWidget(label)
        
        self.gui.count_processing.setStyleSheet(self.gui.count_processing.styleSheet() + "background-color: #DC2626;")
        self.gui.count_waiting.setStyleSheet(self.gui.count_waiting.styleSheet() + "background-color: #4B5563;")
        self.gui.count_completed.setStyleSheet(self.gui.count_completed.styleSheet() + "background-color: #059669;")
        self.gui.count_skipped.setStyleSheet(self.gui.count_skipped.styleSheet() + "background-color: #D97706;")
        self.gui.count_failed.setStyleSheet(self.gui.count_failed.styleSheet() + "background-color: #991B1B;")
        
        self.main_layout.addLayout(count_layout)

    def _configure_queue_table_columns(self):
        tree = self.gui.url_listbox
        header = tree.header()
        header.setMinimumSectionSize(44)
        header.setStretchLastSection(True)
        header.setSectionsMovable(False)

        compact_widths = {
            0: 74,
            1: 316,  # Coupang product URL; full value stays available via selection/copy.
            2: 72,
            3: 88,
        }
        for column, width in compact_widths.items():
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(column, width)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        tree.setTextElideMode(Qt.TextElideMode.ElideRight)

    def _start_auto_refresh(self):
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(30000)
        self._refresh_timer.timeout.connect(self._refresh_queue_view)
        self._refresh_timer.start()
        QTimer.singleShot(0, self._refresh_queue_view)

    def _refresh_queue_view(self):
        updater = getattr(self.gui, "update_url_listbox", None)
        if callable(updater):
            try:
                updater()
                return
            except Exception:
                pass

        manager = getattr(self.gui, "queue_manager", None)
        update = getattr(manager, "update_url_listbox", None)
        if callable(update):
            try:
                update()
            except Exception:
                pass

    def apply_theme(self):
        bg = self.get_color("bg_card")
        border = self.get_color("border_light")
        text_primary = self.get_color("text_primary")
        text_secondary = self.get_color("text_secondary")
        
        self.setStyleSheet(f"background-color: {bg}; border: 1px solid {border}; border-radius: 8px;")
        self.title_label.setStyleSheet(f"color: {text_primary}; font-weight: bold; border: none;")
        self.subtitle_label.setStyleSheet(f"color: {text_secondary}; border: none;")
        chip_style = (
            f"background-color: {self.get_color('bg_input')};"
            f"color: {text_primary};"
            f"border: 1px solid {border};"
            "border-radius: 6px;"
            "padding: 7px 8px;"
            "font-size: 12px;"
            "font-weight: 600;"
        )
        for label in getattr(self, "_status_chips", []):
            label.setStyleSheet(chip_style)

        run_status_label = getattr(self.gui, "start_run_status_label", None)
        if run_status_label is not None:
            run_status_label.setStyleSheet(
                f"color: {text_primary};"
                "border: none;"
                "font-size: 13px;"
                "font-weight: 700;"
                "padding: 2px 0 0 0;"
            )
        run_detail_label = getattr(self.gui, "start_run_detail_label", None)
        if run_detail_label is not None:
            run_detail_label.setStyleSheet(
                f"color: {text_secondary};"
                "border: none;"
                "font-size: 12px;"
                "padding: 0 0 6px 0;"
            )
        
        self.gui.url_listbox.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {self.get_color("bg_input")};
                color: {text_primary};
                border: 1px solid {border};
                border-radius: 4px;
            }}
            QHeaderView::section {{
                background-color: {self.get_color("bg_secondary")};
                color: {text_primary};
                padding: 4px;
                border: none;
            }}
        """)
