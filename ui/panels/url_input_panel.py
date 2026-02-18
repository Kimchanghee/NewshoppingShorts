"""
URL Input Panel for PyQt6
Refactored to integrity with Main Shell Design System
Supports both single video mode and mix mode
"""
import os

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QWidget, QFrame, QLineEdit,
    QPushButton, QScrollArea, QSizePolicy,
    QFileDialog
)
from PyQt6.QtCore import Qt, QEvent, pyqtSignal
from PyQt6.QtGui import QFont
from ui.design_system_v2 import get_design_system, get_color

# Constants for mix mode and local file selection
LOCAL_VIDEO_EXTENSIONS = "영상 파일 (*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm *.m4v);;모든 파일 (*)"
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
        self.setStyleSheet("QLabel { background-color: transparent; border: none; }")

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

        # --- Horizontal split: URL input (left 50%) | Local file (right 50%) ---
        single_split = QHBoxLayout()
        single_split.setSpacing(ds.spacing.space_4)

        # Left side: URL input
        left_url_widget = QWidget()
        left_url_layout = QVBoxLayout(left_url_widget)
        left_url_layout.setContentsMargins(0, 0, 0, 0)
        left_url_layout.setSpacing(ds.spacing.space_2)

        lbl = QLabel("URL 링크 입력")
        lbl.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_sm, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {get_color('text_primary')}; background-color: transparent; border: none;")
        left_url_layout.addWidget(lbl)

        self.gui.url_entry = QTextEdit()
        self.gui.url_entry.setFixedHeight(120)
        self.gui.url_entry.setPlaceholderText(
            "https://v.douyin.com/xxxxx/\nhttps://www.xiaohongshu.com/explore/xxxxxxxx..."
        )
        self.gui.url_entry.setStyleSheet(self._get_input_style())
        left_url_layout.addWidget(self.gui.url_entry)

        hint = QLabel("💡 여러 링크를 붙여넣으면 자동 분리됩니다.")
        hint.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        hint.setStyleSheet(f"color: {get_color('text_muted')}; background-color: transparent; border: none;")
        left_url_layout.addWidget(hint)

        # Single mode URL action buttons
        single_url_action = QHBoxLayout()
        single_url_action.setSpacing(ds.spacing.space_2)

        self.add_btn = QPushButton("목록에 추가")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setStyleSheet(self._get_button_style("primary", "sm"))
        self.add_btn.clicked.connect(self.gui.add_url_from_entry)
        single_url_action.addWidget(self.add_btn)

        self.clipboard_btn = QPushButton("클립보드 붙여넣기")
        self.clipboard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clipboard_btn.setStyleSheet(self._get_button_style("secondary", "sm"))
        self.clipboard_btn.clicked.connect(self.gui.paste_and_extract)
        single_url_action.addWidget(self.clipboard_btn)

        single_url_action.addStretch()
        left_url_layout.addLayout(single_url_action)

        single_split.addWidget(left_url_widget, 1)

        # Vertical divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setStyleSheet(f"color: {get_color('border_light')};")
        single_split.addWidget(divider)

        # Right side: Local file selection
        right_local_widget = QWidget()
        right_local_layout = QVBoxLayout(right_local_widget)
        right_local_layout.setContentsMargins(0, 0, 0, 0)
        right_local_layout.setSpacing(ds.spacing.space_2)

        local_lbl = QLabel("로컬 영상 파일 선택")
        local_lbl.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_sm, QFont.Weight.Bold))
        local_lbl.setStyleSheet(f"color: {get_color('text_primary')}; background-color: transparent; border: none;")
        right_local_layout.addWidget(local_lbl)

        # Drop zone / file display area
        self.single_local_drop_zone = QFrame()
        self.single_local_drop_zone.setFixedHeight(120)
        self.single_local_drop_zone.setStyleSheet(self._get_drop_zone_style())
        drop_zone_layout = QVBoxLayout(self.single_local_drop_zone)
        drop_zone_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.single_local_icon = QLabel("📁")
        self.single_local_icon.setFont(QFont("Segoe UI Symbol", 24))
        self.single_local_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.single_local_icon.setStyleSheet("background-color: transparent; border: none;")
        drop_zone_layout.addWidget(self.single_local_icon)

        self.single_local_file_label = QLabel("파일을 선택하세요")
        self.single_local_file_label.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        self.single_local_file_label.setStyleSheet(f"color: {get_color('text_muted')}; background-color: transparent; border: none;")
        self.single_local_file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.single_local_file_label.setWordWrap(True)
        drop_zone_layout.addWidget(self.single_local_file_label)

        right_local_layout.addWidget(self.single_local_drop_zone)

        local_hint = QLabel("💡 MP4, AVI, MOV 등 영상 파일 지원")
        local_hint.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        local_hint.setStyleSheet(f"color: {get_color('text_muted')}; background-color: transparent; border: none;")
        right_local_layout.addWidget(local_hint)

        # Local file action buttons
        single_local_action = QHBoxLayout()
        single_local_action.setSpacing(ds.spacing.space_2)

        self.single_browse_btn = QPushButton("파일 찾기")
        self.single_browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.single_browse_btn.setStyleSheet(self._get_button_style("primary", "sm"))
        self.single_browse_btn.clicked.connect(lambda: self._select_local_file("single"))
        single_local_action.addWidget(self.single_browse_btn)

        self.single_local_add_btn = QPushButton("목록에 추가")
        self.single_local_add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.single_local_add_btn.setStyleSheet(self._get_button_style("secondary", "sm"))
        self.single_local_add_btn.clicked.connect(lambda: self._add_local_file_to_queue("single"))
        self.single_local_add_btn.setEnabled(False)
        single_local_action.addWidget(self.single_local_add_btn)

        single_local_action.addStretch()
        right_local_layout.addLayout(single_local_action)

        single_split.addWidget(right_local_widget, 1)

        single_layout.addLayout(single_split)
        self.main_layout.addWidget(self.single_mode_container)

        # ========== Mix Mode Container ==========
        self.mix_mode_container = QWidget()
        mix_layout = QVBoxLayout(self.mix_mode_container)
        mix_layout.setContentsMargins(0, 0, 0, 0)
        mix_layout.setSpacing(ds.spacing.space_3)

        mix_desc = QLabel("동일 상품의 여러 영상을 입력하면 랜덤으로 장면을 믹스하여 새로운 영상을 만듭니다.")
        mix_desc.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        mix_desc.setStyleSheet(f"color: {get_color('text_muted')}; background-color: transparent; border: none;")
        mix_desc.setWordWrap(True)
        mix_layout.addWidget(mix_desc)

        # --- Horizontal split: URL input (left 50%) | Local file (right 50%) ---
        mix_split = QHBoxLayout()
        mix_split.setSpacing(ds.spacing.space_4)

        # Left side: URL entries
        left_mix_widget = QWidget()
        left_mix_layout = QVBoxLayout(left_mix_widget)
        left_mix_layout.setContentsMargins(0, 0, 0, 0)
        left_mix_layout.setSpacing(ds.spacing.space_2)

        mix_url_header = QLabel("URL 입력 (최대 5개)")
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
        self.add_url_btn = QPushButton("+ URL 추가")
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

        self.mix_add_btn = QPushButton("대기열에 추가")
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

        mix_split.addWidget(left_mix_widget, 1)

        # Vertical divider
        mix_divider = QFrame()
        mix_divider.setFrameShape(QFrame.Shape.VLine)
        mix_divider.setStyleSheet(f"color: {get_color('border_light')};")
        mix_split.addWidget(mix_divider)

        # Right side: Local file selection for mix
        right_mix_local = QWidget()
        right_mix_local_layout = QVBoxLayout(right_mix_local)
        right_mix_local_layout.setContentsMargins(0, 0, 0, 0)
        right_mix_local_layout.setSpacing(ds.spacing.space_2)

        mix_local_header = QLabel("로컬 영상 파일 선택")
        mix_local_header.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_sm, QFont.Weight.Bold))
        mix_local_header.setStyleSheet(f"color: {get_color('text_primary')}; background-color: transparent; border: none;")
        right_mix_local_layout.addWidget(mix_local_header)

        # Drop zone for mix local files
        self.mix_local_drop_zone = QFrame()
        self.mix_local_drop_zone.setFixedHeight(120)
        self.mix_local_drop_zone.setStyleSheet(self._get_drop_zone_style())
        mix_drop_layout = QVBoxLayout(self.mix_local_drop_zone)
        mix_drop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.mix_local_icon = QLabel("📁")
        self.mix_local_icon.setFont(QFont("Segoe UI Symbol", 24))
        self.mix_local_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mix_local_icon.setStyleSheet("background-color: transparent; border: none;")
        mix_drop_layout.addWidget(self.mix_local_icon)

        self.mix_local_file_label = QLabel("파일을 선택하세요")
        self.mix_local_file_label.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        self.mix_local_file_label.setStyleSheet(f"color: {get_color('text_muted')}; background-color: transparent; border: none;")
        self.mix_local_file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mix_local_file_label.setWordWrap(True)
        mix_drop_layout.addWidget(self.mix_local_file_label)

        right_mix_local_layout.addWidget(self.mix_local_drop_zone)

        # Selected files list for mix
        self.mix_local_files_list = QLabel("")
        self.mix_local_files_list.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        self.mix_local_files_list.setStyleSheet(f"color: {get_color('text_secondary')}; background-color: transparent; border: none;")
        self.mix_local_files_list.setWordWrap(True)
        right_mix_local_layout.addWidget(self.mix_local_files_list)

        # Mix local file action buttons
        mix_local_action = QHBoxLayout()
        mix_local_action.setSpacing(ds.spacing.space_2)

        self.mix_local_browse_btn = QPushButton("파일 추가")
        self.mix_local_browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mix_local_browse_btn.setStyleSheet(self._get_button_style("primary", "sm"))
        self.mix_local_browse_btn.clicked.connect(lambda: self._select_local_file("mix"))
        mix_local_action.addWidget(self.mix_local_browse_btn)

        self.mix_local_add_btn = QPushButton("대기열에 추가")
        self.mix_local_add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mix_local_add_btn.setStyleSheet(self._get_button_style("secondary", "sm"))
        self.mix_local_add_btn.clicked.connect(lambda: self._add_local_file_to_queue("mix"))
        self.mix_local_add_btn.setEnabled(False)
        mix_local_action.addWidget(self.mix_local_add_btn)

        self.mix_local_clear_btn = QPushButton("초기화")
        self.mix_local_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mix_local_clear_btn.setStyleSheet(self._get_button_style("ghost", "sm"))
        self.mix_local_clear_btn.clicked.connect(self._clear_mix_local_files)
        mix_local_action.addWidget(self.mix_local_clear_btn)

        mix_local_action.addStretch()
        right_mix_local_layout.addLayout(mix_local_action)

        mix_split.addWidget(right_mix_local, 1)

        mix_layout.addLayout(mix_split)

        self.mix_mode_container.setVisible(False)
        self.main_layout.addWidget(self.mix_mode_container)

        self.main_layout.addStretch()

        # Local file state
        self._single_local_path = ""  # Selected local file for single mode
        self._mix_local_paths = []  # Selected local files for mix mode

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
        """Add a mix job to the queue."""
        urls = [e.get_url() for e in self._mix_entries if e.get_url()]

        if len(urls) < MIN_MIX_URLS:
            from ui.components.custom_dialog import show_warning
            show_warning(self, "URL 부족", f"믹스 모드는 최소 {MIN_MIX_URLS}개 이상의 영상 URL이 필요합니다.")
            return

        if hasattr(self.gui, "state"):
            self.gui.state.mix_video_urls = list(urls)

        queue_manager = getattr(self.gui, "queue_manager", None)
        if queue_manager is None or not hasattr(queue_manager, "add_mix_job"):
            from ui.components.custom_dialog import show_warning
            show_warning(self, "오류", "믹스 작업을 등록할 수 없습니다.")
            return

        try:
            queue_manager.add_mix_job(urls)
        except Exception as exc:
            from ui.components.custom_dialog import show_warning
            show_warning(self, "오류", f"믹스 대기열 추가 실패: {exc}")
            return

        from ui.components.custom_dialog import show_success
        show_success(self, "추가 완료", f"{len(urls)}개 영상을 믹스 대기열에 추가했습니다.")

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
    # Local file selection methods
    # ================================================================

    def _select_local_file(self, mode: str):
        """Open file dialog to select local video file(s)."""
        if mode == "mix":
            # Allow multiple file selection for mix mode
            files, _ = QFileDialog.getOpenFileNames(
                self, "로컬 영상 파일 선택", "",
                LOCAL_VIDEO_EXTENSIONS
            )
            if files:
                remaining = MAX_MIX_URLS - len(self._mix_local_paths)
                for f in files[:remaining]:
                    if f not in self._mix_local_paths:
                        self._mix_local_paths.append(f)
                self._update_mix_local_ui()
        else:
            # Single file selection
            file_path, _ = QFileDialog.getOpenFileName(
                self, "로컬 영상 파일 선택", "",
                LOCAL_VIDEO_EXTENSIONS
            )
            if file_path:
                self._single_local_path = file_path
                filename = os.path.basename(file_path)
                self.single_local_file_label.setText(filename)
                self.single_local_file_label.setStyleSheet(
                    f"color: {get_color('text_primary')}; background-color: transparent; border: none;"
                )
                self.single_local_icon.setText("🎬")
                self.single_local_add_btn.setEnabled(True)
                self.single_local_drop_zone.setStyleSheet(self._get_drop_zone_style(active=True))

    def _add_local_file_to_queue(self, mode: str):
        """Add selected local file(s) to the processing queue."""
        from ui.components.custom_dialog import show_warning, show_success

        if mode == "mix":
            if len(self._mix_local_paths) < MIN_MIX_URLS:
                show_warning(self, "파일 부족",
                             f"믹스 모드는 최소 {MIN_MIX_URLS}개 이상의 영상 파일이 필요합니다.")
                return

            # Set state for local processing
            if hasattr(self.gui, 'state'):
                self.gui.state.video_source = "local"
                self.gui.state.mix_video_urls = []

            # Add each local file as a local:// prefixed entry to queue
            queue_manager = getattr(self.gui, "queue_manager", None)
            if queue_manager and hasattr(queue_manager, "add_mix_job"):
                local_urls = [f"local://{p}" for p in self._mix_local_paths]
                try:
                    queue_manager.add_mix_job(local_urls)
                    show_success(self, "추가 완료",
                                 f"{len(self._mix_local_paths)}개 로컬 영상을 믹스 대기열에 추가했습니다.")
                    self._clear_mix_local_files()
                except Exception as exc:
                    show_warning(self, "오류", f"대기열 추가 실패: {exc}")
            else:
                show_warning(self, "오류", "대기열 관리자를 찾을 수 없습니다.")
        else:
            # Single mode
            if not self._single_local_path or not os.path.isfile(self._single_local_path):
                show_warning(self, "안내", "로컬 영상 파일을 먼저 선택해주세요.")
                return

            # Set state for local processing
            if hasattr(self.gui, 'state'):
                self.gui.state.video_source = "local"
                self.gui.state.local_file_path = self._single_local_path

            # Add to queue with local:// prefix so queue manager can differentiate
            queue_manager = getattr(self.gui, "queue_manager", None)
            if queue_manager and hasattr(queue_manager, "add_url_to_queue"):
                local_url = f"local://{self._single_local_path}"
                added = queue_manager.add_url_to_queue(local_url)
                if added:
                    show_success(self, "추가 완료",
                                 f"로컬 영상이 대기열에 추가되었습니다.\n{os.path.basename(self._single_local_path)}")
                    self._reset_single_local()
                else:
                    show_warning(self, "안내", "이미 대기열에 있는 파일입니다.")
            else:
                show_warning(self, "오류", "대기열 관리자를 찾을 수 없습니다.")

    def _reset_single_local(self):
        """Reset single mode local file selection."""
        self._single_local_path = ""
        self.single_local_file_label.setText("파일을 선택하세요")
        self.single_local_file_label.setStyleSheet(
            f"color: {get_color('text_muted')}; background-color: transparent; border: none;"
        )
        self.single_local_icon.setText("📁")
        self.single_local_add_btn.setEnabled(False)
        self.single_local_drop_zone.setStyleSheet(self._get_drop_zone_style())

    def _update_mix_local_ui(self):
        """Update mix mode local file display."""
        count = len(self._mix_local_paths)
        if count == 0:
            self.mix_local_file_label.setText("파일을 선택하세요")
            self.mix_local_file_label.setStyleSheet(
                f"color: {get_color('text_muted')}; background-color: transparent; border: none;"
            )
            self.mix_local_icon.setText("📁")
            self.mix_local_add_btn.setEnabled(False)
            self.mix_local_drop_zone.setStyleSheet(self._get_drop_zone_style())
            self.mix_local_files_list.setText("")
        else:
            self.mix_local_file_label.setText(f"{count}개 파일 선택됨")
            self.mix_local_file_label.setStyleSheet(
                f"color: {get_color('text_primary')}; background-color: transparent; border: none;"
            )
            self.mix_local_icon.setText("🎬")
            self.mix_local_add_btn.setEnabled(count >= MIN_MIX_URLS)
            self.mix_local_drop_zone.setStyleSheet(self._get_drop_zone_style(active=True))
            # Show file names
            names = [f"  {i+1}. {os.path.basename(p)}" for i, p in enumerate(self._mix_local_paths)]
            self.mix_local_files_list.setText("\n".join(names))

    def _clear_mix_local_files(self):
        """Clear mix mode local file selections."""
        self._mix_local_paths = []
        self._update_mix_local_ui()

    def _get_drop_zone_style(self, active: bool = False) -> str:
        """Get style for the file drop zone."""
        ds = self.ds
        if active:
            border_color = get_color('primary')
            bg_color = get_color('surface_variant')
        else:
            border_color = get_color('border_light')
            bg_color = get_color('surface_variant')
        return f"""
            QFrame {{
                background-color: {bg_color};
                border: 2px dashed {border_color};
                border-radius: {ds.radius.base}px;
            }}
            QFrame:hover {{
                border-color: {get_color('primary')};
                background-color: {get_color('surface_variant')};
            }}
        """

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
