"""
구독 다이얼로그 (PyQt6)
Uses the design system v2 for consistent styling.
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel
from ui.design_system_v2 import get_design_system, get_color


class SubscriptionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ds = get_design_system()
        
        self.setWindowTitle("구독")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self.ds.spacing.space_6,
            self.ds.spacing.space_6,
            self.ds.spacing.space_6,
            self.ds.spacing.space_6
        )
        layout.setSpacing(self.ds.spacing.space_4)
        
        # Apply design system styling
        label = QLabel("구독 다이얼로그 (준비 중)", self)
        label.setStyleSheet(f"""
            QLabel {{
                color: {get_color('text_primary')};
                font-size: {self.ds.typography.size_base}px;
                font-family: {self.ds.typography.font_family_primary};
            }}
        """)
        layout.addWidget(label)
