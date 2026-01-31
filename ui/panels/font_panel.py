"""
Font Selection Panel for PyQt6
"""
import os
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QScrollArea, QWidget, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QFontDatabase
from ui.components.base_widget import ThemedMixin
from managers.settings_manager import get_settings_manager

class FontCard(QFrame, ThemedMixin):
    clicked = pyqtSignal(str)

    def __init__(self, option, is_selected=False, theme_manager=None):
        super().__init__()
        self.option = option
        self.is_selected = is_selected
        self.__init_themed__(theme_manager)
        
        self.create_widgets()
        self.apply_theme()

    def create_widgets(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        
        # Radio indicator simulation
        self.radio_label = QLabel("●" if self.is_selected else "○")
        self.radio_label.setFixedWidth(24)
        layout.addWidget(self.radio_label)
        
        # Info area
        info_layout = QVBoxLayout()
        self.name_label = QLabel(self.option["name"])
        self.name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        info_layout.addWidget(self.name_label)
        
        self.desc_label = QLabel(self.option["description"])
        self.desc_label.setStyleSheet("font-size: 11px;")
        info_layout.addWidget(self.desc_label)
        layout.addLayout(info_layout)
        
        layout.addStretch()
        
        # Preview text
        self.preview_label = QLabel(self.option["preview"])
        # Attempt to load font for preview
        font_id = -1
        for fp in self.option.get("font_paths", []):
            if os.path.exists(fp):
                font_id = QFontDatabase.addApplicationFont(fp)
                if font_id != -1:
                    family = QFontDatabase.applicationFontFamilies(font_id)[0]
                    self.preview_label.setFont(QFont(family, 16))
                    break
        
        if font_id == -1:
             self.preview_label.setFont(QFont("Arial", 16))
             
        layout.addWidget(self.preview_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.option["id"])

    def apply_theme(self):
        bg = self.get_color("bg_selected") if self.is_selected else self.get_color("bg_card")
        border = self.get_color("primary") if self.is_selected else self.get_color("border_light")
        thickness = 2 if self.is_selected else 1
        
        self.setStyleSheet(f"""
            FontCard {{
                background-color: {bg};
                border: {thickness}px solid {border};
                border-radius: 8px;
            }}
        """)
        
        text_primary = self.get_color("text_primary")
        text_secondary = self.get_color("text_secondary")
        self.name_label.setStyleSheet(f"color: {text_primary}; border: none; font-weight: bold;")
        self.desc_label.setStyleSheet(f"color: {text_secondary}; border: none;")
        self.radio_label.setStyleSheet(f"color: {self.get_color('primary') if self.is_selected else text_secondary}; border: none;")
        self.preview_label.setStyleSheet(f"color: {text_primary}; border: none;")

class FontPanel(QFrame, ThemedMixin):
    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.cards = {}
        self.__init_themed__(theme_manager)
        self.create_widgets()
        self.apply_theme()

    def create_widgets(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 12, 16, 12)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("폰트 선택")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        
        header.addStretch()
        
        self.selected_display = QLabel("선택됨")
        self.selected_display.setStyleSheet(f"""
            background-color: {self.get_color("primary")};
            color: white;
            padding: 4px 12px;
            border-radius: 4px;
            font-weight: bold;
        """)
        header.addWidget(self.selected_display)
        self.main_layout.addLayout(header)
        
        # Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setSpacing(8)
        self.scroll.setWidget(self.scroll_content)
        self.main_layout.addWidget(self.scroll)
        
        self.rebuild_cards()

    def rebuild_cards(self):
        for i in reversed(range(self.scroll_layout.count())):
            self.scroll_layout.itemAt(i).widget().setParent(None)
            
        self.cards = {}
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        fonts_dir = os.path.join(project_root, "fonts")
        
        font_options = [
            {"name": "서울 한강체", "id": "seoul_hangang", "preview": "쇼핑 숏폼 자막", "description": "모던하고 깔끔한 서울시 공식 폰트", "font_paths": [os.path.join(fonts_dir, "SeoulHangangB.ttf")]},
            {"name": "프리텐다드", "id": "pretendard", "preview": "쇼핑 숏폼 자막", "description": "세련된 현대적 고딕체", "font_paths": [os.path.join(fonts_dir, "Pretendard-ExtraBold.ttf")]},
            {"name": "G마켓 산스", "id": "gmarketsans", "preview": "쇼핑 숏폼 자막", "description": "인기 있는 고품질 무료 폰트", "font_paths": [os.path.join(fonts_dir, "GmarketSansTTFBold.ttf")]},
            {"name": "페이퍼로지", "id": "paperlogy", "preview": "쇼핑 숏폼 자막", "description": "부드러운 곡선이 매력적인 폰트", "font_paths": [os.path.join(fonts_dir, "Paperlogy-9Black.ttf")]},
            {"name": "유앤피플", "id": "unpeople_gothic", "preview": "쇼핑 숏폼 자막", "description": "부드럽고 가독성 좋은 고딕체", "font_paths": [os.path.join(fonts_dir, "UnPeople.ttf")]}
        ]
        
        selected_id = getattr(self.gui, 'selected_font_id', 'seoul_hangang')
        
        for option in font_options:
            is_selected = option["id"] == selected_id
            card = FontCard(option, is_selected=is_selected, theme_manager=self.theme_manager)
            card.clicked.connect(self._on_card_clicked)
            self.scroll_layout.addWidget(card)
            self.cards[option["id"]] = card
            
        self.scroll_layout.addStretch()

    def _on_card_clicked(self, font_id):
        self.gui.selected_font_id = font_id
        get_settings_manager().set_font_id(font_id)
        
        for fid, card in self.cards.items():
            card.is_selected = (fid == font_id)
            card.apply_theme()

    def apply_theme(self):
        bg = self.get_color("bg_card")
        self.setStyleSheet(f"background-color: {bg}; border: none;")
        self.scroll.setStyleSheet(f"background-color: {bg};")
        self.scroll_content.setStyleSheet(f"background-color: {bg};")
