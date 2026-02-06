# -*- coding: utf-8 -*-
"""
Tutorial Manager for PyQt6
튜토리얼 상태 관리 및 오케스트레이션
"""
import os
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget

from ui.components.tutorial_spotlight import TutorialSpotlight
from ui.components.tutorial_tooltip import TutorialTooltip

if TYPE_CHECKING:
    from main import VideoAnalyzerGUI


# 튜토리얼 단계 정의 (고정 좌표 사용)
# tooltip_x, tooltip_y: 툴팁의 절대 좌표
TUTORIAL_STEPS: List[Dict[str, Any]] = [
    {
        "id": "mode",
        "title": "모드 선택",
        "description": "영상 제작 방식을 선택하세요.\n\n• 단일 영상: 1개 영상을 변환\n• 믹스 모드: 여러 영상을 믹스",
        "target_type": "sidebar",
        "target_id": "mode",
        "navigate_to": "mode",
        "tooltip_x": 260,
        "tooltip_y": 32,
    },
    {
        "id": "source",
        "title": "소스 입력",
        "description": "변환할 영상의 URL을 입력하세요.\n도우인 영상 링크를 붙여넣고\n추가 버튼을 클릭합니다.",
        "target_type": "sidebar",
        "target_id": "source",
        "navigate_to": "source",
        "tooltip_x": 260,
        "tooltip_y": 80,
    },
    {
        "id": "voice",
        "title": "음성 선택",
        "description": "AI 성우 목소리를 선택하세요.\n여성/남성 필터로 원하는 음성을 찾고\n▶ 버튼으로 미리 들어볼 수 있습니다.",
        "target_type": "sidebar",
        "target_id": "voice",
        "navigate_to": "voice",
        "tooltip_x": 260,
        "tooltip_y": 128,
    },
    {
        "id": "cta",
        "title": "CTA 선택",
        "description": "영상 마지막에 들어갈 행동 유도 문구를\n선택합니다. 구매 유도, 팔로우 유도 등\n다양한 옵션이 있습니다.",
        "target_type": "sidebar",
        "target_id": "cta",
        "navigate_to": "cta",
        "tooltip_x": 260,
        "tooltip_y": 176,
    },
    {
        "id": "font",
        "title": "폰트 선택",
        "description": "자막에 사용할 폰트를 선택하세요.\n각 폰트의 미리보기를 확인하고\n영상 분위기에 맞는 폰트를 고르세요.",
        "target_type": "sidebar",
        "target_id": "font",
        "navigate_to": "font",
        "tooltip_x": 260,
        "tooltip_y": 224,
    },
    {
        "id": "watermark",
        "title": "워터마크 설정",
        "description": "영상에 채널 이름 워터마크를 추가하세요.\n텍스트, 위치, 크기, 폰트를\n자유롭게 설정할 수 있습니다.",
        "target_type": "sidebar",
        "target_id": "watermark",
        "navigate_to": "watermark",
        "tooltip_x": 260,
        "tooltip_y": 272,
    },
    {
        "id": "upload",
        "title": "자동 업로드",
        "description": "완성된 영상을 유튜브에 자동 업로드하세요.\n시간 간격을 설정하면 24시간 최대 6개까지\n자동으로 업로드됩니다.",
        "target_type": "sidebar",
        "target_id": "upload",
        "navigate_to": "upload",
        "tooltip_x": 260,
        "tooltip_y": 320,
    },
    {
        "id": "queue",
        "title": "대기/진행",
        "description": "추가된 영상들의 대기열과\n진행 상태를 확인하고 관리합니다.\n완료된 영상은 여기서 다운로드됩니다.",
        "target_type": "sidebar",
        "target_id": "queue",
        "navigate_to": "queue",
        "tooltip_x": 260,
        "tooltip_y": 368,
    },
    {
        "id": "settings",
        "title": "설정",
        "description": "저장 경로, API 키, 소셜 미디어 채널 연결 등\n앱 설정을 관리합니다.\n튜토리얼도 여기서 다시 볼 수 있습니다.",
        "target_type": "sidebar",
        "target_id": "settings",
        "navigate_to": "settings",
        "tooltip_x": 260,
        "tooltip_y": 416,
    },
    {
        "id": "progress",
        "title": "제작 진행",
        "description": "실시간 영상 제작 진행 상태입니다.\n다운로드, 분석, 번역 등\n각 단계별 상태가 표시됩니다.",
        "target_type": "widget",
        "target_widget": "progress_panel",
        "navigate_to": None,
        "tooltip_x": 260,
        "tooltip_y": 720,
    },
    {
        "id": "last_login",
        "title": "최근 로그인",
        "description": "마지막 로그인 정보와 크레딧 잔여량,\n구독 상태를 확인할 수 있습니다.",
        "target_type": "widget",
        "target_widget": "last_login_label",
        "navigate_to": None,
        "tooltip_x": 1050,
        "tooltip_y": 60,
    },
    {
        "id": "api_key_setup",
        "title": "API Key 연결",
        "description": "영상 제작을 시작하려면 Gemini API Key가\n필요합니다. 아래 입력란에 API Key를 붙여넣고\n'모든 키 저장' 버튼을 클릭하세요.",
        "target_type": "widget",
        "target_widget": "api_key_section",
        "navigate_to": "settings",
        "tooltip_x": 680,
        "tooltip_y": 120,
    },
]


class TutorialManager(QObject):
    """튜토리얼 매니저 - 전체 튜토리얼 흐름 관리"""

    # 시그널
    step_changed = pyqtSignal(int)  # 현재 단계 인덱스
    tutorial_completed = pyqtSignal()
    tutorial_skipped = pyqtSignal()

    def __init__(self, gui: "VideoAnalyzerGUI"):
        super().__init__(gui)
        self._gui = gui
        self._current_step = 0
        self._is_running = False

        # UI 컴포넌트
        self._spotlight: Optional[TutorialSpotlight] = None
        self._tooltip: Optional[TutorialTooltip] = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def current_step(self) -> int:
        return self._current_step

    @property
    def total_steps(self) -> int:
        return len(TUTORIAL_STEPS)

    def start(self):
        """튜토리얼 시작"""
        if self._is_running:
            return

        self._is_running = True
        self._current_step = 0

        # 스포트라이트 생성
        self._spotlight = TutorialSpotlight(self._gui)
        self._spotlight.show()

        # 툴팁 생성
        self._tooltip = TutorialTooltip(self._gui)
        self._tooltip.next_clicked.connect(self._go_next)
        self._tooltip.prev_clicked.connect(self._go_prev)
        self._tooltip.skip_clicked.connect(self._skip)
        self._tooltip.show()

        # 첫 단계로 이동
        self._show_step(0)

    def stop(self):
        """튜토리얼 중지"""
        if not self._is_running:
            return

        self._is_running = False

        if self._spotlight:
            self._spotlight.close()
            self._spotlight.deleteLater()
            self._spotlight = None

        if self._tooltip:
            # 시그널 연결 해제 (메모리 누수 방지)
            try:
                self._tooltip.next_clicked.disconnect()
                self._tooltip.prev_clicked.disconnect()
                self._tooltip.skip_clicked.disconnect()
            except (RuntimeError, TypeError):
                pass  # 이미 해제되었거나 연결되지 않음

            self._tooltip.close()
            self._tooltip.deleteLater()
            self._tooltip = None

    def _show_step(self, step_index: int):
        """특정 단계 표시"""
        if step_index < 0 or step_index >= len(TUTORIAL_STEPS):
            return

        self._current_step = step_index
        step = TUTORIAL_STEPS[step_index]

        # 페이지 네비게이션 (필요한 경우)
        if step.get("navigate_to") and hasattr(self._gui, '_on_step_selected'):
            self._gui._on_step_selected(step["navigate_to"])

        # 약간의 딜레이 후 타겟 하이라이트 (페이지 전환 완료 대기)
        QTimer.singleShot(100, lambda: self._highlight_target(step))

        self.step_changed.emit(step_index)

    def _highlight_target(self, step: Dict[str, Any]):
        """타겟 위젯 하이라이트"""
        if not self._is_running:
            return

        target_widget = self._get_target_widget(step)

        if not target_widget:
            # 타겟을 찾지 못하면 다음 단계로
            self._go_next()
            return

        # 스포트라이트 설정
        if self._spotlight:
            self._spotlight.set_target(target_widget, padding=8)

        # 툴팁 내용 설정
        if self._tooltip:
            is_last = self._current_step == len(TUTORIAL_STEPS) - 1
            self._tooltip.set_content(
                step=self._current_step + 1,
                total=len(TUTORIAL_STEPS),
                title=step["title"],
                description=step["description"],
                is_last=is_last
            )

            # 툴팁 위치 설정
            QTimer.singleShot(50, lambda: self._position_tooltip(step))

    def _position_tooltip(self, step: Dict[str, Any]):
        """툴팁 위치 조정 (고정 좌표 사용)"""
        if not self._tooltip:
            return

        # 고정 좌표 사용
        tooltip_x = step.get("tooltip_x", 260)
        tooltip_y = step.get("tooltip_y", 100)

        self._tooltip.move(tooltip_x, tooltip_y)
        self._tooltip.raise_()

    def _get_target_widget(self, step: Dict[str, Any]) -> Optional[QWidget]:
        """단계에 해당하는 타겟 위젯 가져오기"""
        target_type = step.get("target_type")

        if target_type == "sidebar":
            # 사이드바 버튼
            target_id = step.get("target_id")
            if hasattr(self._gui, 'step_nav'):
                return self._gui.step_nav.get_button(target_id)

        elif target_type == "widget":
            # 일반 위젯
            widget_name = step.get("target_widget")
            if hasattr(self._gui, widget_name):
                return getattr(self._gui, widget_name)

        return None

    def _go_next(self):
        """다음 단계로 이동"""
        if self._current_step < len(TUTORIAL_STEPS) - 1:
            self._show_step(self._current_step + 1)
        else:
            # 마지막 단계 - 완료
            self._complete()

    def _go_prev(self):
        """이전 단계로 이동"""
        if self._current_step > 0:
            self._show_step(self._current_step - 1)

    def _skip(self):
        """튜토리얼 건너뛰기 - 체크박스 체크 시 다음부터 안 보임"""
        dont_show = self._get_dont_show_flag()
        self.stop()
        if dont_show:
            self._mark_complete()
        self.tutorial_skipped.emit()

    def _complete(self):
        """튜토리얼 완료 - 마지막까지 본 경우 항상 완료 처리"""
        self.stop()
        self._mark_complete()
        self.tutorial_completed.emit()

    def _get_dont_show_flag(self) -> bool:
        """툴팁의 '다음에 그만 보기' 체크박스 상태 확인"""
        if self._tooltip and hasattr(self._tooltip, 'dont_show_again'):
            return self._tooltip.dont_show_again
        return False

    def _mark_complete(self):
        """튜토리얼 완료 플래그 저장 (SettingsManager 사용)"""
        try:
            from managers.settings_manager import get_settings_manager
            get_settings_manager().mark_tutorial_completed()
        except Exception:
            # fallback: 파일 직접 저장
            try:
                config_dir = os.path.join(os.path.expanduser("~"), ".ssmaker")
                tutorial_flag = os.path.join(config_dir, ".tutorial_complete")
                os.makedirs(config_dir, exist_ok=True)
                with open(tutorial_flag, 'w') as f:
                    f.write("1")
            except Exception:
                pass

    @staticmethod
    def should_show_tutorial() -> bool:
        """튜토리얼을 보여줘야 하는지 확인 (SettingsManager 기반)"""
        try:
            from managers.settings_manager import get_settings_manager
            return get_settings_manager().is_first_run()
        except Exception:
            # fallback: 파일 직접 확인
            config_dir = os.path.join(os.path.expanduser("~"), ".ssmaker")
            tutorial_flag = os.path.join(config_dir, ".tutorial_complete")
            return not os.path.exists(tutorial_flag)

    @staticmethod
    def reset_tutorial_flag():
        """튜토리얼 플래그 초기화 (재실행용)"""
        try:
            from managers.settings_manager import get_settings_manager
            get_settings_manager().reset_tutorial()
        except Exception:
            config_dir = os.path.join(os.path.expanduser("~"), ".ssmaker")
            tutorial_flag = os.path.join(config_dir, ".tutorial_complete")
            if os.path.exists(tutorial_flag):
                os.remove(tutorial_flag)


def show_guided_tutorial(gui: "VideoAnalyzerGUI", on_complete=None, on_skip=None):
    """가이드 튜토리얼 표시 헬퍼 함수"""
    manager = TutorialManager(gui)

    if on_complete:
        manager.tutorial_completed.connect(on_complete)
    if on_skip:
        manager.tutorial_skipped.connect(on_skip)

    manager.start()
    return manager
