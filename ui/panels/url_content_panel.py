"""
URL Content Panel for PyQt6
"""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QTextEdit, QWidget
)
from PyQt6.QtCore import Qt
from ui.components.tab_container import TabContent
from ui.components.rounded_widgets import create_rounded_button

class URLContentPanel(TabContent):
    """Refactored URL input panel for PyQt6"""
    
    def __init__(self, parent, gui, theme_manager=None):
        self.gui = gui
        super().__init__(parent, theme_manager=theme_manager)
        self.create_widgets()

    def create_widgets(self):
        # Step Header
        header_layout = QHBoxLayout()
        
        badge = QLabel("1단계")
        badge.setStyleSheet(f"""
            background-color: {self.get_color("primary")};
            color: white;
            padding: 4px 12px;
            border-radius: 4px;
            font-weight: bold;
        """)
        header_layout.addWidget(badge)
        
        title = QLabel("링크 입력")
        title.setStyleSheet(f"""
            color: {self.get_color("text_primary")};
            font-size: 18px;
            font-weight: bold;
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()
        self.inner_layout.addLayout(header_layout)
        self.inner_layout.addSpacing(20)
        
        # URL Input Card
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {self.get_color("bg_card")};
                border: 1px solid {self.get_color("border_light")};
                border-radius: 12px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        
        card_title = QLabel("틱톡 / 더우인 링크를 입력하세요")
        card_title.setStyleSheet(f"color: {self.get_color('text_primary')}; font-size: 14px; font-weight: bold; border: none;")
        card_layout.addWidget(card_title)
        
        card_subtitle = QLabel("여러 개의 링크를 한 번에 붙여넣을 수 있습니다. (최대 30개)")
        card_subtitle.setStyleSheet(f"color: {self.get_color('text_secondary')}; font-size: 13px; border: none;")
        card_layout.addWidget(card_subtitle)
        card_layout.addSpacing(12)
        
        self.url_entry = QTextEdit()
        self.url_entry.setPlaceholderText("https://...")
        self.url_entry.setFixedHeight(150)
        self.url_entry.setStyleSheet(f"""
            QTextEdit {{
                background-color: {self.get_color("bg_input")};
                /* Force high-contrast input text for dark UI builds */
                color: #FFFFFF;
                border: 1px solid {self.get_color("border_light")};
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
                selection-background-color: {self.get_color("primary")};
                selection-color: #FFFFFF;
            }}
            QTextEdit:focus {{
                border: 2px solid {self.get_color("border_focus")};
            }}
        """)
        # Link for gui compatibility
        self.gui.url_entry = self.url_entry
        card_layout.addWidget(self.url_entry)
        
        # Example text
        example = QLabel("예: https://v.douyin.com/xxxxx/ 또는 https://vm.tiktok.com/xxxxx/")
        example.setStyleSheet(f"color: {self.get_color('text_disabled')}; font-size: 12px; border: none;")
        card_layout.addWidget(example)
        card_layout.addSpacing(16)
        
        # Buttons Row
        btn_layout = QHBoxLayout()
        self.add_btn = create_rounded_button(card, "링크 추가", self.gui.add_url_from_entry)
        btn_layout.addWidget(self.add_btn)
        
        self.clipboard_btn = create_rounded_button(card, "클립보드에서 추가", self.gui.paste_and_extract, style="secondary")
        btn_layout.addWidget(self.clipboard_btn)
        
        btn_layout.addStretch()
        
        self.url_count_label = QLabel("링크: 0/30")
        self.url_count_label.setStyleSheet(f"color: {self.get_color('text_secondary')}; border: none;")
        btn_layout.addWidget(self.url_count_label)
        
        card_layout.addLayout(btn_layout)
        self.inner_layout.addWidget(card)
        
        # Guide/Next step card
        guide_card = QFrame()
        guide_card.setStyleSheet(f"""
            QFrame {{
                background-color: {self.get_color("info_bg")};
                border: 1px solid {self.get_color("info")};
                border-radius: 8px;
            }}
        """)
        guide_layout = QHBoxLayout(guide_card)
        guide_layout.setContentsMargins(16, 12, 16, 12)
        
        info_icon = QLabel("i")
        info_icon.setFixedSize(24, 24)
        info_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_icon.setStyleSheet(f"""
            background-color: {self.get_color("info")};
            color: white;
            border-radius: 12px;
            font-weight: bold;
        """)
        guide_layout.addWidget(info_icon)
        
        guide_text = QLabel("링크 추가 후 '스타일' 단계에서 음성과 폰트를 선택하세요")
        guide_text.setStyleSheet(f"color: {self.get_color('info')}; border: none;")
        guide_layout.addWidget(guide_text)
        
        guide_layout.addStretch()
        
        self.next_btn = create_rounded_button(guide_card, "다음: 스타일 선택 >", self._go_next_step, style="outline")
        guide_layout.addWidget(self.next_btn)
        
        self.inner_layout.addSpacing(16)
        self.inner_layout.addWidget(guide_card)
        self.inner_layout.addStretch()

    def _go_next_step(self):
        if hasattr(self.gui, 'sidebar_container') and self.gui.sidebar_container:
            self.gui.sidebar_container.go_next()

    def update_url_count(self, count):
        self.url_count_label.setText(f"링크: {count}/30")
