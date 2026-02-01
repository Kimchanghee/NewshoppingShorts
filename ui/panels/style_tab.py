"""
Style Tab for PyQt6 - Redesigned with side-by-side Voice & CTA, compact Font panel
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QFrame, QSplitter
)
from PyQt6.QtCore import Qt
from ui.panels.font_panel import FontPanel
from ui.panels.cta_panel import CTAPanel
from ui.panels.voice_panel import VoicePanel
from ui.design_system_v2 import get_design_system, get_color


class StyleTab(QWidget):
    """
    Style Tab with horizontal split layout:
    - Top: Voice Panel (left) + CTA Panel (right) side by side
    - Bottom: Font Panel in compact horizontal layout
    No scrolling - all content visible at once.
    """
    
    def __init__(self, parent=None, gui=None, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.theme_manager = theme_manager
        self.ds = get_design_system()
        self._setup_ui()

    def _setup_ui(self):
        ds = self.ds
        
        # Main layout - no scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(ds.spacing.space_5, ds.spacing.space_4, ds.spacing.space_5, ds.spacing.space_4)
        main_layout.setSpacing(ds.spacing.space_5)
        
        # Header
        header = QLabel("스타일 설정")
        header.setStyleSheet(f"""
            font-size: {ds.typography.size_2xl}px;
            font-weight: {ds.typography.weight_bold};
            color: {get_color('text_primary')};
        """)
        main_layout.addWidget(header)
        
        # Horizontal splitter for Voice (left) and CTA (right)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(2)
        
        # Voice Panel (Left side - 50%)
        self.voice_panel = VoicePanel(self, gui=self.gui, theme_manager=self.theme_manager)
        self.voice_panel.setMinimumWidth(300)
        self.splitter.addWidget(self.voice_panel)
        
        # CTA Panel (Right side - 50%)
        self.cta_panel = CTAPanel(self, gui=self.gui, theme_manager=self.theme_manager)
        self.cta_panel.setMinimumWidth(300)
        self.splitter.addWidget(self.cta_panel)
        
        # Set equal sizes for splitter (50/50)
        self.splitter.setSizes([500, 500])
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(self.splitter, stretch=1)
        
        # Font Panel at bottom (compact horizontal layout)
        font_container = QFrame()
        font_container.setFrameShape(QFrame.Shape.StyledPanel)
        font_container.setStyleSheet(f"""
            QFrame {{
                background-color: {get_color('surface')};
                border: 1px solid {get_color('border_light')};
                border-radius: {ds.radius.lg}px;
            }}
        """)
        font_layout = QVBoxLayout(font_container)
        font_layout.setContentsMargins(ds.spacing.space_4, ds.spacing.space_3, ds.spacing.space_4, ds.spacing.space_3)
        font_layout.setSpacing(ds.spacing.space_3)
        
        # Font section header
        font_header = QLabel("폰트 선택")
        font_header.setStyleSheet(f"""
            font-size: {ds.typography.size_lg}px;
            font-weight: {ds.typography.weight_bold};
            color: {get_color('text_primary')};
        """)
        font_layout.addWidget(font_header)
        
        # Font panel (compact)
        self.font_panel = CompactFontPanel(self, gui=self.gui, theme_manager=self.theme_manager)
        font_layout.addWidget(self.font_panel)
        
        main_layout.addWidget(font_container)

    def apply_theme(self):
        """Apply theme to all child panels."""
        ds = self.ds
        
        # Update splitter styling
        self.splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {get_color('border_light')};
            }}
        """)
        
        # Apply theme to panels
        if hasattr(self.voice_panel, 'apply_theme'):
            self.voice_panel.apply_theme()
        if hasattr(self.cta_panel, 'apply_theme'):
            self.cta_panel.apply_theme()
        if hasattr(self.font_panel, 'apply_theme'):
            self.font_panel.apply_theme()


class CompactFontPanel(QFrame):
    """
    Compact horizontal font selection panel.
    Shows font options in a single row instead of scrollable list.
    """
    
    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.theme_manager = theme_manager
        self.ds = get_design_system()
        self.cards = {}
        self._setup_ui()

    def _setup_ui(self):
        ds = self.ds
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ds.spacing.space_3)
        
        # Font options data
        import os
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        fonts_dir = os.path.join(project_root, "fonts")
        
        font_options = [
            {"name": "서울 한강체", "id": "seoul_hangang", "description": "모던하고 깔끔한"},
            {"name": "프리텐다드", "id": "pretendard", "description": "세련된 현대적"},
            {"name": "G마켓 산스", "id": "gmarketsans", "description": "인기 있는 고품질"},
            {"name": "페이퍼로지", "id": "paperlogy", "description": "부드러운 곡선"},
            {"name": "유앤피플", "id": "unpeople_gothic", "description": "부드럽고 가독성"},
        ]
        
        selected_id = getattr(self.gui, 'selected_font_id', 'seoul_hangang')
        
        for option in font_options:
            card = CompactFontCard(option, is_selected=(option["id"] == selected_id))
            layout.addWidget(card)
            self.cards[option["id"]] = card
        
        layout.addStretch()

    def _on_font_selected(self, font_id):
        """Handle font selection."""
        from managers.settings_manager import get_settings_manager
        
        self.gui.selected_font_id = font_id
        get_settings_manager().set_font_id(font_id)
        
        # Update card visuals
        for fid, card in self.cards.items():
            card.set_selected(fid == font_id)

    def apply_theme(self):
        """Apply theme to all font cards."""
        for card in self.cards.values():
            card.apply_theme()


class CompactFontCard(QFrame):
    """Compact font card for horizontal layout."""
    
    def __init__(self, option, is_selected=False):
        super().__init__()
        
        self.option = option
        self.is_selected = is_selected
        self.ds = get_design_system()
        self._setup_ui()
        self.apply_theme()

    def _setup_ui(self):
        ds = self.ds
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.spacing.space_3, ds.spacing.space_2, ds.spacing.space_3, ds.spacing.space_2)
        layout.setSpacing(ds.spacing.space_1)
        
        # Font name
        self.name_label = QLabel(self.option["name"])
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label)
        
        # Description
        self.desc_label = QLabel(self.option["description"])
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.desc_label)
        
        # Selection indicator
        self.indicator = QLabel("●" if self.is_selected else "○")
        self.indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.indicator)
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(100)
        self.setFixedHeight(80)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Notify parent panel of selection
            parent = self.parent()
            if parent and hasattr(parent, '_on_font_selected'):
                parent._on_font_selected(self.option["id"])

    def set_selected(self, selected):
        self.is_selected = selected
        self.apply_theme()

    def apply_theme(self):
        ds = self.ds
        
        bg = get_color('surface_variant') if self.is_selected else get_color('surface')
        border = get_color('primary') if self.is_selected else get_color('border_light')
        thickness = 2 if self.is_selected else 1
        
        self.setStyleSheet(f"""
            CompactFontCard {{
                background-color: {bg};
                border: {thickness}px solid {border};
                border-radius: {ds.radius.base}px;
            }}
        """)
        
        primary = get_color('primary')
        text_primary = get_color('text_primary')
        text_secondary = get_color('text_secondary')
        
        self.name_label.setStyleSheet(f"""
            color: {primary if self.is_selected else text_primary};
            font-weight: {ds.typography.weight_bold};
            font-size: {ds.typography.size_sm}px;
        """)
        
        self.desc_label.setStyleSheet(f"""
            color: {text_secondary};
            font-size: {ds.typography.size_2xs}px;
        """)
        
        self.indicator.setStyleSheet(f"""
            color: {primary if self.is_selected else text_secondary};
            font-size: {ds.typography.size_xs}px;
        """)
