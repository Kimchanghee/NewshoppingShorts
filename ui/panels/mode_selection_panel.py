"""
Mode Selection Panel for PyQt6
첫 페이지: 단일 영상 모드 vs 믹스 모드 선택
"""
from typing import Optional, Dict
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, QWidget, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
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
        self.ds = get_design_system()
        self._setup_ui(title, subtitle, description, icon, features)
        self.apply_style()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _setup_ui(self, title: str, subtitle: str, description: str,
                  icon: str, features: list):
        ds = self.ds

        self.setMinimumSize(340, 380)
        self.setMaximumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            ds.spacing.space_6, ds.spacing.space_6,
            ds.spacing.space_6, ds.spacing.space_6
        )
        layout.setSpacing(ds.spacing.space_4)

        # Icon + Title row
        header_layout = QVBoxLayout()
        header_layout.setSpacing(max(ds.spacing.space_3, 12))

        # Icon (large)
        # NOTE:
        # Emoji glyphs can be clipped at startup on some DPI/font fallback paths.
        # Reserve explicit vertical space and strip variation selector to stabilize metrics.
        normalized_icon = (icon or "").replace("\ufe0f", "")
        self.icon_label = QLabel(normalized_icon)
        icon_font = QFont("Segoe UI Emoji", 32)
        self.icon_label.setFont(icon_font)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop)
        self.icon_label.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed
        )
        self.icon_label.setContentsMargins(0, 4, 0, 0)
        # Emoji rendering on Windows is larger than font metrics report.
        # Use a generous fixed height to prevent overlap with title.
        self.icon_label.setFixedHeight(60)
        header_layout.addWidget(self.icon_label)

        # Title
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont(
            ds.typography.font_family_primary,
            ds.typography.size_xl,
            QFont.Weight.Bold
        ))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setContentsMargins(0, 2, 0, 0)
        header_layout.addWidget(self.title_label)

        # Subtitle
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setFont(QFont(
            ds.typography.font_family_primary,
            ds.typography.size_sm
        ))
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.subtitle_label)

        layout.addLayout(header_layout)

        # Separator
        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet(f"background-color: {get_color('border_light')};")
        layout.addWidget(separator)

        # Description
        self.desc_label = QLabel(description)
        self.desc_label.setFont(QFont(
            ds.typography.font_family_primary,
            ds.typography.size_sm
        ))
        self.desc_label.setWordWrap(True)
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.desc_label)

        # Features list
        features_layout = QVBoxLayout()
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
            feature_label.setStyleSheet(f"color: {get_color('text_secondary')};")
            feature_label.setWordWrap(True)
            feature_row.addWidget(feature_label, 1)

            features_layout.addLayout(feature_row)

        layout.addLayout(features_layout)
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
    mode_selected = pyqtSignal(str)  # "single" or "mix"

    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.ds = get_design_system()
        self.theme_manager = theme_manager
        self._current_mode: Optional[str] = None
        self._cards: Dict[str, ModeCard] = {}
        self._setup_ui()

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
            ds.spacing.space_8, ds.spacing.space_6,
            ds.spacing.space_8, ds.spacing.space_6
        )
        main_layout.setSpacing(ds.spacing.space_6)

        # Header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(ds.spacing.space_2)

        welcome_label = QLabel("영상 제작 모드 선택")
        welcome_label.setFont(QFont(
            ds.typography.font_family_primary,
            ds.typography.size_2xl,
            QFont.Weight.Bold
        ))
        welcome_label.setStyleSheet(f"color: {get_color('text_primary')};")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(welcome_label)

        desc_label = QLabel("원하는 영상 제작 방식을 선택하세요")
        desc_label.setFont(QFont(
            ds.typography.font_family_primary,
            ds.typography.size_base
        ))
        desc_label.setStyleSheet(f"color: {get_color('text_muted')};")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(desc_label)

        main_layout.addLayout(header_layout)
        main_layout.addSpacing(ds.spacing.space_4)

        # Cards container
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(ds.spacing.space_6)
        cards_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Single Video Mode Card
        single_card = ModeCard(
            mode_id="single",
            title="단일 영상",
            subtitle="1개의 영상을 변환",
            description="하나의 상품 영상을 한국어 숏폼으로 변환합니다.",
            icon="🎬",
            features=[
                "도우인(抖音) / 샤오홍슈(小红书) 영상 URL 입력",
                "AI 번역 + 한국어 TTS 생성",
                "여러 음성으로 동시 제작 가능",
                "빠른 처리 속도"
            ],
            is_selected=False
        )
        single_card.clicked.connect(self._on_mode_clicked)
        self._cards["single"] = single_card
        cards_layout.addWidget(single_card)

        # Mix Mode Card
        mix_card = ModeCard(
            mode_id="mix",
            title="믹스 모드",
            subtitle="최대 5개 영상을 믹스",
            description="같은 상품의 여러 영상을 랜덤 믹스하여 새로운 영상을 만듭니다.",
            icon="🎞️",
            features=[
                "동일 상품 영상 최대 5개 입력",
                "장면 랜덤 믹스 & 편집",
                "다양한 영상 구성 가능",
                "중복 콘텐츠 방지"
            ],
            is_selected=False
        )
        mix_card.clicked.connect(self._on_mode_clicked)
        self._cards["mix"] = mix_card
        cards_layout.addWidget(mix_card)

        main_layout.addLayout(cards_layout)

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

        # Emit signal and navigate to next step
        self.mode_selected.emit(mode_id)

        # Navigate to source page after short delay
        QTimer.singleShot(300, self._navigate_to_source)

    def _navigate_to_source(self):
        """소스 입력 페이지로 이동"""
        if hasattr(self.gui, '_on_step_selected'):
            self.gui._on_step_selected('source')
        if hasattr(self.gui, 'step_nav'):
            self.gui.step_nav.set_active('source')

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
