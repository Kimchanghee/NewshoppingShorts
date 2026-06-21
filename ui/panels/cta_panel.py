"""
CTA Selection Panel for PyQt6
"""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QWidget, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from ui.components.base_widget import ThemedMixin
from managers.settings_manager import get_settings_manager
from ui.design_system_v2 import get_design_system, get_color

CTA_OPTIONS = [
    {"name": "댓글형", "id": "default", "description": "고정 댓글을 보게 하는 깔끔한 문구", "lines": ["영상 속 제품 정보는", "아래 고정댓글에서", "확인해 보세요!"]},
    {"name": "캡션형", "id": "option1", "description": "영상 아래 설명글을 보게 하는 문구", "lines": ["궁금하신 제품 정보는", "영상 하단 캡션에", "적어두었습니다."]},
    {"name": "직진형", "id": "option2", "description": "바로 구매 링크를 누르게 하는 강한 문구", "lines": ["이 제품이 마음에 든다면", "하단 제품 링크를", "지금 눌러보세요!"]},
    {"name": "링크형", "id": "option3", "description": "영상 아래 링크를 누르게 하는 문구", "lines": ["구매 정보가 궁금할 땐", "영상 아래 링크를", "바로 클릭하세요."]},
    {"name": "버튼형", "id": "option4", "description": "제품 보기 버튼을 누르게 하는 안내 문구", "lines": ["영상 속 핫템 정보는", "왼쪽 하단 버튼에서", "확인 가능합니다!"]},
    {"name": "프로필 링크형", "id": "option5", "description": "프로필에 있는 링크를 보게 하는 문구", "lines": ["더 많은 제품 정보는", "프로필 링크를", "참고해 주세요!"]},
    {"name": "한정형", "id": "option6", "description": "수량이 얼마 없다고 알려 서두르게 하는 문구", "lines": ["수량 한정 상품!", "품절 전에", "서두르세요!"]},
    {"name": "질문형", "id": "option8", "description": "댓글을 달고 싶게 만드는 문구", "lines": ["이 제품 어떠세요?", "의견을 댓글로", "남겨주세요!"]},
    {"name": "팔로우형", "id": "option9", "description": "팔로우하게 만드는 문구", "lines": ["더 많은 추천템은", "팔로우하고", "확인하세요!"]},
]

class CTACard(QFrame, ThemedMixin):
    clicked = pyqtSignal(str)

    def __init__(self, option, is_selected=False, theme_manager=None):
        super().__init__()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFrameShadow(QFrame.Shadow.Plain)  # Remove shadow
        # 카드가 세로로 늘어나 빈 공간이 생기지 않도록 내용 높이에 맞춘다.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.setMinimumWidth(150)
        self.option = option
        self.is_selected = is_selected
        self.ds = get_design_system()
        self.__init_themed__(theme_manager)
        self.create_widgets()
        self.apply_theme()

    def create_widgets(self):
        ds = self.ds
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.spacing.space_2, ds.spacing.space_2, ds.spacing.space_2, ds.spacing.space_2)
        layout.setSpacing(ds.spacing.space_1)

        # Header
        header = QHBoxLayout()
        icon_text = "●" if self.option["id"] == "default" else "◆" if self.option["id"] == "option1" else "▶"
        self.icon_label = QLabel(icon_text)
        self.icon_label.setFixedWidth(18)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("background-color: transparent; border: none;")
        header.addWidget(self.icon_label)

        self.title_label = QLabel(self.option["name"])
        self.title_label.setStyleSheet(
            f"font-weight: {ds.typography.weight_bold}; font-size: 13px; color: #FFFFFF; "
            "background-color: transparent; border: none;"
        )
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        header.addWidget(self.title_label)
        header.addStretch()
        layout.addLayout(header)

        # Preview box
        self.preview_box = QFrame()
        preview_layout = QVBoxLayout(self.preview_box)
        preview_layout.setContentsMargins(ds.spacing.space_2, ds.spacing.space_1, ds.spacing.space_2, ds.spacing.space_1)
        preview_layout.setSpacing(1)

        for line in self.option["lines"]:
            lbl = QLabel(line)
            lbl.setStyleSheet("font-size: 11px; color: #FFFFFF; background-color: transparent; border: none;")
            lbl.setWordWrap(True)
            preview_layout.addWidget(lbl)

        layout.addWidget(self.preview_box)

        # Description
        self.desc_label = QLabel(self.option["description"])
        self.desc_label.setStyleSheet(
            "font-size: 11px; color: #B8B8B8; background-color: transparent; border: none;"
        )
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
            CTACard QLabel {{
                background-color: transparent;
                border: none;
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
        self.title_label.setStyleSheet(
            f"color: {primary_color if self.is_selected else '#FFFFFF'}; border: none; "
            f"font-weight: {ds.typography.weight_bold}; font-size: 14px; background-color: transparent;"
        )
        self.icon_label.setStyleSheet(
            f"color: {primary_color if self.is_selected else '#B8B8B8'}; border: none; "
            "font-weight: bold; font-size: 12px; background-color: transparent;"
        )
        self.desc_label.setStyleSheet(
            "color: #B8B8B8; border: none; font-size: 12px; background-color: transparent;"
        )

class CTAPanel(QFrame, ThemedMixin):
    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.cards = {}
        self._current_columns = 0
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
        title.setStyleSheet(
            f"font-size: 16px; font-weight: {ds.typography.weight_bold}; color: #FFFFFF; "
            "background-color: transparent; border: none;"
        )
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

        # Helper description (gloss CTA in plain words)
        cta_help = QLabel("CTA는 영상 끝에 넣는 행동 유도 문구예요. 보는 사람이 무엇을 하면 좋을지 알려 줘요.")
        cta_help.setWordWrap(True)
        cta_help.setStyleSheet(
            "font-size: 12px; color: #B8B8B8; background-color: transparent; border: none; padding-bottom: 3px;"
        )
        self.main_layout.addWidget(cta_help)

        # Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {get_color('surface')};
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: {get_color('surface')};
            }}
            QScrollArea QWidget {{
                background-color: transparent;
                border: none;
            }}
        """)
        
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
        valid_ids = {option["id"] for option in CTA_OPTIONS}
        selected_id = getattr(self.gui, 'selected_cta_id', 'default')
        if selected_id not in valid_ids:
            selected_id = CTA_OPTIONS[0]["id"]
            self.gui.selected_cta_id = selected_id
            get_settings_manager().set_cta_id(selected_id)
        columns = self._column_count()
        self._current_columns = columns
        
        for i, option in enumerate(CTA_OPTIONS):
            is_selected = option["id"] == selected_id
            card = CTACard(option, is_selected=is_selected, theme_manager=self.theme_manager)
            card.clicked.connect(self._on_card_clicked)
            
            row, col = divmod(i, columns)
            self.grid_layout.addWidget(card, row, col)
            self.cards[option["id"]] = card

        # 카드들이 위쪽에 모이도록 마지막에 신축 행 추가
        for col in range(columns):
            self.grid_layout.setColumnStretch(col, 1)
        last_row = (len(CTA_OPTIONS) + columns - 1) // columns
        self.grid_layout.setRowStretch(last_row, 1)

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
        self.grid_widget.setStyleSheet("background-color: transparent; border: none;")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        columns = self._column_count()
        if columns != self._current_columns:
            QTimer.singleShot(0, self.rebuild_cards)

    def _column_count(self) -> int:
        width = self.width()
        if width < 390:
            return 1
        if width < 620:
            return 2
        return 3

def get_selected_cta_lines(gui) -> list:
    selected_id = getattr(gui, 'selected_cta_id', 'default')
    for option in CTA_OPTIONS:
        if option["id"] == selected_id:
            return option["lines"]
    return CTA_OPTIONS[0]["lines"]
