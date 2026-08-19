"""URL-only input panel for single-video and mix-video editing modes."""

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QWidget, QFrame, QLineEdit,
    QPushButton, QSizePolicy,
)
from PyQt6.QtCore import Qt, QEvent, pyqtSignal
from PyQt6.QtGui import QFont
from ui.design_system_v2 import get_design_system, get_color

MIN_MIX_URLS = 2
MAX_MIX_URLS = 5


class MixURLEntry(QFrame):
    """믹스 모드용 개별 URL 입력 위젯"""
    url_changed = pyqtSignal(int, str)  # (index, url)
    remove_requested = pyqtSignal(int)  # index

    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.ds = get_design_system()
        self._setup_ui()

    def _setup_ui(self):
        ds = self.ds

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ds.spacing.space_2)

        # Index label
        self.index_label = QLabel(f"{self.index + 1}")
        self.index_label.setFixedWidth(28)
        self.index_label.setFixedHeight(28)
        self.index_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.index_label.setFont(QFont(ds.typography.font_family_primary, 12, QFont.Weight.Bold))
        self.index_label.setStyleSheet(f"""
            QLabel {{
                background-color: {get_color('primary')};
                color: white;
                border-radius: 14px;
            }}
        """)
        layout.addWidget(self.index_label)

        # URL input
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(f"{self.index + 1}번째 영상 링크를 붙여넣어 주세요")
        self.url_input.setStyleSheet(self._get_input_style())
        self.url_input.textChanged.connect(lambda text: self.url_changed.emit(self.index, text))
        layout.addWidget(self.url_input, 1)

        # Remove button (only show for index > 0)
        self.remove_btn = QPushButton("✕")
        self.remove_btn.setFixedSize(28, 28)
        self.remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {get_color('text_muted')};
                border: 1px solid {get_color('border_light')};
                border-radius: 4px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {get_color('error')};
                color: white;
                border-color: {get_color('error')};
            }}
        """)
        self.remove_btn.clicked.connect(lambda: self.remove_requested.emit(self.index))
        if self.index == 0:
            self.remove_btn.setVisible(False)
        layout.addWidget(self.remove_btn)

    def _get_input_style(self) -> str:
        ds = self.ds
        return f"""
            QLineEdit {{
                background-color: {get_color('surface_variant')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border')};
                border-radius: {ds.radius.base}px;
                padding: 8px 12px;
                font-family: {ds.typography.font_family_primary};
                font-size: {ds.typography.size_sm}px;
            }}
            QLineEdit:focus {{
                border: 2px solid {get_color('primary')};
            }}
            QLineEdit::placeholder {{
                color: {get_color('text_muted')};
            }}
        """

    def get_url(self) -> str:
        return self.url_input.text().strip()

    def set_url(self, url: str):
        self.url_input.setText(url)

    def update_index(self, new_index: int):
        """인덱스 업데이트 (재정렬 후)"""
        self.index = new_index
        self.index_label.setText(f"{self.index + 1}")
        self.url_input.setPlaceholderText(f"{self.index + 1}번째 영상 링크를 붙여넣어 주세요")
        self.remove_btn.setVisible(self.index > 0)


class URLInputPanel(QWidget):
    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.ds = get_design_system()
        self._mix_entries = []  # 믹스 모드 URL 입력 위젯들
        self.create_widgets()

    def create_widgets(self):
        ds = self.ds
        self.setStyleSheet("QLabel { background-color: transparent; border: none; }")

        # Main vertical layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(ds.spacing.space_4)

        # Mode indicator
        self.mode_indicator = QFrame()
        mode_layout = QHBoxLayout(self.mode_indicator)
        mode_layout.setContentsMargins(ds.spacing.space_3, ds.spacing.space_2, ds.spacing.space_3, ds.spacing.space_2)

        self.mode_icon = QLabel("🎬")
        self.mode_icon.setFont(QFont("Segoe UI Symbol", 16))
        mode_layout.addWidget(self.mode_icon)

        self.mode_label = QLabel("단일 영상 만들기")
        self.mode_label.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_sm, QFont.Weight.Bold))
        self.mode_label.setStyleSheet(f"color: {get_color('text_primary')}; background-color: transparent; border: none;")
        mode_layout.addWidget(self.mode_label)

        mode_layout.addStretch()

        self.change_mode_btn = QPushButton("모드 변경")
        self.change_mode_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.change_mode_btn.setStyleSheet(self._get_button_style("ghost", "sm"))
        self.change_mode_btn.clicked.connect(self._on_change_mode)
        mode_layout.addWidget(self.change_mode_btn)

        self.mode_indicator.setStyleSheet(f"""
            QFrame {{
                background-color: {get_color('surface_variant')};
                border-radius: {ds.radius.base}px;
            }}
        """)
        self.main_layout.addWidget(self.mode_indicator)

        # ========== Single Mode Container ==========
        self.single_mode_container = QWidget()
        single_layout = QVBoxLayout(self.single_mode_container)
        single_layout.setContentsMargins(0, 0, 0, 0)
        single_layout.setSpacing(ds.spacing.space_2)

        # URL input only. User-selected computer files are intentionally not
        # accepted in manual modes; every manual job starts from a video link.
        left_url_widget = QWidget()
        left_url_layout = QVBoxLayout(left_url_widget)
        left_url_layout.setContentsMargins(0, 0, 0, 0)
        left_url_layout.setSpacing(ds.spacing.space_2)

        lbl = QLabel("영상 링크 붙여넣기")
        lbl.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_sm, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {get_color('text_primary')}; background-color: transparent; border: none;")
        left_url_layout.addWidget(lbl)

        self.gui.url_entry = QTextEdit()
        self.gui.url_entry.setMinimumHeight(140)
        self.gui.url_entry.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.gui.url_entry.setPlaceholderText(
            "영상 링크 1개를 붙여넣어 주세요\n예: https://v.douyin.com/xxxxx/"
        )
        self.gui.url_entry.setStyleSheet(self._get_input_style())
        self.gui.url_entry.installEventFilter(self)
        left_url_layout.addWidget(self.gui.url_entry)

        hint = QLabel("💡 단일 영상 모드는 영상 링크를 한 번에 1개씩 담습니다.")
        hint.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        hint.setStyleSheet(f"color: {get_color('text_muted')}; background-color: transparent; border: none;")
        left_url_layout.addWidget(hint)

        # Single mode URL action buttons
        single_url_action = QHBoxLayout()
        single_url_action.setSpacing(ds.spacing.space_2)

        self.add_btn = QPushButton("만들 목록에 담기")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setStyleSheet(self._get_button_style("primary", "sm"))
        self.add_btn.clicked.connect(self.gui.add_url_from_entry)
        single_url_action.addWidget(self.add_btn)

        self.clipboard_btn = QPushButton("복사한 링크 붙여넣기")
        self.clipboard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clipboard_btn.setStyleSheet(self._get_button_style("secondary", "sm"))
        self.clipboard_btn.clicked.connect(self.gui.paste_and_extract)
        single_url_action.addWidget(self.clipboard_btn)

        single_url_action.addStretch()
        left_url_layout.addLayout(single_url_action)

        single_layout.addWidget(left_url_widget, 1)
        self.main_layout.addWidget(self.single_mode_container, 1)

        # ========== Mix Mode Container ==========
        self.mix_mode_container = QWidget()
        mix_layout = QVBoxLayout(self.mix_mode_container)
        mix_layout.setContentsMargins(0, 0, 0, 0)
        mix_layout.setSpacing(ds.spacing.space_3)

        mix_desc = QLabel("같은 상품 영상을 여러 개 넣으면 장면을 자동으로 섞어서 새 영상을 만들어 줍니다.")
        mix_desc.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        mix_desc.setStyleSheet(f"color: {get_color('text_muted')}; background-color: transparent; border: none; padding-bottom: 3px;")
        mix_desc.setWordWrap(True)
        mix_layout.addWidget(mix_desc)

        # URL entries only.
        left_mix_widget = QWidget()
        left_mix_layout = QVBoxLayout(left_mix_widget)
        left_mix_layout.setContentsMargins(0, 0, 0, 0)
        left_mix_layout.setSpacing(ds.spacing.space_2)

        mix_url_header = QLabel("영상 링크 붙여넣기 (최대 5개)")
        mix_url_header.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_sm, QFont.Weight.Bold))
        mix_url_header.setStyleSheet(f"color: {get_color('text_primary')}; background-color: transparent; border: none;")
        left_mix_layout.addWidget(mix_url_header)

        # URL entries container
        self.mix_entries_container = QWidget()
        self.mix_entries_layout = QVBoxLayout(self.mix_entries_container)
        self.mix_entries_layout.setContentsMargins(0, 0, 0, 0)
        self.mix_entries_layout.setSpacing(ds.spacing.space_2)
        left_mix_layout.addWidget(self.mix_entries_container)

        # Add URL button
        add_url_layout = QHBoxLayout()
        self.add_url_btn = QPushButton("+ 영상 링크 추가")
        self.add_url_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_url_btn.setStyleSheet(self._get_button_style("secondary", "sm"))
        self.add_url_btn.clicked.connect(self._add_mix_entry)
        add_url_layout.addWidget(self.add_url_btn)
        add_url_layout.addStretch()

        self.url_count_label = QLabel("1/5")
        self.url_count_label.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        self.url_count_label.setStyleSheet(f"color: {get_color('text_muted')}; background-color: transparent; border: none;")
        add_url_layout.addWidget(self.url_count_label)

        left_mix_layout.addLayout(add_url_layout)

        # Mix mode URL action buttons
        mix_action = QHBoxLayout()
        mix_action.setSpacing(ds.spacing.space_2)

        self.mix_add_btn = QPushButton("만들 목록에 담기")
        self.mix_add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mix_add_btn.setStyleSheet(self._get_button_style("primary", "sm"))
        self.mix_add_btn.clicked.connect(self._add_mix_to_queue)
        mix_action.addWidget(self.mix_add_btn)

        self.mix_clear_btn = QPushButton("모두 지우기")
        self.mix_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mix_clear_btn.setStyleSheet(self._get_button_style("ghost", "sm"))
        self.mix_clear_btn.clicked.connect(self._clear_mix_entries)
        mix_action.addWidget(self.mix_clear_btn)

        mix_action.addStretch()
        left_mix_layout.addLayout(mix_action)

        mix_layout.addWidget(left_mix_widget, 1)

        self.mix_mode_container.setVisible(False)
        self.main_layout.addWidget(self.mix_mode_container, 1)

        # Initialize with one mix entry
        self._add_mix_entry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Update UI based on current mode
        self._update_mode_ui()

    def _update_mode_ui(self):
        """모드에 따라 UI 업데이트"""
        mode = self._get_current_mode()

        if mode == "mix":
            self.mode_icon.setText("🎞️")
            self.mode_label.setText("믹스 모드 (영상 섞기)")
            self.single_mode_container.setVisible(False)
            self.mix_mode_container.setVisible(True)
        else:
            self.mode_icon.setText("🎬")
            self.mode_label.setText("단일 영상 만들기")
            self.single_mode_container.setVisible(True)
            self.mix_mode_container.setVisible(False)

    def _get_current_mode(self) -> str:
        """현재 모드 가져오기"""
        if hasattr(self.gui, 'state') and hasattr(self.gui.state, 'processing_mode'):
            return self.gui.state.processing_mode
        return "single"

    def _on_change_mode(self):
        """모드 변경 버튼 클릭"""
        if hasattr(self.gui, '_on_step_selected'):
            self.gui._on_step_selected('mode')
        if hasattr(self.gui, 'step_nav'):
            self.gui.step_nav.set_active('mode')

    def _add_mix_entry(self):
        """믹스 모드 URL 입력 추가"""
        if len(self._mix_entries) >= MAX_MIX_URLS:
            return

        entry = MixURLEntry(len(self._mix_entries))
        entry.url_changed.connect(self._on_mix_url_changed)
        entry.remove_requested.connect(self._remove_mix_entry)

        self._mix_entries.append(entry)
        self.mix_entries_layout.addWidget(entry)

        self._update_mix_ui()

    def _remove_mix_entry(self, index: int):
        """믹스 모드 URL 입력 제거"""
        if index < 0 or index >= len(self._mix_entries):
            return

        entry = self._mix_entries.pop(index)
        self.mix_entries_layout.removeWidget(entry)
        entry.deleteLater()

        # Update indices
        for i, e in enumerate(self._mix_entries):
            e.update_index(i)

        self._update_mix_ui()

    def _on_mix_url_changed(self, index: int, url: str):
        """믹스 URL 변경 시"""
        if hasattr(self.gui, 'state'):
            urls = [e.get_url() for e in self._mix_entries]
            self.gui.state.mix_video_urls = [u for u in urls if u]

    def _update_mix_ui(self):
        """믹스 모드 UI 업데이트"""
        count = len(self._mix_entries)
        self.url_count_label.setText(f"{count}/{MAX_MIX_URLS}")
        self.add_url_btn.setEnabled(count < MAX_MIX_URLS)

        if count >= MAX_MIX_URLS:
            self.add_url_btn.setText(f"최대 {MAX_MIX_URLS}개")
        else:
            self.add_url_btn.setText("+ 영상 링크 추가")

    def _add_mix_to_queue(self):
        """Add a mix job to the queue."""
        urls = [e.get_url() for e in self._mix_entries if e.get_url()]

        if len(urls) < MIN_MIX_URLS:
            from ui.components.custom_dialog import show_warning
            show_warning(self, "영상이 더 필요해요", f"믹스 모드는 영상 링크가 최소 {MIN_MIX_URLS}개 이상 필요합니다.")
            return

        if hasattr(self.gui, "state"):
            self.gui.state.mix_video_urls = list(urls)

        queue_manager = getattr(self.gui, "queue_manager", None)
        if queue_manager is None or not hasattr(queue_manager, "add_mix_job"):
            from ui.components.custom_dialog import show_warning
            show_warning(self, "잠시 문제가 생겼어요", "믹스 작업을 등록할 수 없습니다.")
            return

        try:
            queue_manager.add_mix_job(urls)
        except Exception as exc:
            from ui.components.custom_dialog import show_warning
            from user_facing_errors import sanitize_user_message
            show_warning(
                self,
                "목록에 담지 못했어요",
                sanitize_user_message(
                    exc,
                    fallback="영상 링크를 목록에 담지 못했어요. 입력 내용을 확인해 주세요.",
                ),
            )
            return

        from ui.components.custom_dialog import show_success
        show_success(self, "담았어요", f"영상 {len(urls)}개를 믹스 목록에 담았습니다.")

        self._clear_mix_entries()

    def _clear_mix_entries(self):
        """믹스 입력 초기화"""
        while len(self._mix_entries) > 1:
            entry = self._mix_entries.pop()
            self.mix_entries_layout.removeWidget(entry)
            entry.deleteLater()

        if self._mix_entries:
            self._mix_entries[0].set_url("")

        self._update_mix_ui()

        if hasattr(self.gui, 'state'):
            self.gui.state.mix_video_urls = []

    def refresh_mode(self):
        """외부에서 모드 변경 시 호출"""
        self._update_mode_ui()

    def eventFilter(self, obj, event):
        """Enter key triggers URL add (Shift+Enter for newline)"""
        if obj is self.gui.url_entry and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                    self.gui.add_url_from_entry()
                    return True
        return super().eventFilter(obj, event)

    # ================================================================
    # Style methods
    # ================================================================

    def _get_input_style(self) -> str:
        """Get input style using design system v2."""
        ds = self.ds
        return f"""
            QTextEdit {{
                background-color: {get_color('surface_variant')};
                /* Force high-contrast input text for dark UI builds */
                color: #FFFFFF;
                border: 1px solid {get_color('border')};
                border-radius: {ds.radius.base}px;
                padding: {ds.spacing.space_2}px;
                font-family: {ds.typography.font_family_primary};
                font-size: {ds.typography.size_sm}px;
                selection-background-color: {get_color('primary')};
                selection-color: #FFFFFF;
            }}
            QTextEdit:focus {{
                border: 2px solid {get_color('primary')};
            }}
            QTextEdit::placeholder {{
                color: {get_color('text_muted')};
            }}
        """

    def _get_button_style(self, variant: str = "primary", size: str = "md") -> str:
        """Get button style using design system v2."""
        ds = self.ds
        btn_size = ds.get_button_size(size)

        if variant == "primary":
            bg_color = get_color('primary')
            text_color = "white"
            hover_bg = "#C41230"
        elif variant == "secondary":
            bg_color = get_color('surface_variant')
            text_color = get_color('text_primary')
            hover_bg = get_color('border_light')
        else:  # ghost
            bg_color = "transparent"
            text_color = get_color('text_secondary')
            hover_bg = get_color('surface_variant')

        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: none;
                border-radius: {ds.radius.base}px;
                padding: 0 {btn_size.padding_x}px;
                height: {btn_size.height}px;
                font-family: {ds.typography.font_family_primary};
                font-size: {btn_size.font_size}px;
                font-weight: {ds.typography.weight_medium};
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
            }}
            QPushButton:disabled {{
                background-color: {get_color('surface_variant')};
                color: {get_color('text_muted')};
            }}
        """
