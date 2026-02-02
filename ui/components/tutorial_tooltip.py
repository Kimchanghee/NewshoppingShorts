# -*- coding: utf-8 -*-
"""
Tutorial Tooltip Component for PyQt6
고정 크기 튜토리얼 툴팁 카드
"""
from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsOpacityEffect, QWidget
)
from PyQt6.QtGui import QFont

from ui.design_system_v2 import get_design_system


class TutorialTooltip(QFrame):
    """튜토리얼 툴팁 - 고정 크기 카드"""

    next_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()
    skip_clicked = pyqtSignal()

    # 고정 크기
    TOOLTIP_WIDTH = 340
    TOOLTIP_HEIGHT = 200

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ds = get_design_system()
        self._setup_ui()
        self._setup_animation()

    def _setup_ui(self):
        c = self.ds.colors

        # 고정 크기 설정
        self.setFixedSize(self.TOOLTIP_WIDTH, self.TOOLTIP_HEIGHT)

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
        self.step_label.setFixedHeight(20)
        self.step_label.setFont(QFont(self.ds.typography.font_family_primary, 11))
        self.step_label.setStyleSheet(f"color: {c.text_muted}; background: transparent;")
        layout.addWidget(self.step_label)

        # 제목
        self.title_label = QLabel()
        self.title_label.setFixedHeight(28)
        self.title_label.setFont(QFont(self.ds.typography.font_family_primary, 16, QFont.Weight.Bold))
        self.title_label.setStyleSheet(f"color: {c.text_primary}; background: transparent;")
        layout.addWidget(self.title_label)

        # 설명 (고정 높이)
        self.desc_label = QLabel()
        self.desc_label.setFixedHeight(60)
        self.desc_label.setFont(QFont(self.ds.typography.font_family_primary, 12))
        self.desc_label.setStyleSheet(f"color: {c.text_secondary}; background: transparent;")
        self.desc_label.setWordWrap(True)
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.desc_label)

        layout.addStretch()

        # 버튼 영역
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        # 건너뛰기 버튼
        self.skip_btn = QPushButton("건너뛰기")
        self.skip_btn.setFixedSize(80, 36)
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
        self.prev_btn.setFixedSize(70, 36)
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
        self.next_btn.setFixedSize(80, 36)
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

        # 마지막 단계면 버튼 텍스트 변경
        self.next_btn.setText("완료" if is_last else "다음")

        # 첫 번째 단계면 이전 버튼 숨김
        self.prev_btn.setVisible(step > 1)

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
