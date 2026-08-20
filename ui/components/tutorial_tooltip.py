# -*- coding: utf-8 -*-
"""Token-driven tutorial card used by the guided spotlight flow."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QFontMetrics
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.design_system_v2 import get_color, get_design_system


class TutorialTooltip(QFrame):
    """A readable, keyboard-friendly tutorial card clamped to the app viewport."""

    next_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()
    skip_clicked = pyqtSignal()

    TOOLTIP_WIDTH = 400
    TOOLTIP_HEIGHT = 266
    TOOLTIP_HEIGHT_LAST = 302
    MIN_TOOLTIP_WIDTH = 280
    VIEWPORT_MARGIN = 16

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ds = get_design_system()
        self._is_last = False
        self._setup_ui()
        self._setup_animation()

    def _setup_ui(self):
        c = self.ds.colors
        family = self.ds.typography.font_family_primary

        self.setObjectName("tutorialTooltip")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(f"""
            QFrame#tutorialTooltip {{
                background-color: {c.surface};
                border: 1px solid {c.border_medium};
                border-radius: 16px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)
        guide_label = QLabel("사용 가이드")
        guide_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        guide_label.setFixedHeight(24)
        guide_label.setMinimumWidth(72)
        guide_label.setFont(QFont(family, 9, QFont.Weight.Bold))
        guide_label.setStyleSheet(f"""
            background: {c.surface_variant}; color: {c.primary};
            border: 1px solid {c.border_light}; border-radius: 12px;
        """)
        meta_row.addWidget(guide_label)
        meta_row.addStretch()
        self.step_label = QLabel()
        self.step_label.setFont(QFont(family, 10, QFont.Weight.Bold))
        self.step_label.setStyleSheet(f"color: {c.text_muted}; background: transparent; border: none;")
        meta_row.addWidget(self.step_label)
        layout.addLayout(meta_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {c.surface_variant}; border: none; border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {c.primary}; border-radius: 2px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        self.title_label = QLabel()
        self.title_label.setMinimumHeight(30)
        self.title_label.setFont(QFont(family, 17, QFont.Weight.Bold))
        self.title_label.setStyleSheet(f"color: {c.text_primary}; background: transparent; border: none;")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.desc_label = QLabel()
        self.desc_label.setMinimumHeight(66)
        self.desc_label.setFont(QFont(family, 12))
        self.desc_label.setStyleSheet(f"""
            color: {c.text_secondary}; background: transparent; border: none;
            padding-bottom: 3px;
        """)
        self.desc_label.setWordWrap(True)
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.desc_label)

        self.dont_show_checkbox = QCheckBox("다음부터 이 가이드 보지 않기")
        self.dont_show_checkbox.setFont(QFont(family, 10))
        self.dont_show_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {c.text_secondary}; background: transparent; spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border: 1px solid {c.border_medium}; border-radius: 4px;
                background: {c.surface};
            }}
            QCheckBox::indicator:hover {{ border-color: {c.primary}; }}
            QCheckBox::indicator:checked {{
                background: {c.primary}; border-color: {c.primary};
            }}
        """)
        self.dont_show_checkbox.setVisible(False)
        layout.addWidget(self.dont_show_checkbox)
        layout.addStretch()

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {c.border_light}; border: none;")
        layout.addWidget(divider)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self.skip_btn = QPushButton("건너뛰기")
        self.skip_btn.setMinimumSize(84, 42)
        self.skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip_btn.setFont(QFont(family, 10))
        self.skip_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {c.text_muted};
                border: none; border-radius: 8px;
            }}
            QPushButton:hover {{ background: {c.surface_variant}; color: {c.text_primary}; }}
            QPushButton:focus {{ border: 1px solid {c.primary}; }}
        """)
        self.skip_btn.clicked.connect(self.skip_clicked.emit)
        button_row.addWidget(self.skip_btn)
        button_row.addStretch()

        self.prev_btn = QPushButton("이전")
        self.prev_btn.setMinimumSize(76, 42)
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.setFont(QFont(family, 10, QFont.Weight.Medium))
        self.prev_btn.setStyleSheet(f"""
            QPushButton {{
                background: {c.surface}; color: {c.text_primary};
                border: 1px solid {c.border_medium}; border-radius: 8px;
            }}
            QPushButton:hover {{ background: {c.surface_variant}; border-color: {c.primary}; }}
            QPushButton:focus {{ border: 2px solid {c.primary}; }}
        """)
        self.prev_btn.clicked.connect(self.prev_clicked.emit)
        button_row.addWidget(self.prev_btn)

        self.next_btn = QPushButton("다음")
        self.next_btn.setMinimumSize(92, 42)
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setFont(QFont(family, 10, QFont.Weight.Bold))
        self.next_btn.setStyleSheet(f"""
            QPushButton {{
                background: {c.primary}; color: {c.text_on_primary};
                border: none; border-radius: 8px;
            }}
            QPushButton:hover {{ background: {c.primary_hover}; }}
            QPushButton:pressed {{ background: {c.primary_dark}; }}
            QPushButton:focus {{ border: 2px solid {c.text_primary}; }}
        """)
        self.next_btn.clicked.connect(self.next_clicked.emit)
        button_row.addWidget(self.next_btn)
        layout.addLayout(button_row)

    def _setup_animation(self):
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(180)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_content(self, step: int, total: int, title: str, description: str, is_last: bool = False):
        self.step_label.setText(f"{step} / {total}")
        self.progress_bar.setValue(round(step / max(1, total) * 100))
        self.title_label.setText(title)
        self.desc_label.setText(description)
        self._is_last = is_last
        self.next_btn.setText("가이드 완료" if is_last else "다음")
        self.prev_btn.setVisible(step > 1)
        self.dont_show_checkbox.setVisible(is_last)
        parent_size = self.parentWidget().size() if self.parentWidget() else QSize(1024, 680)
        self.fit_to_viewport(parent_size)

    def fit_to_viewport(self, viewport_size: QSize) -> QSize:
        available_width = max(1, viewport_size.width() - self.VIEWPORT_MARGIN * 2)
        width = min(self.TOOLTIP_WIDTH, available_width)
        if available_width >= self.MIN_TOOLTIP_WIDTH:
            width = max(self.MIN_TOOLTIP_WIDTH, width)

        content_width = max(100, width - 48)
        flags = Qt.TextFlag.TextWordWrap | Qt.TextFlag.TextExpandTabs
        title_height = max(
            30,
            QFontMetrics(self.title_label.font()).boundingRect(
                QRect(0, 0, content_width, 1000), int(flags), self.title_label.text()
            ).height() + 4,
        )
        description_height = max(
            66,
            QFontMetrics(self.desc_label.font()).boundingRect(
                QRect(0, 0, content_width, 1000), int(flags), self.desc_label.text()
            ).height() + 8,
        )
        self.title_label.setFixedHeight(title_height)
        self.desc_label.setFixedHeight(description_height)

        self.setFixedWidth(width)
        self.layout().activate()
        desired_height = self.layout().sizeHint().height()
        baseline = self.TOOLTIP_HEIGHT_LAST if self._is_last else self.TOOLTIP_HEIGHT
        available_height = max(1, viewport_size.height() - self.VIEWPORT_MARGIN * 2)
        self.setFixedHeight(min(available_height, max(baseline, desired_height)))
        return self.size()

    @property
    def dont_show_again(self) -> bool:
        return self.dont_show_checkbox.isChecked()

    def fade_in(self):
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def fade_out(self):
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.start()

    def keyPressEvent(self, event):  # noqa: N802 - Qt API
        if event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.next_clicked.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Left and self.prev_btn.isVisible():
            self.prev_clicked.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.skip_clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def showEvent(self, event):  # noqa: N802 - Qt API
        super().showEvent(event)
        self.setFocus(Qt.FocusReason.OtherFocusReason)
