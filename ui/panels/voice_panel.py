"""
Voice Selection Panel for PyQt6
"""
import logging
from typing import Dict, Optional, List
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QScrollArea, QWidget, QGridLayout, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal
from ui.components.base_widget import ThemedMixin
from ui.design_system_v2 import get_design_system, get_color

logger = logging.getLogger(__name__)

class VoiceCard(QFrame, ThemedMixin):
    """A single voice selection card in PyQt6"""
    clicked = pyqtSignal(str)

    def __init__(self, profile, is_selected=False, theme_manager=None):
        super().__init__()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFrameShadow(QFrame.Shadow.Plain)  # Remove shadow
        self.profile = profile
        self.is_selected = is_selected
        self.ds = get_design_system()
        self.__init_themed__(theme_manager)
        self.create_widgets()
        self.apply_theme()
        
    def create_widgets(self):
        ds = self.ds
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.spacing.space_3, ds.spacing.space_2, ds.spacing.space_3, ds.spacing.space_2)
        
        top_row = QHBoxLayout()
        
        # Check indicator
        self.check_label = QLabel("✓" if self.is_selected else "")
        self.check_label.setFixedSize(20, 20)
        self.check_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(self.check_label)
        
        # Gender Icon + Name
        gender_icon = "♀" if self.profile.get("gender") == "female" else "♂"
        icon_color = "#FF6B81" if self.profile.get("gender") == "female" else "#5B9BD5"
        self.name_label = QLabel(f"{gender_icon} {self.profile['label']}")
        self.name_label.setStyleSheet(
            f"font-weight: {ds.typography.weight_bold}; font-size: 14px; "
            f"color: {icon_color}; background-color: transparent; border: none;"
        )
        top_row.addWidget(self.name_label)
        
        top_row.addStretch()
        
        # Play button
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(30, 24)
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {icon_color};
                color: white;
                border: none;
                border-radius: {ds.radius.sm}px;
            }}
        """)
        top_row.addWidget(self.play_btn)
        
        layout.addLayout(top_row)
        
        # Description
        self.desc_label = QLabel(self.profile["description"])
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet(
            "font-size: 16px; color: #FFFFFF; background-color: transparent; border: none;"
        )
        layout.addWidget(self.desc_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.profile["id"])

    def apply_theme(self):
        ds = self.ds
        bg = get_color('surface_variant') if self.is_selected else get_color('surface')
        border = get_color('primary') if self.is_selected else get_color('border_light')
        thickness = 2 if self.is_selected else 1
        
        self.setStyleSheet(f"""
            VoiceCard {{
                background-color: {bg};
                border: {thickness}px solid {border};
                border-radius: {ds.radius.base}px;
            }}
            VoiceCard QLabel {{
                background-color: transparent;
                border: none;
            }}
        """)
        
        check_bg = get_color('primary') if self.is_selected else get_color('surface_variant')
        check_fg = "white" if self.is_selected else "transparent"
        self.check_label.setStyleSheet(f"""
            background-color: {check_bg};
            color: {check_fg};
            border-radius: {ds.radius.sm}px;
        """)
        
        text_primary = get_color('text_primary')
        text_secondary = get_color('text_secondary')
        self.desc_label.setStyleSheet(f"color: #FFFFFF; border: none; font-size: 16px;")

class VoicePanel(QFrame, ThemedMixin):
    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.gender_filter = "all"
        self.voice_cards = {}
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
        title = QLabel("음성 선택")
        title.setStyleSheet(
            f"font-size: 16px; font-weight: {ds.typography.weight_bold}; "
            "color: #FFFFFF; background-color: transparent; border: none;"
        )
        header.addWidget(title)
        
        header.addStretch()
        
        self.count_badge = QLabel("0개 선택")
        self.count_badge.setStyleSheet(f"""
            background-color: {get_color('primary')};
            color: white;
            padding: {ds.spacing.space_1}px {ds.spacing.space_3}px;
            border-radius: {ds.radius.sm}px;
            font-weight: {ds.typography.weight_bold};
            font-size: {ds.typography.size_xs}px;
        """)
        header.addWidget(self.count_badge)
        self.main_layout.addLayout(header)
        
        # Tab Filter
        tab_layout = QHBoxLayout()
        self.tab_all = QPushButton("전체")
        self.tab_female = QPushButton("여성")
        self.tab_male = QPushButton("남성")
        
        for btn in [self.tab_all, self.tab_female, self.tab_male]:
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            tab_layout.addWidget(btn)
        
        self.tab_all.setChecked(True)
        
        # Connect filter buttons
        self.tab_all.clicked.connect(lambda: self._set_gender_filter("all"))
        self.tab_female.clicked.connect(lambda: self._set_gender_filter("female"))
        self.tab_male.clicked.connect(lambda: self._set_gender_filter("male"))
        
        self.main_layout.addLayout(tab_layout)
        
        # Grid Area - Scrollable
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet(f"""
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
        self.scroll_area.setWidget(self.grid_widget)
        self.main_layout.addWidget(self.scroll_area)
        
        # Reference containers
        self.gui.voice_card_frames = {}
        self.gui.voice_play_buttons = {}
        
        self.rebuild_grid()

    def rebuild_grid(self):
        ds = self.ds
        # Clear layout
        for i in reversed(range(self.grid_layout.count())): 
            self.grid_layout.itemAt(i).widget().setParent(None)
            
        self.voice_cards = {}
        profiles = self.gui.voice_profiles
        if self.gender_filter == "female":
            profiles = [p for p in profiles if p.get("gender") == "female"]
        elif self.gender_filter == "male":
            profiles = [p for p in profiles if p.get("gender") == "male"]

        for i, profile in enumerate(profiles):
            is_selected = False
            if hasattr(self.gui, 'voice_vars') and profile["id"] in self.gui.voice_vars:
                var = self.gui.voice_vars[profile["id"]]
                is_selected = var.get() if hasattr(var, "get") else bool(var)

            card = VoiceCard(profile, is_selected=is_selected, theme_manager=self.theme_manager)
            card.clicked.connect(self._on_card_clicked)
            card.play_btn.clicked.connect(lambda _, vid=profile["id"]: self.gui.play_voice_sample(vid))
            
            row, col = divmod(i, 2)
            self.grid_layout.addWidget(card, row, col)
            self.voice_cards[profile["id"]] = card
            self.gui.voice_card_frames[profile["id"]] = card
            self.gui.voice_play_buttons[profile["id"]] = card.play_btn

        # Update selection count badge
        self._update_count_badge()

    def _on_card_clicked(self, voice_id):
        """Handle voice card click - toggle selection and update UI"""
        # Toggle via VoiceManager (which updates voice_vars)
        if hasattr(self.gui, '_toggle_voice'):
            self.gui._toggle_voice(voice_id)
        elif hasattr(self.gui, 'voice_manager'):
            self.gui.voice_manager.on_voice_card_clicked(voice_id)

        # Update card visual state
        card = self.voice_cards.get(voice_id)
        if card and hasattr(self.gui, 'voice_vars'):
            var = self.gui.voice_vars.get(voice_id)
            if var:
                card.is_selected = var.get() if hasattr(var, "get") else bool(var)
                card.check_label.setText("✓" if card.is_selected else "")
                card.apply_theme()

        # Update selection count badge
        self._update_count_badge()

    def _set_gender_filter(self, gender: str):
        """Set gender filter and rebuild grid"""
        self.gender_filter = gender

        # Update button states
        self.tab_all.setChecked(gender == "all")
        self.tab_female.setChecked(gender == "female")
        self.tab_male.setChecked(gender == "male")

        # Rebuild the grid with filtered profiles (also updates count badge)
        self.rebuild_grid()

    def _update_count_badge(self):
        """Update the selection count badge"""
        if not hasattr(self.gui, 'voice_vars'):
            self.count_badge.setText("0개 선택")
            return

        selected_count = 0
        for voice_id, var in self.gui.voice_vars.items():
            is_selected = var.get() if hasattr(var, "get") else bool(var)
            if is_selected:
                selected_count += 1

        self.count_badge.setText(f"{selected_count}개 선택")

    def apply_theme(self):
        ds = self.ds
        bg = get_color('surface')
        self.setStyleSheet(f"background-color: {bg}; border: none;")
        self.grid_widget.setStyleSheet("background-color: transparent; border: none;")
        
        primary = get_color('primary')
        text_primary = get_color('text_primary')
        text_secondary = get_color('text_secondary')
        
        tab_style = f"""
            QPushButton {{
                background-color: {get_color('surface_variant')};
                color: {text_secondary};
                border-radius: {ds.radius.sm}px;
                padding: 6px {ds.spacing.space_4}px;
                border: none;
                font-size: {ds.typography.size_sm}px;
            }}
            QPushButton:checked {{
                background-color: {primary};
                color: white;
                font-weight: {ds.typography.weight_bold};
            }}
        """
        self.tab_all.setStyleSheet(tab_style)
        self.tab_female.setStyleSheet(tab_style)
        self.tab_male.setStyleSheet(tab_style)
