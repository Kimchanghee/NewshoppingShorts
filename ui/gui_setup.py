"""
GUI Setup Module

This module handles the UI initialization and setup for VideoAnalyzerGUI.
Extracted from main.py for better code organization.
"""

import tkinter as tk
from typing import TYPE_CHECKING

from ui.components import StatusBar
from ui.components.settings_button import SettingsButton
from ui.components.settings_modal import SettingsModal
from ui.components.theme_toggle import ThemeToggle
from ui.components.tutorial_overlay import TutorialOverlay
from ui.components.sidebar_container import SidebarContainer
from ui.components.fixed_layout import LAYOUT
from ui.panels.url_content_panel import URLContentPanel
from ui.panels.style_tab import StyleTab
from ui.panels.queue_tab import QueueTab
from ui.theme_manager import get_theme_manager
from managers.settings_manager import get_settings_manager
from utils.logging_config import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from main import VideoAnalyzerGUI


class GUISetup:
    """Handles GUI initialization and setup"""

    def __init__(self, app: 'VideoAnalyzerGUI'):
        self.app = app

    def setup_ui(self):
        """전체 UI 구성 - 사이드바 기반 레이아웃"""
        # ===== 테마 관리자 초기화 =====
        self.app.theme_manager = get_theme_manager()

        # 저장된 테마 설정 로드
        self._load_saved_theme()

        self.app._apply_theme_colors()

        # 테마 변경 옵저버 등록
        self.app.theme_manager.register_observer(self.app._on_theme_changed)

        self.app.root.configure(bg=self.app.bg_color)

        # Style configuration
        self.app._configure_ttk_styles()

        # ===== 헤더 영역 (고정 높이) =====
        self._create_header()

        # ===== 사이드바 컨테이너 =====
        self._create_sidebar()

        # ===== 상태 표시줄 =====
        StatusBar(self.app.root, self.app)

        # 더미 위젯 (호환성)
        self.app.create_dummy_widgets()

        # 기존 패널에서 사용하던 위젯 참조 설정 (호환성)
        self.app._setup_legacy_widget_references()

        # UI 초기화
        self.app.update_analyze_button()
        self.app.refresh_output_folder_display()

        # 반응형 창 크기 이벤트 바인딩
        self.app.root.bind("<Configure>", self.app.on_window_resize)

        # 스크린샷 캡처 단축키 (Ctrl+Shift+S)
        self.app.root.bind("<Control-Shift-s>", self.app._capture_all_pages)
        self.app.root.bind("<Control-Shift-S>", self.app._capture_all_pages)

        # ===== 첫 실행 시 튜토리얼 표시 =====
        self._show_tutorial_if_first_run()

    def _load_saved_theme(self):
        """저장된 테마 설정 로드"""
        try:
            settings = get_settings_manager()
            saved_theme = settings.get_theme()
            if saved_theme in ("light", "dark"):
                self.app.theme_manager.set_theme(saved_theme)
        except Exception:
            pass

    def _create_header(self):
        """헤더 영역 생성"""
        self.app._header_frame = tk.Frame(
            self.app.root,
            bg=self.app.header_bg,
            height=LAYOUT.HEADER_HEIGHT
        )
        self.app._header_frame.pack(fill=tk.X)
        self.app._header_frame.pack_propagate(False)

        # 로고/타이틀
        self.app._title_frame = tk.Frame(self.app._header_frame, bg=self.app.header_bg)
        self.app._title_frame.pack(side=tk.LEFT, padx=20, pady=10)

        self.app._main_title_label = tk.Label(
            self.app._title_frame,
            text="쇼핑 숏폼 메이커",
            font=("맑은 고딕", 16, "bold"),
            bg=self.app.header_bg,
            fg=self.app.primary_color
        )
        self.app._main_title_label.pack(side=tk.LEFT)

        self.app._sub_title_label = tk.Label(
            self.app._title_frame,
            text="AI 기반 숏폼 자동 제작",
            font=("맑은 고딕", 10),
            bg=self.app.header_bg,
            fg=self.app.secondary_text
        )
        self.app._sub_title_label.pack(side=tk.LEFT, padx=(12, 0))

        # 우측: 설정 버튼 + 테마 토글
        self.app._right_frame = tk.Frame(self.app._header_frame, bg=self.app.header_bg)
        self.app._right_frame.pack(side=tk.RIGHT, padx=20, pady=10)

        # 테마 토글
        self.app.theme_toggle = ThemeToggle(
            self.app._right_frame,
            theme_manager=self.app.theme_manager,
            on_toggle=self.app._toggle_theme
        )
        self.app.theme_toggle.pack(side=tk.RIGHT)

        # 설정 버튼 (톱니바퀴)
        self.app.settings_button = SettingsButton(
            self.app._right_frame,
            theme_manager=self.app.theme_manager,
            on_click=self._open_settings_modal
        )
        self.app.settings_button.pack(side=tk.RIGHT, padx=(0, 12))

        # 헤더 하단 구분선
        self.app._header_divider = tk.Frame(self.app.root, bg=self.app.border_color, height=1)
        self.app._header_divider.pack(fill=tk.X)

    def _create_sidebar(self):
        """사이드바 컨테이너 생성"""
        self.app.sidebar_container = SidebarContainer(
            self.app.root,
            theme_manager=self.app.theme_manager,
            sidebar_width=LAYOUT.SIDEBAR_WIDTH,
            gui=self.app
        )
        self.app.sidebar_container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # 메뉴 추가: URL 입력 (1단계), 스타일 (2단계), 작업 (3단계)
        self.app.url_panel = URLContentPanel(
            self.app.sidebar_container.content_frame,
            self.app,
            theme_manager=self.app.theme_manager
        )
        self.app.sidebar_container.add_menu_item("url", "URL 입력", self.app.url_panel, step_number=1, icon="")

        self.app.style_tab = StyleTab(
            self.app.sidebar_container.content_frame,
            self.app,
            theme_manager=self.app.theme_manager
        )
        self.app.sidebar_container.add_menu_item("style", "스타일", self.app.style_tab, step_number=2, icon="")

        self.app.queue_tab = QueueTab(
            self.app.sidebar_container.content_frame,
            self.app,
            theme_manager=self.app.theme_manager
        )
        self.app.sidebar_container.add_menu_item("queue", "작업", self.app.queue_tab, step_number=3, icon="")

        # 기본 메뉴 선택 (URL 입력이 첫 단계)
        self.app.sidebar_container.select_menu("url")

        # 호환성을 위한 별칭
        self.app.settings_tab = self.app.url_panel
        self.app.tab_container = self.app.sidebar_container  # 레거시 호환

    def _open_settings_modal(self):
        """설정 모달 열기"""
        SettingsModal(self.app.root, self.app, theme_manager=self.app.theme_manager)

    def _show_tutorial_if_first_run(self):
        """첫 실행 시 튜토리얼 오버레이 표시"""
        try:
            settings = get_settings_manager()
            if settings.is_first_run():
                self.app.root.after(500, lambda: self._show_tutorial(settings))
        except Exception as e:
            logger.warning(f"튜토리얼 표시 확인 실패: {e}")

    def _show_tutorial(self, settings=None):
        """튜토리얼 오버레이 표시"""
        def on_tutorial_complete():
            if settings:
                settings.mark_tutorial_completed()
            logger.info("튜토리얼 완료")
            self.app._tutorial_overlay = None

        self.app._tutorial_overlay = TutorialOverlay(
            self.app.root,
            on_complete=on_tutorial_complete,
            theme_manager=self.app.theme_manager
        )
        self.app._tutorial_overlay.show()

    def show_tutorial(self):
        """수동으로 튜토리얼 표시"""
        self._show_tutorial()
