"""
Subscription popup placeholder (PyQt6)
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel

class SubscriptionPopup(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("구독 안내")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Subscription popup placeholder", self))
