"""
Queue Panel for PyQt6
"""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QBoxLayout, QLabel, QFrame,
    QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator,
    QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt, QTimer
from ui.components.rounded_widgets import create_rounded_button
from ui.components.base_widget import ThemedMixin

class QueuePanel(QFrame, ThemedMixin):
    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.gui.queue_panel = self
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
        self.subtitle_label.setWordWrap(True)
        self.main_layout.addWidget(self.subtitle_label)

        self.title_label.setText("제작 대기열")
        self.subtitle_label.setText("풀자동화 예약, YouTube 연결, 다음 업로드 시간을 실제 큐 기준으로 표시합니다.")

        status_layout = QHBoxLayout()
        self._status_layout = status_layout
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
        self._control_layout = control_layout
        self.gui.start_batch_button = create_rounded_button(self, "▶ 작업 시작", self.gui.start_batch_processing)
        control_layout.addWidget(self.gui.start_batch_button)
        
        self.gui.stop_batch_button = create_rounded_button(self, "■ 작업 중지", self.gui.stop_batch_processing, style="secondary")
        self.gui.stop_batch_button.setEnabled(False)
        control_layout.addWidget(self.gui.stop_batch_button)
        
        self.clear_waiting_btn = create_rounded_button(self, "대기 삭제 (0)", self.gui.clear_waiting_only, style="secondary")
        self.clear_waiting_btn.setAccessibleName("대기 중인 작업 모두 삭제")
        self.clear_waiting_btn.setToolTip("일반 작업과 풀자동 예약 중 대기 상태인 항목을 삭제합니다.")
        self.clear_waiting_btn.setEnabled(False)
        control_layout.addWidget(self.clear_waiting_btn)

        self.clear_completed_btn = create_rounded_button(self, "완료 삭제 (0)", self.gui.clear_completed_only, style="secondary")
        self.clear_completed_btn.setAccessibleName("완료된 작업 모두 삭제")
        self.clear_completed_btn.setToolTip("일반 작업과 풀자동 예약의 완료 이력을 삭제합니다.")
        self.clear_completed_btn.setEnabled(False)
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
        self.gui.url_listbox.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.gui.url_listbox.itemSelectionChanged.connect(self.sync_delete_controls)
        self._configure_queue_table_columns()
        self.main_layout.addWidget(self.gui.url_listbox)
        
        # Action Buttons
        action_layout = QHBoxLayout()
        self._action_layout = action_layout
        self.remove_btn = create_rounded_button(self, "선택 삭제 (0)", self.gui.remove_selected_url, style="danger")
        self.remove_btn.setAccessibleName("선택한 대기열 항목 삭제")
        self.remove_btn.setToolTip("표에서 삭제할 항목을 하나 이상 선택해 주세요.")
        self.remove_btn.setEnabled(False)
        action_layout.addWidget(self.remove_btn)
        
        self.clear_btn = create_rounded_button(self, "전체 삭제 (0)", self.gui.clear_url_queue, style="secondary")
        self.clear_btn.setAccessibleName("삭제 가능한 대기열 전체 삭제")
        self.clear_btn.setToolTip("진행 중인 작업을 제외한 일반 작업과 풀자동 예약을 모두 삭제합니다.")
        self.clear_btn.setEnabled(False)
        action_layout.addWidget(self.clear_btn)
        
        action_layout.addStretch()
        self.main_layout.addLayout(action_layout)

        self.delete_feedback_label = QLabel("삭제 결과가 여기에 표시됩니다.")
        self.delete_feedback_label.setAccessibleName("대기열 삭제 결과")
        self.delete_feedback_label.setWordWrap(True)
        self.main_layout.addWidget(self.delete_feedback_label)
        
        # Status Counts
        count_layout = QHBoxLayout()
        self._count_layout = count_layout
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

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        """Stack dense rows before their button text is squeezed."""
        super().resizeEvent(event)
        direction = (
            QBoxLayout.Direction.TopToBottom
            if event.size().width() < 720
            else QBoxLayout.Direction.LeftToRight
        )
        for layout in (
            self._status_layout,
            self._control_layout,
            self._action_layout,
            self._count_layout,
        ):
            layout.setDirection(direction)

    def sync_delete_controls(self, summer_snapshot=None):
        status = getattr(self.gui, "url_status", {})
        queue = getattr(self.gui, "url_queue", [])
        manager = getattr(self.gui, "queue_manager", None)
        normalize = getattr(manager, "_normalize_status", lambda value: str(value or "waiting"))
        local_keys = set(queue).union(status.keys())
        local_waiting = sum(
            1 for key in local_keys
            if normalize(status.get(key)) == "waiting"
        )
        local_completed = sum(
            1 for key in local_keys
            if normalize(status.get(key)) == "completed"
        )
        local_deletable = sum(
            1 for key in local_keys
            if normalize(status.get(key)) != "processing"
        )

        if not isinstance(summer_snapshot, dict):
            summer_snapshot = getattr(
                getattr(self.gui, "queue_manager", None),
                "_last_summer_coupang_snapshot",
                {},
            ) or {}
        counts = summer_snapshot.get("counts", {}) if isinstance(summer_snapshot, dict) else {}
        waiting = local_waiting + int(counts.get("waiting", 0) or 0)
        completed = local_completed + int(counts.get("completed", 0) or 0)
        scheduled_deletable = int(summer_snapshot.get("total", 0) or 0) - int(
            counts.get("processing", 0) or 0
        )
        deletable = local_deletable + max(0, scheduled_deletable)

        selected_deletable = 0
        for item in self.gui.url_listbox.selectedItems():
            metadata = item.data(0, Qt.ItemDataRole.UserRole)
            if not isinstance(metadata, dict):
                continue
            if normalize(metadata.get("status")) != "processing":
                selected_deletable += 1

        self.clear_waiting_btn.setText(f"대기 삭제 ({waiting})")
        self.clear_waiting_btn.setEnabled(waiting > 0)
        self.clear_completed_btn.setText(f"완료 삭제 ({completed})")
        self.clear_completed_btn.setEnabled(completed > 0)
        self.remove_btn.setText(f"선택 삭제 ({selected_deletable})")
        self.remove_btn.setEnabled(selected_deletable > 0)
        self.clear_btn.setText(f"전체 삭제 ({deletable})")
        self.clear_btn.setEnabled(deletable > 0)

    def show_delete_feedback(self, message):
        self.delete_feedback_label.setText(f"✓ {message}")
        self.delete_feedback_label.setAccessibleDescription(message)
        self.delete_feedback_label.setStyleSheet(
            "color: #10B981; border: none; font-size: 12px; font-weight: 600; padding: 2px 0;"
        )

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
                QTimer.singleShot(0, self._apply_item_tooltips)
                return
            except Exception:
                pass

        manager = getattr(self.gui, "queue_manager", None)
        update = getattr(manager, "update_url_listbox", None)
        if callable(update):
            try:
                update()
                QTimer.singleShot(0, self._apply_item_tooltips)
            except Exception:
                pass

    def _apply_item_tooltips(self) -> None:
        """Expose every elided table value without changing compact columns."""
        iterator = QTreeWidgetItemIterator(self.gui.url_listbox)
        while iterator.value() is not None:
            item = iterator.value()
            for column in range(self.gui.url_listbox.columnCount()):
                item.setToolTip(column, item.text(column))
            iterator += 1

    def apply_theme(self):
        bg = self.get_color("bg_card")
        border = self.get_color("border_light")
        text_primary = self.get_color("text_primary")
        text_secondary = self.get_color("text_secondary")
        
        self.setStyleSheet(f"background-color: {bg}; border: 1px solid {border}; border-radius: 8px;")
        self.title_label.setStyleSheet(f"color: {text_primary}; font-weight: bold; border: none;")
        self.subtitle_label.setStyleSheet(f"color: {text_secondary}; border: none;")
        self.delete_feedback_label.setStyleSheet(
            f"color: {text_secondary}; border: none; font-size: 12px; padding: 2px 0;"
        )
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
