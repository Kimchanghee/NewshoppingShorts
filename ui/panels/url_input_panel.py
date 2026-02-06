"""
URL Input Panel for PyQt6
Refactored to integrity with Main Shell Design System
Supports both single video mode and mix mode
"""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QWidget, QFrame, QLineEdit,
    QPushButton, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, QEvent, pyqtSignal
from PyQt6.QtGui import QFont
from ui.design_system_v2 import get_design_system, get_color

# Constants for mix mode
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
        self.url_input.setPlaceholderText(f"영상 URL #{self.index + 1} 입력...")
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
        self.url_input.setPlaceholderText(f"영상 URL #{self.index + 1} 입력...")
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

        # Main vertical layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(ds.spacing.space_5)

        # Mode indicator
        self.mode_indicator = QFrame()
        mode_layout = QHBoxLayout(self.mode_indicator)
        mode_layout.setContentsMargins(ds.spacing.space_3, ds.spacing.space_2, ds.spacing.space_3, ds.spacing.space_2)

        self.mode_icon = QLabel("🎬")
        self.mode_icon.setFont(QFont("Segoe UI Symbol", 16))
        mode_layout.addWidget(self.mode_icon)

        self.mode_label = QLabel("단일 영상 모드")
        self.mode_label.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_sm, QFont.Weight.Bold))
        self.mode_label.setStyleSheet(f"color: {get_color('text_primary')};")
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

        lbl = QLabel("쇼핑몰 상품 링크 또는 영상 URL 입력")
        lbl.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_sm, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {get_color('text_primary')};")
        single_layout.addWidget(lbl)

        self.gui.url_entry = QTextEdit()
        self.gui.url_entry.setFixedHeight(120)
        self.gui.url_entry.setPlaceholderText("https://www.tiktok.com/@user/video/...\nhttps://smartstore.naver.com/...")
        self.gui.url_entry.setStyleSheet(self._get_input_style())
        single_layout.addWidget(self.gui.url_entry)

        hint = QLabel("💡 팁: 여러 개의 링크를 붙여넣으면 자동으로 분리하여 목록에 추가됩니다.")
        hint.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        hint.setStyleSheet(f"color: {get_color('text_muted')};")
        single_layout.addWidget(hint)

        # Single mode action buttons
        single_action = QHBoxLayout()
        single_action.setSpacing(ds.spacing.space_3)

        self.add_btn = QPushButton("목록에 추가")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setStyleSheet(self._get_button_style("primary", "md"))
        self.add_btn.clicked.connect(self.gui.add_url_from_entry)
        single_action.addWidget(self.add_btn)

        self.clipboard_btn = QPushButton("클립보드에서 붙여넣기")
        self.clipboard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clipboard_btn.setStyleSheet(self._get_button_style("secondary", "md"))
        self.clipboard_btn.clicked.connect(self.gui.paste_and_extract)
        single_action.addWidget(self.clipboard_btn)

        single_action.addStretch()
        single_layout.addLayout(single_action)

        self.main_layout.addWidget(self.single_mode_container)

        # ========== Mix Mode Container ==========
        self.mix_mode_container = QWidget()
        mix_layout = QVBoxLayout(self.mix_mode_container)
        mix_layout.setContentsMargins(0, 0, 0, 0)
        mix_layout.setSpacing(ds.spacing.space_3)

        mix_header = QLabel("같은 상품의 영상 URL 입력 (최대 5개)")
        mix_header.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_sm, QFont.Weight.Bold))
        mix_header.setStyleSheet(f"color: {get_color('text_primary')};")
        mix_layout.addWidget(mix_header)

        mix_desc = QLabel("동일 상품의 여러 영상을 입력하면 랜덤으로 장면을 믹스하여 새로운 영상을 만듭니다.")
        mix_desc.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        mix_desc.setStyleSheet(f"color: {get_color('text_muted')};")
        mix_desc.setWordWrap(True)
        mix_layout.addWidget(mix_desc)

        # URL entries container
        self.mix_entries_container = QWidget()
        self.mix_entries_layout = QVBoxLayout(self.mix_entries_container)
        self.mix_entries_layout.setContentsMargins(0, 0, 0, 0)
        self.mix_entries_layout.setSpacing(ds.spacing.space_2)
        mix_layout.addWidget(self.mix_entries_container)

        # Add URL button
        add_url_layout = QHBoxLayout()
        self.add_url_btn = QPushButton("+ URL 추가")
        self.add_url_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_url_btn.setStyleSheet(self._get_button_style("secondary", "sm"))
        self.add_url_btn.clicked.connect(self._add_mix_entry)
        add_url_layout.addWidget(self.add_url_btn)
        add_url_layout.addStretch()

        self.url_count_label = QLabel("1/5")
        self.url_count_label.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        self.url_count_label.setStyleSheet(f"color: {get_color('text_muted')};")
        add_url_layout.addWidget(self.url_count_label)

        mix_layout.addLayout(add_url_layout)

        # Mix mode action buttons
        mix_action = QHBoxLayout()
        mix_action.setSpacing(ds.spacing.space_3)

        self.mix_add_btn = QPushButton("믹스 영상 대기열에 추가")
        self.mix_add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mix_add_btn.setStyleSheet(self._get_button_style("primary", "md"))
        self.mix_add_btn.clicked.connect(self._add_mix_to_queue)
        mix_action.addWidget(self.mix_add_btn)

        self.mix_clear_btn = QPushButton("모두 지우기")
        self.mix_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mix_clear_btn.setStyleSheet(self._get_button_style("ghost", "md"))
        self.mix_clear_btn.clicked.connect(self._clear_mix_entries)
        mix_action.addWidget(self.mix_clear_btn)

        mix_action.addStretch()
        mix_layout.addLayout(mix_action)

        self.mix_mode_container.setVisible(False)
        self.main_layout.addWidget(self.mix_mode_container)

        self.main_layout.addStretch()

        # Initialize with one mix entry
        self._add_mix_entry()

        # Enter key to add URL
        self.gui.url_entry.installEventFilter(self)

        # Update UI based on current mode
        self._update_mode_ui()

    def _update_mode_ui(self):
        """모드에 따라 UI 업데이트"""
        mode = self._get_current_mode()

        if mode == "mix":
            self.mode_icon.setText("🎞️")
            self.mode_label.setText("믹스 모드")
            self.single_mode_container.setVisible(False)
            self.mix_mode_container.setVisible(True)
        else:
            self.mode_icon.setText("🎬")
            self.mode_label.setText("단일 영상 모드")
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
            self.add_url_btn.setText("+ URL 추가")

    def _add_mix_to_queue(self):
        """믹스 영상을 대기열에 추가"""
        urls = [e.get_url() for e in self._mix_entries if e.get_url()]

        if len(urls) < MIN_MIX_URLS:
            from ui.components.custom_dialog import show_warning
            show_warning(self, "URL 부족", f"믹스 모드는 최소 {MIN_MIX_URLS}개 이상의 영상 URL이 필요합니다.")
            return

        # Store mix URLs in state
        if hasattr(self.gui, 'state'):
            self.gui.state.mix_video_urls = urls

        # Create a special mix entry in queue
        mix_identifier = f"[믹스] {len(urls)}개 영상"
        if hasattr(self.gui, 'queue_manager'):
            self.gui.queue_manager.add_url_to_queue(mix_identifier)

        from ui.components.custom_dialog import show_success
        show_success(self, "추가 완료", f"{len(urls)}개 영상이 믹스 대기열에 추가되었습니다.")

        # Clear entries
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

    def _get_input_style(self) -> str:
        """Get input style using design system v2."""
        ds = self.ds
        return f"""
            QTextEdit {{
                background-color: {get_color('surface_variant')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border')};
                border-radius: {ds.radius.base}px;
                padding: {ds.spacing.space_2}px;
                font-family: {ds.typography.font_family_primary};
                font-size: {ds.typography.size_sm}px;
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
