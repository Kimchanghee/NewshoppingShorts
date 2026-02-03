# -*- coding: utf-8 -*-
"""
Shopping Shorts Maker - PyQt6 main application entry.
Re-designed with Enhanced Design System (Industrial-Creative Hybrid)
"""
import sys
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QPushButton,
    QFrame,
    QStackedWidget,
    QSizePolicy,
)

import config
# Ensure ffmpeg is discoverable for pydub
FFMPEG_FALLBACK = r"C:\Program Files (x86)\UltData\Resources\ffmpegs"
if os.path.isdir(FFMPEG_FALLBACK) and FFMPEG_FALLBACK not in os.environ.get("PATH", ""):
    os.environ["PATH"] = FFMPEG_FALLBACK + os.pathsep + os.environ.get("PATH", "")

from app.state import AppState
from app.api_handler import APIHandler
from managers.queue_manager import QueueManager
from managers.voice_manager import VoiceManager
from managers.output_manager import OutputManager
from ui.panels import HeaderPanel, URLInputPanel, VoicePanel, QueuePanel, ProgressPanel, SubscriptionPanel, FontPanel, CTAPanel
from ui.panels.settings_tab import SettingsTab
from ui.components.status_bar import StatusBar
from ui.components.custom_dialog import show_info, show_warning
from ui.theme_manager import get_theme_manager
from ui.design_system_v2 import get_design_system
from utils.logging_config import get_logger
from utils.error_handlers import global_exception_handler
from core.providers import VertexGeminiProvider
from ui.components.step_nav import StepNav
from ui.components.tutorial_manager import TutorialManager, show_guided_tutorial
from caller import rest

logger = get_logger(__name__)

URL_PATTERN = re.compile(r"https?://[^\\s\"'<>]+")


class VideoAnalyzerGUI(QMainWindow):
    # Signals for cross-thread logging/progress
    update_status_signal = None
    log_signal = None

    def __init__(self, parent=None, login_data=None, preloaded_ocr=None):
        super().__init__(parent)
        self.login_data = login_data
        self.preloaded_ocr = preloaded_ocr
        self.state = AppState(root=self, login_data=login_data)
        self.theme_manager = get_theme_manager()
        self.design = get_design_system()  # Load enhanced design system

        self.url_queue: List[str] = []
        self.url_status: Dict[str, str] = {}
        self.url_status_message: Dict[str, str] = {}
        self.url_remarks: Dict[str, str] = {}
        self.url_timestamps: Dict[str, Any] = {}

        self.output_folder_path = self.state.output_folder_path
        self.output_folder_label = None

        self.voice_profiles = self.state.voice_profiles
        self.voice_vars = self.state.voice_vars
        self.voice_sample_paths = self.state.voice_sample_paths
        self.multi_voice_presets = self.state.multi_voice_presets
        self.available_tts_voices = self.state.available_tts_voices
        self.max_voice_selection = self.state.max_voice_selection

        self.api_key_manager = None

        self.queue_manager = QueueManager(self)
        self.voice_manager = VoiceManager(self)
        self.output_manager = OutputManager(self)
        self.api_handler = APIHandler(self)
        self.model_provider = VertexGeminiProvider()
        self._warn_if_vertex_unset()
        
        # Tutorial flag
        self._tutorial_shown = False
        self._check_first_run()

        self.init_ui()
        self.api_handler.load_saved_api_keys()
        self.refresh_user_status()

        # 구독 상태 자동 갱신 타이머 (60초마다)
        self._subscription_timer = QTimer(self)
        self._subscription_timer.timeout.connect(self._auto_refresh_subscription)
        self._subscription_timer.start(60000)  # 60초 = 60000ms

        # 구독 만료 시간 카운트다운 타이머 (1초마다)
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._update_countdown_display)
        self._subscription_expires_at = None  # ISO format datetime string

        # 초기 구독 상태 로드
        self._auto_refresh_subscription()

    def _auto_refresh_subscription(self):
        """서버에서 구독 상태를 자동으로 갱신 (60초마다 호출)"""
        if not self.login_data:
            return

        try:
            # Extract user ID
            data_part = self.login_data.get("data", {})
            if isinstance(data_part, dict):
                inner_data = data_part.get("data", {})
                user_id = inner_data.get("id")
            else:
                user_id = None

            if not user_id:
                user_id = self.login_data.get("userId")

            if not user_id:
                return

            # API 호출
            status = rest.getSubscriptionStatus(user_id)

            if status.get("success", True):  # API 성공 시
                # 구독 만료 시간 저장
                expires_at = status.get("subscription_expires_at")

                if expires_at:
                    self._subscription_expires_at = expires_at
                    # 카운트다운 타이머 시작
                    if not self._countdown_timer.isActive():
                        self._countdown_timer.start(1000)  # 1초마다
                    # 즉시 업데이트
                    self._update_countdown_display()
                else:
                    # 구독 없음 - 타이머 중지 및 레이블 숨김
                    self._subscription_expires_at = None
                    self._countdown_timer.stop()
                    self.subscription_time_label.hide()

                # 크레딧 및 배지 업데이트
                remaining = status.get("remaining", 0)
                total = status.get("work_count", 0)
                self.credits_label.setText(f"크레딧: {remaining}/{total}")

                logger.debug(f"[Subscription] Auto-refresh: expires_at={expires_at}, remaining={remaining}/{total}")

        except Exception as e:
            logger.error(f"[Subscription] Auto-refresh failed: {e}")

    def _update_countdown_display(self):
        """구독 남은 시간 카운트다운 업데이트 (1초마다 호출)"""
        if not self._subscription_expires_at:
            self.subscription_time_label.hide()
            return

        try:
            from datetime import datetime, timezone

            # ISO 형식 파싱
            expires_str = self._subscription_expires_at
            if expires_str.endswith("Z"):
                expires_str = expires_str[:-1] + "+00:00"

            expires_dt = datetime.fromisoformat(expires_str)

            # UTC로 변환 후 현재 시간과 비교
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            diff = expires_dt - now

            total_seconds = int(diff.total_seconds())

            if total_seconds <= 0:
                # 구독 만료됨
                self.subscription_time_label.setText("구독 만료됨")
                self.subscription_time_label.setStyleSheet(f"color: #EF4444; font-weight: bold;")
                self.subscription_time_label.show()
                self._countdown_timer.stop()
                return

            # 년-월-일-시간-분-초 계산
            years = total_seconds // (365 * 24 * 3600)
            remaining = total_seconds % (365 * 24 * 3600)

            months = remaining // (30 * 24 * 3600)
            remaining = remaining % (30 * 24 * 3600)

            days = remaining // (24 * 3600)
            remaining = remaining % (24 * 3600)

            hours = remaining // 3600
            remaining = remaining % 3600

            minutes = remaining // 60
            seconds = remaining % 60

            # 포맷 생성 (0인 단위는 생략)
            parts = []
            if years > 0:
                parts.append(f"{years}년")
            if months > 0:
                parts.append(f"{months}월")
            if days > 0:
                parts.append(f"{days}일")
            if hours > 0:
                parts.append(f"{hours}시간")
            if minutes > 0:
                parts.append(f"{minutes}분")
            parts.append(f"{seconds}초")

            time_str = " ".join(parts)
            self.subscription_time_label.setText(f"구독 남은 시간: {time_str}")

            # 색상 설정 (7일 미만이면 경고색)
            d = self.design
            if total_seconds < 7 * 24 * 3600:
                self.subscription_time_label.setStyleSheet(f"color: #F59E0B; font-weight: bold;")  # 주황색 경고
            else:
                self.subscription_time_label.setStyleSheet(f"color: {d.colors.success}; font-weight: bold;")

            self.subscription_time_label.show()

        except Exception as e:
            logger.error(f"[Subscription] Countdown update failed: {e}")
            self.subscription_time_label.hide()

    def _check_first_run(self):
        """Check if this is the first run to show tutorial"""
        import os
        config_dir = os.path.join(os.path.expanduser("~"), ".ssmaker")
        tutorial_flag = os.path.join(config_dir, ".tutorial_complete")
        
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        
        self._should_show_tutorial = not os.path.exists(tutorial_flag)
    
    def _mark_tutorial_complete(self):
        """Mark tutorial as completed"""
        import os
        config_dir = os.path.join(os.path.expanduser("~"), ".ssmaker")
        tutorial_flag = os.path.join(config_dir, ".tutorial_complete")
        
        with open(tutorial_flag, 'w') as f:
            f.write("1")
    
    def showEvent(self, event):
        """Show tutorial on first launch"""
        super().showEvent(event)
        
        if hasattr(self, '_should_show_tutorial') and self._should_show_tutorial and not self._tutorial_shown:
            self._tutorial_shown = True
            # Delay to let UI fully render
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, self._show_tutorial)
    
    def _show_tutorial(self):
        """Display guided tutorial with spotlight effect"""
        self._tutorial_manager = show_guided_tutorial(self)

    def show_tutorial_manual(self):
        """Manually show tutorial (from settings or help menu)"""
        # 기존 튜토리얼이 실행 중이면 중지
        if hasattr(self, '_tutorial_manager') and self._tutorial_manager and self._tutorial_manager.is_running:
            self._tutorial_manager.stop()
        self._tutorial_manager = show_guided_tutorial(self)

    # ---------------- UI -----------------
    def init_ui(self):
        d = self.design
        self.setWindowTitle("쇼핑 숏폼 메이커 - 스튜디오")
        icon_path = os.path.join(os.path.dirname(__file__), "resource", "mainTrayIcon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.resize(1440, 960)

        central = QWidget()
        central.setObjectName("CentralWidget")
        central.setStyleSheet(f"#CentralWidget {{ background-color: {d.colors.bg_main}; }}")
        self.setCentralWidget(central)

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
        
        # 1. Sidebar (StepNav) - Removed progress and subscription
        # Updated menu structure with clean icons (no emojis)
        steps = [
            ("source", "소스 입력", "source"),
            ("voice", "음성 선택", "voice"),
            ("cta", "CTA 선택", "cta"),
            ("font", "폰트 선택", "font"),
            ("queue", "대기/진행", "queue"),
            ("settings", "설정", "settings"),
        ]
        self.step_nav = StepNav(steps)
        left_layout.addWidget(self.step_nav, stretch=0)

        # 2. Minimal spacer
        left_layout.addSpacing(4)  # 8px -> 4px (tight fit)

        # 3. Log Panel (ProgressPanel) - Bottom left, takes remaining space
        self.progress_panel = ProgressPanel(self, self, theme_manager=self.theme_manager)
        self.progress_panel.setMinimumHeight(360) # Increased to avoid scroll
        self.progress_panel.setMaximumHeight(600)  # Allow growth
        self.progress_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_layout.addWidget(self.progress_panel, stretch=1)
        
        main_layout.addWidget(left_container)

        # 3. Main Content Area (Right Side)
        right_container = QWidget()
        right_container.setObjectName("RightContainer")
        right_container.setStyleSheet(f"#RightContainer {{ background-color: {d.colors.bg_main}; }}")
        
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # 3-1. Top Bar
        right_layout.addWidget(self._build_topbar())

        # 3-2. Main content area (stacked pages)
        content_container = QWidget()
        content_container.setObjectName("ContentContainer")
        content_container.setStyleSheet(f"#ContentContainer {{ background-color: {d.colors.bg_main}; }}")
        
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Stacked Pages
        self.stack = QStackedWidget()
        
        # Add padding around the stack for better visual balance
        stack_wrapper = QWidget()
        stack_layout = QVBoxLayout(stack_wrapper)
        stack_layout.setContentsMargins(20, 16, 20, 16)  # Compact padding
        stack_layout.addWidget(self.stack)
        
        content_layout.addWidget(stack_wrapper)
        right_layout.addWidget(content_container)
        main_layout.addWidget(right_container, stretch=1)

        # Build pages as cards - separated Voice, CTA, Font panels
        self.url_input_panel = URLInputPanel(self.stack, self, theme_manager=self.theme_manager)
        self.voice_panel = VoicePanel(self.stack, self, theme_manager=self.theme_manager)
        self.cta_panel = CTAPanel(self.stack, self, theme_manager=self.theme_manager)
        self.font_panel = FontPanel(self.stack, self, theme_manager=self.theme_manager)
        self.queue_panel = QueuePanel(self.stack, self, theme_manager=self.theme_manager)
        self.settings_tab = SettingsTab(self.stack, self, theme_manager=self.theme_manager)
        self.subscription_panel = SubscriptionPanel(self.stack, self)

        pages = [
            ("source", "소스 입력", "숏폼으로 변환할 쇼핑몰 링크나 영상을 추가하세요.", self.url_input_panel),
            ("voice", "음성 선택", "AI 성우 목소리와 나레이션 스타일을 선택하세요.", self.voice_panel),
            ("cta", "CTA 선택", "영상 마지막 클릭 유도 멘트를 선택하세요.", self.cta_panel),
            ("font", "폰트 선택", "자막에 사용할 폰트를 선택하세요.", self.font_panel),
            ("queue", "대기/진행", "작업 대기열 및 진행 상황을 관리합니다.", self.queue_panel),
            ("settings", "설정", "앱 설정 및 API 키를 관리합니다.", self.settings_tab),
        ]

        self.page_index = {}
        for idx, (sid, title, subtitle, widget) in enumerate(pages):
            card = self._wrap_card(widget, title, subtitle)
            self.stack.addWidget(card)
            self.page_index[sid] = idx

        self.step_nav.step_selected.connect(self._on_step_selected)
        self._on_step_selected("source")

        # Status bar is separate at main window level or can be added to bottom of content
        # Adding to right layout to keep sidebar full height
        self.status_bar = StatusBar(self, self)
        right_layout.addWidget(self.status_bar)

    # ------------- URL helpers -------------
    def add_url_from_entry(self):
        show_warning(self, "안내", "URL 추가 로직은 미구현 상태입니다.")

    def paste_and_extract(self):
        show_info(self, "안내", "클립보드 붙여넣기 로직은 미구현 상태입니다.")

    def remove_selected_url(self):
        self.queue_manager.remove_selected_url()

    def clear_url_queue(self):
        self.queue_manager.clear_url_queue()

    def clear_waiting_only(self):
        self.queue_manager.clear_waiting_only()

    # ------------- Batch stubs -------------
    def start_batch_processing(self):
        if not self.url_queue:
            show_warning(self, "안내", "대기열이 비어 있습니다.")
            return
        url = self.url_queue[0]
        self.url_status[url] = "processing"
        self.queue_manager.update_url_listbox()
        self.queue_manager.update_queue_count()
        try:
            preview = self.model_provider.generate_text("Health check: respond with 'OK'.")
            logger.info(f"Model response: {preview[:80]}")
        except Exception as e:
            logger.warning(f"Model call failed: {e}")
        show_info(self, "시작", "배치 처리를 시작합니다. (데모 모드)")

    def stop_batch_processing(self):
        show_info(self, "중지", "배치 처리를 중지했습니다. (데모 모드)")

    # ------------- Output / API -------------
    def select_output_folder(self):
        self.output_manager.select_output_folder()

    def show_api_key_manager(self):
        self.api_handler.show_api_key_manager()

    def show_api_status(self):
        self.api_handler.show_api_status()

    # ------------- Voice -------------
    def play_voice_sample(self, voice_id: str):
        self.voice_manager.play_voice_sample(voice_id)

    def _toggle_voice(self, voice_id: str):
        self.voice_manager.on_voice_card_clicked(voice_id)

    # ------------- Shell helpers -------------
    def _warn_if_vertex_unset(self):
        if not config.VERTEX_PROJECT_ID or not config.VERTEX_MODEL_ID:
            logger.warning("[Vertex] 프로젝트/모델 ID가 설정되지 않았습니다. GEMINI로 폴백됩니다.")
        if not (config.VERTEX_JSON_KEY_PATH or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")):
            logger.info("[Vertex] 서비스 계정 키 경로가 비어 있습니다. ADC 또는 기본 자격 증명 사용을 시도합니다.")

    def _build_topbar(self) -> QWidget:
        """상단 헤더바 - STITCH 디자인 적용"""
        d = self.design
        c = d.colors

        bar = QFrame()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(68)  # STITCH: 68px 고정 높이
        bar.setStyleSheet(f"""
            #TopBar {{
                background-color: {c.bg_header};
                border-bottom: 1px solid {c.border_light};
            }}
        """)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 12, 24, 12)  # STITCH: 24px 패딩 유지
        layout.setSpacing(16)  # STITCH: 20px → 16px (더 compact)

        # Title - Reduced font size
        app_title = QLabel("쇼핑 숏폼 메이커 - 스튜디오")
        app_title.setFont(QFont(
            d.typography.font_family_heading,  # Outfit
            d.typography.size_sm,              # 14px (reduced from 18px)
            QFont.Weight.Bold
        ))
        app_title.setStyleSheet(f"color: {c.text_primary}; letter-spacing: -0.5px;")
        layout.addWidget(app_title)

        layout.addStretch()

        # Credits Button - STITCH: Primary 버튼 스타일
        self.credits_label = QPushButton("")
        self.credits_label.setFont(QFont(d.typography.font_family_body, d.typography.size_xs, QFont.Weight.Bold))
        self.credits_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.credits_label.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.primary};
                color: white;
                padding: 8px 16px;
                border-radius: {d.radius.md}px;
                border: none;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {c.primary_hover};
            }}
        """)
        self.credits_label.clicked.connect(self._show_subscription_panel)
        layout.addWidget(self.credits_label)

        # Username - STITCH: 폰트 크기 증가
        self.username_label = QLabel("사용자")
        self.username_label.setFont(QFont(d.typography.font_family_body, d.typography.size_xs))  # 11px → 12px
        self.username_label.setStyleSheet(f"color: {c.text_secondary};")
        layout.addWidget(self.username_label)

        # Last login - STITCH: 폰트 크기 유지
        self.last_login_label = QLabel("")
        self.last_login_label.setFont(QFont(d.typography.font_family_body, d.typography.size_2xs))  # 10px
        self.last_login_label.setStyleSheet(f"color: {c.text_muted};")
        layout.addWidget(self.last_login_label)

        # Subscription Badge - STITCH: 스타일 개선
        self.sub_badge = QPushButton("게스트")
        self.sub_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sub_badge.setFont(QFont(d.typography.font_family_body, d.typography.size_2xs, QFont.Weight.Bold))
        self.sub_badge.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.05);
                color: {c.text_secondary};
                padding: 6px 12px;
                border-radius: {d.radius.base}px;
                border: 1px solid {c.border_light};
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.1);
                border-color: {c.primary};
            }}
        """)
        self.sub_badge.clicked.connect(self._show_subscription_panel)
        layout.addWidget(self.sub_badge)

        # 구독 남은 시간 표시 레이블
        self.subscription_time_label = QLabel("")
        self.subscription_time_label.setFont(QFont(d.typography.font_family_body, d.typography.size_2xs))
        self.subscription_time_label.setStyleSheet(f"color: {c.success}; font-weight: bold;")
        self.subscription_time_label.hide()  # 초기에는 숨김 (구독자만 표시)
        layout.addWidget(self.subscription_time_label)

        return bar

    def refresh_user_status(self):
        """Update user subscription status, credits, and user info from server"""
        if not self.login_data:
            self.sub_badge.setText("게스트")
            self.username_label.setText("게스트")
            self.last_login_label.setText("최근 로그인: -")
            return

        try:
            # Extract user ID and username safely
            # Structure: {'data': {'data': {'id': ...}}}
            data_part = self.login_data.get("data", {})
            if isinstance(data_part, dict):
                inner_data = data_part.get("data", {})
                user_id = inner_data.get("id")
                # Username might be in login_data top level or in inner data
                username = inner_data.get("username") or data_part.get("username") or "사용자"
                # Backend returns 'last_login_at' not 'last_login'
                last_login = inner_data.get("last_login_at", None)
            else:
                user_id = None
                username = "사용자"
                last_login = None
            
            if not user_id:
                # Fallback if structure is different
                user_id = self.login_data.get("userId")

            # Update username and last login labels
            self.username_label.setText(username or "사용자")
            if last_login:
                # Format last login date if it's a timestamp or ISO string
                try:
                    from datetime import datetime
                    if isinstance(last_login, str):
                        dt = datetime.fromisoformat(last_login.replace("Z", "+00:00"))
                        formatted = dt.strftime("%Y-%m-%d %H:%M")
                    else:
                        formatted = str(last_login)[:16]
                    self.last_login_label.setText(f"최근 로그인: {formatted}")
                except:
                    self.last_login_label.setText(f"최근 로그인: {str(last_login)[:10]}")
            else:
                self.last_login_label.setText("최근 로그인: 오늘")

            if user_id:
                # Call API
                info = rest.check_work_available(user_id)
                
                # Update Credits
                remaining = info.get("remaining", 0)
                total = info.get("total", 0)
                used = info.get("used", 0)
                
                # 'available' means user can still work
                is_available = info.get("available", False)
                
                self.credits_label.setText(f"크레딧: {remaining}/{total}")
                
                # Update Badge based on logic
                # You might want to get actual user_type if available from another API, 
                # but currently we can infer from credits or initial login data
                top_data = self.login_data.get("data", {}).get("data", {})
                user_type = top_data.get("user_type", "trial")
                
                d = self.design
                c = d.colors

                badge_text = user_type.upper()
                badge_bg = c.bg_card
                badge_color = c.text_secondary
                
                if user_type == "subscriber":
                    badge_text = "프로 플랜"
                    badge_bg = c.primary_light
                    badge_color = c.primary
                elif user_type == "admin":
                    badge_text = "관리자"
                    badge_bg = "#374151"  # Dark gray
                    badge_color = "#FFFFFF"
                else: # trial
                    badge_text = "체험판"
                    if remaining <= 0:
                        badge_bg = "#FEF2F2" # Red tint
                        badge_color = "#EF4444" # Red
                
                self.sub_badge.setText(badge_text)
                self.sub_badge.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {badge_bg};
                        color: {badge_color};
                        padding: 6px 12px;
                        border-radius: 6px;
                        font-weight: bold;
                        border: 1px solid {c.border_light};
                    }}
                    QPushButton:hover {{
                        background-color: {c.bg_hover};
                        opacity: 0.9;
                    }}
                """)
                
                logger.info(f"User status refreshed: {user_id} | {user_type} | {remaining}/{total}")
            else:
                logger.warning("Could not extract user_id from login_data for status refresh")
        except Exception as e:
            logger.error(f"Failed to refresh user status: {e}")

    def _wrap_card(self, widget: QWidget, title: str, subtitle: str) -> QWidget:
        """컨텐츠 카드 래퍼 - STITCH 디자인 적용"""
        d = self.design

        # Card container - STITCH: 다크 배경, 미묘한 테두리
        card = QFrame()
        card.setObjectName("ContentCard")
        card.setStyleSheet(f"""
            #ContentCard {{
                background-color: {d.colors.surface};
                border: 1px solid {d.colors.border_light};
                border-radius: {d.radius.xl}px;
            }}
        """)

        # STITCH: 카드 패딩 조정 (40px → 32px, 더 compact)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 32, 32, 32)
        card_layout.setSpacing(d.spacing.section)  # 32px

        # Header Area
        header_layout = QVBoxLayout()
        header_layout.setSpacing(d.spacing.space_2)  # 8px

        # Title - Reduced font size
        title_lbl = QLabel(title)
        title_lbl.setFont(QFont(
            d.typography.font_family_heading,  # Outfit
            d.typography.size_lg,              # 20px (reduced from 32px)
            QFont.Weight.Bold
        ))
        title_lbl.setStyleSheet(f"""
            color: {d.colors.text_primary};
            letter-spacing: -0.5px;
        """)

        # Subtitle - Reduced font size
        sub_lbl = QLabel(subtitle)
        sub_lbl.setFont(QFont(
            d.typography.font_family_body,  # Manrope
            d.typography.size_sm            # 14px (reduced from 16px)
        ))
        sub_lbl.setStyleSheet(f"color: {d.colors.text_secondary}; line-height: 1.5;")
        
        header_layout.addWidget(title_lbl)
        header_layout.addWidget(sub_lbl)
        
        card_layout.addLayout(header_layout)
        
        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {d.colors.border_light};")
        card_layout.addWidget(line)
        
        # Content
        card_layout.addWidget(widget)
        
        return card

    def _on_step_selected(self, step_id: str):
        idx = self.page_index.get(step_id, 0)
        self.stack.setCurrentIndex(idx)
        self.step_nav.set_active(step_id)

    def _show_subscription_panel(self):
        """Show the subscription/payment panel"""
        self._on_step_selected("subscription")

    # Removed _apply_shell_styles as we now apply consistent styles via DesignSystem inline or in components


def main():
    sys.excepthook = global_exception_handler
    app = QApplication(sys.argv)
    
    # Load fonts if possible, or rely on system
    # here we assume fonts are installed or fallback to system sans-serif
    
    gui = VideoAnalyzerGUI()
    gui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
