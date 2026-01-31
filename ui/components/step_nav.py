"""
Step navigation bar for the main shell (PyQt6).
"""
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QPushButton, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal


class StepNav(QFrame):
    step_selected = pyqtSignal(str)

    def __init__(self, steps, parent=None):
        super().__init__(parent)
        self._buttons = {}
        self.setObjectName("StepNav")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(8)

        for step_id, label, icon_text in steps:
            btn = QPushButton(f"{icon_text}  {label}")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, sid=step_id: self._on_click(sid))
            btn.setObjectName(f"step_{step_id}")
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            layout.addWidget(btn)
            self._buttons[step_id] = btn

        layout.addStretch()
        if steps:
            self.set_active(steps[0][0])

    def _on_click(self, step_id: str):
        self.set_active(step_id)
        self.step_selected.emit(step_id)

    def set_active(self, step_id: str):
        for sid, btn in self._buttons.items():
            btn.setChecked(sid == step_id)
