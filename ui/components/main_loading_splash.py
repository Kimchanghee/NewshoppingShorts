"""
Main loading splash placeholder (PyQt6)
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel

class MainLoadingSplash(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Loading")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Main loading...", self))

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    splash = MainLoadingSplash()
    splash.show()
    sys.exit(app.exec())
