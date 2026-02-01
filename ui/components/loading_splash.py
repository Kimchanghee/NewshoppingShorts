"""
Loading splash placeholder (PyQt6)
Uses the design system v2 for consistent styling.
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel
from ui.design_system_v2 import get_design_system, get_color


class LoadingSplash(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ds = get_design_system()
        
        self.setWindowTitle("Loading")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self.ds.spacing.space_6,
            self.ds.spacing.space_6,
            self.ds.spacing.space_6,
            self.ds.spacing.space_6
        )
        layout.setSpacing(self.ds.spacing.space_4)
        
        label = QLabel("Loading...", self)
        label.setStyleSheet(f"""
            QLabel {{
                color: {get_color('text_primary')};
                font-size: {self.ds.typography.size_lg}px;
                font-family: {self.ds.typography.font_family_primary};
            }}
        """)
        layout.addWidget(label)


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    splash = LoadingSplash()
    splash.show()
    sys.exit(app.exec())
