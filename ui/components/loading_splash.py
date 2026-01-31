"""
Loading splash placeholder (PyQt6)
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel

class LoadingSplash(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Loading")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Loading...", self))

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    splash = LoadingSplash()
    splash.show()
    sys.exit(app.exec())
