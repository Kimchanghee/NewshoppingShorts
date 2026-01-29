# -*- coding: utf-8 -*-
"""
튜토리얼 오버레이 (PyQt5 버전)
Tutorial Overlay using PyQt5

Tkinter 메인 윈도우 위에 PyQt5 오버레이를 표시합니다.
Shows PyQt5 overlay on top of Tkinter main window.
"""

import logging
import sys
from typing import Optional, Callable, List, Dict, Any, Tuple

from PyQt5.QtCore import Qt, QRect
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication
from PyQt5.QtGui import QColor, QPainter, QBrush, QPen, QFont

logger = logging.getLogger(__name__)


class TutorialOverlay(QWidget):
    """
    PyQt5 기반 튜토리얼 오버레이
    PyQt5-based Tutorial Overlay

    Tkinter 윈도우 위치를 추적하여 오버레이를 표시합니다.
    Tracks Tkinter window position and displays overlay.
    """

    STEPS: List[Dict[str, Any]] = [
        {
            "title": "1. URL 입력",
            "description": "TikTok 또는 Douyin 영상의\nURL을 붙여넣으세요",
            "icon": "🔗",
            "target": "sidebar_menu_1",
        },
        {
            "title": "2. 스타일 선택",
            "description": "음성과 폰트 스타일을\n선택하세요",
            "icon": "🎨",
            "target": "sidebar_menu_2",
        },
        {
            "title": "3. 작업 실행",
            "description": "설정이 완료되면 작업을 시작하세요.\n진행 상황은 실시간으로 표시됩니다.",
            "icon": "🚀",
            "target": "sidebar_menu_3",
        },
        {
            "title": "4. 설정",
            "description": "API 키, 테마, 출력 폴더 등\n앱의 환경설정을 변경할 수 있습니다.",
            "icon": "⚙️",
            "target": "header_settings_button",
        },
    ]

    def __init__(
        self,
        tk_root,
        on_complete: Optional[Callable] = None,
        on_skip: Optional[Callable] = None,
        theme_manager: Optional[Any] = None,
    ):
        # QApplication 확인/생성
        self._app = QApplication.instance()
        if not self._app:
            self._app = QApplication(sys.argv)
            self._own_app = True
        else:
            self._own_app = False

        super().__init__()

        self.tk_root = tk_root
        self.on_complete = on_complete
        self.on_skip = on_skip
        self.theme_manager = theme_manager
        self.current_step = 0

        # 색상 설정
        self.bg_color = QColor(26, 26, 46, 220)  # 반투명 어두운 배경
        self.border_color = QColor(139, 92, 246)  # 보라색
        self.card_bg = QColor(255, 255, 255)
        self.text_dark = QColor(31, 41, 55)
        self.text_gray = QColor(107, 114, 128)
        self.btn_color = QColor(139, 92, 246)

        self._setup_window()
        self._setup_ui()
        self._start_position_tracking()

    def _setup_window(self) -> None:
        """윈도우 설정"""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

    def _setup_ui(self) -> None:
        """UI 구성"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

    def _start_position_tracking(self) -> None:
        """Tkinter 윈도우 위치 추적 시작 - Tkinter after() 사용"""
        self._tracking = True
        self._tk_sync_position()

    def _tk_sync_position(self) -> None:
        """Tkinter after()를 사용한 위치 동기화"""
        if not self._tracking:
            return

        try:
            self._sync_position()
            # Qt 이벤트 처리
            if self._app:
                self._app.processEvents()
            # 다음 동기화 예약
            self.tk_root.after(50, self._tk_sync_position)
        except RuntimeError as e:
            # Tkinter widget destroyed or Qt application closed
            logger.debug("Position sync stopped: %s", e)
        except Exception as e:
            logger.warning("Unexpected error in position sync: %s", e)

    def _sync_position(self) -> None:
        """Tkinter 윈도우 위치와 동기화"""
        try:
            self.tk_root.update_idletasks()

            x = self.tk_root.winfo_rootx()
            y = self.tk_root.winfo_rooty()
            w = self.tk_root.winfo_width()
            h = self.tk_root.winfo_height()

            if w < 100 or h < 100:
                return

            self.setGeometry(x, y, w, h)
            self.update()

        except RuntimeError as e:
            # Tkinter widget destroyed
            logger.debug("Sync position stopped - widget destroyed: %s", e)
        except Exception as e:
            logger.warning("Unexpected error syncing position: %s", e)

    def _get_target_rect(self, target: str) -> Optional[QRect]:
        """타겟 영역 계산"""
        try:
            if not target.startswith("sidebar_menu_"):
                return None

            idx = int(target.split("_")[-1]) - 1

            # fixed_layout 값 사용
            header_height = 60
            sidebar_width = 240
            item_height = 56

            if target == "header_settings_button":
                # 설정 버튼 위치 (헤더 우측)
                # 실제 위치를 정확히 알기 어려우므로 추정치 사용
                # 우측에서 60px 정도 떨어짐
                win_w = self.width()
                x = win_w - 60 - 40
                y = 20
                w = 40
                h = 40
                return QRect(x, y, w, h)

            x = 8
            y = header_height + 17 + idx * 60
            w = sidebar_width - 16
            h = item_height

            return QRect(x, y, w, h)
        except (ValueError, IndexError) as e:
            logger.debug("Invalid target format '%s': %s", target, e)
            return None
        except Exception as e:
            logger.warning("Unexpected error calculating target rect: %s", e)
            return None

    def paintEvent(self, event) -> None:
        """오버레이 그리기"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        step = self.STEPS[self.current_step]
        rect = self._get_target_rect(step.get("target", ""))

        if rect:
            self._draw_spotlight(painter, w, h, rect)
            self._draw_card(painter, w, h, rect, step)
        else:
            self._draw_center_card(painter, w, h, step)

        self._draw_skip_link(painter, w, h)

    def _draw_spotlight(self, painter: QPainter, w: int, h: int, rect: QRect) -> None:
        """스포트라이트 효과"""
        pad = 8
        x1, y1 = rect.x() - pad, rect.y() - pad
        x2, y2 = rect.right() + pad, rect.bottom() + pad

        # 어두운 영역 (스포트라이트 제외)
        painter.setBrush(QBrush(self.bg_color))
        painter.setPen(Qt.NoPen)

        # 상단
        painter.drawRect(0, 0, w, y1)
        # 하단
        painter.drawRect(0, y2, w, h - y2)
        # 좌측
        painter.drawRect(0, y1, x1, y2 - y1)
        # 우측
        painter.drawRect(x2, y1, w - x2, y2 - y1)

        # 스포트라이트 테두리
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(self.border_color, 3))
        painter.drawRect(x1, y1, x2 - x1, y2 - y1)

    def _draw_card(
        self, painter: QPainter, w: int, h: int, rect: QRect, step: Dict[str, Any]
    ) -> None:
        """설명 카드"""
        card_w, card_h = 260, 180
        sidebar_width = 240

        card_x = sidebar_width + 50
        card_y = rect.y()

        if card_y + card_h > h - 50:
            card_y = h - card_h - 50

        self._draw_card_content(painter, card_x, card_y, card_w, card_h, step)

    def _draw_center_card(
        self, painter: QPainter, w: int, h: int, step: Dict[str, Any]
    ) -> None:
        """중앙 카드 (폴백)"""
        # 전체 어두운 배경
        painter.setBrush(QBrush(self.bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, w, h)

        card_w, card_h = 260, 180
        card_x = (w - card_w) // 2
        card_y = (h - card_h) // 2

        self._draw_card_content(painter, card_x, card_y, card_w, card_h, step)

    def _draw_card_content(
        self, painter: QPainter, x: int, y: int, w: int, h: int, step: Dict[str, Any]
    ) -> None:
        """카드 내용 그리기"""
        # 카드 배경
        painter.setBrush(QBrush(self.card_bg))
        painter.setPen(QPen(QColor(229, 231, 235), 1))
        painter.drawRoundedRect(x, y, w, h, 8, 8)

        # 단계 표시
        painter.setPen(QPen(self.text_gray))
        font = QFont("맑은 고딕", 10)
        painter.setFont(font)
        painter.drawText(
            QRect(x, y + 12, w, 20),
            Qt.AlignCenter,
            f"{self.current_step + 1} / {len(self.STEPS)}",
        )

        # 아이콘
        font_icon = QFont("Segoe UI Emoji", 24)
        painter.setFont(font_icon)
        painter.drawText(QRect(x, y + 35, w, 40), Qt.AlignCenter, step["icon"])

        # 제목
        font_title = QFont("맑은 고딕", 13)
        font_title.setBold(True)
        painter.setFont(font_title)
        painter.setPen(QPen(self.text_dark))
        painter.drawText(QRect(x, y + 75, w, 25), Qt.AlignCenter, step["title"])

        # 설명
        font_desc = QFont("맑은 고딕", 10)
        painter.setFont(font_desc)
        painter.setPen(QPen(self.text_gray))
        painter.drawText(
            QRect(x + 10, y + 100, w - 20, 50),
            Qt.AlignCenter | Qt.TextWordWrap,
            step["description"],
        )

        # 버튼 영역 저장 (클릭 처리용)
        btn_y = y + h - 40
        btn_h = 28

        # 이전 버튼
        if self.current_step > 0:
            self._prev_btn_rect = QRect(x + 15, btn_y, 50, btn_h)
            painter.setBrush(QBrush(QColor(229, 231, 235)))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(self._prev_btn_rect, 4, 4)

            painter.setPen(QPen(self.text_dark))
            font_btn = QFont("맑은 고딕", 10)
            font_btn.setBold(True)
            painter.setFont(font_btn)
            painter.drawText(self._prev_btn_rect, Qt.AlignCenter, "이전")
        else:
            self._prev_btn_rect = None

        # 다음/완료 버튼
        if self.current_step < len(self.STEPS) - 1:
            btn_text = "다음"
            btn_w = 50
        else:
            btn_text = "완료"
            btn_w = 60

        self._next_btn_rect = QRect(x + w - btn_w - 15, btn_y, btn_w, btn_h)
        painter.setBrush(QBrush(self.btn_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self._next_btn_rect, 4, 4)

        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.drawText(self._next_btn_rect, Qt.AlignCenter, btn_text)

    def _draw_skip_link(self, painter: QPainter, w: int, h: int) -> None:
        """건너뛰기 링크"""
        self._skip_rect = QRect(w - 120, h - 35, 100, 20)

        painter.setPen(QPen(QColor(156, 163, 175)))
        font = QFont("맑은 고딕", 10)
        painter.setFont(font)
        painter.drawText(self._skip_rect, Qt.AlignRight, "건너뛰기 ✕")

    def mousePressEvent(self, event) -> None:
        """클릭 처리"""
        pos = event.pos()

        # 이전 버튼
        if self._prev_btn_rect and self._prev_btn_rect.contains(pos):
            self._prev_step()
            return

        # 다음 버튼
        if hasattr(self, "_next_btn_rect") and self._next_btn_rect.contains(pos):
            self._next_step()
            return

        # 건너뛰기
        if hasattr(self, "_skip_rect") and self._skip_rect.contains(pos):
            self._skip()
            return

    def _next_step(self) -> None:
        """다음 단계"""
        if self.current_step < len(self.STEPS) - 1:
            self.current_step += 1
            self.update()
        else:
            self._complete()

    def _prev_step(self) -> None:
        """이전 단계"""
        if self.current_step > 0:
            self.current_step -= 1
            self.update()

    def _complete(self) -> None:
        """완료"""
        self.close()
        if self.on_complete:
            self.on_complete()

    def _skip(self) -> None:
        """건너뛰기"""
        self.close()
        if self.on_skip:
            self.on_skip()
        elif self.on_complete:
            self.on_complete()

    def keyPressEvent(self, event) -> None:
        """키보드 처리"""
        key = event.key()
        if key == Qt.Key_Escape:
            self._skip()
        elif key in (Qt.Key_Return, Qt.Key_Right):
            self._next_step()
        elif key == Qt.Key_Left:
            self._prev_step()

    def show(self) -> None:
        """오버레이 표시"""
        super().show()
        self.raise_()
        self.activateWindow()

    def close(self) -> None:
        """오버레이 닫기"""
        self._tracking = False
        super().close()


def test_tutorial():
    """테스트"""
    import tkinter as tk

    # Tkinter 루트 윈도우 생성
    root = tk.Tk()
    root.geometry("1300x950")
    root.title("튜토리얼 테스트")
    root.configure(bg="#f0f0f0")

    # 더미 사이드바 시뮬레이션
    sidebar = tk.Frame(root, width=240, bg="#ffffff")
    sidebar.pack(side=tk.LEFT, fill=tk.Y)
    sidebar.pack_propagate(False)

    for i, text in enumerate(["URL 입력", "스타일 선택", "작업 실행"]):
        btn = tk.Button(sidebar, text=text, width=25, height=2)
        btn.pack(pady=5, padx=10)

    def on_done():
        logger.info("튜토리얼 완료!")

    def show_tutorial():
        TutorialOverlay(root, on_complete=on_done).show()

    # 약간 지연 후 튜토리얼 표시
    root.after(500, show_tutorial)
    root.mainloop()


if __name__ == "__main__":
    test_tutorial()
