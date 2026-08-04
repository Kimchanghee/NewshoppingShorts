# -*- coding: utf-8 -*-
"""
Tutorial Tooltip Component for PyQt6
화면 크기와 텍스트 배율에 맞춰 조절되는 튜토리얼 카드
"""
from typing import Optional
from PyQt6.QtCore import Qt, QRect, QSize, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsOpacityEffect, QWidget, QCheckBox, QSizePolicy
)
from PyQt6.QtGui import QFont, QFontMetrics

from ui.design_system_v2 import get_design_system


class TutorialTooltip(QFrame):
    """Tutorial card that always keeps its navigation controls reachable."""

    next_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()
    skip_clicked = pyqtSignal()

    TOOLTIP_WIDTH = 360
    TOOLTIP_HEIGHT = 230
    TOOLTIP_HEIGHT_LAST = 264
    MIN_TOOLTIP_WIDTH = 220
    VIEWPORT_MARGIN = 12

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ds = get_design_system()
        self._is_last = False
        self._setup_ui()
        self._setup_animation()

    def _setup_ui(self):
        c = self.ds.colors

        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # 스타일 적용
        self.setStyleSheet(f"""
            TutorialTooltip {{
                background-color: {c.surface};
                border: 1px solid {c.border_light};
                border-radius: 12px;
            }}
        """)

        # 메인 레이아웃
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        # 단계 표시 (예: "1 / 8")
        self.step_label = QLabel()
        self.step_label.setMinimumHeight(20)
        self.step_label.setFont(QFont(self.ds.typography.font_family_primary, 11))
        self.step_label.setStyleSheet(f"color: {c.text_muted}; background: transparent;")
        layout.addWidget(self.step_label)

        # 제목
        self.title_label = QLabel()
        self.title_label.setMinimumHeight(28)
        self.title_label.setFont(QFont(self.ds.typography.font_family_primary, 16, QFont.Weight.Bold))
        self.title_label.setStyleSheet(f"color: {c.text_primary}; background: transparent;")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        # 설명
        self.desc_label = QLabel()
        self.desc_label.setMinimumHeight(48)
        self.desc_label.setFont(QFont(self.ds.typography.font_family_primary, 12))
        self.desc_label.setStyleSheet(f"color: {c.text_secondary}; background: transparent; padding-bottom: 3px;")
        self.desc_label.setWordWrap(True)
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.desc_label)

        # "다음에 그만 보기" 체크박스 (마지막 단계에서만 표시)
        self.dont_show_checkbox = QCheckBox("다음에 그만 보기")
        self.dont_show_checkbox.setFont(QFont(self.ds.typography.font_family_primary, 10))
        self.dont_show_checkbox.setStyleSheet("""
            QCheckBox {
                color: #FFFFFF;
                background: transparent;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border: 1.5px solid #94A3B8;
                border-radius: 3px;
                background: transparent;
            }
            QCheckBox::indicator:hover {
                border-color: #FFFFFF;
            }
            QCheckBox::indicator:checked {
                background: #3B82F6;
                border-color: #3B82F6;
            }
        """)
        self.dont_show_checkbox.setVisible(False)
        layout.addWidget(self.dont_show_checkbox)

        layout.addStretch()

        # 버튼 영역
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        # 건너뛰기 버튼
        self.skip_btn = QPushButton("건너뛰기")
        self.skip_btn.setMinimumSize(64, 36)
        self.skip_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip_btn.setFont(QFont(self.ds.typography.font_family_primary, 11))
        self.skip_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {c.text_muted};
                border: none;
            }}
            QPushButton:hover {{
                color: {c.text_secondary};
            }}
        """)
        self.skip_btn.clicked.connect(self.skip_clicked.emit)
        btn_layout.addWidget(self.skip_btn)

        btn_layout.addStretch()

        # 이전 버튼
        self.prev_btn = QPushButton("이전")
        self.prev_btn.setMinimumSize(56, 36)
        self.prev_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.setFont(QFont(self.ds.typography.font_family_primary, 11))
        self.prev_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.surface_variant};
                color: {c.text_primary};
                border: 1px solid {c.border_light};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {c.surface};
            }}
        """)
        self.prev_btn.clicked.connect(self.prev_clicked.emit)
        btn_layout.addWidget(self.prev_btn)

        # 다음 버튼
        self.next_btn = QPushButton("다음")
        self.next_btn.setMinimumSize(64, 36)
        self.next_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setFont(QFont(self.ds.typography.font_family_primary, 11, QFont.Weight.Bold))
        self.next_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
        """)
        self.next_btn.clicked.connect(self.next_clicked.emit)
        btn_layout.addWidget(self.next_btn)

        layout.addLayout(btn_layout)

    def _setup_animation(self):
        """페이드 애니메이션 설정"""
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(200)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_content(self, step: int, total: int, title: str, description: str, is_last: bool = False):
        """툴팁 내용 설정"""
        self.step_label.setText(f"{step} / {total}")
        self.title_label.setText(title)
        self.desc_label.setText(description)
        self._is_last = is_last

        # 마지막 단계면 버튼 텍스트 변경
        self.next_btn.setText("완료" if is_last else "다음")

        # 첫 번째 단계면 이전 버튼 숨김
        self.prev_btn.setVisible(step > 1)

        # 마지막 단계에서만 "다음에 그만 보기" 체크박스 표시
        self.dont_show_checkbox.setVisible(is_last)
        parent_size = self.parentWidget().size() if self.parentWidget() else QSize(1024, 680)
        self.fit_to_viewport(parent_size)

    def fit_to_viewport(self, viewport_size: QSize) -> QSize:
        """Resize from content while staying inside the parent viewport."""
        available_width = max(1, viewport_size.width() - self.VIEWPORT_MARGIN * 2)
        width = min(self.TOOLTIP_WIDTH, available_width)
        if available_width >= self.MIN_TOOLTIP_WIDTH:
            width = max(self.MIN_TOOLTIP_WIDTH, width)

        content_width = max(80, width - 40)
        title_flags = Qt.TextFlag.TextWordWrap | Qt.TextFlag.TextExpandTabs
        desc_flags = title_flags

        title_height = max(
            28,
            QFontMetrics(self.title_label.font()).boundingRect(
                QRect(0, 0, content_width, 1000),
                int(title_flags),
                self.title_label.text(),
            ).height() + 2,
        )
        desc_height = max(
            48,
            QFontMetrics(self.desc_label.font()).boundingRect(
                QRect(0, 0, content_width, 1000),
                int(desc_flags),
                self.desc_label.text(),
            ).height() + 6,
        )
        self.title_label.setMinimumHeight(title_height)
        self.title_label.setMaximumHeight(title_height)
        self.desc_label.setMinimumHeight(desc_height)
        self.desc_label.setMaximumHeight(desc_height)

        self.setFixedWidth(width)
        self.layout().activate()
        desired_height = self.layout().sizeHint().height()
        baseline = self.TOOLTIP_HEIGHT_LAST if self._is_last else self.TOOLTIP_HEIGHT
        available_height = max(1, viewport_size.height() - self.VIEWPORT_MARGIN * 2)
        height = min(available_height, max(baseline, desired_height))
        self.setFixedHeight(height)
        return self.size()

    @property
    def dont_show_again(self) -> bool:
        """체크박스 상태 반환"""
        return self.dont_show_checkbox.isChecked()

    def fade_in(self):
        """페이드 인 애니메이션"""
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def fade_out(self):
        """페이드 아웃 애니메이션"""
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.start()

    def keyPressEvent(self, event):
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

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus(Qt.FocusReason.OtherFocusReason)
