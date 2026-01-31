"""
Animated progress placeholder (PyQt6)
"""
from PyQt6.QtWidgets import QProgressBar

class AnimatedProgressBar(QProgressBar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setRange(0, 100)
