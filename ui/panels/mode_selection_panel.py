"""
Mode Selection Panel for PyQt6
첫 페이지: 단일 영상 / 믹스 / 소싱(풀 자동화) 3가지 모드 선택
"""
from typing import Optional, Dict
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QWidget, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QFontMetricsF
from ui.design_system_v2 import get_design_system, get_color


class ModeCard(QFrame):
    """모드 선택 카드 위젯"""
    clicked = pyqtSignal(str)

    def __init__(self, mode_id: str, title: str, subtitle: str,
                 description: str, icon: str, features: list,
                 is_selected: bool = False, parent=None):
        super().__init__(parent)
        self.mode_id = mode_id
        self.is_selected = is_selected
        self._compact_mode = False
        self.ds = get_design_system()
        self._setup_ui(title, subtitle, description, icon, features)
        self.apply_style()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _setup_ui(self, title: str, subtitle: str, description: str,
                  icon: str, features: list):
        ds = self.ds

        self.setMinimumSize(210, 300)
        self.setMaximumWidth(360)
        self.setMaximumHeight(350)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            ds.spacing.space_3, ds.spacing.space_3,
            ds.spacing.space_3, ds.spacing.space_3
        )
        layout.setSpacing(ds.spacing.space_2)

        # Icon + title block. Keep each text row in its own reserved lane so
        # Windows emoji font fallback cannot paint over the title at odd DPI.
        self.header_frame = QFrame()
        self.header_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.header_frame.setMinimumHeight(88)
        self.header_frame.setStyleSheet("background: transparent; border: none;")
        header_layout = QVBoxLayout(self.header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(ds.spacing.space_2)

        normalized_icon = (icon or "").replace("\ufe0f", "")
        self.icon_box = QFrame()
        self.icon_box.setFixedHeight(34)
        self.icon_box.setStyleSheet("background: transparent; border: none;")
        icon_box_layout = QVBoxLayout(self.icon_box)
        icon_box_layout.setContentsMargins(0, 0, 0, 0)
        icon_box_layout.setSpacing(0)

        self.icon_label = QLabel(normalized_icon)
        icon_font = QFont("Segoe UI Emoji", 19)
        self.icon_label.setFont(icon_font)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed
        )
        self.icon_label.setFixedHeight(32)
        icon_box_layout.addWidget(self.icon_label)
        header_layout.addWidget(self.icon_box)

        # Title
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont(
            ds.typography.font_family_primary,
            ds.typography.size_xl,
            QFont.Weight.Bold
        ))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setMinimumHeight(24)
        header_layout.addWidget(self.title_label)

        # Subtitle
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setFont(QFont(
            ds.typography.font_family_primary,
            ds.typography.size_sm
        ))
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setMinimumHeight(28)
        header_layout.addWidget(self.subtitle_label)

        layout.addWidget(self.header_frame)

        # Separator
        self.separator = QFrame()
        self.separator.setFixedHeight(1)
        self.separator.setStyleSheet(f"background-color: {get_color('border_light')};")
        layout.addWidget(self.separator)

        # Description
        self.desc_label = QLabel(description)
        self.desc_label.setFont(QFont(
            ds.typography.font_family_primary,
            ds.typography.size_sm
        ))
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("padding-bottom: 3px;")
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.desc_label)

        # Features list
        self.features_widget = QWidget()
        features_layout = QVBoxLayout(self.features_widget)
        features_layout.setContentsMargins(0, 0, 0, 0)
        features_layout.setSpacing(ds.spacing.space_2)

        for feature in features:
            feature_row = QHBoxLayout()
            feature_row.setSpacing(ds.spacing.space_2)

            check_icon = QLabel("✓")
            check_icon.setFixedWidth(20)
            check_icon.setStyleSheet(f"color: {get_color('success')};")
            check_icon.setFont(QFont(ds.typography.font_family_primary, 12, QFont.Weight.Bold))
            feature_row.addWidget(check_icon)

            feature_label = QLabel(feature)
            feature_label.setFont(QFont(
                ds.typography.font_family_primary,
                ds.typography.size_xs
            ))
            feature_label.setStyleSheet(f"color: {get_color('text_secondary')}; padding-bottom: 3px;")
            feature_label.setWordWrap(True)
            feature_row.addWidget(feature_label, 1)

            features_layout.addLayout(feature_row)

        layout.addWidget(self.features_widget)
        layout.addStretch()

        # Selection indicator
        self.select_label = QLabel("클릭하여 선택")
        self.select_label.setFont(QFont(
            ds.typography.font_family_primary,
            ds.typography.size_sm,
            QFont.Weight.Medium
        ))
        self.select_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.select_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.mode_id)
        super().mousePressEvent(event)

    def sizeHint(self) -> QSize:
        return QSize(280, 330)

    def minimumSizeHint(self) -> QSize:
        return QSize(170, 170) if self._compact_mode else QSize(210, 300)

    def set_compact_mode(self, compact: bool) -> None:
        compact = bool(compact)
        if compact == self._compact_mode:
            return
        self._compact_mode = compact
        self.desc_label.setVisible(not compact)
        self.features_widget.setVisible(not compact)
        if compact:
            self.setMinimumSize(170, 170)
            self.setMaximumHeight(210)
            self.layout().setContentsMargins(10, 10, 10, 10)
            self.layout().setSpacing(6)
        else:
            self.setMinimumSize(210, 300)
            self.setMaximumHeight(350)
            self.layout().setContentsMargins(12, 12, 12, 12)
            self.layout().setSpacing(self.ds.spacing.space_2)
        self.updateGeometry()

    def enterEvent(self, event):
        """Hover effect"""
        if not self.is_selected:
            self.setStyleSheet(self._get_style(hover=True))
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Remove hover effect"""
        self.apply_style()
        super().leaveEvent(event)

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.apply_style()

    def apply_style(self):
        self.setStyleSheet(self._get_style())

        # Update label colors
        text_primary = get_color('text_primary')
        text_secondary = get_color('text_secondary')
        text_muted = get_color('text_muted')
        primary = get_color('primary')

        self.icon_label.setStyleSheet(
            f"color: {primary if self.is_selected else text_secondary}; background: transparent;"
        )
        self.title_label.setStyleSheet(f"color: {text_primary}; background: transparent;")
        self.subtitle_label.setStyleSheet(f"color: {text_secondary}; background: transparent;")
        self.desc_label.setStyleSheet(f"color: {text_muted}; background: transparent;")

        if self.is_selected:
            self.select_label.setText("✓ 선택됨")
            self.select_label.setStyleSheet(
                f"color: {primary}; background: transparent; font-weight: bold;"
            )
        else:
            self.select_label.setText("클릭하여 선택")
            self.select_label.setStyleSheet(
                f"color: {text_muted}; background: transparent;"
            )

    def _get_style(self, hover: bool = False) -> str:
        ds = self.ds
        text_color = get_color('text_primary')

        if self.is_selected:
            bg = get_color('surface_variant')
            border = get_color('primary')
            border_width = 3
        elif hover:
            bg = get_color('surface')
            border = get_color('text_muted')
            border_width = 2
        else:
            bg = get_color('surface')
            border = get_color('border_light')
            border_width = 1

        return f"""
            ModeCard {{
                background-color: {bg};
                border: {border_width}px solid {border};
                border-radius: {ds.radius.lg}px;
                color: {text_color};
            }}
            ModeCard QLabel {{
                color: {text_color};
                background: transparent;
            }}
        """


class ModeSelectionPanel(QWidget):
    """모드 선택 패널 - 첫 페이지"""
    mode_selected = pyqtSignal(str)  # "single", "mix", or "sourcing"

    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.ds = get_design_system()
        self.theme_manager = theme_manager
        self._current_mode: Optional[str] = None
        self._compact_mode = False
        self._cards: Dict[str, ModeCard] = {}
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(324)
        self.setMaximumHeight(390)
        self._setup_ui()

    def set_compact_mode(self, compact: bool) -> None:
        compact = bool(compact)
        if compact == self._compact_mode:
            return
        self._compact_mode = compact
        for card in self._cards.values():
            card.set_compact_mode(compact)
        if compact:
            self.setMinimumHeight(200)
            self.setMaximumHeight(240)
        else:
            self.setMinimumHeight(324)
            self.setMaximumHeight(390)
        self._card_columns = 0
        self._relayout_cards(3 if self.width() >= (540 if compact else 670) else 2)
        self.updateGeometry()

    def _setup_ui(self):
        ds = self.ds

        # Panel styling
        self.setStyleSheet(f"""
            ModeSelectionPanel {{
                background-color: {get_color('background')};
            }}
            ModeSelectionPanel QLabel {{
                color: {get_color('text_primary')};
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            ds.spacing.space_2, 0,
            ds.spacing.space_2, 0
        )
        main_layout.setSpacing(ds.spacing.space_2)

        # Cards container
        self.cards_layout = QGridLayout()
        self.cards_layout.setHorizontalSpacing(ds.spacing.space_3)
        self.cards_layout.setVerticalSpacing(ds.spacing.space_3)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Single Video Mode Card
        single_card = ModeCard(
            mode_id="single",
            title="단일 영상",
            subtitle="영상 1개를 한국어 숏폼으로",
            description="해외 상품 영상 하나를 한국어 숏폼으로 바꿔 줍니다.",
            icon="🎬",
            features=[
                "해외 영상 링크 1개만 붙여넣기 (도우인·샤오홍슈)",
                "AI가 한국어로 번역하고 목소리를 입혀 줘요",
                "여러 목소리로 한 번에 만들 수 있어요",
                "빠르게 완성돼요"
            ],
            is_selected=False
        )
        single_card.clicked.connect(self._on_mode_clicked)
        self._cards["single"] = single_card

        # Mix Mode Card
        mix_card = ModeCard(
            mode_id="mix",
            title="믹스 모드",
            subtitle="영상 여러 개를 섞어서 (최대 5개)",
            description="같은 상품의 영상 여러 개를 자동으로 섞어 새 영상을 만듭니다.",
            icon="🎞️",
            features=[
                "같은 상품 영상을 최대 5개까지 넣기",
                "여러 장면을 자동으로 섞어서 편집",
                "매번 다른 느낌의 영상이 나와요",
                "똑같은 영상이 반복되지 않아요"
            ],
            is_selected=False
        )
        mix_card.clicked.connect(self._on_mode_clicked)
        self._cards["mix"] = mix_card

        # Sourcing (Full Automation) Mode Card - Mode 3
        sourcing_card = ModeCard(
            mode_id="sourcing",
            title="전체 자동 만들기",
            subtitle="쿠팡 링크 하나로 영상 파일까지 자동",
            description="상품에 맞는 영상을 찾아 완성 파일을 만들고, 원하면 YouTube 업로드까지 이어서 진행합니다.",
            icon="🤖",
            features=[
                "쿠팡 상품 링크 1개만 붙여넣기",
                "어울리는 해외 영상을 자동으로 찾아 줘요",
                "YouTube·Linktree 연결 없이 영상 파일 제작",
                "YouTube 업로드와 Linktree 등록은 선택"
            ],
            is_selected=False
        )
        sourcing_card.clicked.connect(self._on_mode_clicked)
        self._cards["sourcing"] = sourcing_card
        main_layout.addLayout(self.cards_layout)
        self._card_columns = 0
        self._relayout_cards(1)

        # Bottom hint
        main_layout.addStretch()

        hint_label = QLabel("💡 모드를 선택하면 다음 단계로 진행됩니다")
        hint_label.setFont(QFont(
            ds.typography.font_family_primary,
            ds.typography.size_xs
        ))
        hint_label.setStyleSheet(f"color: {get_color('text_muted')};")
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(hint_label)

    def _relayout_cards(self, columns: int) -> None:
        columns = max(1, min(columns, len(self._cards)))
        if columns == self._card_columns:
            return
        while self.cards_layout.count():
            self.cards_layout.takeAt(0)
        for index, card in enumerate(self._cards.values()):
            self.cards_layout.addWidget(card, index // columns, index % columns)
        self._card_columns = columns

    def sizeHint(self) -> QSize:
        return QSize(720, 220) if self._compact_mode else QSize(900, 324)

    def minimumSizeHint(self) -> QSize:
        return QSize(540, 200) if self._compact_mode else QSize(670, 324)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = event.size().width()
        three_column_min = 540 if self._compact_mode else 670
        columns = 3 if width >= three_column_min else 2 if width >= 460 else 1
        self._relayout_cards(columns)

    def _on_mode_clicked(self, mode_id: str):
        """모드 선택 처리"""
        self._current_mode = mode_id

        # Update card selection state
        for card_id, card in self._cards.items():
            card.set_selected(card_id == mode_id)

        # Update state
        if hasattr(self.gui, 'state'):
            self.gui.state.processing_mode = mode_id
            self.gui.state.mode_selected = True
        # Keep GUI alias in sync (StateBridgeMixin copies this at init only)
        if hasattr(self.gui, 'processing_mode'):
            self.gui.processing_mode = mode_id

        # Emit signal and navigate to next step
        self.mode_selected.emit(mode_id)

        # Navigate to the next step after short delay (mode-specific)
        QTimer.singleShot(300, lambda: self._navigate_next(mode_id))

    def _navigate_next(self, mode_id: str):
        """모드별 다음 페이지로 이동.

        - single / mix : 'source' (영상 URL 입력)
        - sourcing     : 'sourcing' (쿠팡 링크 풀 자동화)
        """
        target = 'sourcing' if mode_id == 'sourcing' else 'source'
        if hasattr(self.gui, '_on_step_selected'):
            self.gui._on_step_selected(target)
        if hasattr(self.gui, 'step_nav'):
            self.gui.step_nav.set_active(target)

    # Backward compatibility: keep the old method name in case anything calls it externally.
    def _navigate_to_source(self):
        self._navigate_next(self._current_mode or 'single')

    def get_current_mode(self) -> str:
        """현재 선택된 모드 반환"""
        return self._current_mode or "single"

    def reset_selection(self):
        """선택 초기화"""
        self._current_mode = None
        for card in self._cards.values():
            card.set_selected(False)
        if hasattr(self.gui, 'state'):
            self.gui.state.mode_selected = False
