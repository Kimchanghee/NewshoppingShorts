"""
Step navigation bar for the main shell (PyQt6).
Modernized with Enhanced Design System.
"""
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QPushButton, QSizePolicy, 
    QLabel, QHBoxLayout, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QFont, QColor

from ui.design_system_enhanced import get_design_system


class StepButton(QPushButton):
    """Custom styled navigation button"""
    def __init__(self, step_id, label, icon_text, parent=None):
        super().__init__(parent)
        self.step_id = step_id
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(50)
        
        # Design System
        self.ds = get_design_system()
        
        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(12)
        
        # Icon (Text for now, typically would be SVG/Pixmap)
        self.icon_label = QLabel(icon_text)
        self.icon_label.setFont(QFont(self.ds.typography.font_family_body, 16))
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        self.icon_label.setFixedWidth(24)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Text
        self.text_label = QLabel(label)
        self.text_label.setFont(QFont(self.ds.typography.font_family_body, 10, QFont.Weight.Medium))
        self.text_label.setStyleSheet("background: transparent; border: none;")
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        layout.addStretch()
        
        # Initial Style
        self.update_style(False)

    def setChecked(self, checked):
        super().setChecked(checked)
        self.update_style(checked)

    def update_style(self, checked):
        c = self.ds.colors
        if checked:
            bg = c.bg_selected
            text_color = c.primary
            border = f"4px solid {c.primary}"
            font_weight = QFont.Weight.Bold
        else:
            bg = "transparent"
            text_color = c.text_secondary
            border = "4px solid transparent"
            font_weight = QFont.Weight.Medium

        self.setStyleSheet(f"""
            StepButton {{
                background-color: {bg};
                border: none;
                border-left: {border};
                border-radius: 0px; /* Rectangular full width or minimal radius usually for sidebars */
                text-align: left;
            }}
            StepButton:hover {{
                background-color: {c.bg_hover};
            }}
        """)
        
        self.text_label.setStyleSheet(f"color: {text_color}; background: transparent;")
        self.icon_label.setStyleSheet(f"color: {text_color}; background: transparent;")
        
        f = self.text_label.font()
        f.setWeight(font_weight)
        self.text_label.setFont(f)


class StepNav(QFrame):
    step_selected = pyqtSignal(str)

    def __init__(self, steps, parent=None):
        super().__init__(parent)
        self.ds = get_design_system()
        self._buttons = {}
        
        self.setObjectName("StepNav")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setFixedWidth(260)  # Fixed width for consistency
        
        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 30, 0, 30)  # Top/Bottom padding
        layout.setSpacing(4)
        
        # Styling
        self.setStyleSheet(f"""
            #StepNav {{
                background-color: {self.ds.colors.bg_sidebar};
                border-right: 1px solid {self.ds.colors.border_light};
            }}
        """)

        # Add buttons
        for step_id, label, icon_text in steps:
            btn = StepButton(step_id, label, icon_text, self)
            btn.clicked.connect(lambda _, sid=step_id: self._on_click(sid))
            layout.addWidget(btn)
            self._buttons[step_id] = btn

        layout.addStretch()
        
        # Footer / Info area?
        # Could add version info or something here if needed.
        
        if steps:
            self.set_active(steps[0][0])

    def _on_click(self, step_id: str):
        self.set_active(step_id)
        self.step_selected.emit(step_id)

    def set_active(self, step_id: str):
        for sid, btn in self._buttons.items():
            btn.setChecked(sid == step_id)
