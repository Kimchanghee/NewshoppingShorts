# -*- coding: utf-8 -*-
"""
Tutorial Overlay for PyQt6 - Modern Dark Mode Design
각 페이지별 상세 설명 포함 튜토리얼
"""
import sys
from typing import Optional, Callable, List, Dict, Any
from PyQt6.QtCore import Qt, QRect, QEvent, QPropertyAnimation, QEasingCurve, pyqtProperty, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QGraphicsOpacityEffect
)
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QFont, QLinearGradient

from ui.design_system_v2 import get_design_system, get_color


class TutorialOverlay(QWidget):
    """Modern Tutorial Overlay with page-by-page explanations"""
    
    STEPS: List[Dict[str, Any]] = [
        {
            "title": "👋 쇼핑 숏폼 메이커에 오신 것을 환영합니다!",
            "description": "중국 쇼핑 영상을 한국어 숏폼으로\n자동 변환하는 AI 기반 도구입니다.",
            "details": [
                "✓ AI 자동 자막 추출 및 번역",
                "✓ 자연스러운 한국어 음성 생성",
                "✓ 자동 영상 편집 및 자막 오버레이",
            ],
            "page": "welcome",
            "highlight": None,
        },
        {
            "title": "🔗 1단계: 소스 입력",
            "description": "변환할 영상의 URL을 입력하세요.\n도우인(抖音), 샤오홍슈(小红书) 링크를 지원합니다.",
            "details": [
                "• 도우인(抖音), 샤오홍슈(小红书) 영상 링크 지원",
                "• URL 붙여넣기 후 '추가' 버튼 클릭",
                "• 여러 영상을 동시에 대기열에 추가 가능",
            ],
            "page": "source",
            "highlight": "source_panel",
        },
        {
            "title": "🎤 2단계: 음성 선택",
            "description": "생성될 영상의 나레이션 음성을 선택합니다.",
            "details": [
                "• '전체/여성/남성' 필터로 음성 검색",
                "• ▶ 버튼으로 음성 샘플 미리듣기",
                "• 음성 카드 클릭으로 선택",
            ],
            "page": "voice",
            "highlight": "voice_panel",
        },
        {
            "title": "📢 3단계: CTA 선택",
            "description": "영상 마지막에 들어갈 행동 유도 문구를\n선택합니다.",
            "details": [
                "• 기본: 구매 유도 멘트",
                "• 옵션1: 팔로우 유도",
                "• 옵션2: 댓글/공유 유도",
            ],
            "page": "cta",
            "highlight": "cta_panel",
        },
        {
            "title": "🔤 4단계: 폰트 선택",
            "description": "자막에 사용될 폰트 스타일을 선택합니다.",
            "details": [
                "• 각 폰트 미리보기 제공",
                "• 영상 분위기에 맞는 폰트 선택",
                "• 굵기와 가독성 고려",
            ],
            "page": "font",
            "highlight": "font_panel",
        },
        {
            "title": "📝 5단계: 자막 설정",
            "description": "한국어 자막의 위치와 배치 방식을 설정합니다.",
            "details": [
                "• 중국어 자막 위 배치 여부 설정",
                "• 프리뷰에서 자막 위치 직접 선택",
                "• 영상별 가독성 최적화",
            ],
            "page": "subtitle_settings",
            "highlight": "subtitle_settings_panel",
        },
        {
            "title": "📋 6단계: 대기/진행",
            "description": "추가된 영상들의 처리 상태를 확인하고\n관리합니다.",
            "details": [
                "• 대기 중인 영상 목록 확인",
                "• 진행 중인 작업 상태 모니터링",
                "• 완료된 영상 다운로드",
            ],
            "page": "queue",
            "highlight": "queue_panel",
        },
        {
            "title": "📊 제작 진행 패널",
            "description": "왼쪽 하단의 제작 진행 패널에서\n실시간 작업 상태를 확인할 수 있습니다.",
            "details": [
                "• 현재 진행 중인 작업 표시",
                "• 전체 진행률 확인",
                "• 각 단계별 상태 (다운로드, AI분석, 번역 등)",
            ],
            "page": "progress",
            "highlight": "progress_panel",
        },
        {
            "title": "⚙️ 설정",
            "description": "앱 설정을 변경할 수 있습니다.",
            "details": [
                "• 저장 경로 설정",
                "• API 키 관리",
                "• 앱 정보 확인",
            ],
            "page": "settings",
            "highlight": "settings_panel",
        },
        {
            "title": "🚀 준비 완료!",
            "description": "이제 쇼핑 숏폼 제작을 시작하세요!",
            "details": [
                "1️⃣ URL 입력 → 영상 추가",
                "2️⃣ 스타일 선택 (음성, CTA, 폰트, 자막 설정)",
                "3️⃣ 대기열에서 작업 시작",
                "4️⃣ 완료 후 다운로드!",
            ],
            "page": "complete",
            "highlight": None,
        },
    ]

    def __init__(self, parent_window, on_complete=None, on_skip=None):
        super().__init__(parent_window)
        self.ds = get_design_system()
        self.parent_window = parent_window
        self.on_complete = on_complete
        self.on_skip = on_skip
        self.current_step = 0
        self._opacity = 1.0
        
        self._setup_ui()
        self._sync_position()
        if self.parent_window:
            self.parent_window.installEventFilter(self)

    def _setup_ui(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Content will be painted directly
        self.setMouseTracking(True)

    def _sync_position(self):
        if self.parent_window:
            self.setGeometry(self.parent_window.rect())
            self.raise_()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Dark overlay background
        overlay_color = QColor("#0F172A")
        overlay_color.setAlpha(230)
        painter.setBrush(QBrush(overlay_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())
        
        # Card dimensions
        card_w = max(1, min(420, self.width() - 32))
        card_h = max(1, min(380, self.height() - 32))
        card_x = (self.width() - card_w) // 2
        card_y = (self.height() - card_h) // 2
        
        # Card background with gradient
        gradient = QLinearGradient(card_x, card_y, card_x, card_y + card_h)
        gradient.setColorAt(0, QColor("#1E293B"))
        gradient.setColorAt(1, QColor("#0F172A"))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor("#334155"), 1))
        painter.drawRoundedRect(card_x, card_y, card_w, card_h, 16, 16)
        
        step = self.STEPS[self.current_step]
        
        # Progress indicator
        progress_y = card_y + 20
        for i in range(len(self.STEPS)):
            dot_x = card_x + 20 + i * 14
            if i == self.current_step:
                painter.setBrush(QBrush(QColor("#3B82F6")))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(dot_x, progress_y, 8, 8)
            elif i < self.current_step:
                painter.setBrush(QBrush(QColor("#22C55E")))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(dot_x, progress_y, 8, 8)
            else:
                painter.setBrush(QBrush(QColor("#475569")))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(dot_x, progress_y, 8, 8)
        
        # Step counter
        counter_font = QFont("맑은 고딕", 10)
        painter.setFont(counter_font)
        painter.setPen(QPen(QColor("#64748B")))
        painter.drawText(
            QRect(card_x + card_w - 80, progress_y - 2, 60, 20),
            Qt.AlignmentFlag.AlignRight,
            f"{self.current_step + 1} / {len(self.STEPS)}"
        )
        
        # Title
        title_font = QFont("맑은 고딕", 18, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.setPen(QPen(QColor("#F8FAFC")))
        painter.drawText(
            QRect(card_x + 24, card_y + 50, card_w - 48, 40),
            Qt.AlignmentFlag.AlignLeft,
            step["title"]
        )
        
        # Description
        desc_font = QFont("맑은 고딕", 12)
        painter.setFont(desc_font)
        painter.setPen(QPen(QColor("#94A3B8")))
        painter.drawText(
            QRect(card_x + 24, card_y + 95, card_w - 48, 50),
            Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
            step["description"]
        )
        
        # Details section
        details_y = card_y + 145
        detail_font = QFont("맑은 고딕", 11)
        painter.setFont(detail_font)
        
        details = step.get("details", [])
        available_details = max(18, card_h - 215)
        detail_step = max(18, min(26, available_details // max(1, len(details))))
        for i, detail in enumerate(details):
            painter.setPen(QPen(QColor("#CBD5E1")))
            painter.drawText(
                QRect(card_x + 28, details_y + i * detail_step, card_w - 56, detail_step),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                detail
            )
        
        # Navigation buttons
        btn_y = card_y + card_h - 60
        btn_h = 40
        
        # Skip button (left)
        skip_rect = QRect(card_x + 24, btn_y, 80, btn_h)
        painter.setBrush(QBrush(QColor("#1E293B")))
        painter.setPen(QPen(QColor("#475569"), 1))
        painter.drawRoundedRect(skip_rect, 8, 8)
        
        painter.setPen(QPen(QColor("#94A3B8")))
        painter.setFont(QFont("맑은 고딕", 11))
        painter.drawText(skip_rect, Qt.AlignmentFlag.AlignCenter, "건너뛰기")
        
        # Next/Complete button (right)
        next_text = "시작하기" if self.current_step == len(self.STEPS) - 1 else "다음"
        next_rect = QRect(card_x + card_w - 120, btn_y, 96, btn_h)
        
        # Gradient for next button
        btn_gradient = QLinearGradient(next_rect.x(), next_rect.y(), next_rect.x() + next_rect.width(), next_rect.y())
        btn_gradient.setColorAt(0, QColor("#3B82F6"))
        btn_gradient.setColorAt(1, QColor("#2563EB"))
        
        painter.setBrush(QBrush(btn_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(next_rect, 8, 8)
        
        painter.setPen(QPen(QColor("#FFFFFF")))
        painter.setFont(QFont("맑은 고딕", 11, QFont.Weight.Bold))
        painter.drawText(next_rect, Qt.AlignmentFlag.AlignCenter, next_text)
        
        # Store button rects for click handling
        self._skip_rect = skip_rect
        self._next_rect = next_rect

    def mousePressEvent(self, event):
        pos = event.pos()
        
        # Check skip button
        if hasattr(self, '_skip_rect') and self._skip_rect.contains(pos):
            self._finish(skipped=True)
            return
        
        # Check next button
        if hasattr(self, '_next_rect') and self._next_rect.contains(pos):
            self._go_next()
            return
        
        # Click anywhere else to go next
        self._go_next()

    def _go_next(self):
        if self.current_step < len(self.STEPS) - 1:
            self.current_step += 1
            self.update()
        else:
            self._finish(skipped=False)

    def _go_prev(self):
        if self.current_step > 0:
            self.current_step -= 1
            self.update()

    def _finish(self, skipped=False):
        self.close()
        if skipped and self.on_skip:
            self.on_skip()
        elif not skipped and self.on_complete:
            self.on_complete()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._finish(skipped=True)
        elif event.key() == Qt.Key.Key_Right or event.key() == Qt.Key.Key_Return:
            self._go_next()
        elif event.key() == Qt.Key.Key_Left:
            self._go_prev()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_position()
        self.setFocus()

    def eventFilter(self, obj, event) -> bool:
        if obj is self.parent_window and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Move,
            QEvent.Type.WindowStateChange,
        }:
            self._sync_position()
            self.update()
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        if self.parent_window:
            try:
                self.parent_window.removeEventFilter(self)
            except (RuntimeError, TypeError):
                pass
        super().closeEvent(event)


def show_tutorial(parent_window, on_complete=None, on_skip=None):
    """Helper function to show tutorial overlay"""
    tutorial = TutorialOverlay(parent_window, on_complete, on_skip)
    tutorial.show()
    return tutorial
