# -*- coding: utf-8 -*-
"""
Tutorial Spotlight Overlay for PyQt6
스포트라이트 효과로 타겟 위젯 하이라이트
"""
from typing import Optional
from PyQt6.QtCore import (
    Qt, QRect, QRectF, QPoint, QTimer, QEvent,
    QPropertyAnimation, QEasingCurve, pyqtProperty
)
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QPen, QBrush

from ui.design_system_v2 import get_design_system


class TutorialSpotlight(QWidget):
    """전체 화면 오버레이 + 스포트라이트 cutout 효과"""

    def __init__(self, parent_window: QWidget):
        super().__init__(parent_window)
        self.ds = get_design_system()
        self._parent_window = parent_window

        # 스포트라이트 영역
        self._spotlight_rect = QRect(0, 0, 0, 0)
        self._target_widget: Optional[QWidget] = None
        self._padding = 8

        # 캐싱
        self._cached_path: Optional[QPainterPath] = None
        self._cache_valid = False

        # 애니메이션
        self._animation = QPropertyAnimation(self, b"spotlightRect")
        self._animation.setDuration(300)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        # 리사이즈 쓰로틀링
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(60)
        self._resize_timer.timeout.connect(self._on_resize_complete)
        self._is_resizing = False

        self._setup_ui()

        # 부모 창 리사이즈 감지
        parent_window.installEventFilter(self)

    def _setup_ui(self):
        """UI 초기화"""
        # 프레임리스, 투명 배경
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        # 부모 창 크기에 맞춤
        self.setGeometry(self._parent_window.rect())

    # QPropertyAnimation을 위한 프로퍼티
    def _get_spotlight_rect(self) -> QRect:
        return self._spotlight_rect

    def _set_spotlight_rect(self, rect: QRect):
        self._spotlight_rect = rect
        self._invalidate_cache()

    spotlightRect = pyqtProperty(QRect, fget=_get_spotlight_rect, fset=_set_spotlight_rect)

    def _invalidate_cache(self):
        """캐시 무효화"""
        self._cache_valid = False
        self.update()

    def _rebuild_path_cache(self):
        """QPainterPath 캐시 재구성"""
        self._cached_path = QPainterPath()

        # 전체 오버레이 영역
        self._cached_path.addRect(QRectF(self.rect()))

        # 스포트라이트 cutout (빈 영역 생성)
        if not self._spotlight_rect.isEmpty():
            spotlight_path = QPainterPath()
            spotlight_path.addRoundedRect(QRectF(self._spotlight_rect), 12, 12)
            self._cached_path = self._cached_path.subtracted(spotlight_path)

        self._cache_valid = True

    def set_target(self, widget: QWidget, padding: int = 8, animate: bool = True):
        """타겟 위젯에 스포트라이트 설정"""
        self._target_widget = widget
        self._padding = padding

        # 위젯의 전역 좌표를 부모 창 좌표로 변환
        global_pos = widget.mapToGlobal(QPoint(0, 0))
        local_pos = self._parent_window.mapFromGlobal(global_pos)

        new_rect = QRect(
            local_pos.x() - padding,
            local_pos.y() - padding,
            widget.width() + padding * 2,
            widget.height() + padding * 2
        )

        if animate and not self._spotlight_rect.isEmpty():
            # 애니메이션으로 이동 (완전히 중지 후 시작)
            self._animation.stop()
            self._animation.setStartValue(self._spotlight_rect)
            self._animation.setEndValue(new_rect)
            # 안전하게 애니메이션 시작
            if self._animation.state() != QPropertyAnimation.State.Running:
                self._animation.start()
        else:
            # 즉시 이동
            self._spotlight_rect = new_rect
            self._invalidate_cache()

    def get_target_rect(self) -> QRect:
        """현재 스포트라이트 영역 반환"""
        return self._spotlight_rect

    def clear_target(self):
        """스포트라이트 해제"""
        self._target_widget = None
        self._spotlight_rect = QRect(0, 0, 0, 0)
        self._invalidate_cache()

    def eventFilter(self, obj, event) -> bool:
        """부모 창 이벤트 필터"""
        if obj == self._parent_window:
            if event.type() == QEvent.Type.Resize:
                self._is_resizing = True
                # 자신의 크기도 부모에 맞춤
                self.setGeometry(self._parent_window.rect())
                self._invalidate_cache()
                # 쓰로틀링된 위치 업데이트
                self._resize_timer.start()
            elif event.type() == QEvent.Type.Move:
                self._resize_timer.start()

        return super().eventFilter(obj, event)

    def _on_resize_complete(self):
        """리사이즈 완료 후 스포트라이트 위치 재계산"""
        self._is_resizing = False
        if self._target_widget and self._target_widget.isVisible():
            self.set_target(self._target_widget, self._padding, animate=False)

    def paintEvent(self, event):
        """오버레이와 스포트라이트 그리기"""
        if not self._cache_valid:
            self._rebuild_path_cache()

        painter = QPainter(self)

        # 어두운 오버레이 색상
        overlay_color = QColor("#0F172A")
        overlay_color.setAlpha(200)

        # 리사이즈 중에는 간소화된 렌더링 (안티앨리어싱 + 글로우 생략)
        if self._is_resizing:
            painter.fillPath(self._cached_path, overlay_color)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 오버레이 그리기 (스포트라이트 영역 제외)
        painter.fillPath(self._cached_path, overlay_color)

        # 스포트라이트 테두리 (글로우 효과)
        if not self._spotlight_rect.isEmpty():
            # 외부 글로우
            glow_color = QColor("#3B82F6")
            glow_color.setAlpha(100)
            painter.setPen(QPen(glow_color, 4))
            painter.drawRoundedRect(
                self._spotlight_rect.adjusted(-2, -2, 2, 2),
                14, 14
            )

            # 내부 테두리
            painter.setPen(QPen(QColor("#3B82F6"), 2))
            painter.drawRoundedRect(self._spotlight_rect, 12, 12)

    def mousePressEvent(self, event):
        """오버레이 클릭 시 무시 (스포트라이트 영역은 통과)"""
        if self._spotlight_rect.contains(event.pos()):
            # 스포트라이트 영역 클릭 - 이벤트 통과
            event.ignore()
        else:
            # 오버레이 영역 클릭 - 이벤트 소비
            event.accept()

    def showEvent(self, event):
        """표시될 때 크기 동기화"""
        super().showEvent(event)
        self.setGeometry(self._parent_window.rect())
        self.raise_()

    def closeEvent(self, event):
        """닫힐 때 이벤트 필터 정리"""
        if self._parent_window:
            self._parent_window.removeEventFilter(self)
        self._resize_timer.stop()
        self._animation.stop()
        super().closeEvent(event)

    def update_position(self):
        """수동으로 위치 업데이트 (외부 호출용)"""
        if self._target_widget and self._target_widget.isVisible():
            self.set_target(self._target_widget, self._padding, animate=False)
