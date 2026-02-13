# -*- coding: utf-8 -*-
"""
UI Initializer - Handles UI construction for VideoAnalyzerGUI.

Extracted from main.py for cleaner separation of UI building logic.
"""
import os
from typing import TYPE_CHECKING, Dict, Any

from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QStackedWidget,
    QSizePolicy,
)

from ui.panels import (
    URLInputPanel,
    VoicePanel,
    QueuePanel,
    ProgressPanel,
    SubscriptionPanel,
    FontPanel,
    CTAPanel,
    WatermarkPanel,
    ModeSelectionPanel,
    UploadPanel,
)
from ui.panels.subtitle_settings_panel import SubtitleSettingsPanel
from ui.panels.settings_tab import SettingsTab
from ui.panels.topbar_panel import TopBarPanel
from ui.components.status_bar import StatusBar
from ui.components.step_nav import StepNav

if TYPE_CHECKING:
    from main import VideoAnalyzerGUI


class UIInitializer:
    """Handles UI construction for VideoAnalyzerGUI."""

    def __init__(self, gui: "VideoAnalyzerGUI"):
        self.gui = gui
        self.design = gui.design
        self.theme_manager = gui.theme_manager

    def build_ui(self) -> Dict[str, Any]:
        """Construct all UI components.

        Returns:
            Dictionary of created widgets for gui to store as attributes.
        """
        d = self.design
        gui = self.gui

        gui.setWindowTitle("쇼핑 숏폼 메이커 - 스튜디오")
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resource", "mainTrayIcon.png")
        if os.path.exists(icon_path):
            gui.setWindowIcon(QIcon(icon_path))

        # Screen-aware window sizing: fit within available screen area
        screen = QApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            # Use 85% of available screen, capped at 1440x960
            target_w = min(1440, int(available.width() * 0.85))
            target_h = min(960, int(available.height() * 0.85))
            # Minimum usable size
            target_w = max(1024, target_w)
            target_h = max(680, target_h)
            gui.resize(target_w, target_h)
            # Center on screen
            gui.move(
                available.x() + (available.width() - target_w) // 2,
                available.y() + (available.height() - target_h) // 2,
            )
        else:
            gui.resize(1280, 800)

        central = QWidget()
        central.setObjectName("CentralWidget")
        central.setStyleSheet(f"#CentralWidget {{ background-color: {d.colors.bg_main}; }}")
        gui.setCentralWidget(central)

        # Main Horizontal Layout (Sidebar + Content)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left Container (Sidebar + Log Panel) - Vertical Split
        left_container = QWidget()
        left_container.setObjectName("LeftContainer")
        left_container.setStyleSheet(f"#LeftContainer {{ background-color: {d.colors.bg_main}; }}")
        left_container.setMaximumWidth(280)
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # 1. Sidebar (StepNav)
        steps = [
            ("mode", "모드 선택", "mode"),
            ("source", "소스 입력", "source"),
            ("voice", "음성 선택", "voice"),
            ("cta", "CTA 선택", "cta"),
            ("font", "폰트 선택", "font"),
            ("subtitle_settings", "자막 설정", "subtitle_settings"),
            ("watermark", "워터마크", "watermark"),
            ("upload", "업로드 설정", "upload"),
            ("queue", "대기/진행", "queue"),
            ("settings", "설정", "settings"),
        ]
        step_nav = StepNav(steps)
        left_layout.addWidget(step_nav, stretch=0)

        # 2. Minimal spacer
        left_layout.addSpacing(4)

        # 3. Log Panel (ProgressPanel) - Bottom left, takes remaining space
        progress_panel = ProgressPanel(gui, gui, theme_manager=self.theme_manager)
        progress_panel.setMinimumHeight(360)
        progress_panel.setMaximumHeight(600)
        progress_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_layout.addWidget(progress_panel, stretch=1)

        main_layout.addWidget(left_container)

        # 3. Main Content Area (Right Side)
        right_container = QWidget()
        right_container.setObjectName("RightContainer")
        right_container.setStyleSheet(f"#RightContainer {{ background-color: {d.colors.bg_main}; }}")

        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # 3-1. Top Bar
        topbar = TopBarPanel(gui, d)
        right_layout.addWidget(topbar)

        # 3-2. Main content area (stacked pages)
        content_container = QWidget()
        content_container.setObjectName("ContentContainer")
        content_container.setStyleSheet(f"#ContentContainer {{ background-color: {d.colors.bg_main}; }}")

        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Stacked Pages
        stack = QStackedWidget()

        # Add padding around the stack for better visual balance
        stack_wrapper = QWidget()
        stack_layout = QVBoxLayout(stack_wrapper)
        stack_layout.setContentsMargins(20, 16, 20, 16)
        stack_layout.addWidget(stack)

        content_layout.addWidget(stack_wrapper)
        right_layout.addWidget(content_container)
        main_layout.addWidget(right_container, stretch=1)

        # Build pages as cards
        mode_selection_panel = ModeSelectionPanel(stack, gui, theme_manager=self.theme_manager)
        url_input_panel = URLInputPanel(stack, gui, theme_manager=self.theme_manager)
        voice_panel = VoicePanel(stack, gui, theme_manager=self.theme_manager)
        cta_panel = CTAPanel(stack, gui, theme_manager=self.theme_manager)
        font_panel = FontPanel(stack, gui, theme_manager=self.theme_manager)
        subtitle_settings_panel = SubtitleSettingsPanel(stack, gui, theme_manager=self.theme_manager)
        watermark_panel = WatermarkPanel(stack, gui, theme_manager=self.theme_manager)
        upload_panel = UploadPanel(stack, gui, theme_manager=self.theme_manager)
        queue_panel = QueuePanel(stack, gui, theme_manager=self.theme_manager)
        settings_tab = SettingsTab(stack, gui, theme_manager=self.theme_manager)
        subscription_panel = SubscriptionPanel(stack, gui)

        pages = [
            ("mode", "모드 선택", "영상 제작 방식을 선택하세요.", mode_selection_panel),
            ("source", "소스 입력", "숏폼으로 변환할 쇼핑몰 링크나 영상을 추가하세요.", url_input_panel),
            ("voice", "음성 선택", "AI 성우 목소리와 나레이션 스타일을 선택하세요.", voice_panel),
            ("cta", "CTA 선택", "영상 마지막 클릭 유도 멘트를 선택하세요.", cta_panel),
            ("font", "폰트 선택", "자막에 사용할 폰트를 선택하세요.", font_panel),
            ("subtitle_settings", "자막 설정", "한국어 자막의 위치와 배치 방식을 설정하세요.", subtitle_settings_panel),
            ("watermark", "워터마크 설정", "영상에 표시할 워터마크를 설정하세요.", watermark_panel),
            ("upload", "소셜 미디어 업로드 설정", "채널 연결 및 자동 업로드 프롬프트를 설정합니다.", upload_panel),
            ("queue", "대기/진행", "작업 대기열 및 진행 상황을 관리합니다.", queue_panel),
            ("settings", "설정", "앱 설정 및 API 키를 관리합니다.", settings_tab),
            ("subscription", "구독 관리", "구독 상태 및 플랜을 관리합니다.", subscription_panel),
        ]

        page_index = {}
        for idx, (sid, title, subtitle, widget) in enumerate(pages):
            card = self._wrap_card(widget, title, subtitle)
            stack.addWidget(card)
            page_index[sid] = idx

        # Status bar
        status_bar = StatusBar(gui, gui)
        right_layout.addWidget(status_bar)

        # Return all widgets for gui to store
        return {
            "step_nav": step_nav,
            "progress_panel": progress_panel,
            "topbar": topbar,
            "stack": stack,
            "page_index": page_index,
            "status_bar": status_bar,
            # Panels
            "mode_selection_panel": mode_selection_panel,
            "url_input_panel": url_input_panel,
            "voice_panel": voice_panel,
            "cta_panel": cta_panel,
            "font_panel": font_panel,
            "subtitle_settings_panel": subtitle_settings_panel,
            "watermark_panel": watermark_panel,
            "upload_panel": upload_panel,
            "queue_panel": queue_panel,
            "settings_tab": settings_tab,
            "subscription_panel": subscription_panel,
            "api_key_section": settings_tab.api_section,
        }

    def _wrap_card(self, widget: QWidget, title: str, subtitle: str) -> QWidget:
        """Create content card wrapper with STITCH design.

        Args:
            widget: The panel widget to wrap
            title: Card title
            subtitle: Card subtitle/description

        Returns:
            Wrapped card widget.
        """
        d = self.design

        card = QFrame()
        card.setObjectName("ContentCard")
        card.setStyleSheet(f"""
            #ContentCard {{
                background-color: {d.colors.surface};
                border: 1px solid {d.colors.border_light};
                border-radius: {d.radius.xl}px;
            }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 32, 32, 32)
        card_layout.setSpacing(d.spacing.section)

        header_layout = QVBoxLayout()
        header_layout.setSpacing(d.spacing.space_2)

        title_font_size = max(12, int(round(d.typography.size_lg * 0.7)))
        subtitle_font_size = max(9, int(round(d.typography.size_sm * 0.7)))

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont(
            d.typography.font_family_heading,
            title_font_size,
            QFont.Weight.Bold
        ))
        title_lbl.setStyleSheet(f"""
            color: {d.colors.text_primary};
            letter-spacing: -0.5px;
        """)

        sub_lbl = QLabel(subtitle)
        sub_lbl.setFont(QFont(
            d.typography.font_family_body,
            subtitle_font_size
        ))
        sub_lbl.setStyleSheet(f"color: {d.colors.text_secondary}; line-height: 1.5;")

        header_layout.addWidget(title_lbl)
        header_layout.addWidget(sub_lbl)

        card_layout.addLayout(header_layout)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {d.colors.border_light};")
        card_layout.addWidget(line)

        card_layout.addWidget(widget)

        return card
