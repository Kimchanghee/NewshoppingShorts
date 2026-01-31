"""
Queue Panel for PyQt6
"""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QTreeWidget, QTreeWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt
from ui.components.rounded_widgets import create_rounded_button
from ui.components.base_widget import ThemedMixin

class QueuePanel(QFrame, ThemedMixin):
    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.__init_themed__(theme_manager)
        self.create_widgets()
        self.apply_theme()

    def create_widgets(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(18, 16, 18, 16)
        
        # Header
        self.title_label = QLabel("제작 대기열")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.main_layout.addWidget(self.title_label)
        
        self.subtitle_label = QLabel("대기 | 완료 | 실패 건수를 자동으로 추적합니다.")
        self.subtitle_label.setStyleSheet("font-size: 11px;")
        self.main_layout.addWidget(self.subtitle_label)
        
        # Control Buttons
        control_layout = QHBoxLayout()
        self.gui.start_batch_button = create_rounded_button(self, "▶ 작업 시작", self.gui.start_batch_processing)
        control_layout.addWidget(self.gui.start_batch_button)
        
        self.gui.stop_batch_button = create_rounded_button(self, "■ 작업 중지", self.gui.stop_batch_processing, style="secondary")
        self.gui.stop_batch_button.setEnabled(False)
        control_layout.addWidget(self.gui.stop_batch_button)
        
        self.clear_waiting_btn = create_rounded_button(self, "대기중 삭제", self.gui.clear_waiting_only, style="secondary")
        control_layout.addWidget(self.clear_waiting_btn)
        
        control_layout.addStretch()
        self.main_layout.addLayout(control_layout)
        
        # TreeWidget (Replacement for Treeview)
        self.gui.url_listbox = QTreeWidget()
        self.gui.url_listbox.setColumnCount(4)
        self.gui.url_listbox.setHeaderLabels(["구분", "URL", "상태", "비고"])
        self.gui.url_listbox.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.gui.url_listbox.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.gui.url_listbox.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.gui.url_listbox.header().resizeSection(2, 100)
        self.gui.url_listbox.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
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

    def apply_theme(self):
        bg = self.get_color("bg_card")
        border = self.get_color("border_light")
        text_primary = self.get_color("text_primary")
        text_secondary = self.get_color("text_secondary")
        
        self.setStyleSheet(f"background-color: {bg}; border: 1px solid {border}; border-radius: 8px;")
        self.title_label.setStyleSheet(f"color: {text_primary}; font-weight: bold; border: none;")
        self.subtitle_label.setStyleSheet(f"color: {text_secondary}; border: none;")
        
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
