"""
Subscription dialog placeholder (PyQt6)
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel

class SubscriptionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("구독")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Subscription dialog placeholder", self))
