"""
Settings tab implementation (PyQt6).
Provides API key management, output folder settings, theme settings, and app info.
Uses design system v2 for consistent styling.
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
import requests
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QLineEdit, QPushButton, QScrollArea, QFileDialog, QCheckBox, QTextEdit,
    QTabWidget
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QFont, QDesktopServices
from ui.design_system_v2 import get_design_system
from ui.components.base_widget import ThemedMixin
from utils.secrets_manager import SecretsManager
from utils.logging_config import get_logger
from core.api.ApiKeyManager import APIKeyManager
from managers.settings_manager import get_settings_manager
from managers.coupang_manager import get_coupang_manager
from managers.linktree_manager import get_linktree_manager
from managers.tiktok_manager import get_tiktok_manager
import config

# Gemini API 키 패턴 검증
GEMINI_API_KEY_PATTERN = re.compile(r"^AIza[A-Za-z0-9_-]{35,96}$")
LINKTREE_SIGNUP_URL = "https://linktr.ee/register"
LINKTREE_ADMIN_URL = "https://linktr.ee/admin/links"
TIKTOK_LOGIN_URL = "https://www.tiktok.com/login"
INSTAGRAM_LOGIN_URL = "https://www.instagram.com/accounts/login/"
THREADS_LOGIN_URL = "https://www.threads.com/login"
META_APPS_URL = "https://developers.facebook.com/apps/"
SETUP_NOTICE_BASE_URL = "https://shoppingshorts.store/notice"
logger = get_logger(__name__)


class SettingsSection(QFrame):
    """A styled section container for settings groups"""
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.ds = get_design_system()
        self.title = title
        self._setup_ui()
    
    def _setup_ui(self):
        ds = self.ds
        c = ds.colors
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {c.surface};
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.base}px;
            }}
        """)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(
            ds.spacing.space_5, ds.spacing.space_4, 
            ds.spacing.space_5, ds.spacing.space_4
        )
        self.main_layout.setSpacing(ds.spacing.space_3)
        
        # Title
        title_label = QLabel(self.title)
        title_label.setFont(QFont(ds.typography.font_family_primary, 14, QFont.Weight.Bold))
        title_label.setStyleSheet(f"""
            color: {c.text_primary}; 
            border: none; 
            background: transparent;
        """)
        self.main_layout.addWidget(title_label)
        
        # Content area
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(ds.spacing.space_3)
        self.main_layout.addLayout(self.content_layout)
    
    def add_row(self, label_text: str, widget: QWidget):
        """Add a labeled widget row"""
        ds = self.ds
        c = ds.colors
        row = QHBoxLayout()
        row.setSpacing(ds.spacing.space_4)
        
        label = QLabel(label_text)
        label.setFont(QFont(ds.typography.font_family_primary, 12))
        label.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent; padding-bottom: 3px;")
        label.setMinimumWidth(120)
        row.addWidget(label)
        
        widget.setStyleSheet(widget.styleSheet() + " border: none;")
        row.addWidget(widget, stretch=1)
        
        self.content_layout.addLayout(row)


class SettingsTab(QWidget, ThemedMixin):
    """Settings page with API keys, output folder, theme, and app info"""
    SETUP_STEP_DEFS: Dict[str, Dict[str, str]] = {
        "precheck": {"title": "사전 점검", "actor": "auto"},
        "youtube_prepare": {"title": "YouTube OAuth 준비", "actor": "auto"},
        "youtube_user_auth": {"title": "YouTube 로그인/동의", "actor": "user"},
        "youtube_verify": {"title": "YouTube 연결 검증", "actor": "auto"},
        "tiktok_prepare": {"title": "TikTok OAuth 준비", "actor": "auto"},
        "tiktok_user_auth": {"title": "TikTok 로그인/승인", "actor": "user"},
        "tiktok_code_exchange": {"title": "TikTok 코드 교환", "actor": "auto"},
        "tiktok_verify": {"title": "TikTok 연결 검증", "actor": "auto"},
        "instagram_user_setup": {"title": "Instagram 연결 정보 입력", "actor": "user"},
        "instagram_verify": {"title": "Instagram 연결 검증", "actor": "auto"},
        "threads_user_setup": {"title": "Threads 연결 정보 입력", "actor": "user"},
        "threads_verify": {"title": "Threads 연결 검증", "actor": "auto"},
        "linktree_user_setup": {"title": "Linktree 로그인/주소 입력", "actor": "user"},
        "linktree_save_verify": {"title": "Linktree 저장/검증", "actor": "auto"},
        "final_verify": {"title": "최종 연결 테스트", "actor": "auto"},
    }
    
    def __init__(self, parent=None, gui=None, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.ds = get_design_system()
        self.__init_themed__(theme_manager)
        self._setup_running = False
        self._setup_scope = "all"
        self._setup_steps: List[str] = []
        self._setup_step_index = -1
        self._setup_waiting_user = False
        self._setup_action_callback: Optional[Callable[[], None]] = None
        self._setup_rows: Dict[str, Dict[str, QLabel]] = {}
        self._setup_last_tiktok_auth_url = ""
        self._setup_clipboard_last_text = ""
        self._setup_clipboard_auto_enabled = True
        self._setup_clipboard_timer = QTimer(self)
        self._setup_clipboard_timer.setInterval(1200)
        self._setup_clipboard_timer.timeout.connect(self._poll_setup_clipboard)
        self._codex_status_summary = "Codex 상태: 미확인"
        self._computer_use_paid_cache_value = False
        self._computer_use_paid_cache_ts = 0.0
        self._create_widgets()
        self._apply_theme()
        self._setup_clipboard_timer.start()
        QTimer.singleShot(0, self.refresh_work_community_stats)
    
    def _create_widgets(self):
        ds = self.ds
        c = ds.colors
        
        # ── 탭 구조: 길게 스크롤하던 설정들을 주제별 탭으로 분리 ──
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background-color: {c.background};
            }}
            QTabBar::tab {{
                background-color: {c.surface_variant};
                color: {c.text_secondary};
                padding: 9px 18px;
                margin-right: 4px;
                border-top-left-radius: {ds.radius.sm}px;
                border-top-right-radius: {ds.radius.sm}px;
                font-size: 13px;
                font-weight: 600;
            }}
            QTabBar::tab:selected {{
                background-color: {c.primary};
                color: {c.text_on_primary};
            }}
            QTabBar::tab:hover:!selected {{
                color: {c.text_primary};
            }}
        """)
        main_layout.addWidget(self.tab_widget)

        def _make_tab():
            tab_scroll = QScrollArea()
            tab_scroll.setWidgetResizable(True)
            tab_scroll.setFrameShape(QFrame.Shape.NoFrame)
            tab_scroll.setStyleSheet(f"background-color: {c.background}; border: none;")
            page = QWidget()
            lay = QVBoxLayout(page)
            lay.setContentsMargins(
                ds.spacing.space_4, ds.spacing.space_4,
                ds.spacing.space_4, ds.spacing.space_4
            )
            lay.setSpacing(ds.spacing.space_5)
            tab_scroll.setWidget(page)
            return tab_scroll, lay

        gen_scroll, gen_layout = _make_tab()
        api_scroll, api_layout = _make_tab()
        upload_scroll, upload_layout = _make_tab()
        connect_scroll, connect_layout = _make_tab()
        etc_scroll, etc_layout = _make_tab()

        self.tab_widget.addTab(gen_scroll, "일반")
        self.tab_widget.addTab(api_scroll, "API 키")
        self.tab_widget.addTab(upload_scroll, "영상 올리기")
        self.tab_widget.addTab(connect_scroll, "연결 도우미")
        self.tab_widget.addTab(etc_scroll, "구독·문의")

        # focus 헬퍼/탭 이동에서 사용
        self.scroll_area = api_scroll          # focus_api_key_setup 용
        self._connect_scroll = connect_scroll  # focus_coupang_setup 용
        self._upload_tab_layout = upload_layout
        self._tab_index = {"general": 0, "api": 1, "upload": 2, "connect": 3, "etc": 4}

        # =================== SECTION: Output Folder ===================
        output_section = SettingsSection("저장 경로 설정")
        
        # Folder path display
        folder_container = QWidget()
        folder_layout = QHBoxLayout(folder_container)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.setSpacing(ds.spacing.space_3)
        
        self.folder_input = QLineEdit()
        self.folder_input.setReadOnly(True)
        self.folder_input.setPlaceholderText("출력 폴더를 선택하세요")
        if self.gui:
            self.folder_input.setText(getattr(self.gui, 'output_folder_path', ''))
        self.folder_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {c.surface_variant};
                color: {c.text_primary};
                padding: 10px 14px;
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.sm}px;
                font-size: {ds.typography.size_sm}px;
            }}
        """)
        folder_layout.addWidget(self.folder_input, stretch=1)
        
        self.folder_btn = QPushButton("폴더 변경")
        self.folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.folder_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.primary};
                color: white;
                padding: 10px 16px;
                border-radius: {ds.radius.sm}px;
                font-weight: bold;
                font-size: {ds.typography.size_sm}px;
            }}
            QPushButton:hover {{
                background-color: {c.secondary};
            }}
        """)
        self.folder_btn.clicked.connect(self._select_folder)
        folder_layout.addWidget(self.folder_btn)

        self.folder_open_btn = QPushButton("폴더 열기")
        self.folder_open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.folder_open_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.surface_variant};
                color: {c.text_primary};
                padding: 10px 16px;
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.sm}px;
                font-weight: bold;
                font-size: {ds.typography.size_sm}px;
            }}
            QPushButton:hover {{
                background-color: {c.surface};
            }}
        """)
        self.folder_open_btn.clicked.connect(self._open_folder)
        folder_layout.addWidget(self.folder_open_btn)

        output_section.add_row("저장 위치", folder_container)
        gen_layout.addWidget(output_section)

        # =================== SECTION: Work Community ===================
        self.work_community_section = SettingsSection("작업 커뮤니티")

        self.work_community_intro = QLabel(
            "현재까지 작업량은? 내가 만든 쇼츠 수를 확인하고 커뮤니티 레벨을 올려보세요."
        )
        self.work_community_intro.setWordWrap(True)
        self.work_community_intro.setStyleSheet(
            f"color: {c.text_secondary}; border: none; background: transparent; padding-bottom: 3px;"
        )
        self.work_community_section.content_layout.addWidget(self.work_community_intro)

        self.work_community_question = QLabel("현재까지 작업량은?")
        self.work_community_question.setStyleSheet(
            f"color: {c.text_muted}; border: none; background: transparent; font-size: 11px; padding-bottom: 3px;"
        )
        self.work_community_section.content_layout.addWidget(self.work_community_question)

        self.work_community_count = QLabel("0회 생성")
        self.work_community_count.setStyleSheet(
            f"color: {c.text_primary}; border: none; background: transparent; font-size: 26px; font-weight: 800;"
        )
        self.work_community_section.content_layout.addWidget(self.work_community_count)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(ds.spacing.space_3)

        self.work_community_level = QLabel("레벨: 새싹 메이커")
        self.work_community_level.setStyleSheet(
            f"background-color: {c.surface_variant}; color: {c.text_primary}; border-radius: {ds.radius.full}px; padding: 4px 10px; font-weight: 600;"
        )
        meta_row.addWidget(self.work_community_level, alignment=Qt.AlignmentFlag.AlignLeft)

        self.work_community_next = QLabel("다음 레벨까지 5회")
        self.work_community_next.setStyleSheet(
            f"color: {c.text_secondary}; border: none; background: transparent; padding-bottom: 3px;"
        )
        meta_row.addWidget(self.work_community_next, alignment=Qt.AlignmentFlag.AlignLeft)
        meta_row.addStretch()
        self.work_community_section.content_layout.addLayout(meta_row)

        self.work_community_refresh_btn = QPushButton("작업량 새로고침")
        self.work_community_refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.work_community_refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.surface_variant};
                color: {c.text_primary};
                padding: 8px 14px;
                border-radius: {ds.radius.sm}px;
                border: 1px solid {c.border_light};
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {c.surface};
            }}
        """)
        self.work_community_refresh_btn.clicked.connect(self.refresh_work_community_stats)
        self.work_community_section.content_layout.addWidget(
            self.work_community_refresh_btn,
            alignment=Qt.AlignmentFlag.AlignLeft
        )

        gen_layout.addWidget(self.work_community_section)

        # =================== SECTION: Guided Setup Assistant ===================
        self._build_setup_assistant_section(connect_layout)
        
        # =================== SECTION: API Key Management ===================
        self.api_section = SettingsSection("API 키 설정 (최대 8개)")

        # API KEY 발급 안내 링크 (타이틀 바로 아래)
        api_guide_link = QLabel('<a href="https://ssmaker.lovable.app/notice" style="color: #3B82F6; text-decoration: none;">API KEY 발급 안내 →</a>')
        api_guide_link.setOpenExternalLinks(True)
        api_guide_link.setStyleSheet(f"border: none; background: transparent; font-size: 12px;")
        self.api_section.content_layout.addWidget(api_guide_link)

        # 설명 라벨
        desc_label = QLabel("여러 개의 API 키를 등록하면 자동으로 로테이션됩니다. Rate Limit 발생 시 다음 키로 자동 전환됩니다.")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"color: {c.text_muted}; border: none; background: transparent; font-size: 11px; padding-bottom: 3px;")
        self.api_section.content_layout.addWidget(desc_label)

        # API 키 입력 필드들 (8개)
        self.api_key_inputs = []
        MAX_API_KEYS = 8

        input_style = f"""
            QLineEdit {{
                background-color: {c.surface_variant};
                color: {c.text_primary};
                padding: 8px 12px;
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.sm}px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {c.primary};
            }}
        """

        for i in range(1, MAX_API_KEYS + 1):
            row_widget = QWidget()
            row_widget.setStyleSheet("background: transparent; border: none;")
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            # 라벨
            label = QLabel(f"키 {i}")
            label.setFixedWidth(30)
            label.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent; font-size: 12px;")
            row_layout.addWidget(label)

            # 입력 필드
            key_input = QLineEdit()
            key_input.setPlaceholderText(f"API 키 {i} (AIza...)")
            key_input.setEchoMode(QLineEdit.EchoMode.Password)
            key_input.setStyleSheet(input_style)
            row_layout.addWidget(key_input, stretch=1)

            # 보기/숨기기 버튼
            toggle_btn = QPushButton("👁")
            toggle_btn.setFixedSize(32, 32)
            toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: 1px solid {c.border_light};
                    border-radius: 4px;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: {c.surface_variant};
                }}
            """)
            toggle_btn.clicked.connect(lambda checked, inp=key_input: self._toggle_key_visibility(inp))
            row_layout.addWidget(toggle_btn)

            self.api_section.content_layout.addWidget(row_widget)
            self.api_key_inputs.append(key_input)

        # 버튼 영역
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 8, 0, 0)
        btn_layout.setSpacing(12)

        # 저장된 키 불러오기 (기본: 자동 로드하지 않음)
        # 보안/UX: 앱 첫 실행/빌드 테스트 시 민감 정보가 "입력칸에 미리 채워진 것"처럼 보이지 않도록
        # 사용자가 원할 때만 불러와서 표시합니다.
        self.api_load_btn = QPushButton("저장된 키 불러오기")
        self.api_load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.api_load_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.surface_variant};
                color: {c.text_primary};
                padding: 10px 20px;
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.sm}px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {c.surface};
            }}
        """)
        self.api_load_btn.clicked.connect(self._load_saved_api_keys)
        btn_layout.addWidget(self.api_load_btn)

        # 저장 버튼
        self.api_save_btn = QPushButton("모든 키 저장")
        self.api_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.api_save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.primary};
                color: white;
                padding: 10px 24px;
                border-radius: {ds.radius.sm}px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {c.secondary};
            }}
        """)
        self.api_save_btn.clicked.connect(self._save_all_api_keys)
        btn_layout.addWidget(self.api_save_btn)

        # 상태 확인 버튼
        self.api_status_btn = QPushButton("API 상태 확인")
        self.api_status_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.api_status_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.surface_variant};
                color: {c.text_primary};
                padding: 10px 20px;
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.sm}px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {c.surface};
            }}
        """)
        self.api_status_btn.clicked.connect(self._show_api_status)
        btn_layout.addWidget(self.api_status_btn)

        # 전체 삭제 버튼
        self.api_clear_btn = QPushButton("전체 삭제")
        self.api_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.api_clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {c.error};
                padding: 10px 20px;
                border: 1px solid {c.error};
                border-radius: {ds.radius.sm}px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {c.error};
                color: white;
            }}
        """)
        self.api_clear_btn.clicked.connect(self._clear_all_api_keys)
        btn_layout.addWidget(self.api_clear_btn)

        btn_layout.addStretch()
        self.api_section.content_layout.addWidget(btn_container)

        # 등록된 키 개수 표시
        self.api_count_label = QLabel("저장된 키: 0개")
        self.api_count_label.setStyleSheet(f"color: {c.text_muted}; border: none; background: transparent; font-size: 11px; padding-bottom: 3px;")
        self.api_section.content_layout.addWidget(self.api_count_label)

        api_layout.addWidget(self.api_section)

        # 저장된 키 개수만 표시 (값은 자동으로 입력칸에 채우지 않음)
        self._update_key_count()
        
        # =================== SECTION: Coupang + Linktree Automation ===================
        self.link_automation_section = SettingsSection("링크트리 연결 (선택)")

        automation_intro = QLabel(
            "쿠팡 단축 링크를 직접 쓰면 아래 공개 주소만 저장하면 됩니다. "
            "API와 Webhook은 자동화가 필요할 때만 열어 설정하세요."
        )
        automation_intro.setWordWrap(True)
        automation_intro.setStyleSheet(
            f"color: {c.text_muted}; border: none; background: transparent; font-size: 11px; padding-bottom: 3px;"
        )
        self.link_automation_section.content_layout.addWidget(automation_intro)

        automation_input_style = f"""
            QLineEdit {{
                background-color: {c.surface_variant};
                color: {c.text_primary};
                padding: 8px 12px;
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.sm}px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {c.primary};
            }}
        """

        automation_button_style = f"""
            QPushButton {{
                background-color: {c.surface_variant};
                color: {c.text_primary};
                padding: 8px 12px;
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.sm}px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {c.surface};
            }}
        """
        automation_primary_button_style = f"""
            QPushButton {{
                background-color: {c.primary};
                color: {c.text_on_primary};
                padding: 8px 14px;
                border: 1px solid {c.primary};
                border-radius: {ds.radius.sm}px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {c.primary_hover};
                border-color: {c.primary_hover};
            }}
        """

        self.linktree_profile_input = QLineEdit()
        self.linktree_profile_input.setPlaceholderText("Linktree 공개 주소 예) https://linktr.ee/myshop")
        self.linktree_profile_input.setToolTip("YouTube 설명과 검수 화면에서 사용할 Linktree 공개 프로필 주소입니다.")
        self.linktree_profile_input.setStyleSheet(automation_input_style)
        self.linktree_profile_input.textChanged.connect(self._update_link_automation_status)
        self.link_automation_section.add_row("공개 주소", self.linktree_profile_input)

        quick_btn_container = QWidget()
        quick_btn_container.setStyleSheet("background: transparent; border: none;")
        quick_btn_layout = QHBoxLayout(quick_btn_container)
        quick_btn_layout.setContentsMargins(0, 0, 0, 0)
        quick_btn_layout.setSpacing(8)

        self.linktree_guide_btn = QPushButton("🪄 간편 설정 가이드")
        self.linktree_guide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.linktree_guide_btn.setStyleSheet(automation_primary_button_style)
        self.linktree_guide_btn.setToolTip("웹훅 연결을 단계별로 안내하고 테스트까지 한 번에 진행합니다.")
        self.linktree_guide_btn.clicked.connect(self._open_linktree_setup_guide)
        quick_btn_layout.addWidget(self.linktree_guide_btn)

        self.linktree_save_btn = QPushButton("저장")
        self.linktree_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.linktree_save_btn.setStyleSheet(automation_button_style)
        self.linktree_save_btn.clicked.connect(self._save_linktree_settings)
        quick_btn_layout.addWidget(self.linktree_save_btn)
        quick_btn_layout.addStretch()
        self.link_automation_section.add_row("Linktree", quick_btn_container)

        setup_notice_links = QLabel(
            f'<a href="{SETUP_NOTICE_BASE_URL}/linktree-signup-link-setup" style="color: #3B82F6; text-decoration: none;">Linktree 세팅 가이드</a>'
        )
        setup_notice_links.setWordWrap(True)
        setup_notice_links.setOpenExternalLinks(True)
        setup_notice_links.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        setup_notice_links.setStyleSheet(
            f"color: {c.text_secondary}; border: none; background: transparent; font-size: 12px;"
        )
        self.link_automation_section.content_layout.addWidget(setup_notice_links)

        self.link_advanced_toggle = QCheckBox("고급 자동화 설정 보기")
        self.link_advanced_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.link_advanced_toggle.setStyleSheet(
            f"color: {c.text_primary}; spacing: 8px; border: none; background: transparent;"
        )
        self.link_advanced_toggle.toggled.connect(self._set_link_advanced_visible)
        self.link_automation_section.content_layout.addWidget(self.link_advanced_toggle)

        # ── 고급 자동화: 항목별 접이식 카드 (한 번에 하나만 펼침, 기본 접힘) ──
        self.link_advanced_container = QFrame()
        self.link_advanced_container.setStyleSheet("QFrame { background: transparent; border: none; }")
        link_advanced_layout = QVBoxLayout(self.link_advanced_container)
        link_advanced_layout.setContentsMargins(0, 4, 0, 0)
        link_advanced_layout.setSpacing(8)

        card_style = f"""
            QFrame#CuCard {{
                background-color: {c.surface_variant};
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.base}px;
            }}
        """
        card_header_style = f"""
            QPushButton {{
                background: transparent;
                color: {c.text_primary};
                text-align: left;
                padding: 11px 14px;
                border: none;
                font-weight: 700;
                font-size: 13px;
            }}
            QPushButton:hover {{ color: {c.primary}; }}
        """
        cu_button_style = f"""
            QPushButton {{
                background-color: {c.primary};
                color: {c.text_on_primary};
                padding: 8px 14px;
                border: 1px solid {c.primary};
                border-radius: {ds.radius.sm}px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {c.primary_hover};
                border-color: {c.primary_hover};
            }}
        """
        cu_tooltip = (
            "컴퓨터를 자동 조작해 이 항목 설정을 대신 진행합니다(선택 기능).\n"
            "필요 조건: 유료 플랜, Codex CLI 설치 및 'codex login', computer-use MCP 활성화.\n"
            "조건 미충족 시 실행되지 않고 안내만 표시됩니다."
        )

        self._link_cards = []

        def make_card(title: str, subtitle: str = ""):
            """Create a collapsible card; returns its body layout. Accordion: opening
            one collapses the others."""
            card = QFrame()
            card.setObjectName("CuCard")
            card.setStyleSheet(card_style)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(0)

            header = QPushButton("▸  " + title)
            header.setCheckable(True)
            header.setCursor(Qt.CursorShape.PointingHandCursor)
            header.setStyleSheet(card_header_style)
            cl.addWidget(header)

            body = QFrame()
            body.setStyleSheet("background: transparent; border: none;")
            body.setVisible(False)
            bl = QVBoxLayout(body)
            bl.setContentsMargins(14, 2, 14, 14)
            bl.setSpacing(10)
            if subtitle:
                sub = QLabel(subtitle)
                sub.setWordWrap(True)
                sub.setStyleSheet(
                    f"color: {c.text_muted}; border: none; background: transparent; font-size: 11px; padding-bottom: 3px;"
                )
                bl.addWidget(sub)
            cl.addWidget(body)

            def _on_toggled(checked, _h=header, _b=body, _t=title):
                _b.setVisible(checked)
                _h.setText(("▾  " if checked else "▸  ") + _t)
                if checked:
                    for other_h, _other_b in self._link_cards:
                        if other_h is not _h and other_h.isChecked():
                            other_h.setChecked(False)

            header.toggled.connect(_on_toggled)
            self._link_cards.append((header, body))
            link_advanced_layout.addWidget(card)
            return bl

        def add_row(layout, label_text: str, widget: QWidget):
            row = QHBoxLayout()
            row.setSpacing(ds.spacing.space_4)
            label = QLabel(label_text)
            label.setFont(QFont(ds.typography.font_family_primary, 12))
            label.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent; padding-bottom: 3px;")
            label.setMinimumWidth(110)
            row.addWidget(label)
            widget.setStyleSheet(widget.styleSheet() + " border: none;")
            row.addWidget(widget, stretch=1)
            layout.addLayout(row)

        def button_row(*buttons):
            cont = QWidget()
            cont.setStyleSheet("background: transparent; border: none;")
            lay = QHBoxLayout(cont)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(8)
            for b in buttons:
                lay.addWidget(b)
            lay.addStretch()
            return cont

        def make_cu_button(target: str, label: str):
            btn = QPushButton("🤖 자동으로 설정")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(cu_button_style)
            btn.setToolTip(cu_tooltip)
            btn.clicked.connect(
                lambda _checked=False, t=target, lb=label: self._run_computer_use_prompt(
                    self._build_computer_use_prompt_for_target(t), lb
                )
            )
            return btn

        # ── Card 1: Linktree 계정 연결 ──
        lt_body = make_card(
            "Linktree 계정 연결",
            "공개 프로필 주소와 로그인 계정을 기록합니다. 로그인은 직접 진행하세요.",
        )

        self.linktree_profile_open_btn = QPushButton("공개 페이지 열기")
        self.linktree_profile_open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.linktree_profile_open_btn.setStyleSheet(automation_button_style)
        self.linktree_profile_open_btn.clicked.connect(self._open_linktree_profile)

        self.linktree_admin_btn = QPushButton("관리자 열기")
        self.linktree_admin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.linktree_admin_btn.setStyleSheet(automation_button_style)
        self.linktree_admin_btn.clicked.connect(self._open_linktree_admin)

        self.linktree_signup_btn = QPushButton("가입/로그인")
        self.linktree_signup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.linktree_signup_btn.setStyleSheet(automation_button_style)
        self.linktree_signup_btn.clicked.connect(self._open_linktree_signup)
        add_row(lt_body, "바로가기", button_row(
            self.linktree_profile_open_btn, self.linktree_admin_btn, self.linktree_signup_btn
        ))

        self.linktree_account_email_input = QLineEdit()
        self.linktree_account_email_input.setPlaceholderText("Linktree 로그인 이메일")
        self.linktree_account_email_input.setToolTip("현재 Linktree에 연결한 계정 이메일을 기록합니다.")
        self.linktree_account_email_input.setStyleSheet(automation_input_style)
        self.linktree_account_email_input.textChanged.connect(self._update_link_automation_status)
        add_row(lt_body, "Linktree 계정", self.linktree_account_email_input)

        self.linktree_expected_email_input = QLineEdit()
        self.linktree_expected_email_input.setPlaceholderText("기대 계정 이메일")
        self.linktree_expected_email_input.setToolTip("이 이메일과 Linktree 계정 이메일이 일치할 때만 자동 발행을 허용합니다.")
        self.linktree_expected_email_input.setStyleSheet(automation_input_style)
        self.linktree_expected_email_input.textChanged.connect(self._update_link_automation_status)
        add_row(lt_body, "기대 계정", self.linktree_expected_email_input)

        self.linktree_cu_btn = make_cu_button("linktree", "Linktree 자동 설정")
        add_row(lt_body, "Computer Use", button_row(self.linktree_cu_btn))

        # ── Card 2: 쿠팡 파트너스 딥링크 ──
        cp_body = make_card(
            "쿠팡 파트너스 딥링크 (선택)",
            "원본 coupang.com 링크를 파트너스 딥링크로 자동 변환할 때만 필요합니다.",
        )

        self.coupang_access_input = QLineEdit()
        self.coupang_access_input.setPlaceholderText("선택: 원본 쿠팡 URL 자동 딥링크용 Access Key")
        self.coupang_access_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.coupang_access_input.setStyleSheet(automation_input_style)
        self.coupang_access_input.textChanged.connect(self._update_link_automation_status)
        add_row(cp_body, "Coupang Access", self.coupang_access_input)

        self.coupang_secret_input = QLineEdit()
        self.coupang_secret_input.setPlaceholderText("선택: 원본 쿠팡 URL 자동 딥링크용 Secret Key")
        self.coupang_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.coupang_secret_input.setStyleSheet(automation_input_style)
        self.coupang_secret_input.textChanged.connect(self._update_link_automation_status)
        add_row(cp_body, "Coupang Secret", self.coupang_secret_input)

        self.coupang_save_btn = QPushButton("쿠팡 키 저장")
        self.coupang_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.coupang_save_btn.setStyleSheet(automation_button_style)
        self.coupang_save_btn.clicked.connect(self._save_coupang_settings)

        self.coupang_test_btn = QPushButton("쿠팡 연결 테스트")
        self.coupang_test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.coupang_test_btn.setStyleSheet(automation_button_style)
        self.coupang_test_btn.clicked.connect(self._test_coupang_connection)

        self.coupang_cu_btn = make_cu_button("coupang", "쿠팡 키 자동 발급")
        add_row(cp_body, "작업", button_row(
            self.coupang_save_btn, self.coupang_test_btn, self.coupang_cu_btn
        ))
        self._coupang_card_header = self._link_cards[-1][0]

        # ── Card 3: Webhook 자동 발행 ──
        wh_body = make_card(
            "Webhook 자동 발행 (선택)",
            "Make/Zapier/n8n Webhook으로 Linktree 카드를 자동 추가합니다.",
        )

        self.linktree_webhook_input = QLineEdit()
        self.linktree_webhook_input.setPlaceholderText("선택: 자동 발행용 Webhook URL (https://...)")
        self.linktree_webhook_input.setToolTip("Linktree 카드를 프로그램이 자동으로 추가하려면 Webhook URL이 필요합니다.")
        self.linktree_webhook_input.setStyleSheet(automation_input_style)
        self.linktree_webhook_input.textChanged.connect(self._update_link_automation_status)
        add_row(wh_body, "Webhook URL", self.linktree_webhook_input)

        self.linktree_api_key_input = QLineEdit()
        self.linktree_api_key_input.setPlaceholderText("선택: Webhook 인증 키")
        self.linktree_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.linktree_api_key_input.setStyleSheet(automation_input_style)
        add_row(wh_body, "Webhook 인증 키", self.linktree_api_key_input)

        checkbox_container = QWidget()
        checkbox_container.setStyleSheet("background: transparent; border: none;")
        checkbox_layout = QHBoxLayout(checkbox_container)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        self.linktree_auto_checkbox = QCheckBox("쿠팡 링크 생성 시 Linktree 자동 업로드")
        self.linktree_auto_checkbox.setToolTip("Webhook URL이 있어야 실제 자동 업로드가 됩니다.")
        self.linktree_auto_checkbox.setStyleSheet(
            f"color: {c.text_primary}; spacing: 8px; border: none; background: transparent;"
        )
        self.linktree_auto_checkbox.stateChanged.connect(self._update_link_automation_status)
        checkbox_layout.addWidget(self.linktree_auto_checkbox)
        checkbox_layout.addStretch()
        add_row(wh_body, "자동 업로드", checkbox_container)

        self.linktree_test_btn = QPushButton("테스트 업로드")
        self.linktree_test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.linktree_test_btn.setStyleSheet(automation_button_style)
        self.linktree_test_btn.clicked.connect(self._test_linktree_publish)

        self.webhook_cu_btn = make_cu_button("webhook", "Webhook 시나리오 자동 설정")
        add_row(wh_body, "작업", button_row(self.linktree_test_btn, self.webhook_cu_btn))

        linktree_docs_link = QLabel(
            '<a href="https://docs.linktr.ee/" style="color: #3B82F6; text-decoration: none;">Linktree 개발 문서 보기</a>'
        )
        linktree_docs_link.setOpenExternalLinks(True)
        linktree_docs_link.setStyleSheet("border: none; background: transparent; font-size: 12px;")
        wh_body.addWidget(linktree_docs_link)

        self.link_automation_section.content_layout.addWidget(self.link_advanced_container)
        self._set_link_advanced_visible(False)

        self.link_automation_status = QLabel("상태: 미설정")
        self.link_automation_status.setStyleSheet(
            f"color: {c.text_muted}; border: none; background: transparent; font-size: 11px; padding-bottom: 3px;"
        )
        self.link_automation_section.content_layout.addWidget(self.link_automation_status)

        connect_layout.addWidget(self.link_automation_section)
        self._load_link_automation_settings()
        
        # =================== SECTION: App Info ===================
        info_section = SettingsSection("앱 정보")

        version_info = self._load_version_info()
        version_label = QLabel(f"버전: {version_info.get('version', '알 수 없음')}")
        version_label.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent; padding-bottom: 3px;")
        info_section.content_layout.addWidget(version_label)

        updated_at = version_info.get('updated_at', version_info.get('build_date', '알 수 없음'))
        update_label = QLabel(f"업데이트: {updated_at}")
        update_label.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent; padding-bottom: 3px;")
        info_section.content_layout.addWidget(update_label)

        dev_label = QLabel("개발: 쇼핑 숏폼 팀")
        dev_label.setStyleSheet(f"color: {c.text_muted}; border: none; background: transparent;")
        info_section.content_layout.addWidget(dev_label)

        gen_layout.addWidget(info_section)

        # =================== SECTION: Tutorial ===================
        tutorial_section = SettingsSection("튜토리얼")

        tutorial_desc = QLabel("앱 사용법을 다시 확인하고 싶으시면 튜토리얼을 재실행하세요.")
        tutorial_desc.setWordWrap(True)
        tutorial_desc.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent; padding-bottom: 3px;")
        tutorial_section.content_layout.addWidget(tutorial_desc)

        self.replay_tutorial_btn = QPushButton("튜토리얼 재실행")
        self.replay_tutorial_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.replay_tutorial_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #3B82F6;
                color: white;
                padding: 12px 24px;
                border-radius: {ds.radius.sm}px;
                font-weight: bold;
                font-size: {ds.typography.size_sm}px;
            }}
            QPushButton:hover {{
                background-color: #2563EB;
            }}
        """)
        self.replay_tutorial_btn.clicked.connect(self._replay_tutorial)
        tutorial_section.content_layout.addWidget(self.replay_tutorial_btn)

        gen_layout.addWidget(tutorial_section)

        # =================== SECTION: Subscription ===================
        sub_section = SettingsSection("구독 관리")

        sub_desc = QLabel("구독 상태 확인 및 플랜을 변경할 수 있습니다.")
        sub_desc.setWordWrap(True)
        sub_desc.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent; padding-bottom: 3px;")
        sub_section.content_layout.addWidget(sub_desc)

        self.subscription_btn = QPushButton("구독 관리 페이지로 이동")
        self.subscription_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.subscription_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.primary};
                color: white;
                padding: 12px 24px;
                border-radius: {ds.radius.sm}px;
                font-weight: bold;
                font-size: {ds.typography.size_sm}px;
            }}
            QPushButton:hover {{
                background-color: {c.primary_hover};
            }}
        """)
        self.subscription_btn.clicked.connect(self._go_to_subscription)
        sub_section.content_layout.addWidget(self.subscription_btn)

        etc_layout.addWidget(sub_section)

        # =================== SECTION: Contact ===================
        contact_section = SettingsSection("문의하기")

        contact_desc = QLabel("이용 중 불편사항이나 문의가 있으시면 카카오 오픈채팅으로 연락주세요.")
        contact_desc.setWordWrap(True)
        contact_desc.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent; padding-bottom: 3px;")
        contact_section.content_layout.addWidget(contact_desc)

        self.contact_btn = QPushButton("문의하기")
        self.contact_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.contact_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #FACC15;
                color: #111827;
                padding: 12px 24px;
                border-radius: {ds.radius.sm}px;
                font-weight: bold;
                font-size: {ds.typography.size_sm}px;
            }}
            QPushButton:hover {{
                background-color: #EAB308;
            }}
        """)
        self.contact_btn.clicked.connect(self._open_contact_link)
        contact_section.content_layout.addWidget(self.contact_btn)

        etc_layout.addWidget(contact_section)

        # ── '영상 올리기' 탭: 안내 + 업로드 패널이 들어갈 자리(나중에 attach) ──
        upload_tab_intro = QLabel("YouTube 등 채널 연결과 자동 올리기 설정을 여기서 관리해요.")
        upload_tab_intro.setWordWrap(True)
        upload_tab_intro.setStyleSheet(
            f"color: {c.text_secondary}; border: none; background: transparent; font-size: 12px; padding-bottom: 3px;"
        )
        upload_layout.addWidget(upload_tab_intro)
        self._upload_tab_placeholder = QLabel("업로드 설정을 불러오는 중…")
        self._upload_tab_placeholder.setStyleSheet(
            f"color: {c.text_muted}; border: none; background: transparent;"
        )
        upload_layout.addWidget(self._upload_tab_placeholder)

        # 각 탭 하단 여백
        for _lay in (gen_layout, api_layout, connect_layout, etc_layout):
            _lay.addStretch()
        upload_layout.addStretch()

    def attach_upload_panel(self, panel: QWidget):
        """좌측 메뉴에 있던 '올리기 설정'(UploadPanel)을 '영상 올리기' 탭 안으로 넣는다.
        ui_initializer에서 settings_tab/upload_panel 생성 후 호출."""
        if panel is None:
            return
        try:
            if hasattr(self, "_upload_tab_placeholder") and self._upload_tab_placeholder is not None:
                self._upload_tab_placeholder.setParent(None)
                self._upload_tab_placeholder = None
            # addStretch가 마지막에 있으므로, 그 앞(인덱스 기준 끝-1)에 삽입
            insert_at = max(0, self._upload_tab_layout.count() - 1)
            self._upload_tab_layout.insertWidget(insert_at, panel, 1)
        except Exception as exc:
            logger.warning("[SettingsTab] attach_upload_panel failed: %s", exc)

    def select_upload_tab(self):
        """'영상 올리기' 탭으로 전환."""
        try:
            self.tab_widget.setCurrentIndex(self._tab_index.get("upload", 0))
        except Exception:
            pass
    
    def _select_folder(self):
        """Open folder selection dialog"""
        folder = QFileDialog.getExistingDirectory(
            self, "출력 폴더 선택",
            self.folder_input.text() or ""
        )
        if folder:
            self.folder_input.setText(folder)
            if self.gui:
                self.gui.output_folder_path = folder
            from managers.settings_manager import get_settings_manager
            get_settings_manager().set_output_folder(folder)

    def _open_folder(self):
        """Open the output folder in file explorer"""
        folder_path = self.folder_input.text().strip()
        if folder_path and os.path.isdir(folder_path):
            os.startfile(folder_path)
        else:
            from ui.components.custom_dialog import show_warning
            show_warning(self, "알림", "저장 폴더가 설정되지 않았거나 존재하지 않습니다.")

    def _build_setup_assistant_section(self, content_layout: QVBoxLayout):
        """Build guided setup assistant section inside Settings."""
        ds = self.ds
        c = ds.colors

        self.setup_assistant_section = SettingsSection("설정 도우미 (단계별 안내)")

        intro = QLabel(
            "처음이신가요? 아래 'YouTube 설정' 버튼만 눌러서 채널을 연결하면, 영상이 자동으로 올라갑니다. "
            "방법을 잘 모르겠다면 먼저 '📖 사용 설명서 보기'를 눌러보세요."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(
            f"color: {c.text_secondary}; border: none; background: transparent; font-size: 12px; padding-bottom: 3px;"
        )
        self.setup_assistant_section.content_layout.addWidget(intro)

        # 도움말 버튼: 사용 설명서(웹 공지/매뉴얼) + 'Linktree가 뭔가요?'
        help_row = QHBoxLayout()
        help_row.setSpacing(8)
        self.setup_manual_btn = QPushButton("📖 사용 설명서 보기")
        self.setup_manual_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_manual_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.primary};
                color: {c.text_on_primary};
                border: 1px solid {c.primary};
                border-radius: {ds.radius.sm}px;
                padding: 8px 14px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background-color: {c.primary_hover}; border-color: {c.primary_hover}; }}
        """)
        self.setup_manual_btn.clicked.connect(lambda: self._open_external_url(SETUP_NOTICE_BASE_URL))
        help_row.addWidget(self.setup_manual_btn)

        self.setup_linktree_help_btn = QPushButton("Linktree가 뭔가요?")
        self.setup_linktree_help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_linktree_help_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.surface_variant};
                color: {c.text_primary};
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.sm}px;
                padding: 8px 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {c.surface}; }}
        """)
        self.setup_linktree_help_btn.clicked.connect(
            lambda: self._open_external_url(f"{SETUP_NOTICE_BASE_URL}/linktree-signup-link-setup")
        )
        help_row.addWidget(self.setup_linktree_help_btn)
        help_row.addStretch()
        self.setup_assistant_section.content_layout.addLayout(help_row)

        # 1) Connection chips
        chip_wrap = QWidget()
        chip_wrap.setStyleSheet("background: transparent; border: none;")
        chip_row = QHBoxLayout(chip_wrap)
        chip_row.setContentsMargins(0, 0, 0, 0)
        chip_row.setSpacing(8)

        # 칩 객체는 모두 생성(다른 코드에서 set_chip 참조)하되, 화면에는 동작하는
        # 채널(Gemini/YouTube/Linktree)만 표시한다. 틱톡은 비활성화로 숨김.
        self.setup_chip_gemini = QLabel()
        self.setup_chip_youtube = QLabel()
        self.setup_chip_tiktok = QLabel()
        self.setup_chip_instagram = QLabel()
        self.setup_chip_threads = QLabel()
        self.setup_chip_linktree = QLabel()
        for chip in (
            self.setup_chip_gemini,
            self.setup_chip_youtube,
            self.setup_chip_linktree,
        ):
            chip.setStyleSheet(
                f"padding: 5px 10px; border-radius: {ds.radius.full}px; "
                f"border: 1px solid {c.border_light}; background: {c.surface_variant}; color: {c.text_primary};"
            )
            chip_row.addWidget(chip)
        chip_row.addStretch()
        self.setup_assistant_section.add_row("연결 상태", chip_wrap)

        # 2) Start buttons
        start_wrap = QWidget()
        start_wrap.setStyleSheet("background: transparent; border: none;")
        start_row = QHBoxLayout(start_wrap)
        start_row.setContentsMargins(0, 0, 0, 0)
        start_row.setSpacing(8)

        self.setup_start_all_btn = QPushButton("원클릭 설정 시작")
        self.setup_start_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_start_all_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.primary};
                color: {c.text_on_primary};
                border: 1px solid {c.primary};
                border-radius: {ds.radius.sm}px;
                padding: 8px 14px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {c.primary_hover};
                border-color: {c.primary_hover};
            }}
        """)
        # '원클릭 설정 시작'/'소셜4종'/'TikTok만'/'Instagram만'/'Threads만'은
        # 실효성이 없어(외부 Codex 필요 + 틱톡/IG/스레드는 지원예정) 화면에서 제거.
        # 실제로 작동하는 YouTube·Linktree 설정만 남긴다.
        # setup_start_all_btn 객체는 다른 버튼들의 스타일 소스로만 유지(레이아웃 미추가).
        self.setup_start_all_btn.clicked.connect(lambda: self._start_setup_assistant("all"))

        self.setup_start_youtube_btn = QPushButton("YouTube 설정")
        self.setup_start_youtube_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_start_youtube_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.surface_variant};
                color: {c.text_primary};
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.sm}px;
                padding: 8px 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {c.surface}; }}
        """)
        self.setup_start_youtube_btn.clicked.connect(lambda: self._start_setup_assistant("youtube"))
        start_row.addWidget(self.setup_start_youtube_btn)

        self.setup_start_linktree_btn = QPushButton("Linktree 설정")
        self.setup_start_linktree_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_start_linktree_btn.setStyleSheet(self.setup_start_youtube_btn.styleSheet())
        self.setup_start_linktree_btn.clicked.connect(lambda: self._start_setup_assistant("linktree"))
        start_row.addWidget(self.setup_start_linktree_btn)
        start_row.addStretch()
        self.setup_assistant_section.add_row("도우미 실행", start_wrap)

        # 2-1) OAuth/code/manual identity input helpers
        setup_input_wrap = QFrame()
        setup_input_wrap.setStyleSheet(f"""
            QFrame {{
                background-color: {c.surface_variant};
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.base}px;
            }}
            QLineEdit {{
                background-color: {c.surface};
                color: {c.text_primary};
                padding: 8px 10px;
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.sm}px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {c.primary};
            }}
        """)
        setup_input_layout = QVBoxLayout(setup_input_wrap)
        setup_input_layout.setContentsMargins(12, 10, 12, 10)
        setup_input_layout.setSpacing(8)

        tiktok_input_row = QHBoxLayout()
        tiktok_input_row.setSpacing(8)
        self.setup_tiktok_code_input = QLineEdit()
        self.setup_tiktok_code_input.setPlaceholderText("TikTok OAuth 완료 후 리디렉션 URL의 code 값")
        self.setup_tiktok_code_input.setToolTip("예: http://localhost:8080/callback?code=... 에서 code 값만 붙여넣기")
        tiktok_input_row.addWidget(self.setup_tiktok_code_input, stretch=1)
        self.setup_open_tiktok_auth_btn = QPushButton("TikTok 인증 페이지 열기")
        self.setup_open_tiktok_auth_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_open_tiktok_auth_btn.setStyleSheet(self.setup_start_youtube_btn.styleSheet())
        self.setup_open_tiktok_auth_btn.clicked.connect(self._assistant_open_tiktok_auth)
        tiktok_input_row.addWidget(self.setup_open_tiktok_auth_btn)
        # 틱톡 비활성화: 위젯 객체는 다른 코드 참조 안전을 위해 생성만 하고 화면에는 추가하지 않는다.
        # setup_input_layout.addLayout(tiktok_input_row)

        insta_input_row = QHBoxLayout()
        insta_input_row.setSpacing(8)
        self.setup_instagram_handle_input = QLineEdit()
        self.setup_instagram_handle_input.setPlaceholderText("Instagram 계정 (@없이 username 또는 프로필 URL)")
        insta_input_row.addWidget(self.setup_instagram_handle_input, stretch=1)
        self.setup_open_instagram_btn = QPushButton("Instagram 열기")
        self.setup_open_instagram_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_open_instagram_btn.setStyleSheet(self.setup_start_youtube_btn.styleSheet())
        self.setup_open_instagram_btn.clicked.connect(self._assistant_open_instagram_setup)
        insta_input_row.addWidget(self.setup_open_instagram_btn)
        setup_input_layout.addLayout(insta_input_row)

        threads_input_row = QHBoxLayout()
        threads_input_row.setSpacing(8)
        self.setup_threads_handle_input = QLineEdit()
        self.setup_threads_handle_input.setPlaceholderText("Threads 계정 (@없이 username 또는 프로필 URL)")
        threads_input_row.addWidget(self.setup_threads_handle_input, stretch=1)
        self.setup_open_threads_btn = QPushButton("Threads 열기")
        self.setup_open_threads_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_open_threads_btn.setStyleSheet(self.setup_start_youtube_btn.styleSheet())
        self.setup_open_threads_btn.clicked.connect(self._assistant_open_threads_setup)
        threads_input_row.addWidget(self.setup_open_threads_btn)
        setup_input_layout.addLayout(threads_input_row)

        helper_row = QHBoxLayout()
        helper_row.setSpacing(8)
        self.setup_open_meta_console_btn = QPushButton("Meta App 콘솔 열기")
        self.setup_open_meta_console_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_open_meta_console_btn.setStyleSheet(self.setup_start_youtube_btn.styleSheet())
        self.setup_open_meta_console_btn.clicked.connect(lambda: self._open_external_url(META_APPS_URL))
        helper_row.addWidget(self.setup_open_meta_console_btn)

        self.setup_open_computer_use_guide_btn = QPushButton("Computer Use 가이드 열기")
        self.setup_open_computer_use_guide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_open_computer_use_guide_btn.setStyleSheet(self.setup_start_youtube_btn.styleSheet())
        self.setup_open_computer_use_guide_btn.clicked.connect(self._assistant_open_computer_use_guide)
        helper_row.addWidget(self.setup_open_computer_use_guide_btn)
        helper_row.addStretch()
        setup_input_layout.addLayout(helper_row)

        codex_config_row = QHBoxLayout()
        codex_config_row.setSpacing(8)
        self.setup_codex_path_input = QLineEdit()
        self.setup_codex_path_input.setPlaceholderText("Codex CLI 경로 (기본: codex)")
        self.setup_codex_path_input.setToolTip("예: codex 또는 /usr/local/bin/codex")
        codex_config_row.addWidget(self.setup_codex_path_input, stretch=1)
        self.setup_codex_model_input = QLineEdit()
        self.setup_codex_model_input.setPlaceholderText("모델 (선택, 비우면 기본)")
        self.setup_codex_model_input.setToolTip("예: gpt-5.4, gpt-5.5")
        codex_config_row.addWidget(self.setup_codex_model_input, stretch=1)
        self.setup_codex_save_btn = QPushButton("Codex 설정 저장")
        self.setup_codex_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_codex_save_btn.setStyleSheet(self.setup_start_youtube_btn.styleSheet())
        self.setup_codex_save_btn.clicked.connect(self._save_codex_cli_settings)
        codex_config_row.addWidget(self.setup_codex_save_btn)
        setup_input_layout.addLayout(codex_config_row)

        computer_use_policy_row = QHBoxLayout()
        computer_use_policy_row.setSpacing(8)
        self.setup_computer_use_paid_only_checkbox = QCheckBox("Computer Use 유료 전용")
        self.setup_computer_use_paid_only_checkbox.setChecked(True)
        self.setup_computer_use_paid_only_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_computer_use_paid_only_checkbox.setStyleSheet(
            f"color: {c.text_primary}; spacing: 8px; border: none; background: transparent;"
        )
        computer_use_policy_row.addWidget(self.setup_computer_use_paid_only_checkbox)

        self.setup_computer_use_bridge_checkbox = QCheckBox("공용 서버 브리지 사용")
        self.setup_computer_use_bridge_checkbox.setChecked(False)
        self.setup_computer_use_bridge_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_computer_use_bridge_checkbox.setStyleSheet(
            f"color: {c.text_primary}; spacing: 8px; border: none; background: transparent;"
        )
        computer_use_policy_row.addWidget(self.setup_computer_use_bridge_checkbox)
        computer_use_policy_row.addStretch()
        setup_input_layout.addLayout(computer_use_policy_row)

        bridge_row = QHBoxLayout()
        bridge_row.setSpacing(8)
        self.setup_computer_use_bridge_url_input = QLineEdit()
        self.setup_computer_use_bridge_url_input.setPlaceholderText("공용 브리지 URL (예: https://api.yourserver.com)")
        self.setup_computer_use_bridge_url_input.setToolTip("유료 사용자 Computer Use 요청을 서버로 위임할 때 사용합니다.")
        bridge_row.addWidget(self.setup_computer_use_bridge_url_input, stretch=1)
        self.setup_computer_use_bridge_key_input = QLineEdit()
        self.setup_computer_use_bridge_key_input.setPlaceholderText("브리지 API 키 (선택)")
        self.setup_computer_use_bridge_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        bridge_row.addWidget(self.setup_computer_use_bridge_key_input, stretch=1)
        setup_input_layout.addLayout(bridge_row)

        codex_row = QHBoxLayout()
        codex_row.setSpacing(8)
        self.setup_codex_check_btn = QPushButton("Codex 상태 점검")
        self.setup_codex_check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_codex_check_btn.setStyleSheet(self.setup_start_youtube_btn.styleSheet())
        self.setup_codex_check_btn.clicked.connect(lambda: self._refresh_codex_cli_status(show_dialog=True))
        codex_row.addWidget(self.setup_codex_check_btn)

        self.setup_codex_launch_btn = QPushButton("현재 단계 Codex 실행")
        self.setup_codex_launch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_codex_launch_btn.setStyleSheet(self.setup_start_all_btn.styleSheet())
        self.setup_codex_launch_btn.setToolTip(
            "컴퓨터를 자동 조작해 현재 단계를 대신 처리합니다(선택 기능).\n"
            "필요 조건: 유료 플랜, Codex CLI 설치 및 'codex login', computer-use MCP 활성화.\n"
            "조건이 충족되지 않으면 실행되지 않고 안내만 표시됩니다."
        )
        self.setup_codex_launch_btn.clicked.connect(self._launch_codex_for_current_step)
        codex_row.addWidget(self.setup_codex_launch_btn)

        self.setup_codex_status = QLabel(self._codex_status_summary)
        self.setup_codex_status.setStyleSheet(
            f"color: {c.text_muted}; border: none; background: transparent; font-size: 11px; padding-bottom: 3px;"
        )
        codex_row.addWidget(self.setup_codex_status, stretch=1)
        setup_input_layout.addLayout(codex_row)

        clipboard_row = QHBoxLayout()
        clipboard_row.setSpacing(8)

        self.setup_clipboard_auto_checkbox = QCheckBox("클립보드 자동감지")
        self.setup_clipboard_auto_checkbox.setChecked(True)
        self.setup_clipboard_auto_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_clipboard_auto_checkbox.setStyleSheet(
            f"color: {c.text_primary}; spacing: 8px; border: none; background: transparent;"
        )
        self.setup_clipboard_auto_checkbox.stateChanged.connect(self._on_setup_clipboard_auto_toggled)
        clipboard_row.addWidget(self.setup_clipboard_auto_checkbox)

        self.setup_clipboard_apply_btn = QPushButton("클립보드 즉시 반영")
        self.setup_clipboard_apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_clipboard_apply_btn.setStyleSheet(self.setup_start_youtube_btn.styleSheet())
        self.setup_clipboard_apply_btn.clicked.connect(self._on_setup_clipboard_apply_clicked)
        clipboard_row.addWidget(self.setup_clipboard_apply_btn)

        self.setup_clipboard_status = QLabel("대기 중")
        self.setup_clipboard_status.setStyleSheet(
            f"color: {c.text_muted}; border: none; background: transparent; font-size: 11px; padding-bottom: 3px;"
        )
        clipboard_row.addWidget(self.setup_clipboard_status, stretch=1)
        setup_input_layout.addLayout(clipboard_row)

        # '소셜 인증 입력'은 컴퓨터 자동조작(Codex)·브리지 등 고급/개발자용 항목이라
        # 초보자가 겁먹지 않도록 기본 숨김 처리하고, 토글로만 펼치게 한다.
        self.setup_advanced_toggle = QCheckBox("고급 설정 보기 (개발자용 · 평소엔 안 건드려도 됩니다)")
        self.setup_advanced_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_advanced_toggle.setStyleSheet(
            f"color: {c.text_muted}; spacing: 8px; border: none; background: transparent; font-size: 11px;"
        )
        self.setup_advanced_toggle.toggled.connect(setup_input_wrap.setVisible)
        self.setup_assistant_section.content_layout.addWidget(self.setup_advanced_toggle)

        setup_input_wrap.setVisible(False)
        self.setup_assistant_section.content_layout.addWidget(setup_input_wrap)
        self._load_codex_cli_settings()

        # 3) Timeline 제거됨 — '진행 타임라인'이 소싱 화면의 '콘텐츠 생성 진행 목록'과
        #    혼동을 일으켜 삭제. 단계 상태는 로그(_append_setup_log)와 현재 단계 패널로 확인한다.
        #    _set_setup_row_state/_reset_setup_timeline은 빈 dict에서 안전하게 no-op 처리된다.
        self._setup_rows = {}

        # 4) Current action panel
        action_wrap = QFrame()
        action_wrap.setStyleSheet(f"""
            QFrame {{
                background-color: {c.surface_variant};
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.base}px;
            }}
        """)
        action_layout = QVBoxLayout(action_wrap)
        action_layout.setContentsMargins(12, 10, 12, 10)
        action_layout.setSpacing(8)

        self.setup_current_title = QLabel("대기 중")
        self.setup_current_title.setStyleSheet(
            f"color: {c.text_primary}; border: none; background: transparent; font-weight: 700;"
        )
        action_layout.addWidget(self.setup_current_title)

        self.setup_current_desc = QLabel("도우미를 시작하면 단계별로 필요한 작업을 안내합니다.")
        self.setup_current_desc.setWordWrap(True)
        self.setup_current_desc.setStyleSheet(
            f"color: {c.text_secondary}; border: none; background: transparent; padding-bottom: 3px;"
        )
        action_layout.addWidget(self.setup_current_desc)

        action_btn_row = QHBoxLayout()
        action_btn_row.setSpacing(8)

        self.setup_action_btn = QPushButton("작업 열기")
        self.setup_action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_action_btn.setStyleSheet(self.setup_start_youtube_btn.styleSheet())
        self.setup_action_btn.clicked.connect(self._on_setup_action_clicked)
        action_btn_row.addWidget(self.setup_action_btn)

        self.setup_done_btn = QPushButton("완료했어요")
        self.setup_done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_done_btn.setStyleSheet(self.setup_start_all_btn.styleSheet())
        self.setup_done_btn.clicked.connect(self._on_setup_done_clicked)
        action_btn_row.addWidget(self.setup_done_btn)

        self.setup_retry_btn = QPushButton("재검증")
        self.setup_retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_retry_btn.setStyleSheet(self.setup_start_youtube_btn.styleSheet())
        self.setup_retry_btn.clicked.connect(self._on_setup_retry_clicked)
        action_btn_row.addWidget(self.setup_retry_btn)

        self.setup_stop_btn = QPushButton("중단")
        self.setup_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_stop_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {c.error};
                border: 1px solid {c.error};
                border-radius: {ds.radius.sm}px;
                padding: 8px 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {c.error};
                color: white;
            }}
        """)
        self.setup_stop_btn.clicked.connect(self._stop_setup_assistant)
        action_btn_row.addWidget(self.setup_stop_btn)
        action_btn_row.addStretch()
        action_layout.addLayout(action_btn_row)

        self.setup_assistant_section.add_row("현재 해야 할 일", action_wrap)

        # 5) Live logs
        self.setup_log = QTextEdit()
        self.setup_log.setReadOnly(True)
        self.setup_log.setMinimumHeight(120)
        self.setup_log.setMaximumHeight(180)
        self.setup_log.setStyleSheet(f"""
            QTextEdit {{
                background-color: {c.surface_variant};
                color: {c.text_primary};
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.sm}px;
                padding: 8px;
                font-size: 11px;
            }}
        """)
        self.setup_assistant_section.add_row("실시간 로그", self.setup_log)

        content_layout.addWidget(self.setup_assistant_section)
        self._reset_setup_timeline()
        self._refresh_setup_assistant_status()
        self._set_setup_current_action(
            title="대기 중",
            description="도우미를 시작하면 자동/사용자 단계를 순서대로 진행합니다.",
            action_text="",
            action_callback=None,
            show_done=False,
        )

    def _reset_setup_timeline(self):
        """Reset all setup timeline rows to pending state."""
        for step_id in self._setup_rows:
            self._set_setup_row_state(step_id, "pending")

    def _set_setup_row_state(self, step_id: str, state: str, detail: str = ""):
        """Render one setup timeline row state."""
        row = self._setup_rows.get(step_id)
        if not row:
            return

        c = self.ds.colors
        state_label = row["state"]
        title_label = row["title"]

        if state == "running":
            title_label.setStyleSheet(
                f"color: {c.primary}; border: none; background: transparent; font-weight: 700;"
            )
            state_label.setStyleSheet(f"color: {c.primary}; border: none; background: transparent;")
            state_label.setText("진행 중")
            return
        if state == "done":
            title_label.setStyleSheet(
                f"color: {c.success}; border: none; background: transparent; font-weight: 600;"
            )
            state_label.setStyleSheet(f"color: {c.success}; border: none; background: transparent;")
            state_label.setText("완료")
            return
        if state == "waiting":
            title_label.setStyleSheet(
                f"color: {c.warning}; border: none; background: transparent; font-weight: 600;"
            )
            state_label.setStyleSheet(f"color: {c.warning}; border: none; background: transparent;")
            state_label.setText(detail or "사용자 확인")
            return
        if state == "error":
            title_label.setStyleSheet(
                f"color: {c.error}; border: none; background: transparent; font-weight: 600;"
            )
            state_label.setStyleSheet(f"color: {c.error}; border: none; background: transparent;")
            state_label.setText(detail or "오류")
            return
        if state == "skipped":
            title_label.setStyleSheet(
                f"color: {c.text_muted}; border: none; background: transparent;"
            )
            state_label.setStyleSheet(f"color: {c.text_muted}; border: none; background: transparent;")
            state_label.setText("건너뜀")
            return

        # pending/default
        title_label.setStyleSheet(
            f"color: {c.text_primary}; border: none; background: transparent;"
        )
        state_label.setStyleSheet(f"color: {c.text_muted}; border: none; background: transparent;")
        state_label.setText("대기")

    def _append_setup_log(self, message: str):
        """Append one setup log line."""
        if not hasattr(self, "setup_log"):
            return
        ts = datetime.now().strftime("%H:%M:%S")
        self.setup_log.append(f"[{ts}] {message}")
        self.setup_log.verticalScrollBar().setValue(self.setup_log.verticalScrollBar().maximum())

    def _set_setup_current_action(
        self,
        title: str,
        description: str,
        action_text: str,
        action_callback: Optional[Callable[[], None]],
        show_done: bool,
    ):
        """Update current-action card content and buttons."""
        self.setup_current_title.setText(title)
        desc = str(description or "").strip()
        if show_done:
            desc += "\n\n팁: code/프로필 URL/API 키를 복사하면 클립보드 자동감지로 입력됩니다."
        self.setup_current_desc.setText(desc)
        self._setup_action_callback = action_callback

        has_action = bool(action_text and action_callback)
        self.setup_action_btn.setVisible(has_action)
        self.setup_action_btn.setEnabled(has_action)
        if has_action:
            self.setup_action_btn.setText(action_text)

        self.setup_done_btn.setVisible(bool(show_done))
        self.setup_done_btn.setEnabled(bool(show_done))

        running = bool(self._setup_running)
        self.setup_retry_btn.setVisible(running)
        self.setup_stop_btn.setVisible(running)

    def _on_setup_action_clicked(self):
        """Handle dynamic action button click."""
        if self._setup_action_callback:
            try:
                self._setup_action_callback()
            except Exception as exc:
                logger.warning("[SetupAssistant] action callback failed: %s", exc)
                self._append_setup_log(f"작업 실행 오류: {exc}")

    def _on_setup_clipboard_auto_toggled(self, state: int):
        """Enable/disable clipboard auto detection while setup assistant runs."""
        self._setup_clipboard_auto_enabled = bool(state)
        if self._setup_clipboard_auto_enabled:
            self._update_setup_clipboard_status("자동감지 활성화", level="ok")
        else:
            self._update_setup_clipboard_status("자동감지 비활성화", level="warn")

    def _on_setup_clipboard_apply_clicked(self):
        """Apply current clipboard text to setup fields immediately."""
        try:
            text = str(QApplication.clipboard().text() or "").strip()
        except Exception:
            text = ""
        if not text:
            self._update_setup_clipboard_status("클립보드가 비어 있습니다", level="warn")
            return
        consumed = self._apply_clipboard_payload(text, auto_confirm=True)
        if not consumed:
            self._update_setup_clipboard_status("인식 가능한 값이 없습니다", level="warn")

    def _poll_setup_clipboard(self):
        """Background clipboard poller for setup assistant autofill."""
        if not self._setup_clipboard_auto_enabled:
            return
        if not self._setup_running or not self._setup_waiting_user:
            return
        try:
            text = str(QApplication.clipboard().text() or "").strip()
        except Exception:
            return
        if not text or text == self._setup_clipboard_last_text:
            return
        self._setup_clipboard_last_text = text
        self._apply_clipboard_payload(text, auto_confirm=True)

    def _update_setup_clipboard_status(self, message: str, level: str = "info"):
        """Render clipboard helper status text."""
        if not hasattr(self, "setup_clipboard_status"):
            return
        c = self.ds.colors
        if level == "ok":
            color = c.success
        elif level == "warn":
            color = c.warning
        elif level == "error":
            color = c.error
        else:
            color = c.text_muted
        self.setup_clipboard_status.setStyleSheet(
            f"color: {color}; border: none; background: transparent; font-size: 11px;"
        )
        self.setup_clipboard_status.setText(str(message or "").strip())

    @staticmethod
    def _extract_gemini_key_from_text(raw_text: str) -> str:
        """Extract one Gemini API key token from arbitrary text."""
        text = str(raw_text or "")
        match = re.search(r"AIza[A-Za-z0-9_-]{35,96}", text)
        if not match:
            return ""
        key = match.group(0).strip()
        return key if GEMINI_API_KEY_PATTERN.match(key) else ""

    @staticmethod
    def _extract_first_http_url(raw_text: str) -> str:
        """Extract first http(s) URL from arbitrary text."""
        text = str(raw_text or "")
        match = re.search(r"https?://[^\s\"'<>]+", text, flags=re.IGNORECASE)
        if not match:
            return ""
        url = match.group(0).rstrip(".,);]")
        return url.strip()

    @staticmethod
    def _extract_linktree_url_from_text(raw_text: str) -> str:
        """Extract Linktree profile URL from text."""
        text = str(raw_text or "").strip()
        if not text:
            return ""
        explicit = re.search(r"https?://(?:www\.)?linktr\.ee/[^\s\"'<>?#]+", text, flags=re.IGNORECASE)
        if explicit:
            return explicit.group(0).rstrip(".,);]").strip()
        shorthand = re.search(r"(?:www\.)?linktr\.ee/[^\s\"'<>?#]+", text, flags=re.IGNORECASE)
        if shorthand:
            return ("https://" + shorthand.group(0).rstrip(".,);]").strip()).strip()
        return ""

    def _extract_social_handle_from_text(self, raw_text: str, platform: str) -> str:
        """Extract social account handle from URL/text."""
        text = str(raw_text or "").strip()
        if not text:
            return ""
        lower = text.lower()
        if platform == "instagram" and "instagram.com" in lower:
            match = re.search(r"https?://(?:www\.)?instagram\.com/([^/?#\s]+)", text, flags=re.IGNORECASE)
            if match:
                return self._normalize_social_account_input(match.group(1))
        if platform == "threads" and ("threads.net" in lower or "threads.com" in lower):
            match = re.search(r"https?://(?:www\.)?threads\.(?:net|com)/@?([^/?#\s]+)", text, flags=re.IGNORECASE)
            if match:
                return self._normalize_social_account_input(match.group(1))
        if "\n" in text or "\t" in text or " " in text:
            url = self._extract_first_http_url(text)
            if url:
                return self._normalize_social_account_input(url)
            return ""
        return self._normalize_social_account_input(text)

    def _extract_oauth_code_candidate_from_text(self, raw_text: str) -> str:
        """Extract OAuth code from clipboard text with safety checks."""
        text = str(raw_text or "").strip()
        if not text:
            return ""
        code = self._extract_oauth_code(text)
        if not code:
            return ""
        if re.search(r"(?:[?&#]|^)code=", text, flags=re.IGNORECASE):
            return code
        if re.search(r"\s", code):
            return ""
        if re.fullmatch(r"[A-Za-z0-9._~%-]{8,512}", code):
            return code
        return ""

    def _store_gemini_key_silent(self, key_value: str) -> bool:
        """Store one Gemini API key without modal dialogs."""
        key = str(key_value or "").strip()
        if not GEMINI_API_KEY_PATTERN.match(key):
            return False

        max_keys = len(self.api_key_inputs) if hasattr(self, "api_key_inputs") else 8
        existing: List[str] = []
        for i in range(1, max_keys + 1):
            value = str(SecretsManager.get_api_key(f"gemini_api_{i}") or "").strip()
            if value and GEMINI_API_KEY_PATTERN.match(value) and value not in existing:
                existing.append(value)

        for inp in getattr(self, "api_key_inputs", []):
            value = str(inp.text() or "").strip()
            if value and GEMINI_API_KEY_PATTERN.match(value) and value not in existing:
                existing.append(value)

        if key not in existing:
            existing.append(key)
        keys = existing[:max_keys]

        for idx, saved_key in enumerate(keys, start=1):
            if not SecretsManager.store_api_key(f"gemini_api_{idx}", saved_key):
                return False
            loaded = str(SecretsManager.get_api_key(f"gemini_api_{idx}") or "").strip()
            if loaded != saved_key:
                return False
        for idx in range(len(keys) + 1, max_keys + 1):
            SecretsManager.delete_api_key(f"gemini_api_{idx}")

        for inp in getattr(self, "api_key_inputs", []):
            inp.clear()
        for i, saved_key in enumerate(keys):
            if i < len(self.api_key_inputs):
                self.api_key_inputs[i].setText(saved_key)

        config.GEMINI_API_KEYS = {f"api_{i + 1}": saved_key for i, saved_key in enumerate(keys)}
        if self.gui and hasattr(self.gui, "api_key_manager"):
            self.gui.api_key_manager = APIKeyManager(use_secrets_manager=True)
            if hasattr(self.gui, "init_client"):
                try:
                    self.gui.init_client()
                except Exception:
                    pass
        self._update_key_count()
        self._refresh_setup_assistant_status()
        return True

    def _apply_clipboard_payload(self, raw_text: str, auto_confirm: bool = False) -> bool:
        """Apply clipboard text to relevant setup inputs and optionally auto-confirm."""
        text = str(raw_text or "").strip()
        if not text:
            return False

        step_id = ""
        if self._setup_running and 0 <= self._setup_step_index < len(self._setup_steps):
            step_id = self._setup_steps[self._setup_step_index]

        consumed = False
        summary = ""

        # 1) Gemini key
        if step_id in ("", "precheck"):
            gemini_key = self._extract_gemini_key_from_text(text)
            if gemini_key and self._store_gemini_key_silent(gemini_key):
                consumed = True
                summary = "Gemini API 키 자동 반영"

        # 2) TikTok OAuth code
        if not consumed and step_id in ("", "tiktok_user_auth", "tiktok_code_exchange", "tiktok_verify"):
            auth_code = self._extract_oauth_code_candidate_from_text(text)
            if auth_code:
                self.setup_tiktok_code_input.setText(auth_code)
                consumed = True
                summary = "TikTok code 자동 입력"

        # 3) Instagram handle
        if not consumed and step_id in ("", "instagram_user_setup", "instagram_verify"):
            handle = self._extract_social_handle_from_text(text, "instagram")
            if handle:
                self.setup_instagram_handle_input.setText(handle)
                consumed = True
                summary = f"Instagram 계정 자동 입력 (@{handle})"

        # 4) Threads handle
        if not consumed and step_id in ("", "threads_user_setup", "threads_verify"):
            handle = self._extract_social_handle_from_text(text, "threads")
            if handle:
                self.setup_threads_handle_input.setText(handle)
                consumed = True
                summary = f"Threads 계정 자동 입력 (@{handle})"

        # 5) Linktree profile
        if not consumed and step_id in ("", "linktree_user_setup", "linktree_save_verify"):
            linktree_url = self._extract_linktree_url_from_text(text)
            if linktree_url:
                normalized = self._normalize_http_url(linktree_url)
                if self._is_valid_http_url(normalized):
                    self.linktree_profile_input.setText(normalized)
                    consumed = True
                    summary = "Linktree 공개 주소 자동 입력"

        if not consumed:
            return False

        self._append_setup_log(f"클립보드 자동 반영: {summary}")
        self._update_setup_clipboard_status(summary, level="ok")

        if auto_confirm and self._setup_running and self._setup_waiting_user:
            QTimer.singleShot(10, self._on_setup_done_clicked)
        return True

    def _get_saved_gemini_key_count(self) -> int:
        """Return number of saved Gemini keys in secure store."""
        count = 0
        for i in range(1, 9):
            value = SecretsManager.get_api_key(f"gemini_api_{i}")
            if value and str(value).strip():
                count += 1
        if count == 0:
            legacy = SecretsManager.get_api_key("gemini")
            if legacy and str(legacy).strip():
                count = 1
        return count

    def _is_youtube_connected(self) -> bool:
        """Resolve YouTube connection state from shared settings/manager."""
        settings = get_settings_manager()
        if settings.get_youtube_connected():
            return True

        yt_manager = getattr(self.gui, "youtube_manager", None) if self.gui else None
        if yt_manager and hasattr(yt_manager, "is_connected"):
            try:
                if bool(yt_manager.is_connected()):
                    info = yt_manager.get_channel_info() or {}
                    settings.set_youtube_connected(
                        True,
                        str(info.get("id", "")),
                        str(info.get("title") or info.get("channel_name") or ""),
                    )
                    return True
            except Exception:
                pass
        return False

    def _get_tiktok_manager(self):
        """Resolve TikTok manager instance from GUI or singleton."""
        manager = getattr(self.gui, "tiktok_manager", None) if self.gui else None
        if manager is not None:
            return manager
        try:
            manager = get_tiktok_manager(gui=self.gui)
            if self.gui is not None and not getattr(self.gui, "tiktok_manager", None):
                self.gui.tiktok_manager = manager
            return manager
        except Exception as exc:
            logger.warning("[SetupAssistant] TikTok manager unavailable: %s", exc)
            return None

    def _is_tiktok_connected(self) -> bool:
        """Resolve TikTok connection state from settings/manager."""
        settings = get_settings_manager()
        if settings.get_social_connection_status("tiktok"):
            return True

        manager = self._get_tiktok_manager()
        if manager and hasattr(manager, "is_connected"):
            try:
                if bool(manager.is_connected()):
                    account_name = ""
                    if hasattr(manager, "get_channel_info"):
                        ch = manager.get_channel_info()
                        account_name = (
                            str(getattr(ch, "display_name", "") or "")
                            or str(getattr(ch, "username", "") or "")
                            or "TikTok 계정"
                        )
                    settings.set_social_connection_status("tiktok", True, account_name=account_name)
                    return True
            except Exception:
                pass
        return False

    @staticmethod
    def _normalize_social_account_input(raw_text: str) -> str:
        """Normalize username/account input from plain handle or profile URL."""
        value = str(raw_text or "").strip()
        if not value:
            return ""
        value = value.replace("\\", "/").strip()
        value = re.sub(r"^https?://", "", value, flags=re.IGNORECASE)
        value = re.sub(r"^www\.", "", value, flags=re.IGNORECASE)
        if "/" in value:
            parts = [segment for segment in value.split("/") if segment]
            if parts:
                value = parts[-1]
        value = value.split("?", 1)[0].split("#", 1)[0].strip()
        if value.startswith("@"):
            value = value[1:]
        if "/" in value:
            value = value.split("/", 1)[0]
        value = value.strip()
        if not value:
            return ""

        blocked_tokens = {
            "accounts", "login", "logout", "auth", "oauth", "signup", "register",
            "explore", "reels", "reel", "home", "about", "privacy", "terms",
            "developers", "developer", "apps", "app",
        }
        if value.lower() in blocked_tokens:
            return ""

        if not re.fullmatch(r"[A-Za-z0-9._]{1,64}", value):
            return ""
        return value

    def _is_instagram_connected(self) -> bool:
        return bool(get_settings_manager().get_social_connection_status("instagram"))

    def _is_threads_connected(self) -> bool:
        return bool(get_settings_manager().get_social_connection_status("threads"))

    def _set_manual_social_connected(self, platform: str, account_name: str) -> bool:
        """Persist manual social account connection and sync GUI state if available."""
        settings = get_settings_manager()
        saved = settings.set_social_connection_status(platform, True, account_name=account_name)
        if saved and self.gui and hasattr(self.gui, "state"):
            try:
                setattr(self.gui.state, f"{platform}_connected", True)
            except Exception:
                pass
        return saved

    @staticmethod
    def _normalize_http_url(raw_url: str) -> str:
        value = str(raw_url or "").strip()
        if not value:
            return ""
        if not value.lower().startswith(("http://", "https://")):
            value = "https://" + value
        return value

    @staticmethod
    def _is_valid_http_url(url: str) -> bool:
        return bool(re.match(r"^https?://[^\s/$.?#].[^\s]*$", str(url or "").strip(), re.IGNORECASE))

    def _is_linktree_profile_ready(self) -> bool:
        """Check whether a valid Linktree public profile URL is provided."""
        if not hasattr(self, "linktree_profile_input"):
            return False
        profile = self._normalize_http_url(self.linktree_profile_input.text())
        return self._is_valid_http_url(profile)

    def _refresh_setup_connection_chips(self):
        """Refresh top status chips in setup assistant."""
        c = self.ds.colors

        def set_chip(chip: QLabel, title: str, ok: bool, detail: str = "", warn: bool = False):
            if ok:
                detail_suffix = f" ({detail})" if detail else ""
                chip.setText(f"{title} · 연결됨{detail_suffix}")
                chip.setStyleSheet(
                    f"padding: 5px 10px; border-radius: {self.ds.radius.full}px; "
                    f"border: 1px solid {c.success}; background: {c.success}22; color: {c.success}; font-weight: 600;"
                )
                return
            if warn:
                chip.setText(f"{title} · 점검 필요{(' (' + detail + ')') if detail else ''}")
                chip.setStyleSheet(
                    f"padding: 5px 10px; border-radius: {self.ds.radius.full}px; "
                    f"border: 1px solid {c.warning}; background: {c.warning}22; color: {c.warning}; font-weight: 600;"
                )
                return
            chip.setText(f"{title} · 미연결")
            chip.setStyleSheet(
                f"padding: 5px 10px; border-radius: {self.ds.radius.full}px; "
                f"border: 1px solid {c.border_light}; background: {c.surface_variant}; color: {c.text_muted};"
            )

        gemini_count = self._get_saved_gemini_key_count()
        set_chip(self.setup_chip_gemini, "Gemini", gemini_count > 0, detail=f"{gemini_count}개")

        settings = get_settings_manager()

        yt_connected = self._is_youtube_connected()
        yt_name = settings.get_youtube_channel_info().get("channel_name", "")
        set_chip(self.setup_chip_youtube, "YouTube", yt_connected, detail=str(yt_name or ""))

        tiktok_connected = self._is_tiktok_connected()
        tiktok_name = settings.get_social_account_name("tiktok")
        set_chip(self.setup_chip_tiktok, "TikTok", tiktok_connected, detail=tiktok_name)

        instagram_connected = self._is_instagram_connected()
        instagram_name = settings.get_social_account_name("instagram")
        set_chip(self.setup_chip_instagram, "Instagram", instagram_connected, detail=instagram_name)

        threads_connected = self._is_threads_connected()
        threads_name = settings.get_social_account_name("threads")
        set_chip(self.setup_chip_threads, "Threads", threads_connected, detail=threads_name)

        linktree_profile_ready = self._is_linktree_profile_ready()
        linktree_auto_enabled = bool(getattr(self, "linktree_auto_checkbox", None) and self.linktree_auto_checkbox.isChecked())
        linktree_webhook_ready = bool(getattr(self, "linktree_webhook_input", None) and self.linktree_webhook_input.text().strip())
        linktree_warn = linktree_auto_enabled and not linktree_webhook_ready
        set_chip(
            self.setup_chip_linktree,
            "Linktree",
            linktree_profile_ready,
            detail="Webhook 필요" if linktree_warn else "",
            warn=linktree_warn and linktree_profile_ready,
        )

    def _refresh_setup_assistant_status(self):
        """Public refresh point after settings changes."""
        if not hasattr(self, "setup_chip_gemini"):
            return
        self._refresh_setup_connection_chips()
        QTimer.singleShot(0, self._refresh_computer_use_access_ui)

    def _build_setup_steps(self, scope: str) -> List[str]:
        """Return step sequence by setup scope."""
        youtube_steps = ["youtube_prepare", "youtube_user_auth", "youtube_verify"]
        tiktok_steps = ["tiktok_prepare", "tiktok_user_auth", "tiktok_code_exchange", "tiktok_verify"]
        instagram_steps = ["instagram_user_setup", "instagram_verify"]
        threads_steps = ["threads_user_setup", "threads_verify"]
        linktree_steps = ["linktree_user_setup", "linktree_save_verify"]

        if scope == "youtube":
            return ["precheck", *youtube_steps, "final_verify"]
        if scope == "tiktok":
            return ["precheck", *tiktok_steps, "final_verify"]
        if scope == "instagram":
            return ["precheck", *instagram_steps, "final_verify"]
        if scope == "threads":
            return ["precheck", *threads_steps, "final_verify"]
        if scope == "social4":
            # 틱톡 비활성화: 틱톡 단계 제외
            return ["precheck", *youtube_steps, *instagram_steps, *threads_steps, "final_verify"]
        if scope == "linktree":
            return ["precheck", *linktree_steps, "final_verify"]
        return [
            "precheck",
            *youtube_steps,
            *instagram_steps,
            *threads_steps,
            *linktree_steps,
            "final_verify",
        ]

    def _start_setup_assistant(self, scope: str):
        """Start guided setup assistant flow."""
        if self._setup_running:
            return
        self._setup_running = True
        self._setup_clipboard_last_text = ""
        self._setup_scope = scope
        self._setup_steps = self._build_setup_steps(scope)
        self._setup_step_index = 0
        self._setup_waiting_user = False

        self._reset_setup_timeline()
        for step_id in self._setup_rows:
            if step_id not in self._setup_steps:
                self._set_setup_row_state(step_id, "skipped")

        self._append_setup_log(f"도우미 시작: scope={scope}")
        self._set_setup_current_action(
            title="도우미 실행 중",
            description="단계 준비 중입니다...",
            action_text="",
            action_callback=None,
            show_done=False,
        )
        self._update_setup_clipboard_status("대기 중", level="info")
        QTimer.singleShot(10, self._run_setup_step)

    def _stop_setup_assistant(self):
        """Stop guided setup assistant."""
        if not self._setup_running:
            return
        self._setup_running = False
        self._setup_waiting_user = False
        self._append_setup_log("도우미 중단")
        self._set_setup_current_action(
            title="중단됨",
            description="사용자가 도우미를 중단했습니다. 다시 시작 버튼으로 재개할 수 있습니다.",
            action_text="",
            action_callback=None,
            show_done=False,
        )
        self.setup_retry_btn.setVisible(False)
        self.setup_stop_btn.setVisible(False)
        self._update_setup_clipboard_status("도우미 중단됨", level="warn")

    def _run_setup_step(self):
        """Execute current setup step."""
        if not self._setup_running:
            return
        if self._setup_step_index >= len(self._setup_steps):
            self._setup_running = False
            self._setup_waiting_user = False
            self._refresh_setup_assistant_status()
            self._set_setup_current_action(
                title="설정 완료",
                description="도우미 흐름이 끝났습니다. 연결 상태 칩과 타임라인을 확인하세요.",
                action_text="",
                action_callback=None,
                show_done=False,
            )
            self.setup_retry_btn.setVisible(False)
            self.setup_stop_btn.setVisible(False)
            self._append_setup_log("도우미 완료")
            self._update_setup_clipboard_status("도우미 완료", level="ok")
            return

        step_id = self._setup_steps[self._setup_step_index]
        self._setup_waiting_user = False
        self._set_setup_row_state(step_id, "running")
        self._append_setup_log(f"단계 시작: {self.SETUP_STEP_DEFS[step_id]['title']}")
        self._set_setup_current_action(
            title=f"{self.SETUP_STEP_DEFS[step_id]['title']} 진행 중",
            description="자동 점검/처리 중입니다. 잠시만 기다려주세요.",
            action_text="",
            action_callback=None,
            show_done=False,
        )

        if step_id == "precheck":
            gemini_count = self._get_saved_gemini_key_count()
            if gemini_count > 0:
                self._set_setup_row_state(step_id, "done")
                self._append_setup_log(f"사전 점검 통과: Gemini 키 {gemini_count}개")
                self._advance_setup_step()
                return

            self._setup_waiting_user = True
            self._set_setup_row_state(step_id, "waiting", "Gemini 키 필요")
            self._set_setup_current_action(
                title="Gemini API 키 입력 필요",
                description=(
                    "API 키가 저장되어 있지 않습니다. 아래 버튼으로 API 키 섹션으로 이동해 키를 저장한 뒤 "
                    "'완료했어요'를 눌러주세요."
                ),
                action_text="API 키 섹션으로 이동",
                action_callback=self.focus_api_key_setup,
                show_done=True,
            )
            return

        if step_id == "youtube_prepare":
            self._refresh_setup_assistant_status()
            self._set_setup_row_state(step_id, "done")
            self._append_setup_log("YouTube OAuth 준비 완료")
            self._advance_setup_step()
            return

        if step_id == "youtube_user_auth":
            if self._is_youtube_connected():
                self._set_setup_row_state(step_id, "done")
                self._append_setup_log("YouTube가 이미 연결되어 있어 사용자 인증 단계를 건너뜁니다.")
                self._advance_setup_step()
                return

            self._setup_waiting_user = True
            self._set_setup_row_state(step_id, "waiting", "사용자 인증 필요")
            self._set_setup_current_action(
                title="YouTube 로그인/동의 진행",
                description=(
                    "OAuth 연결 창을 열어 client_secrets.json 선택 → Google 로그인/2FA/동의를 완료해주세요. "
                    "완료 후 이 화면에서 '완료했어요'를 눌러 검증합니다."
                ),
                action_text="YouTube OAuth 창 열기",
                action_callback=self._assistant_open_youtube_oauth,
                show_done=True,
            )
            return

        if step_id == "youtube_verify":
            if self._is_youtube_connected():
                self._refresh_setup_assistant_status()
                self._set_setup_row_state(step_id, "done")
                self._append_setup_log("YouTube 연결 검증 성공")
                self._advance_setup_step()
                return

            self._setup_waiting_user = True
            self._set_setup_row_state(step_id, "waiting", "연결 확인 필요")
            self._set_setup_current_action(
                title="YouTube 연결이 아직 완료되지 않았습니다",
                description=(
                    "OAuth 연결이 확인되지 않았습니다. 인증 창을 다시 열어 승인 절차를 마친 뒤 "
                    "'완료했어요'를 눌러주세요."
                ),
                action_text="YouTube OAuth 창 다시 열기",
                action_callback=self._assistant_open_youtube_oauth,
                show_done=True,
            )
            return

        if step_id == "tiktok_prepare":
            manager = self._get_tiktok_manager()
            if manager is None:
                self._setup_waiting_user = True
                self._set_setup_row_state(step_id, "waiting", "매니저 초기화 필요")
                self._set_setup_current_action(
                    title="TikTok 매니저 초기화 필요",
                    description=(
                        "TikTok 매니저를 불러오지 못했습니다. 앱을 재실행한 뒤 다시 시도하거나 "
                        "환경변수(TIKTOK_CLIENT_KEY/SECRET/REDIRECT_URI)를 점검하세요."
                    ),
                    action_text="Computer Use 가이드 열기",
                    action_callback=self._assistant_open_computer_use_guide,
                    show_done=True,
                )
                return

            auth_url = ""
            try:
                auth_url = manager.get_auth_url(state=f"setup_{int(datetime.now().timestamp())}")
            except Exception as exc:
                logger.warning("[SetupAssistant] TikTok auth url generation failed: %s", exc)
                auth_url = ""

            self._setup_last_tiktok_auth_url = str(auth_url or "").strip()
            if not self._setup_last_tiktok_auth_url:
                self._setup_waiting_user = True
                self._set_setup_row_state(step_id, "waiting", "OAuth 설정값 필요")
                self._set_setup_current_action(
                    title="TikTok OAuth 설정 필요",
                    description=(
                        "TikTok OAuth URL을 만들지 못했습니다. TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, "
                        "TIKTOK_REDIRECT_URI 설정 후 '완료했어요'를 눌러주세요."
                    ),
                    action_text="Meta/TikTok 개발 콘솔 열기",
                    action_callback=lambda: self._open_external_url("https://developers.tiktok.com/"),
                    show_done=True,
                )
                return

            self._set_setup_row_state(step_id, "done")
            self._append_setup_log("TikTok OAuth 준비 완료")
            self._advance_setup_step()
            return

        if step_id == "tiktok_user_auth":
            if self._is_tiktok_connected():
                self._set_setup_row_state(step_id, "done")
                self._append_setup_log("TikTok이 이미 연결되어 있어 인증 단계를 건너뜁니다.")
                self._advance_setup_step()
                return

            self._setup_waiting_user = True
            self._set_setup_row_state(step_id, "waiting", "사용자 인증 필요")
            self._set_setup_current_action(
                title="TikTok 로그인/승인 진행",
                description=(
                    "인증 페이지를 열어 TikTok 로그인 및 권한 승인을 완료하세요. "
                    "완료 후 리디렉션 URL의 code 값을 아래 입력칸에 붙여넣고 '완료했어요'를 누르세요."
                ),
                action_text="TikTok 인증 페이지 열기",
                action_callback=self._assistant_open_tiktok_auth,
                show_done=True,
            )
            return

        if step_id == "tiktok_code_exchange":
            if self._is_tiktok_connected():
                self._set_setup_row_state(step_id, "done")
                self._append_setup_log("TikTok 코드 교환을 생략합니다(이미 연결됨).")
                self._advance_setup_step()
                return

            auth_code = self._extract_oauth_code(
                self.setup_tiktok_code_input.text() if hasattr(self, "setup_tiktok_code_input") else ""
            )
            if not auth_code:
                self._setup_waiting_user = True
                self._set_setup_row_state(step_id, "waiting", "OAuth code 필요")
                self._set_setup_current_action(
                    title="TikTok OAuth code 입력 필요",
                    description=(
                        "TikTok 인증 후 리디렉션 URL에서 code 값을 복사해 붙여넣어야 합니다. "
                        "값 입력 후 '완료했어요'를 눌러 코드 교환을 진행하세요."
                    ),
                    action_text="입력칸으로 이동",
                    action_callback=lambda: self.setup_tiktok_code_input.setFocus(Qt.FocusReason.OtherFocusReason),
                    show_done=True,
                )
                return

            manager = self._get_tiktok_manager()
            if manager is None:
                self._setup_waiting_user = True
                self._set_setup_row_state(step_id, "error", "매니저 없음")
                self._set_setup_current_action(
                    title="TikTok 매니저 없음",
                    description="TikTok 코드 교환을 수행할 매니저를 찾지 못했습니다. 재검증을 눌러 재시도하세요.",
                    action_text="",
                    action_callback=None,
                    show_done=False,
                )
                return

            exchanged = False
            try:
                exchanged = bool(manager.exchange_code_for_token(auth_code))
            except Exception as exc:
                logger.warning("[SetupAssistant] TikTok code exchange failed: %s", exc)
                exchanged = False

            if not exchanged:
                self._setup_waiting_user = True
                self._set_setup_row_state(step_id, "waiting", "코드 교환 실패")
                self._set_setup_current_action(
                    title="TikTok 코드 교환 실패",
                    description=(
                        "코드가 만료되었거나 OAuth 설정이 맞지 않습니다. 인증 페이지를 다시 열어 새 code를 발급받은 뒤 "
                        "입력해 주세요."
                    ),
                    action_text="TikTok 인증 다시 열기",
                    action_callback=self._assistant_open_tiktok_auth,
                    show_done=True,
                )
                return

            channel = manager.get_channel_info() if hasattr(manager, "get_channel_info") else None
            account_name = (
                str(getattr(channel, "display_name", "") or "")
                or str(getattr(channel, "username", "") or "")
                or "TikTok 계정"
            )
            self._set_manual_social_connected("tiktok", account_name)
            self._refresh_setup_assistant_status()
            self._set_setup_row_state(step_id, "done")
            self._append_setup_log("TikTok 코드 교환 성공")
            self._advance_setup_step()
            return

        if step_id == "tiktok_verify":
            if self._is_tiktok_connected():
                self._refresh_setup_assistant_status()
                self._set_setup_row_state(step_id, "done")
                self._append_setup_log("TikTok 연결 검증 성공")
                self._advance_setup_step()
                return

            self._setup_waiting_user = True
            self._set_setup_row_state(step_id, "waiting", "연결 확인 필요")
            self._set_setup_current_action(
                title="TikTok 연결이 아직 확인되지 않았습니다",
                description="코드 교환이 완료되어야 합니다. 새 code로 다시 시도한 뒤 '완료했어요'를 눌러주세요.",
                action_text="TikTok 인증 다시 열기",
                action_callback=self._assistant_open_tiktok_auth,
                show_done=True,
            )
            return

        if step_id == "instagram_user_setup":
            if self._is_instagram_connected():
                self._set_setup_row_state(step_id, "done")
                self._append_setup_log("Instagram이 이미 연결되어 있습니다.")
                self._advance_setup_step()
                return

            instagram_handle = self._normalize_social_account_input(
                self.setup_instagram_handle_input.text() if hasattr(self, "setup_instagram_handle_input") else ""
            )
            if instagram_handle:
                self.setup_instagram_handle_input.setText(instagram_handle)
                self._set_setup_row_state(step_id, "done")
                self._append_setup_log(f"Instagram 계정 입력 확인: @{instagram_handle}")
                self._advance_setup_step()
                return

            self._setup_waiting_user = True
            self._set_setup_row_state(step_id, "waiting", "계정명 입력 필요")
            self._set_setup_current_action(
                title="Instagram 계정 정보 입력",
                description=(
                    "Instagram 로그인/승인을 완료한 뒤 아래 입력칸에 계정명(또는 프로필 URL)을 입력하고 "
                    "'완료했어요'를 눌러주세요."
                ),
                action_text="Instagram 열기",
                action_callback=self._assistant_open_instagram_setup,
                show_done=True,
            )
            return

        if step_id == "instagram_verify":
            if self._is_instagram_connected():
                self._set_setup_row_state(step_id, "done")
                self._append_setup_log("Instagram 연결 검증 성공")
                self._advance_setup_step()
                return

            instagram_handle = self._normalize_social_account_input(
                self.setup_instagram_handle_input.text() if hasattr(self, "setup_instagram_handle_input") else ""
            )
            if not instagram_handle:
                self._setup_waiting_user = True
                self._set_setup_row_state(step_id, "waiting", "계정명 확인 필요")
                self._set_setup_current_action(
                    title="Instagram 계정명 확인 필요",
                    description="Instagram 계정명을 입력해 주세요. 예: my_shop_account",
                    action_text="입력칸으로 이동",
                    action_callback=lambda: self.setup_instagram_handle_input.setFocus(Qt.FocusReason.OtherFocusReason),
                    show_done=True,
                )
                return

            self.setup_instagram_handle_input.setText(instagram_handle)
            self._set_manual_social_connected("instagram", instagram_handle)
            self._refresh_setup_assistant_status()
            self._set_setup_row_state(step_id, "done")
            self._append_setup_log(f"Instagram 연결 검증 완료: @{instagram_handle}")
            self._advance_setup_step()
            return

        if step_id == "threads_user_setup":
            if self._is_threads_connected():
                self._set_setup_row_state(step_id, "done")
                self._append_setup_log("Threads가 이미 연결되어 있습니다.")
                self._advance_setup_step()
                return

            threads_handle = self._normalize_social_account_input(
                self.setup_threads_handle_input.text() if hasattr(self, "setup_threads_handle_input") else ""
            )
            if threads_handle:
                self.setup_threads_handle_input.setText(threads_handle)
                self._set_setup_row_state(step_id, "done")
                self._append_setup_log(f"Threads 계정 입력 확인: @{threads_handle}")
                self._advance_setup_step()
                return

            self._setup_waiting_user = True
            self._set_setup_row_state(step_id, "waiting", "계정명 입력 필요")
            self._set_setup_current_action(
                title="Threads 계정 정보 입력",
                description=(
                    "Threads 로그인/승인을 완료한 뒤 아래 입력칸에 계정명(또는 프로필 URL)을 입력하고 "
                    "'완료했어요'를 눌러주세요."
                ),
                action_text="Threads 열기",
                action_callback=self._assistant_open_threads_setup,
                show_done=True,
            )
            return

        if step_id == "threads_verify":
            if self._is_threads_connected():
                self._set_setup_row_state(step_id, "done")
                self._append_setup_log("Threads 연결 검증 성공")
                self._advance_setup_step()
                return

            threads_handle = self._normalize_social_account_input(
                self.setup_threads_handle_input.text() if hasattr(self, "setup_threads_handle_input") else ""
            )
            if not threads_handle:
                self._setup_waiting_user = True
                self._set_setup_row_state(step_id, "waiting", "계정명 확인 필요")
                self._set_setup_current_action(
                    title="Threads 계정명 확인 필요",
                    description="Threads 계정명을 입력해 주세요. 예: my_shop_account",
                    action_text="입력칸으로 이동",
                    action_callback=lambda: self.setup_threads_handle_input.setFocus(Qt.FocusReason.OtherFocusReason),
                    show_done=True,
                )
                return

            self.setup_threads_handle_input.setText(threads_handle)
            self._set_manual_social_connected("threads", threads_handle)
            self._refresh_setup_assistant_status()
            self._set_setup_row_state(step_id, "done")
            self._append_setup_log(f"Threads 연결 검증 완료: @{threads_handle}")
            self._advance_setup_step()
            return

        if step_id == "linktree_user_setup":
            if self._is_linktree_profile_ready():
                self._set_setup_row_state(step_id, "done")
                self._append_setup_log("Linktree 공개 주소가 이미 입력되어 있습니다.")
                self._advance_setup_step()
                return

            self._setup_waiting_user = True
            self._set_setup_row_state(step_id, "waiting", "공개 주소 필요")
            self._set_setup_current_action(
                title="Linktree 공개 주소 입력",
                description=(
                    "Linktree 로그인 후 공개 프로필 주소(예: https://linktr.ee/myshop)를 입력하고 "
                    "'완료했어요'를 눌러주세요."
                ),
                action_text="Linktree 관리자 열기",
                action_callback=self._assistant_open_linktree_admin,
                show_done=True,
            )
            return

        if step_id == "linktree_save_verify":
            profile_url = self._normalize_http_url(self.linktree_profile_input.text())
            if not self._is_valid_http_url(profile_url):
                self._setup_waiting_user = True
                self._set_setup_row_state(step_id, "waiting", "주소 형식 확인 필요")
                self._set_setup_current_action(
                    title="Linktree 공개 주소 형식 확인",
                    description="Linktree 공개 주소를 http(s) 형식으로 입력한 뒤 '완료했어요'를 눌러주세요.",
                    action_text="Linktree 입력칸으로 이동",
                    action_callback=lambda: self.linktree_profile_input.setFocus(Qt.FocusReason.OtherFocusReason),
                    show_done=True,
                )
                return

            self.linktree_profile_input.setText(profile_url)
            settings = get_settings_manager()
            saved = settings.set_linktree_settings(
                webhook_url=self.linktree_webhook_input.text().strip(),
                api_key=self.linktree_api_key_input.text().strip(),
                profile_url=profile_url,
                auto_publish=self.linktree_auto_checkbox.isChecked(),
            )
            if not saved:
                self._setup_waiting_user = True
                self._set_setup_row_state(step_id, "error", "저장 실패")
                self._set_setup_current_action(
                    title="Linktree 저장 실패",
                    description="설정 저장 중 오류가 발생했습니다. '재검증'으로 다시 시도해주세요.",
                    action_text="",
                    action_callback=None,
                    show_done=False,
                )
                return

            self._load_link_automation_settings()
            self._refresh_setup_assistant_status()
            self._set_setup_row_state(step_id, "done")
            self._append_setup_log("Linktree 설정 저장/검증 완료")
            self._advance_setup_step()
            return

        if step_id == "final_verify":
            self._refresh_setup_assistant_status()
            missing: List[str] = []
            if self._get_saved_gemini_key_count() <= 0:
                missing.append("Gemini API 키")

            scope = str(self._setup_scope or "")
            need_youtube = scope in ("all", "social4", "youtube")
            need_tiktok = scope in ("all", "social4", "tiktok")
            need_instagram = scope in ("all", "social4", "instagram")
            need_threads = scope in ("all", "social4", "threads")
            need_linktree = scope in ("all", "linktree")

            if need_youtube and not self._is_youtube_connected():
                missing.append("YouTube 연결")
            if need_tiktok and not self._is_tiktok_connected():
                missing.append("TikTok 연결")
            if need_instagram and not self._is_instagram_connected():
                missing.append("Instagram 연결")
            if need_threads and not self._is_threads_connected():
                missing.append("Threads 연결")
            if need_linktree and not self._is_linktree_profile_ready():
                missing.append("Linktree 공개 주소")

            if missing:
                self._setup_waiting_user = True
                self._set_setup_row_state(step_id, "waiting", "추가 설정 필요")
                self._set_setup_current_action(
                    title="최종 점검 미완료",
                    description="다음 항목이 필요합니다: " + ", ".join(missing) + ". 수정 후 '완료했어요'를 눌러주세요.",
                    action_text="설정 상태 새로고침",
                    action_callback=self._refresh_setup_assistant_status,
                    show_done=True,
                )
                self._append_setup_log("최종 점검 대기: " + ", ".join(missing))
                return

            self._set_setup_row_state(step_id, "done")
            self._append_setup_log("최종 연결 테스트 성공")
            self._advance_setup_step()
            return

    def _advance_setup_step(self):
        """Move to next setup step."""
        if not self._setup_running:
            return
        self._setup_step_index += 1
        QTimer.singleShot(40, self._run_setup_step)

    def _assistant_open_youtube_oauth(self):
        """Open existing YouTube OAuth dialog flow from upload panel."""
        self._append_setup_log("YouTube OAuth 창을 엽니다.")
        upload_panel = getattr(self.gui, "upload_panel", None) if self.gui else None
        if upload_panel and hasattr(upload_panel, "_show_youtube_json_connect"):
            try:
                upload_panel._show_youtube_json_connect()
            except Exception as exc:
                logger.warning("[SetupAssistant] Failed to open YouTube OAuth dialog: %s", exc)
                self._append_setup_log(f"YouTube OAuth 창 실행 실패: {exc}")
                return
            self._refresh_setup_assistant_status()
            self._append_setup_log("YouTube OAuth 창이 닫혔습니다. 연결 상태를 다시 확인하세요.")
            return

        # Fallback: open guide page
        self._append_setup_log("업로드 패널을 찾지 못해 OAuth 가이드 페이지를 엽니다.")
        self._open_external_url(f"{SETUP_NOTICE_BASE_URL}/youtube-google-cloud-oauth-screenshots")

    def _assistant_open_linktree_admin(self):
        """Open Linktree admin page and focus profile input."""
        self._open_linktree_admin()
        self.linktree_profile_input.setFocus(Qt.FocusReason.OtherFocusReason)
        self._append_setup_log("Linktree 관리자 페이지를 열었습니다.")

    @staticmethod
    def _extract_oauth_code(raw_value: str) -> str:
        """Extract OAuth code from raw code or callback URL text."""
        text = str(raw_value or "").strip()
        if not text:
            return ""
        match = re.search(r"(?:[?&#]|^)code=([^&#\s]+)", text)
        if match:
            return match.group(1).strip()
        return text

    def _assistant_open_tiktok_auth(self):
        """Open TikTok OAuth/login page and guide user to paste code."""
        manager = self._get_tiktok_manager()
        auth_url = str(self._setup_last_tiktok_auth_url or "").strip()
        if not auth_url and manager is not None:
            try:
                auth_url = str(manager.get_auth_url(state=f"setup_{int(datetime.now().timestamp())}") or "").strip()
            except Exception as exc:
                logger.warning("[SetupAssistant] Failed to regenerate TikTok auth url: %s", exc)

        if auth_url:
            self._setup_last_tiktok_auth_url = auth_url
            self._append_setup_log("TikTok OAuth 인증 페이지를 엽니다.")
            self._open_external_url(auth_url)
            self.setup_tiktok_code_input.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        self._append_setup_log("TikTok OAuth URL 생성 실패 - 로그인/개발자 페이지를 엽니다.")
        self._open_external_url(TIKTOK_LOGIN_URL)
        self._open_external_url("https://developers.tiktok.com/")

    def _assistant_open_instagram_setup(self):
        """Open Instagram + Meta app pages for manual setup."""
        self._open_external_url(INSTAGRAM_LOGIN_URL)
        self._open_external_url(META_APPS_URL)
        self.setup_instagram_handle_input.setFocus(Qt.FocusReason.OtherFocusReason)
        self._append_setup_log("Instagram/Meta 설정 페이지를 열었습니다.")

    def _assistant_open_threads_setup(self):
        """Open Threads + Meta app pages for manual setup."""
        self._open_external_url(THREADS_LOGIN_URL)
        self._open_external_url(META_APPS_URL)
        self.setup_threads_handle_input.setFocus(Qt.FocusReason.OtherFocusReason)
        self._append_setup_log("Threads/Meta 설정 페이지를 열었습니다.")

    def _assistant_open_computer_use_guide(self):
        """Show computer-use setup guidance and open notice page."""
        from ui.components.custom_dialog import show_info

        show_info(
            self,
            "Computer Use 설정 가이드",
            "권장 순서:\n"
            "1) Codex 상태 점검 후 '현재 단계 Codex 실행'\n"
            "2) 로그인/2FA/CAPTCHA/동의만 직접 처리\n"
            "3) code/프로필 URL/API 키는 복사 (클립보드 자동반영)\n"
            "4) 각 단계에서 '완료했어요'로 검증 진행",
        )
        self._open_external_url(f"{SETUP_NOTICE_BASE_URL}/computer-use-social-setup")
        self._append_setup_log("Computer Use 설정 가이드를 열었습니다.")

    def _load_codex_cli_settings(self):
        """Load saved Codex CLI bridge settings and refresh status label."""
        try:
            mgr = get_settings_manager()
            settings = mgr.get_codex_cli_settings()
            cu_settings = mgr.get_computer_use_settings()
        except Exception:
            settings = {"path": "codex", "model": "", "enabled": True}
            cu_settings = {"paid_only": True, "bridge_enabled": False, "bridge_url": "", "bridge_api_key": ""}

        if hasattr(self, "setup_codex_path_input"):
            self.setup_codex_path_input.setText(str(settings.get("path", "codex") or "codex"))
        if hasattr(self, "setup_codex_model_input"):
            self.setup_codex_model_input.setText(str(settings.get("model", "") or ""))
        if hasattr(self, "setup_computer_use_paid_only_checkbox"):
            self.setup_computer_use_paid_only_checkbox.setChecked(bool(cu_settings.get("paid_only", True)))
        if hasattr(self, "setup_computer_use_bridge_checkbox"):
            self.setup_computer_use_bridge_checkbox.setChecked(bool(cu_settings.get("bridge_enabled", False)))
        if hasattr(self, "setup_computer_use_bridge_url_input"):
            self.setup_computer_use_bridge_url_input.setText(str(cu_settings.get("bridge_url", "") or ""))
        if hasattr(self, "setup_computer_use_bridge_key_input"):
            self.setup_computer_use_bridge_key_input.setText(str(cu_settings.get("bridge_api_key", "") or ""))

        QTimer.singleShot(120, self._refresh_computer_use_access_ui)

    def _save_codex_cli_settings(self):
        """Persist Codex CLI bridge settings."""
        from ui.components.custom_dialog import show_info, show_error

        path_value = "codex"
        model_value = ""
        if hasattr(self, "setup_codex_path_input"):
            path_value = str(self.setup_codex_path_input.text() or "").strip() or "codex"
            self.setup_codex_path_input.setText(path_value)
        if hasattr(self, "setup_codex_model_input"):
            model_value = str(self.setup_codex_model_input.text() or "").strip()
            self.setup_codex_model_input.setText(model_value)

        bridge_url = ""
        bridge_api_key = ""
        paid_only = True
        bridge_enabled = False
        if hasattr(self, "setup_computer_use_bridge_url_input"):
            bridge_url = str(self.setup_computer_use_bridge_url_input.text() or "").strip()
            self.setup_computer_use_bridge_url_input.setText(bridge_url)
        if hasattr(self, "setup_computer_use_bridge_key_input"):
            bridge_api_key = str(self.setup_computer_use_bridge_key_input.text() or "").strip()
            self.setup_computer_use_bridge_key_input.setText(bridge_api_key)
        if hasattr(self, "setup_computer_use_paid_only_checkbox"):
            paid_only = bool(self.setup_computer_use_paid_only_checkbox.isChecked())
        if hasattr(self, "setup_computer_use_bridge_checkbox"):
            bridge_enabled = bool(self.setup_computer_use_bridge_checkbox.isChecked())

        try:
            mgr = get_settings_manager()
            ok = mgr.set_codex_cli_settings(path=path_value, model=model_value)
            if not ok:
                show_error(self, "저장 실패", "Codex CLI 설정을 저장하지 못했습니다.")
                return
            ok_policy = mgr.set_computer_use_settings(
                paid_only=paid_only,
                bridge_enabled=bridge_enabled,
                bridge_url=bridge_url,
                bridge_api_key=bridge_api_key,
            )
            if not ok_policy:
                show_error(self, "저장 실패", "Computer Use 정책 설정을 저장하지 못했습니다.")
                return
            self._append_setup_log(f"Codex 설정 저장: path={path_value}, model={model_value or 'default'}")
            self._refresh_computer_use_access_ui()
            show_info(self, "저장 완료", "Codex CLI 설정을 저장했습니다.")
        except Exception as exc:
            show_error(self, "저장 실패", f"Codex CLI 설정 저장 중 오류가 발생했습니다.\n{exc}")

    @staticmethod
    def _resolve_codex_binary(configured_path: str) -> str:
        """Resolve codex executable path from a configured value."""
        candidate = str(configured_path or "").strip() or "codex"
        if os.path.sep in candidate or (os.path.altsep and os.path.altsep in candidate):
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
            return ""
        resolved = shutil.which(candidate)
        return str(resolved or "").strip()

    @staticmethod
    def _has_enabled_computer_use_mcp(mcp_list_output: str) -> bool:
        """Check whether codex mcp list output indicates enabled computer-use server."""
        text = str(mcp_list_output or "")
        for raw_line in text.splitlines():
            line = raw_line.strip().lower()
            if not line or "computer-use" not in line:
                continue
            if "enabled" in line:
                return True
        return False

    def _set_codex_status_text(self, text: str, level: str = "info"):
        """Render Codex status helper label."""
        self._codex_status_summary = str(text or "").strip() or "Codex 상태: 미확인"
        if not hasattr(self, "setup_codex_status"):
            return
        c = self.ds.colors
        if level == "ok":
            color = c.success
        elif level == "warn":
            color = c.warning
        elif level == "error":
            color = c.error
        else:
            color = c.text_muted
        self.setup_codex_status.setStyleSheet(
            f"color: {color}; border: none; background: transparent; font-size: 11px;"
        )
        self.setup_codex_status.setText(self._codex_status_summary)

    def _extract_logged_in_user_id(self) -> str:
        """Extract current user id from gui login payload."""
        if not self.gui:
            return ""
        try:
            from utils.auth_helpers import extract_user_id

            user_id = extract_user_id(getattr(self.gui, "login_data", None))
            return str(user_id or "").strip()
        except Exception:
            return ""

    def _extract_logged_in_token(self) -> str:
        """Extract current login JWT token from gui payload."""
        if not self.gui:
            return ""
        try:
            login_data = getattr(self.gui, "login_data", None)
            if not isinstance(login_data, dict):
                return ""
            data = login_data.get("data", {})
            if not isinstance(data, dict):
                return ""
            token = str(data.get("token") or "").strip()
            return token
        except Exception:
            return ""

    def _is_computer_use_paid_only(self) -> bool:
        """Return whether computer-use feature is restricted to paid users."""
        try:
            cu = get_settings_manager().get_computer_use_settings()
            return bool(cu.get("paid_only", True))
        except Exception:
            return True

    def _is_paid_user_for_computer_use(self, force_refresh: bool = False) -> bool:
        """Resolve paid entitlement for computer-use gating."""
        if not self._is_computer_use_paid_only():
            return True

        now = time.time()
        if (not force_refresh) and (now - self._computer_use_paid_cache_ts < 60):
            return bool(self._computer_use_paid_cache_value)

        paid = False
        user_id = self._extract_logged_in_user_id()
        if user_id:
            try:
                from caller import rest

                sub_status = rest.getSubscriptionStatus(user_id)
                has_expiry = bool(sub_status.get("subscription_expires_at"))
                is_unlimited = sub_status.get("work_count") == -1
                is_trial_flag = sub_status.get("is_trial")
                paid = has_expiry or is_unlimited or (is_trial_flag is False)
            except Exception:
                paid = False

        self._computer_use_paid_cache_value = bool(paid)
        self._computer_use_paid_cache_ts = now
        return bool(paid)

    def _refresh_computer_use_access_ui(self):
        """Update computer-use access controls by subscription policy/state."""
        paid_only = self._is_computer_use_paid_only()
        is_paid = self._is_paid_user_for_computer_use(force_refresh=False)
        allowed = (not paid_only) or is_paid

        if hasattr(self, "setup_codex_launch_btn"):
            self.setup_codex_launch_btn.setEnabled(bool(allowed))
            self.setup_codex_launch_btn.setToolTip(
                "" if allowed else "유료계정 전용 기능입니다. 무료계정은 수동 설정을 사용하세요."
            )
        if hasattr(self, "setup_codex_check_btn"):
            self.setup_codex_check_btn.setEnabled(bool(allowed))
            self.setup_codex_check_btn.setToolTip(
                "" if allowed else "유료계정 전용 기능입니다. 무료계정은 수동 설정을 사용하세요."
            )

        if not allowed and paid_only:
            self._set_codex_status_text("Computer Use: 유료계정 전용", level="warn")
            return

        self._refresh_codex_cli_status(show_dialog=False)

    def _refresh_codex_cli_status(self, show_dialog: bool = False) -> Dict[str, Any]:
        """Run Codex CLI health checks: binary, login, and computer-use MCP."""
        from ui.components.custom_dialog import show_info, show_warning

        try:
            settings = get_settings_manager().get_codex_cli_settings()
        except Exception:
            settings = {"path": "codex", "model": "", "enabled": True}

        configured_path = str(settings.get("path", "codex") or "codex")
        resolved = self._resolve_codex_binary(configured_path)
        if not resolved:
            summary = f"Codex 없음: {configured_path}"
            self._set_codex_status_text(summary, level="error")
            if show_dialog:
                show_warning(
                    self,
                    "Codex 실행 파일 없음",
                    "Codex CLI를 찾지 못했습니다.\n"
                    "설정값을 확인하세요.\n"
                    f"- 입력 경로: {configured_path}",
                )
            return {
                "available": False,
                "login_ok": False,
                "computer_use_ok": False,
                "version": "",
                "resolved_path": "",
            }

        def run_cli(args: List[str], timeout_sec: float = 6.0) -> str:
            try:
                completed = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                    cwd=os.path.expanduser("~"),
                )
                return (completed.stdout or completed.stderr or "").strip()
            except Exception as exc:
                return f"ERROR: {exc}"

        version_text = run_cli([resolved, "--version"], timeout_sec=6.0)
        login_text = run_cli([resolved, "login", "status"], timeout_sec=8.0)
        mcp_text = run_cli([resolved, "mcp", "list"], timeout_sec=8.0)

        login_ok = "logged in" in login_text.lower()
        computer_use_ok = self._has_enabled_computer_use_mcp(mcp_text)

        status_bits = [f"v={version_text or 'unknown'}"]
        status_bits.append("로그인됨" if login_ok else "로그인 필요")
        status_bits.append("computer-use 준비됨" if computer_use_ok else "computer-use 미감지")
        summary = "Codex " + " · ".join(status_bits)
        level = "ok" if (login_ok and computer_use_ok) else ("warn" if login_ok else "error")
        self._set_codex_status_text(summary, level=level)

        if show_dialog:
            body = (
                f"실행 파일: {resolved}\n"
                f"버전: {version_text or '확인 실패'}\n"
                f"로그인: {login_text or '확인 실패'}\n"
                f"computer-use: {'enabled' if computer_use_ok else 'not found/disabled'}"
            )
            if login_ok and computer_use_ok:
                show_info(self, "Codex 상태 정상", body)
            else:
                show_warning(self, "Codex 상태 점검 필요", body)

        return {
            "available": True,
            "login_ok": login_ok,
            "computer_use_ok": computer_use_ok,
            "version": version_text,
            "resolved_path": resolved,
        }

    def _get_active_setup_step_id(self) -> str:
        """Get current step id in setup assistant."""
        if self._setup_running and 0 <= self._setup_step_index < len(self._setup_steps):
            return self._setup_steps[self._setup_step_index]
        return ""

    def _build_codex_prompt_for_current_step(self) -> str:
        """Build one step-scoped handoff prompt for Codex computer-use."""
        step_id = self._get_active_setup_step_id()
        step_meta = self.SETUP_STEP_DEFS.get(step_id, {})
        step_title = step_meta.get("title", "수동 설정 지원")
        scope = str(self._setup_scope or "all")

        focus_map = {
            "youtube": "YouTube OAuth 연결",
            "tiktok": "TikTok OAuth 연결",
            "instagram": "Instagram 계정 연결",
            "threads": "Threads 계정 연결",
            "linktree": "Linktree 프로필 설정",
            "precheck": "Gemini API 키 확인",
        }
        focus_key = "general"
        for candidate in ("youtube", "tiktok", "instagram", "threads", "linktree", "precheck"):
            if step_id.startswith(candidate):
                focus_key = candidate
                break

        focus_text = focus_map.get(focus_key, "소셜 자동설정")
        suggested_pages = {
            "youtube": "https://console.cloud.google.com/ , https://www.youtube.com/",
            "tiktok": "https://developers.tiktok.com/ , https://www.tiktok.com/login",
            "instagram": "https://www.instagram.com/accounts/login/ , https://developers.facebook.com/apps/",
            "threads": "https://www.threads.com/login , https://developers.facebook.com/apps/",
            "linktree": "https://linktr.ee/admin/links",
            "precheck": "https://aistudio.google.com/app/apikey",
            "general": "https://aistudio.google.com/app/apikey , https://www.youtube.com/ , https://developers.tiktok.com/ , https://linktr.ee/admin/links",
        }
        pages = suggested_pages.get(focus_key, suggested_pages["general"])
        if os.name == "nt":
            host_os = "Windows"
        elif sys.platform == "darwin":
            host_os = "macOS"
        else:
            host_os = "Linux"

        return (
            f"You are helping configure NewshoppingShorts on {host_os} using computer-use.\n"
            f"Current setup scope: {scope}\n"
            f"Current step: {step_title} ({step_id or 'manual'})\n"
            f"Primary focus: {focus_text}\n\n"
            "Rules:\n"
            "1) You handle all navigation, page transitions, form fill, and non-sensitive clicks.\n"
            "2) Ask the human only for login, 2FA, CAPTCHA, legal consent, API-key issuance, or payment decisions.\n"
            "3) After human-only actions complete, continue automatically from the current page.\n"
            "4) If you obtain callback URL/code/API key/profile URL, tell the user to copy it. This app auto-reads clipboard.\n"
            "5) Never perform destructive or irreversible actions.\n\n"
            f"Start by opening relevant pages: {pages}\n"
            "Then proceed step-by-step until this current step is done."
        )

    def _submit_computer_use_bridge_job(self, bridge_url: str, api_key: str, prompt: str) -> Dict[str, Any]:
        """Submit one computer-use job to a remote bridge server."""
        user_id = self._extract_logged_in_user_id()
        login_token = self._extract_logged_in_token()
        if not login_token:
            raise ValueError("로그인 토큰이 없어 브리지 요청을 보낼 수 없습니다.")
        step_id = self._get_active_setup_step_id()
        payload = {
            "user_id": user_id,
            "scope": str(self._setup_scope or "all"),
            "step_id": step_id,
            "step_title": self.SETUP_STEP_DEFS.get(step_id, {}).get("title", ""),
            "prompt": prompt,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {login_token}",
        }
        token = str(api_key or "").strip()
        if token:
            headers["X-Bridge-API-Key"] = token

        base = str(bridge_url or "").strip().rstrip("/")
        url = f"{base}/v1/computer-use/jobs"
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        try:
            body = response.json()
        except Exception:
            body = {"raw": response.text[:500]}

        return {
            "ok": 200 <= response.status_code < 300,
            "status_code": response.status_code,
            "body": body,
            "url": url,
        }

    @staticmethod
    def _escape_for_applescript(raw_text: str) -> str:
        """Escape shell command text for AppleScript string literal."""
        return str(raw_text or "").replace("\\", "\\\\").replace("\"", "\\\"")

    def _launch_codex_terminal_process(self, args: List[str], workspace: str) -> None:
        """
        Launch Codex in a new terminal window according to host OS.

        - Windows: new cmd console (/k keeps session open)
        - macOS: Terminal via AppleScript
        - Linux/other: best-effort x-terminal-emulator fallback
        """
        if os.name == "nt":
            windows_cmd = subprocess.list2cmdline(args)
            creation_flags = int(getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
            subprocess.Popen(
                ["cmd.exe", "/k", windows_cmd],
                cwd=workspace,
                creationflags=creation_flags,
            )
            return

        posix_cmd = " ".join(shlex.quote(part) for part in args)
        if sys.platform == "darwin":
            apple_script_lines = [
                'tell application "Terminal"',
                "activate",
                f'do script "{self._escape_for_applescript(posix_cmd)}"',
                "end tell",
            ]
            osa_args: List[str] = []
            for line in apple_script_lines:
                osa_args.extend(["-e", line])
            subprocess.run(["osascript", *osa_args], check=True, timeout=8)
            return

        subprocess.Popen(
            ["x-terminal-emulator", "-e", "bash", "-lc", posix_cmd],
            cwd=workspace,
        )

    def _build_computer_use_prompt_for_target(self, target: str) -> str:
        """Build a Computer Use handoff prompt scoped to a single integration."""
        if os.name == "nt":
            host_os = "Windows"
        elif sys.platform == "darwin":
            host_os = "macOS"
        else:
            host_os = "Linux"

        focus_map = {
            "linktree": (
                "Linktree 계정 로그인 및 공개 프로필 설정",
                "https://linktr.ee/login , https://linktr.ee/admin",
            ),
            "coupang": (
                "쿠팡 파트너스 Access Key / Secret Key 발급",
                "https://partners.coupang.com/",
            ),
            "webhook": (
                "Make(Integromat)/Zapier/n8n에서 Linktree 자동 발행용 Webhook 시나리오 생성 및 Webhook URL 획득",
                "https://www.make.com/ , https://zapier.com/app/zaps",
            ),
            "youtube": (
                "Google Cloud OAuth 클라이언트 발급(client_secrets.json) 및 YouTube 채널 연결",
                "https://console.cloud.google.com/apis/credentials , https://www.youtube.com/",
            ),
        }
        focus_text, pages = focus_map.get(
            target, ("초기 설정", "https://aistudio.google.com/app/apikey")
        )
        return (
            f"You are helping configure NewshoppingShorts on {host_os} using computer-use.\n"
            f"Primary focus: {focus_text}\n\n"
            "Rules:\n"
            "1) You handle navigation, page transitions, form fill, and non-sensitive clicks.\n"
            "2) Ask the human only for login, 2FA, CAPTCHA, legal consent, API-key issuance, or payment.\n"
            "3) After human-only actions complete, continue automatically from the current page.\n"
            "4) If you obtain a key/URL/code, tell the user to copy it. This app auto-reads the clipboard.\n"
            "5) Never perform destructive or irreversible actions.\n\n"
            f"Start by opening relevant pages: {pages}\n"
            "Then proceed step-by-step until this setup is complete."
        )

    def _run_computer_use_prompt(self, prompt: str, label: str) -> None:
        """Shared Computer Use runner: paid gate → bridge or local Codex CLI.

        Used by the per-integration '자동으로 설정' buttons. Mirrors the gating of
        _launch_codex_for_current_step but with a caller-supplied prompt/label."""
        from ui.components.custom_dialog import show_info, show_warning, show_error

        if not self._is_paid_user_for_computer_use(force_refresh=True):
            show_warning(
                self,
                "유료 기능",
                "Computer Use 자동 설정은 유료 사용자 전용입니다.\n"
                "무료 사용자는 같은 카드의 수동 설정(붙여넣기) 흐름을 사용해주세요.",
            )
            return

        try:
            cu_settings = get_settings_manager().get_computer_use_settings()
        except Exception:
            cu_settings = {"bridge_enabled": False, "bridge_url": "", "bridge_api_key": ""}

        bridge_enabled = bool(cu_settings.get("bridge_enabled", False))
        bridge_url = str(cu_settings.get("bridge_url", "") or "").strip()
        bridge_api_key = str(cu_settings.get("bridge_api_key", "") or "").strip()
        if bridge_enabled and bridge_url:
            try:
                result = self._submit_computer_use_bridge_job(bridge_url, bridge_api_key, prompt)
            except Exception as exc:
                show_error(self, "브리지 요청 실패", f"서버 브리지 호출 중 오류가 발생했습니다.\n{exc}")
                return
            if not result.get("ok"):
                show_error(
                    self,
                    "브리지 요청 실패",
                    f"HTTP {result.get('status_code')} 응답입니다.\n"
                    f"URL: {result.get('url')}\n응답: {result.get('body')}",
                )
                return
            body = result.get("body") or {}
            job_id = str(body.get("job_id", "") or body.get("id", "") or "").strip()
            self._append_setup_log(f"Computer Use 브리지 작업 요청 완료({label}): {job_id or 'no-id'}")
            show_info(self, "브리지 작업 접수", f"서버 Computer Use 작업이 접수되었습니다.\njob_id: {job_id or '-'}")
            return

        status = self._refresh_codex_cli_status(show_dialog=False)
        if not status.get("available"):
            show_warning(self, "Codex 실행 불가", "Codex CLI 실행 파일을 찾지 못했습니다. 경로를 확인하세요.")
            return
        if not status.get("login_ok"):
            show_warning(
                self,
                "Codex 로그인 필요",
                "Codex CLI가 로그인되지 않았습니다.\n터미널에서 `codex login` 후 다시 시도하세요.",
            )
            return
        if not status.get("computer_use_ok"):
            show_warning(
                self,
                "computer-use 미준비",
                "Codex CLI에서 computer-use MCP가 활성화되지 않았습니다.\n`codex mcp list` 결과를 확인하세요.",
            )
            return

        try:
            cli_settings = get_settings_manager().get_codex_cli_settings()
        except Exception:
            cli_settings = {"path": "codex", "model": ""}

        codex_path = str(status.get("resolved_path", "") or "").strip()
        model_name = str(cli_settings.get("model", "") or "").strip()
        workspace = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

        args = [codex_path, "--cd", workspace]
        if model_name:
            args.extend(["--model", model_name])
        args.append(prompt)

        try:
            self._launch_codex_terminal_process(args=args, workspace=workspace)
            self._append_setup_log(f"Codex Computer Use 실행: {label}")
            show_info(
                self,
                "Codex 실행 완료",
                "새 터미널에서 Codex가 시작되었습니다.\n"
                "로그인/2FA/CAPTCHA/API 키 발급만 직접 처리하고, 나머지는 Codex가 진행하도록 맡기세요.",
            )
        except Exception as exc:
            show_error(self, "Codex 실행 실패", f"터미널 실행 중 오류가 발생했습니다.\n{exc}")

    def _launch_codex_for_current_step(self):
        """Open a new terminal and start Codex with a step-scoped computer-use prompt."""
        from ui.components.custom_dialog import show_info, show_warning, show_error

        if not self._is_paid_user_for_computer_use(force_refresh=True):
            show_warning(
                self,
                "유료 기능",
                "Computer Use 자동화는 유료 사용자 전용입니다.\n"
                "무료 사용자는 기존 수동 설정 흐름을 사용해주세요.",
            )
            return

        try:
            cu_settings = get_settings_manager().get_computer_use_settings()
        except Exception:
            cu_settings = {"bridge_enabled": False, "bridge_url": "", "bridge_api_key": ""}

        prompt = self._build_codex_prompt_for_current_step()

        bridge_enabled = bool(cu_settings.get("bridge_enabled", False))
        bridge_url = str(cu_settings.get("bridge_url", "") or "").strip()
        bridge_api_key = str(cu_settings.get("bridge_api_key", "") or "").strip()
        if bridge_enabled and bridge_url:
            try:
                result = self._submit_computer_use_bridge_job(bridge_url, bridge_api_key, prompt)
            except Exception as exc:
                show_error(self, "브리지 요청 실패", f"서버 브리지 호출 중 오류가 발생했습니다.\n{exc}")
                return

            if not result.get("ok"):
                show_error(
                    self,
                    "브리지 요청 실패",
                    f"HTTP {result.get('status_code')} 응답입니다.\n"
                    f"URL: {result.get('url')}\n"
                    f"응답: {result.get('body')}",
                )
                return

            body = result.get("body") or {}
            job_id = str(body.get("job_id", "") or body.get("id", "") or "").strip()
            self._append_setup_log(f"Computer Use 브리지 작업 요청 완료: {job_id or 'no-id'}")
            show_info(
                self,
                "브리지 작업 접수",
                "서버 공용 Computer Use 작업이 접수되었습니다.\n"
                f"job_id: {job_id or '-'}",
            )
            return

        status = self._refresh_codex_cli_status(show_dialog=False)
        if not status.get("available"):
            show_warning(self, "Codex 실행 불가", "Codex CLI 실행 파일을 찾지 못했습니다. 경로를 확인하세요.")
            return
        if not status.get("login_ok"):
            show_warning(
                self,
                "Codex 로그인 필요",
                "Codex CLI가 로그인되지 않았습니다.\n터미널에서 `codex login` 후 다시 시도하세요.",
            )
            return
        if not status.get("computer_use_ok"):
            show_warning(
                self,
                "computer-use 미준비",
                "Codex CLI에서 computer-use MCP가 활성화되지 않았습니다.\n`codex mcp list` 결과를 확인하세요.",
            )
            return

        try:
            cli_settings = get_settings_manager().get_codex_cli_settings()
        except Exception:
            cli_settings = {"path": "codex", "model": ""}

        codex_path = str(status.get("resolved_path", "") or "").strip()
        model_name = str(cli_settings.get("model", "") or "").strip()
        workspace = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

        args = [codex_path, "--cd", workspace]
        if model_name:
            args.extend(["--model", model_name])
        args.append(prompt)

        try:
            self._launch_codex_terminal_process(args=args, workspace=workspace)
            step_id = self._get_active_setup_step_id()
            step_title = self.SETUP_STEP_DEFS.get(step_id, {}).get("title", "수동 설정 지원")
            self._append_setup_log(f"Codex Computer Use 실행: {step_title}")
            show_info(
                self,
                "Codex 실행 완료",
                "새 터미널에서 Codex가 시작되었습니다.\n"
                "로그인/2FA/CAPTCHA/API 키 발급만 직접 처리하고, 나머지는 Codex가 진행하도록 맡기세요.",
            )
        except Exception as exc:
            show_error(self, "Codex 실행 실패", f"터미널 실행 중 오류가 발생했습니다.\n{exc}")

    def _on_setup_done_clicked(self):
        """Handle '완료했어요' click for waiting-user steps."""
        from ui.components.custom_dialog import show_warning

        if not self._setup_running or not self._setup_waiting_user:
            return
        if self._setup_step_index < 0 or self._setup_step_index >= len(self._setup_steps):
            return
        step_id = self._setup_steps[self._setup_step_index]
        rerun_current_step = False

        if step_id == "precheck":
            if self._get_saved_gemini_key_count() <= 0:
                show_warning(self, "API 키 필요", "Gemini API 키를 최소 1개 저장한 뒤 다시 눌러주세요.")
                return
        elif step_id in ("youtube_user_auth", "youtube_verify"):
            if not self._is_youtube_connected():
                show_warning(self, "YouTube 미연결", "아직 YouTube 연결이 확인되지 않았습니다. OAuth 인증을 완료해주세요.")
                return
            rerun_current_step = step_id == "youtube_verify"
        elif step_id == "tiktok_prepare":
            rerun_current_step = True
        elif step_id == "tiktok_user_auth":
            raw_code = self.setup_tiktok_code_input.text() if hasattr(self, "setup_tiktok_code_input") else ""
            if not self._extract_oauth_code(raw_code):
                show_warning(self, "TikTok code 필요", "TikTok 인증 후 callback URL의 code 값을 입력해주세요.")
                return
        elif step_id == "tiktok_code_exchange":
            raw_code = self.setup_tiktok_code_input.text() if hasattr(self, "setup_tiktok_code_input") else ""
            auth_code = self._extract_oauth_code(raw_code)
            if not auth_code:
                show_warning(self, "TikTok code 필요", "TikTok 인증 후 callback URL의 code 값을 입력해주세요.")
                return
            self.setup_tiktok_code_input.setText(auth_code)
            rerun_current_step = True
        elif step_id == "tiktok_verify":
            if not self._is_tiktok_connected():
                show_warning(self, "TikTok 미연결", "아직 TikTok 연결이 확인되지 않았습니다. code 교환을 완료해주세요.")
                return
            rerun_current_step = True
        elif step_id in ("instagram_user_setup", "instagram_verify"):
            handle = self._normalize_social_account_input(
                self.setup_instagram_handle_input.text() if hasattr(self, "setup_instagram_handle_input") else ""
            )
            if not handle:
                show_warning(self, "Instagram 계정 확인", "Instagram 계정명(또는 프로필 URL)을 입력해주세요.")
                return
            self.setup_instagram_handle_input.setText(handle)
            rerun_current_step = step_id == "instagram_verify"
        elif step_id in ("threads_user_setup", "threads_verify"):
            handle = self._normalize_social_account_input(
                self.setup_threads_handle_input.text() if hasattr(self, "setup_threads_handle_input") else ""
            )
            if not handle:
                show_warning(self, "Threads 계정 확인", "Threads 계정명(또는 프로필 URL)을 입력해주세요.")
                return
            self.setup_threads_handle_input.setText(handle)
            rerun_current_step = step_id == "threads_verify"
        elif step_id == "linktree_user_setup":
            profile_url = self._normalize_http_url(self.linktree_profile_input.text())
            if not self._is_valid_http_url(profile_url):
                show_warning(self, "Linktree 주소 확인", "올바른 Linktree 공개 주소를 입력해주세요.")
                return
            self.linktree_profile_input.setText(profile_url)
        elif step_id == "linktree_save_verify":
            profile_url = self._normalize_http_url(self.linktree_profile_input.text())
            if not self._is_valid_http_url(profile_url):
                show_warning(self, "Linktree 주소 확인", "올바른 Linktree 공개 주소를 입력해주세요.")
                return
            self.linktree_profile_input.setText(profile_url)
            rerun_current_step = True
        elif step_id == "final_verify":
            rerun_current_step = True

        self._setup_waiting_user = False
        if rerun_current_step:
            self._append_setup_log(f"사용자 확인 완료: {self.SETUP_STEP_DEFS[step_id]['title']} (재검증)")
            self._run_setup_step()
            return

        self._set_setup_row_state(step_id, "done")
        self._append_setup_log(f"사용자 단계 완료 확인: {self.SETUP_STEP_DEFS[step_id]['title']}")
        self._advance_setup_step()

    def _on_setup_retry_clicked(self):
        """Retry current setup step."""
        if not self._setup_running:
            return
        self._append_setup_log("현재 단계를 재검증합니다.")
        self._run_setup_step()
    
    def _load_link_automation_settings(self):
        """Load Coupang/Linktree automation settings into UI controls."""
        try:
            settings = get_settings_manager()
            coupang = settings.get_coupang_keys()
            linktree = settings.get_linktree_settings()

            self.coupang_access_input.setText(coupang.get("access_key", ""))
            self.coupang_secret_input.setText(coupang.get("secret_key", ""))
            self.linktree_webhook_input.setText(linktree.get("webhook_url", ""))
            self.linktree_api_key_input.setText(linktree.get("api_key", ""))
            self.linktree_profile_input.setText(linktree.get("profile_url", ""))
            self.linktree_account_email_input.setText(linktree.get("account_email", ""))
            self.linktree_expected_email_input.setText(linktree.get("expected_account_email", ""))
            self.linktree_auto_checkbox.setChecked(bool(linktree.get("auto_publish", False)))

            if hasattr(self, "setup_instagram_handle_input"):
                saved_instagram = settings.get_social_account_name("instagram")
                if saved_instagram and not self.setup_instagram_handle_input.text().strip():
                    self.setup_instagram_handle_input.setText(saved_instagram)
            if hasattr(self, "setup_threads_handle_input"):
                saved_threads = settings.get_social_account_name("threads")
                if saved_threads and not self.setup_threads_handle_input.text().strip():
                    self.setup_threads_handle_input.setText(saved_threads)

            has_advanced_settings = any([
                coupang.get("access_key"),
                coupang.get("secret_key"),
                linktree.get("webhook_url"),
                linktree.get("api_key"),
                linktree.get("account_email"),
                linktree.get("expected_account_email"),
                linktree.get("auto_publish", False),
            ])
            self._set_link_advanced_visible(has_advanced_settings)
            self._update_link_automation_status()
            self._refresh_setup_assistant_status()
        except Exception as exc:
            logger.warning("[Settings] Failed to load link automation settings: %s", exc)

    def _set_link_advanced_visible(self, visible: bool):
        """Show or hide optional Coupang/Webhook fields."""
        if hasattr(self, "link_advanced_container"):
            self.link_advanced_container.setVisible(bool(visible))

        if hasattr(self, "link_advanced_toggle") and self.link_advanced_toggle.isChecked() != bool(visible):
            self.link_advanced_toggle.blockSignals(True)
            self.link_advanced_toggle.setChecked(bool(visible))
            self.link_advanced_toggle.blockSignals(False)

    def _update_link_automation_status(self):
        """Refresh status label for Coupang/Linktree setup."""
        coupang_ready = bool(self.coupang_access_input.text().strip() and self.coupang_secret_input.text().strip())
        linktree_profile_ready = bool(self.linktree_profile_input.text().strip())
        linktree_auto_ready = bool(self.linktree_webhook_input.text().strip())
        auto_enabled = bool(self.linktree_auto_checkbox.isChecked())
        expected_email = (
            self.linktree_expected_email_input.text().strip()
            if hasattr(self, "linktree_expected_email_input")
            else ""
        )
        account_email = (
            self.linktree_account_email_input.text().strip()
            if hasattr(self, "linktree_account_email_input")
            else ""
        )

        status_parts = ["공개 주소 저장됨" if linktree_profile_ready else "공개 주소 미설정"]
        if expected_email:
            status_parts.append("계정 확인 완료" if account_email.lower() == expected_email.lower() else "Linktree 계정 확인 필요")
        if coupang_ready:
            status_parts.append("쿠팡 자동 딥링크 준비")
        if auto_enabled:
            status_parts.append("Linktree 자동 발행 준비" if linktree_auto_ready else "자동 발행은 Webhook 필요")
        elif linktree_auto_ready:
            status_parts.append("Webhook 저장됨")

        self.link_automation_status.setText("상태: " + " · ".join(status_parts))
        if hasattr(self, "setup_chip_gemini"):
            self._refresh_setup_assistant_status()

    def _open_external_url(self, url: str):
        """Open a setup URL in the user's default browser."""
        QDesktopServices.openUrl(QUrl(url))

    def _open_linktree_signup(self):
        self._open_external_url(LINKTREE_SIGNUP_URL)

    def _open_linktree_admin(self):
        self._open_external_url(LINKTREE_ADMIN_URL)

    def _open_linktree_profile(self):
        from ui.components.custom_dialog import show_warning

        profile_url = self.linktree_profile_input.text().strip()
        if not profile_url:
            show_warning(
                self,
                "Linktree Profile 필요",
                "먼저 Linktree 공개 주소를 입력해 주세요.\n예: https://linktr.ee/myshop",
            )
            return
        if not profile_url.lower().startswith(("http://", "https://")):
            profile_url = "https://" + profile_url
        self._open_external_url(profile_url)

    def _save_coupang_settings(self):
        """Persist Coupang API keys."""
        from ui.components.custom_dialog import show_info, show_warning, show_error

        access_key = self.coupang_access_input.text().strip()
        secret_key = self.coupang_secret_input.text().strip()
        if not access_key or not secret_key:
            show_warning(
                self,
                "입력 확인",
                "쿠팡 API Key는 필수 항목이 아닙니다.\n"
                "원본 coupang.com 링크를 자동으로 파트너스 딥링크로 바꾸고 싶을 때만 "
                "Coupang Access Key와 Secret Key를 모두 입력해 주세요.",
            )
            return

        try:
            saved = get_settings_manager().set_coupang_keys(access_key, secret_key)
            if not saved:
                show_error(self, "저장 실패", "쿠팡 API 키를 저장하지 못했습니다.")
                return
            self._update_link_automation_status()
            self._refresh_setup_assistant_status()
            show_info(self, "저장 완료", "쿠팡 API 키를 저장했습니다.")
        except Exception as exc:
            logger.error("[Settings] Failed to save Coupang settings: %s", exc)
            show_error(self, "저장 실패", f"쿠팡 설정 저장 중 오류가 발생했습니다.\n{exc}")

    def _test_coupang_connection(self):
        """Validate Coupang API keys by requesting one test deep link."""
        from ui.components.custom_dialog import show_info, show_warning, show_error

        access_key = self.coupang_access_input.text().strip()
        secret_key = self.coupang_secret_input.text().strip()
        if not access_key or not secret_key:
            show_warning(self, "입력 확인", "자동 딥링크 기능을 테스트하려면 쿠팡 API 키 2개를 모두 입력하세요.")
            return

        # Save latest input before running test.
        get_settings_manager().set_coupang_keys(access_key, secret_key)
        self._update_link_automation_status()
        self._refresh_setup_assistant_status()

        try:
            manager = getattr(self.gui, "coupang_manager", None) if self.gui else None
            if manager is None:
                manager = get_coupang_manager()

            if manager.check_connection():
                show_info(self, "연결 성공", "쿠팡 딥링크 생성 테스트가 성공했습니다.")
            else:
                show_warning(self, "연결 실패", "쿠팡 딥링크 생성 테스트가 실패했습니다. 키 권한/값을 확인하세요.")
        except Exception as exc:
            logger.error("[Settings] Coupang connection test failed: %s", exc)
            show_error(self, "연결 테스트 실패", f"쿠팡 연결 테스트 중 오류가 발생했습니다.\n{exc}")

    def _open_linktree_setup_guide(self):
        """Open the step-by-step Linktree webhook setup dialog."""
        try:
            from ui.components.linktree_setup_dialog import LinktreeSetupDialog

            dialog = LinktreeSetupDialog(self, on_saved=self._load_link_automation_settings)
            dialog.exec()
        except Exception as exc:
            logger.warning("[Settings] Linktree setup guide failed: %s", exc)
        # 저장 여부와 무관하게 화면을 최신 상태로 갱신한다.
        try:
            self._load_link_automation_settings()
        except Exception:
            pass

    def _save_linktree_settings(self):
        """Persist Linktree webhook/API-key settings."""
        from ui.components.custom_dialog import show_info, show_warning, show_error

        webhook_url = self.linktree_webhook_input.text().strip()
        api_key = self.linktree_api_key_input.text().strip()
        profile_url = self.linktree_profile_input.text().strip()
        account_email = self.linktree_account_email_input.text().strip()
        expected_email = self.linktree_expected_email_input.text().strip()
        auto_publish = self.linktree_auto_checkbox.isChecked()

        if webhook_url and not webhook_url.lower().startswith(("http://", "https://")):
            show_warning(self, "입력 확인", "Webhook URL은 http:// 또는 https:// 형식이어야 합니다.")
            return

        if profile_url and not profile_url.lower().startswith(("http://", "https://")):
            show_warning(self, "입력 확인", "Linktree Profile URL은 http:// 또는 https:// 형식이어야 합니다.")
            return

        for label, email in (("Linktree 계정 이메일", account_email), ("기대 계정 이메일", expected_email)):
            if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                show_warning(self, "이메일 형식 확인", f"{label} 형식을 확인해주세요.")
                return

        if auto_publish and not webhook_url:
            show_warning(
                self,
                "Webhook 필요",
                "Linktree 자동 업로드를 켜려면 Webhook URL이 필요합니다.\n"
                "처음이라면 자동 업로드 체크를 끄고 Profile URL만 먼저 저장해도 됩니다.",
            )
            return

        try:
            saved = get_settings_manager().set_linktree_settings(
                webhook_url=webhook_url,
                api_key=api_key,
                profile_url=profile_url,
                auto_publish=auto_publish,
                account_email=account_email,
                expected_account_email=expected_email,
            )
            if not saved:
                show_error(self, "저장 실패", "링크트리 설정을 저장하지 못했습니다.")
                return
            self._update_link_automation_status()
            self._refresh_setup_assistant_status()
            show_info(self, "저장 완료", "링크트리 설정을 저장했습니다.")
        except Exception as exc:
            logger.error("[Settings] Failed to save Linktree settings: %s", exc)
            show_error(self, "저장 실패", f"링크트리 설정 저장 중 오류가 발생했습니다.\n{exc}")

    def _test_linktree_publish(self):
        """Send test payload via configured Linktree webhook integration."""
        from ui.components.custom_dialog import show_info, show_warning, show_error

        webhook_url = self.linktree_webhook_input.text().strip()
        if not webhook_url:
            show_warning(
                self,
                "Webhook 필요",
                "테스트 업로드는 Webhook URL이 있어야 보낼 수 있습니다.\n"
                "처음 사용자는 위의 'Linktree 가입/로그인'과 '관리자 열기'로 수동 카드 추가부터 확인하세요.",
            )
            return

        # Save latest input before running test.
        get_settings_manager().set_linktree_settings(
            webhook_url=webhook_url,
            api_key=self.linktree_api_key_input.text().strip(),
            profile_url=self.linktree_profile_input.text().strip(),
            auto_publish=self.linktree_auto_checkbox.isChecked(),
            account_email=self.linktree_account_email_input.text().strip(),
            expected_account_email=self.linktree_expected_email_input.text().strip(),
        )
        self._update_link_automation_status()
        self._refresh_setup_assistant_status()

        try:
            manager = getattr(self.gui, "linktree_manager", None) if self.gui else None
            if manager is None:
                manager = get_linktree_manager()

            if manager.test_connection():
                show_info(self, "테스트 성공", "Linktree 테스트 업로드 요청을 전송했습니다.")
            else:
                show_warning(self, "테스트 실패", "테스트 업로드에 실패했습니다. Webhook URL/API Key를 확인하세요.")
        except Exception as exc:
            logger.error("[Settings] Linktree test publish failed: %s", exc)
            show_error(self, "테스트 실패", f"링크트리 테스트 업로드 중 오류가 발생했습니다.\n{exc}")

    @staticmethod
    def _resolve_creator_level(used_count: int):
        """Return gamified community level and next target."""
        levels = [
            (0, "새싹 메이커", 5),
            (5, "꾸준한 크리에이터", 20),
            (20, "쇼츠 장인", 50),
            (50, "커뮤니티 리더", 100),
            (100, "레전드 빌더", None),
        ]
        current = levels[0]
        for level in levels:
            if used_count >= level[0]:
                current = level
            else:
                break
        return current[1], current[2]

    def _apply_work_community_ui(self, used_count: int | None, message: str | None = None):
        """Render work count/community labels."""
        if used_count is None:
            self.work_community_count.setText("-")
            self.work_community_level.setText("레벨: 확인 필요")
            self.work_community_next.setText(message or "로그인 후 작업량을 확인할 수 있어요.")
            return

        safe_used = max(int(used_count), 0)
        level_name, next_target = self._resolve_creator_level(safe_used)
        self.work_community_count.setText(f"{safe_used}회 생성")
        self.work_community_level.setText(f"레벨: {level_name}")

        if next_target is None:
            self.work_community_next.setText("이미 상위권입니다. 계속 기록을 쌓아보세요.")
            return

        remaining = max(next_target - safe_used, 0)
        if remaining == 0:
            self.work_community_next.setText("새 레벨 달성! 다음 목표를 확인해보세요.")
        else:
            self.work_community_next.setText(f"다음 레벨까지 {remaining}회")

    def refresh_work_community_stats(self, used_count: int | None = None):
        """Refresh cumulative work stats shown in Settings community card."""
        if used_count is not None:
            self._apply_work_community_ui(used_count)
            return

        if not self.gui:
            self._apply_work_community_ui(None, "앱 정보가 없어 작업량을 불러올 수 없습니다.")
            return

        from utils.auth_helpers import extract_user_id
        user_id = extract_user_id(getattr(self.gui, "login_data", None))
        if not user_id:
            self._apply_work_community_ui(None, "로그인 후 작업량을 확인할 수 있어요.")
            return

        try:
            from caller import rest
            info = rest.check_work_available(str(user_id))
            used = info.get("used", 0)
            if isinstance(used, int):
                self._apply_work_community_ui(used)
            else:
                self._apply_work_community_ui(None, "작업량 응답을 해석하지 못했습니다.")
        except Exception:
            self._apply_work_community_ui(None, "작업량 조회 중 오류가 발생했습니다.")

    def _show_api_status(self):
        """Show API status dialog"""
        if self.gui and hasattr(self.gui, 'show_api_status'):
            self.gui.show_api_status()

    def _toggle_key_visibility(self, input_field: QLineEdit):
        """API 키 보기/숨기기 토글"""
        if input_field.echoMode() == QLineEdit.EchoMode.Password:
            input_field.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            input_field.setEchoMode(QLineEdit.EchoMode.Password)

    def _load_saved_api_keys(self):
        """저장된 API 키들을 로드하여 입력 필드에 표시"""
        try:
            for key_input in self.api_key_inputs:
                key_input.clear()
            for i in range(1, 9):
                key_value = SecretsManager.get_api_key(f"gemini_api_{i}")
                if i == 1 and not key_value:
                    # 하위 호환: 과거 단일 키 저장 포맷
                    legacy_value = SecretsManager.get_api_key("gemini")
                    if legacy_value and legacy_value.strip():
                        key_value = legacy_value.strip()
                        try:
                            SecretsManager.store_api_key("gemini_api_1", key_value)
                        except Exception:
                            pass
                if key_value and i <= len(self.api_key_inputs):
                    self.api_key_inputs[i - 1].setText(key_value.strip())
            self._update_key_count()
            self._refresh_setup_assistant_status()
        except Exception as e:
            from utils.logging_config import get_logger
            logger = get_logger(__name__)
            logger.warning(f"[Settings] API 키 로드 실패: {e}")

    def _update_key_count(self):
        """저장된 키 개수 업데이트 (SecretsManager 기준)."""
        try:
            count = 0
            for i in range(1, 9):
                key_value = SecretsManager.get_api_key(f"gemini_api_{i}")
                if key_value and str(key_value).strip():
                    count += 1
            if count == 0:
                legacy_value = SecretsManager.get_api_key("gemini")
                if legacy_value and str(legacy_value).strip():
                    count = 1
            self.api_count_label.setText(f"저장된 키: {count}개")
        except Exception:
            # Fallback: UI 입력값 기준 (예외 상황에서만)
            count = sum(1 for inp in self.api_key_inputs if inp.text().strip())
            self.api_count_label.setText(f"저장된 키: {count}개")

    def _save_all_api_keys(self):
        """모든 API 키 저장 (빈칸 제거 및 당겨서 저장)"""
        from ui.components.custom_dialog import show_info, show_warning, show_error

        # 1. 유효한 키 수집 (빈칸 제거)
        valid_keys = []
        invalid_format_keys = []
        restricted_aq_keys = []  # 'AQ.' 제한 토큰 (Gemini API에서 작동하지 않음)

        # 현재 입력된 모든 텍스트 확인
        for i, key_input in enumerate(self.api_key_inputs):
            key_value = key_input.text().strip()
            if not key_value:
                continue

            # 키 형식 검증
            if not GEMINI_API_KEY_PATTERN.match(key_value):
                # 'AQ.' 토큰은 계정 제한 시 발급되는 키로 Gemini API에서 401로 거부됨
                if key_value.startswith("AQ."):
                    restricted_aq_keys.append(i + 1)
                else:
                    invalid_format_keys.append(i + 1)
                # 형식이 잘못돼도 일단 수집하지 않음 (저장하지 않음)
                continue

            valid_keys.append(key_value)

        # 'AQ.' 제한 토큰이 있으면 별도 안내 후 중단
        if restricted_aq_keys:
            show_warning(
                self,
                "사용할 수 없는 'AQ.' 키",
                f"다음 위치의 키는 'AQ.'로 시작하는 제한된 토큰입니다: {restricted_aq_keys}\n\n"
                "이 토큰은 계정이 제한됐을 때(주로 이전 키가 외부에 노출된 경우) 발급되며,\n"
                "Gemini API에서는 작동하지 않습니다(401 오류).\n\n"
                "Google AI Studio(aistudio.google.com/apikey)에서 'AIza...'로 시작하는\n"
                "표준 키를 새로 발급받아 입력해주세요. (필요 시 새 프로젝트에서 생성)"
            )
            return

        # 형식이 잘못된 키가 있으면 경고하고 중단
        if invalid_format_keys:
            show_warning(
                self,
                "형식이 올바르지 않은 키",
                f"다음 위치의 키 형식이 올바르지 않습니다: {invalid_format_keys}\n\n"
                "Gemini API 키는 'AIza'로 시작해야 합니다.\n"
                "해당 키를 수정하거나 지운 후 다시 저장해주세요."
            )
            return

        # 2. 저장 및 미사용 슬롯 삭제
        saved_count = 0
        failed_save = []
        failed_verify = []
        new_keys_dict = {}
        
        try:
            # 2-1. 유효한 키 순서대로 저장
            for i, key_value in enumerate(valid_keys):
                idx = i + 1  # 1-based index

                if not SecretsManager.store_api_key(f"gemini_api_{idx}", key_value):
                    failed_save.append(idx)
                    continue

                # 저장 직후 읽기 검증으로 환경별 저장 실패를 조기에 감지
                loaded_value = SecretsManager.get_api_key(f"gemini_api_{idx}")
                if (loaded_value or "").strip() != key_value:
                    failed_verify.append(idx)
                    continue

                new_keys_dict[f"api_{idx}"] = key_value
                saved_count += 1

            if failed_save or failed_verify:
                detail_lines = []
                if failed_save:
                    detail_lines.append(f"- 저장 실패 위치: {failed_save}")
                if failed_verify:
                    detail_lines.append(f"- 저장 검증 실패 위치: {failed_verify}")
                show_error(
                    self,
                    "저장 오류",
                    "일부 API 키를 저장하지 못했습니다.\n"
                    + "\n".join(detail_lines)
                    + "\n\n보안 프로그램/권한 정책으로 사용자 저장소 쓰기가 막힌 환경인지 확인해주세요."
                )
                return
            
            # 2-2. 나머지 슬롯(기존에 있었을 수 있는 키) 삭제
            # valid_keys 개수 다음부터 MAX_API_KEYS(20)까지 삭제
            MAX_API_KEYS = len(self.api_key_inputs)
            for i in range(len(valid_keys) + 1, MAX_API_KEYS + 1):
                SecretsManager.delete_api_key(f"gemini_api_{i}")
                
        except Exception as e:
            from utils.logging_config import get_logger
            logger = get_logger(__name__)
            logger.error(f"[Settings] API 키 저장 중 오류 발생: {e}")
            show_error(self, "저장 오류", f"API 키 저장 중 오류가 발생했습니다:\n{e}")
            return

        # 3. UI 업데이트 (앞으로 당기기)
        for key_input in self.api_key_inputs:
            key_input.clear()
        for i, key_value in enumerate(valid_keys):
            if i < len(self.api_key_inputs):
                self.api_key_inputs[i].setText(key_value)

        # 4. config 업데이트 및 매니저 재초기화
        config.GEMINI_API_KEYS = new_keys_dict

        # APIKeyManager 재초기화
        if self.gui and hasattr(self.gui, 'api_key_manager'):
            self.gui.api_key_manager = APIKeyManager(use_secrets_manager=True)
            # genai client 재초기화
            if hasattr(self.gui, 'init_client'):
                self.gui.init_client()

        self._update_key_count()
        self._refresh_setup_assistant_status()

        if saved_count > 0:
            show_info(self, "저장 완료", f"총 {saved_count}개의 API 키가 순서대로 정렬되어 저장되었습니다.")
        else:
            show_info(self, "저장 완료", "모든 API 키가 삭제되었습니다.")

    def _clear_all_api_keys(self):
        """모든 API 키 삭제"""
        from ui.components.custom_dialog import show_question, show_info

        if not show_question(self, "확인", "모든 API 키를 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다."):
            return

        # 입력 필드 초기화
        for key_input in self.api_key_inputs:
            key_input.clear()

        # SecretsManager에서 삭제
        from utils.logging_config import get_logger
        _logger = get_logger(__name__)
        for i in range(1, 9):
            try:
                SecretsManager.delete_api_key(f"gemini_api_{i}")
            except Exception as del_err:
                _logger.debug(f"[Settings] Failed to delete gemini_api_{i}: {del_err}")

        # config 초기화
        config.GEMINI_API_KEYS = {}

        self._update_key_count()
        self._refresh_setup_assistant_status()
        show_info(self, "삭제 완료", "모든 API 키가 삭제되었습니다.")
    
    @staticmethod
    def _load_version_info() -> dict:
        """version.json에서 앱 버전 정보 로드 (PyInstaller frozen 빌드 지원)"""
        import json
        import sys
        try:
            # 1순위: auto_updater의 경로 탐색 (frozen/dev 모두 지원)
            from utils.auto_updater import get_version_file_path, get_current_version
            version_path = get_version_file_path()
            if version_path and version_path.exists():
                with open(version_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            # fallback: 버전 문자열만 반환
            return {"version": get_current_version(), "updated_at": "알 수 없음"}
        except Exception:
            pass
        # 2순위: 소스 기반 상대 경로 (개발 환경)
        try:
            version_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "version.json")
            with open(version_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"version": "알 수 없음", "updated_at": "알 수 없음"}

    def _replay_tutorial(self):
        """튜토리얼 재실행"""
        if self.gui and hasattr(self.gui, 'show_tutorial_manual'):
            self.gui.show_tutorial_manual()

    def _go_to_subscription(self):
        """구독 관리 페이지로 이동"""
        if self.gui and hasattr(self.gui, '_on_step_selected'):
            self.gui._on_step_selected("subscription")

    def _open_contact_link(self):
        """Open Kakao inquiry link."""
        QDesktopServices.openUrl(QUrl("https://open.kakao.com/o/sVkZPsfi"))

    def focus_api_key_setup(self):
        """Scroll to API key section and focus the most relevant input."""
        # 'API 키' 탭으로 먼저 전환.
        try:
            self.tab_widget.setCurrentIndex(self._tab_index.get("api", 0))
        except Exception:
            pass
        try:
            bar = self.scroll_area.verticalScrollBar()
            target_y = max(0, self.api_section.y() - 24)
            bar.setValue(target_y)
        except Exception:
            pass

        if not self.api_key_inputs:
            return

        target_input = next(
            (inp for inp in self.api_key_inputs if not inp.text().strip()),
            self.api_key_inputs[0],
        )
        target_input.setFocus(Qt.FocusReason.OtherFocusReason)
        target_input.selectAll()

    def focus_coupang_setup(self):
        """Reveal the optional Coupang/Linktree advanced fields and focus the
        first empty Coupang key input, scrolling the section into view."""
        # '연결 도우미' 탭으로 먼저 전환.
        try:
            self.tab_widget.setCurrentIndex(self._tab_index.get("connect", 0))
        except Exception:
            pass
        # 고급 자동화(쿠팡 키) 영역은 기본적으로 접혀 있으므로 먼저 펼친다.
        try:
            self._set_link_advanced_visible(True)
        except Exception:
            pass

        # 쿠팡 카드(아코디언)도 펼쳐서 입력칸이 바로 보이게 한다.
        try:
            header = getattr(self, "_coupang_card_header", None)
            if header is not None and not header.isChecked():
                header.setChecked(True)
        except Exception:
            pass

        try:
            bar = self._connect_scroll.verticalScrollBar()
            target_y = max(0, self.link_automation_section.y() - 24)
            bar.setValue(target_y)
        except Exception:
            pass

        access = getattr(self, "coupang_access_input", None)
        secret = getattr(self, "coupang_secret_input", None)
        if access is None:
            return
        target_input = access if not access.text().strip() else (secret or access)
        target_input.setFocus(Qt.FocusReason.OtherFocusReason)
        target_input.selectAll()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.refresh_work_community_stats)
        QTimer.singleShot(0, self._refresh_setup_assistant_status)
        QTimer.singleShot(0, self._refresh_computer_use_access_ui)

    def _apply_theme(self):
        c = self.ds.colors
        self.setStyleSheet(f"background-color: {c.background};")
