"""
Watermark Settings Panel for PyQt6
"""
import os
import logging
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QWidget, QLineEdit, QGridLayout,
    QPushButton, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QFontDatabase, QPainter, QColor, QPen
from ui.components.base_widget import ThemedMixin
from managers.settings_manager import get_settings_manager
from ui.design_system_v2 import get_design_system, get_color

logger = logging.getLogger(__name__)

# Font options matching font_panel.py
WATERMARK_FONT_OPTIONS = [
    {"name": "프리텐다드", "id": "pretendard", "description": "세련된 현대적 고딕체"},
    {"name": "서울 한강체", "id": "seoul_hangang", "description": "모던하고 깔끔한 서울시 공식 폰트"},
    {"name": "G마켓 산스", "id": "gmarketsans", "description": "인기 있는 고품질 무료 폰트"},
    {"name": "페이퍼로지", "id": "paperlogy", "description": "부드러운 곡선이 매력적인 폰트"},
    {"name": "유앤피플", "id": "unpeople_gothic", "description": "부드럽고 가독성 좋은 고딕체"},
]

SIZE_OPTIONS = [
    {"label": "작게", "id": "small", "description": "영상 높이의 1.5%"},
    {"label": "보통", "id": "medium", "description": "영상 높이의 2.5%"},
    {"label": "크게", "id": "large", "description": "영상 높이의 3.5%"},
]

POSITION_OPTIONS = [
    {"label": "좌상단", "id": "top_left"},
    {"label": "우상단", "id": "top_right"},
    {"label": "좌하단", "id": "bottom_left"},
    {"label": "우하단", "id": "bottom_right"},
]


class PositionPreview(QFrame):
    """Mini video frame preview showing watermark position"""
    position_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_position = "bottom_right"
        self.setFixedSize(180, 320)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_position(self, position):
        self.current_position = position
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background (dark video frame)
        painter.setBrush(QColor(30, 30, 30))
        painter.setPen(QPen(QColor(60, 60, 60), 1))
        painter.drawRoundedRect(0, 0, self.width() - 1, self.height() - 1, 8, 8)

        # 9:16 label
        painter.setPen(QColor(80, 80, 80))
        painter.setFont(QFont("Arial", 9))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "9:16")

        # Watermark dot
        margin = 12
        dot_w, dot_h = 50, 14
        positions = {
            "top_left": (margin, margin),
            "top_right": (self.width() - dot_w - margin, margin),
            "bottom_left": (margin, self.height() - dot_h - margin),
            "bottom_right": (self.width() - dot_w - margin, self.height() - dot_h - margin),
        }

        for pos_id, (x, y) in positions.items():
            if pos_id == self.current_position:
                painter.setBrush(QColor(227, 22, 57, 200))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(x, y, dot_w, dot_h, 3, 3)
                painter.setPen(QColor(255, 255, 255))
                painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
                painter.drawText(x, y, dot_w, dot_h, Qt.AlignmentFlag.AlignCenter, "워터마크")
            else:
                painter.setBrush(QColor(80, 80, 80, 100))
                painter.setPen(QPen(QColor(100, 100, 100, 80), 1, Qt.PenStyle.DashLine))
                painter.drawRoundedRect(x, y, dot_w, dot_h, 3, 3)

        painter.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        x, y = event.position().x(), event.position().y()
        cx, cy = self.width() / 2, self.height() / 2
        if x < cx and y < cy:
            pos = "top_left"
        elif x >= cx and y < cy:
            pos = "top_right"
        elif x < cx and y >= cy:
            pos = "bottom_left"
        else:
            pos = "bottom_right"
        self.position_clicked.emit(pos)


class WatermarkFontCard(QFrame, ThemedMixin):
    clicked = pyqtSignal(str)

    def __init__(self, option, is_selected=False, theme_manager=None):
        super().__init__()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.option = option
        self.is_selected = is_selected
        self.ds = get_design_system()
        self.__init_themed__(theme_manager)
        self.create_widgets()
        self.apply_theme()

    def create_widgets(self):
        ds = self.ds
        layout = QHBoxLayout(self)
        layout.setContentsMargins(ds.spacing.space_3, ds.spacing.space_2, ds.spacing.space_3, ds.spacing.space_2)

        self.radio_label = QLabel("●" if self.is_selected else "○")
        self.radio_label.setFixedWidth(20)
        layout.addWidget(self.radio_label)

        self.name_label = QLabel(self.option["name"])
        self.name_label.setStyleSheet(
            f"font-weight: {ds.typography.weight_bold}; font-size: 13px; color: #FFFFFF; "
            "background-color: transparent; border: none;"
        )
        layout.addWidget(self.name_label)

        layout.addStretch()

        self.desc_label = QLabel(self.option["description"])
        self.desc_label.setStyleSheet(
            "font-size: 11px; color: #B8B8B8; background-color: transparent; border: none;"
        )
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
            WatermarkFontCard {{
                background-color: {bg};
                border: {thickness}px solid {border};
                border-radius: {ds.radius.sm}px;
            }}
            WatermarkFontCard QLabel {{
                background-color: transparent;
                border: none;
            }}
        """)

        text_secondary = get_color('text_secondary')
        self.name_label.setStyleSheet(
            f"color: #FFFFFF; border: none; font-weight: {ds.typography.weight_bold}; "
            "font-size: 13px; background-color: transparent;"
        )
        self.desc_label.setStyleSheet("color: #B8B8B8; border: none; font-size: 11px; background-color: transparent;")
        self.radio_label.setStyleSheet(
            f"color: {get_color('primary') if self.is_selected else text_secondary}; "
            "border: none; background-color: transparent;"
        )


class WatermarkPanel(QFrame, ThemedMixin):
    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.ds = get_design_system()
        self.font_cards = {}
        self.position_buttons = {}
        self.size_buttons = {}
        self.__init_themed__(theme_manager)
        self._loading = True
        self.create_widgets()
        self._load_settings()
        self._loading = False
        self.apply_theme()

    def create_widgets(self):
        ds = self.ds

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(ds.spacing.space_4, ds.spacing.space_3, ds.spacing.space_4, ds.spacing.space_3)
        main_layout.setSpacing(ds.spacing.space_3)

        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"""
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
        self.scroll = scroll

        scroll_content = QWidget()
        self.scroll_content = scroll_content
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setSpacing(ds.spacing.space_4)

        # ── Section 1: Enable Toggle ──
        enable_section = self._create_section("워터마크 활성화", "영상에 채널 이름 워터마크를 표시합니다.")
        enable_row = QHBoxLayout()

        self.enable_btn = QPushButton("꺼짐")
        self.enable_btn.setCheckable(True)
        self.enable_btn.setFixedSize(60, 32)
        self.enable_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.enable_btn.clicked.connect(self._on_enable_toggled)
        enable_row.addWidget(self.enable_btn)
        enable_row.addStretch()

        enable_section.layout().addLayout(enable_row)
        content_layout.addWidget(enable_section)

        # ── Section 2: Text Input ──
        text_section = self._create_section("워터마크 텍스트", "영상에 표시할 채널 이름 또는 텍스트를 입력하세요. (최대 50자)")

        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("예: @내채널이름")
        self.text_input.setMaxLength(50)
        self.text_input.setFixedHeight(40)
        self.text_input.textChanged.connect(self._on_text_changed)
        text_section.layout().addWidget(self.text_input)

        self.char_count_label = QLabel("0 / 50")
        self.char_count_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.char_count_label.setStyleSheet("font-size: 11px; color: #888; background-color: transparent; border: none;")
        text_section.layout().addWidget(self.char_count_label)

        content_layout.addWidget(text_section)

        # ── Section 3: Position ──
        position_section = self._create_section("워터마크 위치", "워터마크가 표시될 위치를 선택하세요.")

        pos_content = QHBoxLayout()
        pos_content.setSpacing(ds.spacing.space_4)

        # Position buttons grid
        pos_grid = QGridLayout()
        pos_grid.setSpacing(ds.spacing.space_2)

        for i, opt in enumerate(POSITION_OPTIONS):
            btn = QPushButton(opt["label"])
            btn.setCheckable(True)
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, pid=opt["id"]: self._on_position_selected(pid))
            row, col = divmod(i, 2)
            pos_grid.addWidget(btn, row, col)
            self.position_buttons[opt["id"]] = btn

        pos_content.addLayout(pos_grid)

        # Preview
        self.position_preview = PositionPreview()
        self.position_preview.position_clicked.connect(self._on_position_selected)
        pos_content.addWidget(self.position_preview)

        position_section.layout().addLayout(pos_content)
        content_layout.addWidget(position_section)

        # ── Section 4: Size ──
        size_section = self._create_section("워터마크 크기", "워터마크 텍스트의 크기를 선택하세요.")

        size_row = QHBoxLayout()
        size_row.setSpacing(ds.spacing.space_2)

        for opt in SIZE_OPTIONS:
            btn = QPushButton(f"{opt['label']}")
            btn.setCheckable(True)
            btn.setFixedHeight(36)
            btn.setMinimumWidth(80)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(opt["description"])
            btn.clicked.connect(lambda checked, sid=opt["id"]: self._on_size_selected(sid))
            size_row.addWidget(btn)
            self.size_buttons[opt["id"]] = btn

        size_row.addStretch()
        size_section.layout().addLayout(size_row)
        content_layout.addWidget(size_section)

        # ── Section 5: Font ──
        font_section = self._create_section("워터마크 폰트", "워터마크에 사용할 폰트를 선택하세요.")

        for opt in WATERMARK_FONT_OPTIONS:
            card = WatermarkFontCard(opt, is_selected=False, theme_manager=self.theme_manager)
            card.clicked.connect(self._on_font_selected)
            font_section.layout().addWidget(card)
            self.font_cards[opt["id"]] = card

        content_layout.addWidget(font_section)

        content_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    def _create_section(self, title, description):
        ds = self.ds
        section = QFrame()
        section.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(ds.spacing.space_3, ds.spacing.space_3, ds.spacing.space_3, ds.spacing.space_3)
        layout.setSpacing(ds.spacing.space_2)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"font-size: 14px; font-weight: {ds.typography.weight_bold}; color: #FFFFFF; "
            "background-color: transparent; border: none;"
        )
        layout.addWidget(title_label)

        desc_label = QLabel(description)
        desc_label.setStyleSheet("font-size: 12px; color: #888888; background-color: transparent; border: none;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        return section

    # ── Settings Load ──

    def _load_settings(self):
        sm = get_settings_manager()
        settings = sm.get_watermark_settings()

        enabled = settings.get("enabled", False)
        channel_name = settings.get("channel_name", "")
        position = settings.get("position", "bottom_right")
        font_id = settings.get("font_id", "pretendard")
        font_size = settings.get("font_size", "medium")

        self.enable_btn.setChecked(enabled)
        self._update_enable_btn_style(enabled)

        self.text_input.setText(channel_name)
        self.char_count_label.setText(f"{len(channel_name)} / 50")

        self._update_position_selection(position)
        self._update_size_selection(font_size)
        self._update_font_selection(font_id)

        # Set gui attributes for video pipeline
        self.gui.watermark_enabled = enabled
        self.gui.watermark_channel_name = channel_name
        self.gui.watermark_position = position
        self.gui.watermark_font_id = font_id
        self.gui.watermark_font_size = font_size

        logger.info("[워터마크 패널] 설정 로드 완료: enabled=%s, text='%s', pos=%s, font=%s, size=%s",
                     enabled, channel_name, position, font_id, font_size)

    # ── Event Handlers ──

    def _on_enable_toggled(self):
        enabled = self.enable_btn.isChecked()
        self._update_enable_btn_style(enabled)
        self.gui.watermark_enabled = enabled
        get_settings_manager().set_watermark_enabled(enabled)
        logger.info("[워터마크] 활성화: %s", enabled)

    def _update_enable_btn_style(self, enabled):
        ds = self.ds
        if enabled:
            self.enable_btn.setText("켜짐")
            self.enable_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {get_color('primary')};
                    color: white;
                    border: none;
                    border-radius: {ds.radius.sm}px;
                    font-weight: bold;
                    font-size: 13px;
                }}
            """)
        else:
            self.enable_btn.setText("꺼짐")
            self.enable_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {get_color('surface_variant')};
                    color: {get_color('text_secondary')};
                    border: 1px solid {get_color('border_light')};
                    border-radius: {ds.radius.sm}px;
                    font-weight: bold;
                    font-size: 13px;
                }}
            """)

    def _on_text_changed(self, text):
        self.char_count_label.setText(f"{len(text)} / 50")
        if self._loading:
            return
        self.gui.watermark_channel_name = text
        get_settings_manager().set_watermark_channel_name(text)
        logger.debug("[워터마크] 텍스트 변경: '%s'", text)

    def _on_position_selected(self, position_id):
        self._update_position_selection(position_id)
        self.gui.watermark_position = position_id
        get_settings_manager().set_watermark_position(position_id)
        logger.info("[워터마크] 위치 변경: %s", position_id)

    def _update_position_selection(self, selected_id):
        ds = self.ds
        for pid, btn in self.position_buttons.items():
            is_sel = (pid == selected_id)
            btn.setChecked(is_sel)
            if is_sel:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {get_color('primary')};
                        color: white;
                        border: none;
                        border-radius: {ds.radius.sm}px;
                        font-weight: bold;
                        font-size: 12px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {get_color('surface_variant')};
                        color: {get_color('text_secondary')};
                        border: 1px solid {get_color('border_light')};
                        border-radius: {ds.radius.sm}px;
                        font-size: 12px;
                    }}
                """)
        self.position_preview.set_position(selected_id)

    def _on_size_selected(self, size_id):
        self._update_size_selection(size_id)
        self.gui.watermark_font_size = size_id
        get_settings_manager().set_watermark_font_size(size_id)
        logger.info("[워터마크] 크기 변경: %s", size_id)

    def _update_size_selection(self, selected_id):
        ds = self.ds
        for sid, btn in self.size_buttons.items():
            is_sel = (sid == selected_id)
            btn.setChecked(is_sel)
            if is_sel:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {get_color('primary')};
                        color: white;
                        border: none;
                        border-radius: {ds.radius.sm}px;
                        font-weight: bold;
                        font-size: 12px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {get_color('surface_variant')};
                        color: {get_color('text_secondary')};
                        border: 1px solid {get_color('border_light')};
                        border-radius: {ds.radius.sm}px;
                        font-size: 12px;
                    }}
                """)

    def _on_font_selected(self, font_id):
        self._update_font_selection(font_id)
        self.gui.watermark_font_id = font_id
        get_settings_manager().set_watermark_font_id(font_id)
        logger.info("[워터마크] 폰트 변경: %s", font_id)

    def _update_font_selection(self, selected_id):
        for fid, card in self.font_cards.items():
            card.is_selected = (fid == selected_id)
            card.apply_theme()

    def apply_theme(self):
        ds = self.ds
        bg = get_color('surface')
        self.setStyleSheet(f"""
            background-color: {bg};
            border: none;
        """)
        self.scroll_content.setStyleSheet("background-color: transparent; border: none;")

        # Text input styling
        self.text_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {get_color('surface_variant')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border_light')};
                border-radius: {ds.radius.sm}px;
                padding: 0 {ds.spacing.space_3}px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 2px solid {get_color('primary')};
            }}
        """)
