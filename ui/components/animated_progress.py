"""
Animated progress placeholder (PyQt6)
Uses the design system v2 for consistent styling.
"""
from PyQt6.QtWidgets import QProgressBar
from ui.design_system_v2 import get_design_system, get_color


class AnimatedProgressBar(QProgressBar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ds = get_design_system()
        self.setRange(0, 100)
        
        # Apply design system styling
        self.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {get_color('border_light')};
                border-radius: {self.ds.border_radius.radius_sm}px;
                text-align: center;
                background-color: {get_color('surface_variant')};
            }}
            QProgressBar::chunk {{
                background-color: {get_color('primary')};
                border-radius: {self.ds.border_radius.radius_sm}px;
            }}
        """)
