"""
CTA Selection Panel for PyQt6
"""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QScrollArea, QWidget, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal
from ui.components.base_widget import ThemedMixin
from managers.settings_manager import get_settings_manager
from ui.design_system_v2 import get_design_system, get_color

CTA_OPTIONS = [
    {"name": "댓글형", "id": "default", "description": "고정댓글로 유도하는 깔끔한 멘트", "lines": ["영상 속 제품 정보는", "아래 고정댓글에서", "확인해 보세요!"]},
    {"name": "캡션형", "id": "option1", "description": "캡션(본문) 확인을 유도하는 직관적 멘트", "lines": ["궁금하신 제품 정보는", "영상 하단 캡션에", "적어두었습니다."]},
    {"name": "직진형", "id": "option2", "description": "즉시 구매 링크 클릭을 유도하는 강력한 멘트", "lines": ["이 제품이 마음에 든다면", "하단 제품 링크를", "지금 눌러보세요!"]},
    {"name": "링크형", "id": "option3", "description": "추가 정보를 위해 링크 클릭을 유도하는 멘트", "lines": ["구매 정보가 궁금할 땐", "영상 아래 링크를", "바로 클릭하세요."]},
    {"name": "버튼형", "id": "option4", "description": "제품보기 버튼 클릭을 유도하는 안내 멘트", "lines": ["영상 속 핫템 정보는", "왼쪽 하단 버튼에서", "확인 가능합니다!"]},
    {"name": "할인형", "id": "option5", "description": "할인 혜택을 강조하는 멘트", "lines": ["지금 구매하면", "특별 할인 혜택이", "적용됩니다!"]},
    {"name": "한정형", "id": "option6", "description": "수량 한정 긴급함을 주는 멘트", "lines": ["수량 한정 상품!", "품절 전에", "서두르세요!"]},
    {"name": "후기형", "id": "option7", "description": "실제 후기 확인을 유도하는 멘트", "lines": ["실제 구매 후기가", "궁금하다면", "댓글을 확인하세요!"]},
    {"name": "질문형", "id": "option8", "description": "댓글 참여를 유도하는 멘트", "lines": ["이 제품 어떠세요?", "의견을 댓글로", "남겨주세요!"]},
    {"name": "팔로우형", "id": "option9", "description": "팔로우를 유도하는 멘트", "lines": ["더 많은 추천템은", "팔로우하고", "확인하세요!"]},
]

class CTACard(QFrame, ThemedMixin):
    clicked = pyqtSignal(str)

    def __init__(self, option, is_selected=False, theme_manager=None):
        super().__init__()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFrameShadow(QFrame.Shadow.Plain)  # Remove shadow
        self.option = option
        self.is_selected = is_selected
        self.ds = get_design_system()
        self.__init_themed__(theme_manager)
        self.create_widgets()
        self.apply_theme()

    def create_widgets(self):
        ds = self.ds
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.spacing.space_3, ds.spacing.space_2, ds.spacing.space_3, ds.spacing.space_2)
        
        # Header
        header = QHBoxLayout()
        icon_text = "📍" if self.option["id"] == "default" else "📝" if self.option["id"] == "option1" else "🔥"
        self.title_label = QLabel(f"{icon_text} {self.option['name']}")
        self.title_label.setStyleSheet(f"font-weight: {ds.typography.weight_bold}; font-size: 14px; color: #FFFFFF;")
        header.addWidget(self.title_label)
        header.addStretch()
        layout.addLayout(header)
        
        # Preview box
        self.preview_box = QFrame()
        preview_layout = QVBoxLayout(self.preview_box)
        preview_layout.setContentsMargins(ds.spacing.space_2, ds.spacing.space_1, ds.spacing.space_2, ds.spacing.space_1)
        preview_layout.setSpacing(2)
        
        for line in self.option["lines"]:
            lbl = QLabel(line)
            lbl.setStyleSheet(f"font-size: 12px; color: #FFFFFF;")
            preview_layout.addWidget(lbl)
            
        layout.addWidget(self.preview_box)
        
        # Description
        self.desc_label = QLabel(self.option["description"])
        self.desc_label.setStyleSheet(f"font-size: 12px; color: #B8B8B8;")
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.desc_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.option["id"])

    def apply_theme(self):
        ds = self.ds
        bg = get_color('surface_variant') if self.is_selected else get_color('surface')
        border = get_color('primary') if self.is_selected else get_color('border_light')
        thickness = 2 if self.is_selected else 1
        
        self.setStyleSheet(f"""
            CTACard {{
                background-color: {bg};
                border: {thickness}px solid {border};
                border-radius: {ds.radius.base}px;
            }}
        """)
        
        # No background on preview box - transparent
        self.preview_box.setStyleSheet(f"""
            QFrame {{
                background-color: transparent;
                border: none;
            }}
            QLabel {{
                color: #FFFFFF;
            }}
        """)
        
        primary_color = get_color('primary')
        text_primary = get_color('text_primary')
        self.title_label.setStyleSheet(f"color: {primary_color if self.is_selected else '#FFFFFF'}; border: none; font-weight: {ds.typography.weight_bold}; font-size: 14px;")
        self.desc_label.setStyleSheet(f"color: #B8B8B8; border: none; font-size: 12px;")

class CTAPanel(QFrame, ThemedMixin):
    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.cards = {}
        self.ds = get_design_system()
        self.__init_themed__(theme_manager)
        self.create_widgets()
        self.apply_theme()

    def create_widgets(self):
        ds = self.ds
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(ds.spacing.space_4, ds.spacing.space_3, ds.spacing.space_4, ds.spacing.space_3)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("CTA 선택")
        title.setStyleSheet(f"font-size: 16px; font-weight: {ds.typography.weight_bold}; color: #FFFFFF;")
        header.addWidget(title)
        
        header.addStretch()
        
        self.selected_badge = QLabel("✓ 선택됨")
        self.selected_badge.setStyleSheet(f"""
            background-color: {get_color('primary')};
            color: white;
            padding: {ds.spacing.space_1}px {ds.spacing.space_3}px;
            border-radius: {ds.radius.sm}px;
            font-weight: {ds.typography.weight_bold};
            font-size: {ds.typography.size_xs}px;
        """)
        header.addWidget(self.selected_badge)
        self.main_layout.addLayout(header)
        
        # Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(ds.spacing.space_2)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll.setWidget(self.grid_widget)
        self.main_layout.addWidget(self.scroll)
        
        self.rebuild_cards()

    def rebuild_cards(self):
        for i in reversed(range(self.grid_layout.count())):
            self.grid_layout.itemAt(i).widget().setParent(None)
            
        self.cards = {}
        selected_id = getattr(self.gui, 'selected_cta_id', 'default')
        
        for i, option in enumerate(CTA_OPTIONS):
            is_selected = option["id"] == selected_id
            card = CTACard(option, is_selected=is_selected, theme_manager=self.theme_manager)
            card.clicked.connect(self._on_card_clicked)
            
            row, col = divmod(i, 2)
            self.grid_layout.addWidget(card, row, col)
            self.cards[option["id"]] = card

    def _on_card_clicked(self, cta_id):
        self.gui.selected_cta_id = cta_id
        get_settings_manager().set_cta_id(cta_id)
        
        for cid, card in self.cards.items():
            card.is_selected = (cid == cta_id)
            card.apply_theme()

    def apply_theme(self):
        ds = self.ds
        bg = get_color('surface')
        self.setStyleSheet(f"background-color: {bg}; border: none;")
        self.scroll.setStyleSheet(f"background-color: {bg};")
        self.grid_widget.setStyleSheet(f"background-color: {bg};")

def get_selected_cta_lines(gui) -> list:
    selected_id = getattr(gui, 'selected_cta_id', 'default')
    for option in CTA_OPTIONS:
        if option["id"] == selected_id:
            return option["lines"]
    return CTA_OPTIONS[0]["lines"]
