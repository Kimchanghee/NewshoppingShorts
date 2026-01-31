# -*- coding: utf-8 -*-
"""
Enhanced Voice Selection Panel - Content Creator's Studio Theme

Features:
- Elevated voice cards with hover effects
- Smooth selection animations
- Professional tab filters
- Grid layout with proper spacing
"""

import logging
from typing import Dict, Optional, List
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QWidget, QGridLayout, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont

from ui.components.base_widget_enhanced import ThemedMixin, EnhancedCard, create_button, create_label

logger = logging.getLogger(__name__)


class EnhancedVoiceCard(EnhancedCard):
    """
    Enhanced voice selection card with micro-interactions

    Features:
    - Hover elevation
    - Selection animation
    - Gender-colored accents
    - Play button integration
    """

    clicked = pyqtSignal(str)

    def __init__(self, profile, is_selected=False, theme_manager=None):
        super().__init__(elevation="sm", hoverable=True)
        self.profile = profile
        self.is_selected = is_selected
        self._setup_animations()
        self.create_widgets()
        self.apply_theme()

    def _setup_animations(self):
        """Setup selection animation"""
        self._select_anim = QPropertyAnimation(self, b"minimumHeight")
        self._select_anim.setDuration(self.ds.animation.duration_fast)
        self._select_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def create_widgets(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self.spacing.lg,
            self.spacing.md,
            self.spacing.lg,
            self.spacing.md
        )
        layout.setSpacing(self.spacing.sm)

        # Top row: Check + Name + Play
        top_row = QHBoxLayout()
        top_row.setSpacing(self.spacing.sm)

        # Check indicator
        self.check_label = QLabel("✓" if self.is_selected else "")
        self.check_label.setFixedSize(24, 24)
        self.check_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(self.check_label)

        # Gender Icon + Name
        gender_icon = "♀" if self.profile.get("gender") == "female" else "♂"
        self.gender_color = "#FF6B9D" if self.profile.get("gender") == "female" else "#3B82F6"

        self.name_label = QLabel(f"{gender_icon} {self.profile['label']}")
        top_row.addWidget(self.name_label)

        top_row.addStretch()

        # Play button
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(32, 28)
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.setToolTip("샘플 듣기")
        top_row.addWidget(self.play_btn)

        layout.addLayout(top_row)

        # Description
        self.desc_label = QLabel(self.profile.get("description", ""))
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.desc_label)

        # Make card clickable
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        """Handle card click"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.profile["id"])
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        """Update selection state with animation"""
        self.is_selected = selected
        self.check_label.setText("✓" if selected else "")
        self.apply_theme()

    def apply_theme(self):
        """Apply voice card styling"""
        c = self.colors
        t = self.typography
        r = self.ds.radius

        # Card background - elevated when selected
        border_width = 2 if self.is_selected else 1
        bg_color = c.bg_selected if self.is_selected else c.bg_card
        border_color = c.primary if self.is_selected else c.border_light

        self.setStyleSheet(f"""
            EnhancedVoiceCard {{
                background-color: {bg_color};
                border: {border_width}px solid {border_color};
                border-radius: {r.lg}px;
                padding: 0;
            }}
            EnhancedVoiceCard:hover {{
                border-color: {c.primary};
                background-color: {c.bg_hover if not self.is_selected else c.bg_selected};
            }}
        """)

        # Check indicator
        check_bg = c.primary if self.is_selected else c.bg_secondary
        check_fg = c.text_on_primary if self.is_selected else "transparent"
        self.check_label.setStyleSheet(f"""
            QLabel {{
                background-color: {check_bg};
                color: {check_fg};
                border-radius: {r.sm}px;
                font-weight: {t.font_weight_bold};
                border: none;
            }}
        """)

        # Name label with gender color
        self.name_label.setStyleSheet(f"""
            QLabel {{
                color: {self.gender_color};
                font-family: {t.font_family_body};
                font-size: {t.font_size_md}px;
                font-weight: {t.font_weight_semibold};
                background: transparent;
                border: none;
            }}
        """)

        # Description
        self.desc_label.setStyleSheet(f"""
            QLabel {{
                color: {c.text_secondary};
                font-family: {t.font_family_body};
                font-size: {t.font_size_sm}px;
                line-height: {int(t.font_size_sm * t.line_height_relaxed)}px;
                background: transparent;
                border: none;
            }}
        """)

        # Play button
        self.play_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {c.gradient_start},
                    stop:1 {c.gradient_end}
                );
                color: {c.text_on_primary};
                border: none;
                border-radius: {r.sm}px;
                font-size: {t.font_size_sm}px;
                font-weight: {t.font_weight_bold};
            }}
            QPushButton:hover {{
                background: {c.primary_hover};
            }}
            QPushButton:pressed {{
                background: {c.primary_dark};
            }}
        """)


class EnhancedVoicePanel(QFrame, ThemedMixin):
    """
    Enhanced voice selection panel with grid layout

    Features:
    - Tabbed gender filter
    - Grid of voice cards
    - Selection counter badge
    - Smooth scrolling
    """

    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.gender_filter = "all"
        self.voice_cards = {}
        self.__init_themed__(theme_manager)
        self.create_widgets()
        self.apply_theme()

    def create_widgets(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(
            self.spacing.xl2,
            self.spacing.lg,
            self.spacing.xl2,
            self.spacing.lg
        )
        self.main_layout.setSpacing(self.spacing.lg)

        # Header
        header = self._create_header()
        self.main_layout.addLayout(header)

        # Tab Filter
        tab_layout = self._create_tab_filter()
        self.main_layout.addLayout(tab_layout)

        # Voice Grid Area
        self._create_voice_grid()

    def _create_header(self) -> QHBoxLayout:
        """Create panel header with title and counter"""
        header = QHBoxLayout()
        header.setSpacing(self.spacing.lg)

        # Title
        self.title_label = QLabel("음성 선택")
        header.addWidget(self.title_label)

        header.addStretch()

        # Selection counter badge
        self.count_badge = QLabel("0개 선택")
        self.count_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.count_badge.setFixedHeight(32)
        header.addWidget(self.count_badge)

        return header

    def _create_tab_filter(self) -> QHBoxLayout:
        """Create gender filter tabs"""
        tab_layout = QHBoxLayout()
        tab_layout.setSpacing(self.spacing.sm)

        # Tab buttons
        self.tab_all = QPushButton("전체")
        self.tab_female = QPushButton("여성")
        self.tab_male = QPushButton("남성")

        self.tabs = [self.tab_all, self.tab_female, self.tab_male]

        for btn in self.tabs:
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(40)
            tab_layout.addWidget(btn)

        self.tab_all.setChecked(True)

        tab_layout.addStretch()

        return tab_layout

    def _create_voice_grid(self):
        """Create scrollable grid of voice cards"""
        # Scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Grid container
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(self.spacing.lg)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area.setWidget(self.grid_container)
        self.main_layout.addWidget(self.scroll_area)

    def populate_voices(self, voice_profiles: List[Dict]):
        """Populate grid with voice cards"""
        # Clear existing
        for card in self.voice_cards.values():
            card.deleteLater()
        self.voice_cards.clear()

        # Add voice cards in grid (3 columns)
        row, col = 0, 0
        columns = 3

        for profile in voice_profiles:
            card = EnhancedVoiceCard(profile, is_selected=False)
            card.clicked.connect(self._on_voice_selected)
            self.grid_layout.addWidget(card, row, col)
            self.voice_cards[profile["id"]] = card

            col += 1
            if col >= columns:
                col = 0
                row += 1

        # Add stretch to push cards to top
        self.grid_layout.setRowStretch(row + 1, 1)

    def _on_voice_selected(self, voice_id: str):
        """Handle voice card selection"""
        # Toggle selection logic (managed by parent gui)
        if hasattr(self.gui, 'toggle_voice_selection'):
            self.gui.toggle_voice_selection(voice_id)
        self.update_selection_count()

    def update_selection_count(self):
        """Update selection counter badge"""
        count = sum(1 for card in self.voice_cards.values() if card.is_selected)
        self.count_badge.setText(f"{count}개 선택")

    def apply_theme(self):
        """Apply panel styling"""
        c = self.colors
        t = self.typography
        r = self.ds.radius

        # Panel background
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {c.bg_card};
                border: 1px solid {c.border_card};
                border-radius: {r.xl}px;
            }}
        """)

        # Title
        self.title_label.setStyleSheet(f"""
            QLabel {{
                color: {c.text_primary};
                font-family: {t.font_family_heading};
                font-size: {t.font_size_2xl}px;
                font-weight: {t.font_weight_bold};
                background: transparent;
                border: none;
            }}
        """)

        # Counter badge
        self.count_badge.setStyleSheet(f"""
            QLabel {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {c.gradient_start},
                    stop:1 {c.gradient_end}
                );
                color: {c.text_on_primary};
                padding: {self.spacing.sm}px {self.spacing.lg}px;
                border-radius: {r.md}px;
                font-family: {t.font_family_body};
                font-size: {t.font_size_sm}px;
                font-weight: {t.font_weight_bold};
            }}
        """)

        # Tab buttons
        for i, btn in enumerate(self.tabs):
            is_checked = btn.isChecked()
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c.bg_selected if is_checked else c.bg_secondary};
                    color: {c.primary if is_checked else c.text_primary};
                    border: 2px solid {c.primary if is_checked else c.border_light};
                    border-radius: {r.lg}px;
                    padding: {self.spacing.sm}px {self.spacing.xl}px;
                    font-family: {t.font_family_body};
                    font-size: {t.font_size_base}px;
                    font-weight: {t.font_weight_semibold if is_checked else t.font_weight_normal};
                }}
                QPushButton:hover {{
                    background-color: {c.bg_hover};
                    border-color: {c.primary};
                }}
                QPushButton:checked {{
                    background-color: {c.bg_selected};
                    color: {c.primary};
                    border-color: {c.primary};
                }}
            """)

        # Scroll area
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            {self.ds.get_scrollbar_style()}
        """)
