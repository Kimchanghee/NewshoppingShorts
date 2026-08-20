# -*- coding: utf-8 -*-
"""
UI Initializer - Handles UI construction for VideoAnalyzerGUI.

Extracted from main.py for cleaner separation of UI building logic.
"""
import os
from typing import TYPE_CHECKING, Dict, Any

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QCursor, QIcon, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QStackedWidget,
    QScrollArea,
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
from ui.panels.sourcing_panel import SourcingPanel
from ui.panels.multi_account_panel import MultiAccountPanel
from ui.panels.topbar_panel import TopBarPanel
from ui.components.status_bar import StatusBar
from ui.components.step_nav import StepNav
from ui.responsive import (
    FixedWindowController,
    ResponsiveLayoutController,
    apply_fixed_window_geometry,
)

from utils.app_identity import APP_DISPLAY_NAME
from utils.logging_config import get_logger
logger = get_logger(__name__)

if TYPE_CHECKING:
    from main import VideoAnalyzerGUI


class CurrentPageStack(QStackedWidget):
    """QStackedWidget that sizes from the visible page, not hidden pages."""

    def sizeHint(self):
        current = self.currentWidget()
        return current.sizeHint() if current is not None else super().sizeHint()

    def minimumSizeHint(self):
        current = self.currentWidget()
        return current.minimumSizeHint() if current is not None else super().minimumSizeHint()

    def hasHeightForWidth(self) -> bool:
        current = self.currentWidget()
        return bool(current and current.hasHeightForWidth())

    def heightForWidth(self, width: int) -> int:
        current = self.currentWidget()
        if current is None:
            return super().heightForWidth(width)
        if current.hasHeightForWidth():
            return current.heightForWidth(width)
        return current.sizeHint().height()


class CurrentPageHost(QWidget):
    """Scroll host whose geometry is derived only from the visible page."""

    def __init__(self, stack: CurrentPageStack):
        super().__init__()
        self.stack = stack
        self.host_layout = QVBoxLayout(self)
        self.host_layout.setContentsMargins(0, 0, 0, 0)
        self.host_layout.addWidget(stack)

    def _margins(self) -> tuple[int, int, int, int]:
        return self.host_layout.getContentsMargins()

    def sizeHint(self):
        hint = self.stack.sizeHint()
        left, top, right, bottom = self._margins()
        return hint + QSize(left + right, top + bottom)

    def minimumSizeHint(self):
        hint = self.stack.minimumSizeHint()
        left, top, right, bottom = self._margins()
        return hint + QSize(left + right, top + bottom)

    def hasHeightForWidth(self) -> bool:
        return self.stack.hasHeightForWidth()

    def heightForWidth(self, width: int) -> int:
        left, top, right, bottom = self._margins()
        inner_width = max(1, width - left - right)
        return self.stack.heightForWidth(inner_width) + top + bottom


class UnavailableFeaturePanel(QWidget):
    """Small recovery card used when one optional feature cannot initialize."""

    def __init__(self, component: str, code: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        title = QLabel(f"{component} 기능을 불러오지 못했습니다")
        title.setFont(QFont("", 14, QFont.Weight.Bold))
        detail = QLabel(
            f"오류 코드: {code}\n다른 기능은 계속 사용할 수 있습니다. "
            "설정을 확인한 뒤 프로그램을 다시 실행해 주세요."
        )
        detail.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(detail)
        layout.addStretch(1)


class UIInitializer:
    """Handles UI construction for VideoAnalyzerGUI."""

    def __init__(self, gui: "VideoAnalyzerGUI"):
        self.gui = gui
        self.design = gui.design
        self.theme_manager = gui.theme_manager

    def _optional_panel(self, component: str, code: str, factory):
        try:
            return factory()
        except Exception as exc:
            logger.error(
                "[Startup][%s] Optional panel %s failed",
                code,
                component,
                exc_info=True,
            )
            try:
                from startup.diagnostics import record_startup_exception

                issue = record_startup_exception(
                    "main-ui",
                    f"panel.{component}",
                    exc,
                    code=code,
                    recoverable=True,
                    offline_allowed=True,
                )
                issues = getattr(self.gui, "startup_component_issues", None)
                if isinstance(issues, list):
                    issues.append(issue.to_dict())
            except Exception:
                pass
            return UnavailableFeaturePanel(component, code)

    def build_ui(self) -> Dict[str, Any]:
        """Construct all UI components.

        Returns:
            Dictionary of created widgets for gui to store as attributes.
        """
        d = self.design
        gui = self.gui

        gui.setWindowTitle(APP_DISPLAY_NAME)
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resource", "mainTrayIcon.png")
        if os.path.exists(icon_path):
            gui.setWindowIcon(QIcon(icon_path))

        # Screen-aware initial sizing in logical pixels. The shell remains
        # resizable/maximizable so high Windows text scaling can request more
        # space instead of clipping controls inside a fixed canvas.
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            apply_fixed_window_geometry(gui, available)
        else:
            gui.setMinimumSize(760, 520)
            gui.resize(1280, 800)
        gui.fixed_window_controller = FixedWindowController(gui)

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
        left_container.setMinimumWidth(72)
        left_container.setMaximumWidth(280)
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # 1. Sidebar (StepNav)
        steps = [
            ("mode", "만들기 방식", "mode"),
            ("sourcing", "전체 자동 만들기", "sourcing"),   # Mode 3 only
            ("source", "영상 넣기", "source"),             # Mode 1/2 only
            ("voice", "목소리 선택", "voice"),
            ("cta", "마무리 멘트", "cta"),
            ("font", "글씨체 선택", "font"),
            ("subtitle_settings", "자막 설정", "subtitle_settings"),
            ("watermark", "워터마크", "watermark"),
            # '올리기 설정'은 '설정' 화면의 '영상 올리기' 탭으로 이동했으므로 좌측 메뉴에서 제외.
            ("queue", "진행 상황", "queue"),
            ("multi_account", "다계정 자동화", "multi_account"),
            ("settings", "설정", "settings"),
        ]
        step_nav = StepNav(steps)
        left_layout.addWidget(step_nav, stretch=0)

        # 2. Minimal spacer
        left_layout.addSpacing(4)

        # 3. Log Panel (ProgressPanel) - Bottom left, takes remaining space
        progress_panel = ProgressPanel(gui, gui, theme_manager=self.theme_manager)
        progress_panel.setMinimumHeight(150)
        progress_panel.setMaximumHeight(520)
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
        stack = CurrentPageStack()

        # Add padding around the stack for better visual balance
        stack_wrapper = CurrentPageHost(stack)
        stack_layout = stack_wrapper.host_layout
        stack_layout.setContentsMargins(14, 10, 14, 10)

        # An outer safety scroll area keeps every page reachable on unusually
        # short/portrait desktops. Pages that already scroll continue to size
        # normally; this activates only when a page minimum exceeds the viewport.
        content_scroll = QScrollArea()
        content_scroll.setObjectName("MainContentScroll")
        content_scroll.setWidgetResizable(True)
        content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        content_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        content_scroll.setStyleSheet(
            "#MainContentScroll { border: none; background: transparent; }"
            "#MainContentScroll > QWidget > QWidget { background: transparent; }"
        )
        content_scroll.setWidget(stack_wrapper)
        content_layout.addWidget(content_scroll)
        right_layout.addWidget(content_container)
        main_layout.addWidget(right_container, stretch=1)

        # Build pages as cards
        logger.info("[UI] 패널 생성 중... (잠시 기다려주세요)")
        mode_selection_panel = ModeSelectionPanel(stack, gui, theme_manager=self.theme_manager)
        sourcing_panel = self._optional_panel(
            "전체 자동 만들기",
            "ST-U101",
            lambda: SourcingPanel(stack, gui, theme_manager=self.theme_manager),
        )
        url_input_panel = URLInputPanel(stack, gui, theme_manager=self.theme_manager)
        voice_panel = VoicePanel(stack, gui, theme_manager=self.theme_manager)
        cta_panel = CTAPanel(stack, gui, theme_manager=self.theme_manager)
        font_panel = FontPanel(stack, gui, theme_manager=self.theme_manager)
        subtitle_settings_panel = SubtitleSettingsPanel(stack, gui, theme_manager=self.theme_manager)
        watermark_panel = WatermarkPanel(stack, gui, theme_manager=self.theme_manager)
        logger.info("[UI] 업로드/대기열 패널 생성 중...")
        upload_panel = self._optional_panel(
            "YouTube 업로드",
            "ST-Y001",
            lambda: UploadPanel(stack, gui, theme_manager=self.theme_manager),
        )
        queue_panel = QueuePanel(stack, gui, theme_manager=self.theme_manager)
        settings_tab = self._optional_panel(
            "설정",
            "ST-T001",
            lambda: SettingsTab(stack, gui, theme_manager=self.theme_manager),
        )
        subscription_panel = SubscriptionPanel(stack, gui)
        multi_account_panel = self._optional_panel(
            "다계정 자동화",
            "ST-Y002",
            lambda: MultiAccountPanel(stack, gui, theme_manager=self.theme_manager),
        )
        logger.info("[UI] 모든 패널 생성 완료")

        pages = [
            ("mode", "만들기 방식 선택", "어떤 방식으로 영상을 만들지 골라 주세요.", mode_selection_panel),
            ("sourcing", "전체 자동 만들기", "쿠팡 상품 링크로 영상 파일까지 자동 제작하고, 원하면 YouTube 업로드까지 진행해요.", sourcing_panel),
            ("source", "영상 링크 넣기", "숏폼으로 만들 영상 링크만 넣어 주세요.", url_input_panel),
            ("voice", "목소리 선택", "영상에 입힐 AI 목소리를 골라 주세요.", voice_panel),
            ("cta", "마무리 멘트 선택", "영상 끝에 넣을 행동 유도 문구를 골라 주세요.", cta_panel),
            ("font", "글씨체 선택", "자막에 쓸 글씨체를 골라 주세요.", font_panel),
            ("subtitle_settings", "자막 설정", "한국어 자막의 위치와 넣는 방식을 정해 주세요.", subtitle_settings_panel),
            ("watermark", "워터마크 설정", "영상에 옅게 새길 내 채널 이름(워터마크)을 설정해요.", watermark_panel),
            # 'upload'(올리기 설정)은 settings_tab의 '영상 올리기' 탭으로 편입 → 스택 페이지에서 제외.
            ("queue", "진행 상황", "만들 목록과 진행 상황을 봐요.", queue_panel),
            ("multi_account", "다계정 자동화", "여러 계정을 등록하고 니치별로 자동 업로드를 배분해요.", multi_account_panel),
            ("settings", "설정", "앱 설정과 API 키를 관리해요.", settings_tab),
            ("subscription", "구독 관리", "구독 상태와 요금제를 관리해요.", subscription_panel),
        ]

        page_index = {}
        for idx, (sid, title, subtitle, widget) in enumerate(pages):
            card = self._wrap_card(widget, title, subtitle, compact=sid == "mode")
            stack.addWidget(card)
            page_index[sid] = idx

        def sync_content_scroll(page_index_value: int) -> None:
            is_mode_page = page_index_value == page_index["mode"]
            content_scroll.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                if is_mode_page
                else Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )
            # The first page used to disable scrolling entirely, which made
            # its buttons unreachable on short/high-DPI desktops.
            content_scroll.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )
            if is_mode_page:
                content_scroll.horizontalScrollBar().setValue(0)
                content_scroll.verticalScrollBar().setValue(0)

        stack.currentChanged.connect(sync_content_scroll)
        sync_content_scroll(stack.currentIndex())

        # '올리기 설정'(UploadPanel)을 '설정' 화면의 '영상 올리기' 탭 안으로 편입.
        try:
            if hasattr(settings_tab, "attach_upload_panel"):
                settings_tab.attach_upload_panel(upload_panel)
        except Exception as exc:
            logger.warning("[UI] attach_upload_panel 실패: %s", exc)

        # Status bar
        status_bar = StatusBar(gui, gui)
        right_layout.addWidget(status_bar)

        gui.responsive_layout = ResponsiveLayoutController(
            window=gui,
            step_nav=step_nav,
            left_container=left_container,
            progress_panel=progress_panel,
            stack_layout=stack_layout,
            topbar=topbar,
            mode_selection_panel=mode_selection_panel,
        )
        gui.responsive_layout.apply(gui.size())

        # Return all widgets for gui to store
        return {
            "step_nav": step_nav,
            "progress_panel": progress_panel,
            "topbar": topbar,
            "stack": stack,
            "page_index": page_index,
            "status_bar": status_bar,
            "content_scroll": content_scroll,
            # Panels
            "mode_selection_panel": mode_selection_panel,
            "sourcing_panel": sourcing_panel,
            "url_input_panel": url_input_panel,
            "voice_panel": voice_panel,
            "cta_panel": cta_panel,
            "font_panel": font_panel,
            "subtitle_settings_panel": subtitle_settings_panel,
            "watermark_panel": watermark_panel,
            "upload_panel": upload_panel,
            "queue_panel": queue_panel,
            "multi_account_panel": multi_account_panel,
            "settings_tab": settings_tab,
            "subscription_panel": subscription_panel,
            "api_key_section": getattr(settings_tab, "api_section", settings_tab),
        }

    def _wrap_card(
        self,
        widget: QWidget,
        title: str,
        subtitle: str,
        *,
        compact: bool = False,
    ) -> QWidget:
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
            #ContentCard QLabel {{
                background-color: transparent;
            }}
            #ContentCard QCheckBox {{
                background-color: transparent;
            }}
            #ContentCard QRadioButton {{
                background-color: transparent;
            }}
        """)

        card_layout = QVBoxLayout(card)
        margin = 12 if compact else 20
        card_layout.setContentsMargins(margin, margin, margin, margin)
        card_layout.setSpacing(8 if compact else 12)

        header_layout = QVBoxLayout()
        header_layout.setSpacing(d.spacing.space_2)

        title_font_size = max(12, int(round(d.typography.size_lg * 0.7)))
        subtitle_font_size = max(9, int(round(d.typography.size_sm * 0.7)))

        title_lbl = QLabel(title)
        title_lbl.setWordWrap(True)
        title_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
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
        sub_lbl.setWordWrap(True)
        sub_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
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
