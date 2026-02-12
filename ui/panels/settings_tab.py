"""
Settings tab implementation (PyQt6).
Provides API key management, output folder settings, theme settings, and app info.
Uses design system v2 for consistent styling.
"""
import os
import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QLineEdit, QPushButton, QScrollArea, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from ui.design_system_v2 import get_design_system
from ui.components.base_widget import ThemedMixin
from utils.secrets_manager import SecretsManager
from core.api.ApiKeyManager import APIKeyManager
import config

# Gemini API 키 패턴 검증
GEMINI_API_KEY_PATTERN = re.compile(r"^AIza[A-Za-z0-9_-]{35,96}$")


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
        label.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent;")
        label.setMinimumWidth(120)
        row.addWidget(label)
        
        widget.setStyleSheet(widget.styleSheet() + " border: none;")
        row.addWidget(widget, stretch=1)
        
        self.content_layout.addLayout(row)


class SettingsTab(QWidget, ThemedMixin):
    """Settings page with API keys, output folder, theme, and app info"""
    
    def __init__(self, parent=None, gui=None, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.ds = get_design_system()
        self.__init_themed__(theme_manager)
        self._create_widgets()
        self._apply_theme()
        QTimer.singleShot(0, self.refresh_work_community_stats)
    
    def _create_widgets(self):
        ds = self.ds
        c = ds.colors
        
        # Main scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        scroll = self.scroll_area = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background-color: {c.background};")
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(
            ds.spacing.space_4, ds.spacing.space_4,
            ds.spacing.space_4, ds.spacing.space_4
        )
        content_layout.setSpacing(ds.spacing.space_5)
        
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
        content_layout.addWidget(output_section)

        # =================== SECTION: Work Community ===================
        self.work_community_section = SettingsSection("작업 커뮤니티")

        self.work_community_intro = QLabel(
            "현재까지 작업량은? 내가 만든 쇼츠 수를 확인하고 커뮤니티 레벨을 올려보세요."
        )
        self.work_community_intro.setWordWrap(True)
        self.work_community_intro.setStyleSheet(
            f"color: {c.text_secondary}; border: none; background: transparent;"
        )
        self.work_community_section.content_layout.addWidget(self.work_community_intro)

        self.work_community_question = QLabel("현재까지 작업량은?")
        self.work_community_question.setStyleSheet(
            f"color: {c.text_muted}; border: none; background: transparent; font-size: 11px;"
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
            f"color: {c.text_secondary}; border: none; background: transparent;"
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

        content_layout.addWidget(self.work_community_section)
        
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
        desc_label.setStyleSheet(f"color: {c.text_muted}; border: none; background: transparent; font-size: 11px;")
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
        self.api_count_label.setStyleSheet(f"color: {c.text_muted}; border: none; background: transparent; font-size: 11px;")
        self.api_section.content_layout.addWidget(self.api_count_label)

        content_layout.addWidget(self.api_section)

        # 저장된 키 개수만 표시 (값은 자동으로 입력칸에 채우지 않음)
        self._update_key_count()
        
        # =================== SECTION: App Info ===================
        info_section = SettingsSection("앱 정보")

        version_info = self._load_version_info()
        version_label = QLabel(f"버전: {version_info.get('version', '알 수 없음')}")
        version_label.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent;")
        info_section.content_layout.addWidget(version_label)

        updated_at = version_info.get('updated_at', version_info.get('build_date', '알 수 없음'))
        update_label = QLabel(f"업데이트: {updated_at}")
        update_label.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent;")
        info_section.content_layout.addWidget(update_label)

        dev_label = QLabel("개발: 쇼핑 숏폼 팀")
        dev_label.setStyleSheet(f"color: {c.text_muted}; border: none; background: transparent;")
        info_section.content_layout.addWidget(dev_label)

        content_layout.addWidget(info_section)

        # =================== SECTION: Social Media Connections ===================
        social_section = SettingsSection("소셜 미디어 채널 연결")

        social_desc = QLabel("영상 자동 업로드를 위해 소셜 미디어 채널을 연결하세요.")
        social_desc.setWordWrap(True)
        social_desc.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent; font-size: 11px;")
        social_section.content_layout.addWidget(social_desc)

        # YouTube connection card
        from ui.components.social_auth_card import SocialAuthCard
        from managers.settings_manager import get_settings_manager

        self._social_settings = get_settings_manager()

        self.youtube_card = SocialAuthCard(
            platform_id="youtube",
            is_connected=False,
            channel_info=None,
            coming_soon=True,
            parent=self
        )
        social_section.content_layout.addWidget(self.youtube_card)

        # TikTok (COMING SOON)
        self.tiktok_card = SocialAuthCard(
            platform_id="tiktok",
            coming_soon=True,
            parent=self
        )
        social_section.content_layout.addWidget(self.tiktok_card)

        # Instagram (COMING SOON)
        self.instagram_card = SocialAuthCard(
            platform_id="instagram",
            coming_soon=True,
            parent=self
        )
        social_section.content_layout.addWidget(self.instagram_card)

        # Threads (COMING SOON)
        self.threads_card = SocialAuthCard(
            platform_id="threads",
            coming_soon=True,
            parent=self
        )
        social_section.content_layout.addWidget(self.threads_card)

        # X (COMING SOON)
        self.x_card = SocialAuthCard(
            platform_id="x",
            coming_soon=True,
            parent=self
        )
        social_section.content_layout.addWidget(self.x_card)

        content_layout.addWidget(social_section)

        # =================== SECTION: Tutorial ===================
        tutorial_section = SettingsSection("튜토리얼")

        tutorial_desc = QLabel("앱 사용법을 다시 확인하고 싶으시면 튜토리얼을 재실행하세요.")
        tutorial_desc.setWordWrap(True)
        tutorial_desc.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent;")
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

        content_layout.addWidget(tutorial_section)

        # =================== SECTION: Subscription ===================
        sub_section = SettingsSection("구독 관리")

        sub_desc = QLabel("구독 상태 확인 및 플랜을 변경할 수 있습니다.")
        sub_desc.setWordWrap(True)
        sub_desc.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent;")
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

        content_layout.addWidget(sub_section)

        # Spacer
        content_layout.addStretch()
        
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
    
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
    
    @staticmethod
    def _extract_user_id_from_login_data(login_data):
        """Safely extract user_id from login_data payload."""
        if not login_data or not isinstance(login_data, dict):
            return None
        data_part = login_data.get("data", {})
        if isinstance(data_part, dict):
            inner = data_part.get("data", {})
            user_id = inner.get("id") if isinstance(inner, dict) else None
            if user_id:
                return user_id
        return login_data.get("userId")

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

        user_id = self._extract_user_id_from_login_data(getattr(self.gui, "login_data", None))
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
            loaded_count = 0
            for i in range(1, 9):
                key_value = SecretsManager.get_api_key(f"gemini_api_{i}")
                if key_value and i <= len(self.api_key_inputs):
                    self.api_key_inputs[i - 1].setText(key_value)
                    loaded_count += 1
            self._update_key_count()
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
        
        # 현재 입력된 모든 텍스트 확인
        for i, key_input in enumerate(self.api_key_inputs):
            key_value = key_input.text().strip()
            if not key_value:
                continue
                
            # 키 형식 검증
            if not GEMINI_API_KEY_PATTERN.match(key_value):
                invalid_format_keys.append(i + 1)
                # 형식이 잘못돼도 일단 수집하지 않음 (저장하지 않음)
                continue
                
            valid_keys.append(key_value)

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

        # 2. UI 업데이트 (앞으로 당기기)
        # 모든 입력창 초기화
        for key_input in self.api_key_inputs:
            key_input.clear()
            
        # 유효한 키 순서대로 채우기
        for i, key_value in enumerate(valid_keys):
            if i < len(self.api_key_inputs):
                self.api_key_inputs[i].setText(key_value)

        # 3. 저장 및 미사용 슬롯 삭제
        saved_count = 0
        new_keys_dict = {}
        
        try:
            # 3-1. 유효한 키 순서대로 저장
            for i, key_value in enumerate(valid_keys):
                idx = i + 1  # 1-based index
                SecretsManager.store_api_key(f"gemini_api_{idx}", key_value)
                new_keys_dict[f"api_{idx}"] = key_value
                saved_count += 1
            
            # 3-2. 나머지 슬롯(기존에 있었을 수 있는 키) 삭제
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

        # 4. config 업데이트 및 매니저 재초기화
        config.GEMINI_API_KEYS = new_keys_dict

        # APIKeyManager 재초기화
        if self.gui and hasattr(self.gui, 'api_key_manager'):
            self.gui.api_key_manager = APIKeyManager(use_secrets_manager=True)
            # genai client 재초기화
            if hasattr(self.gui, 'init_client'):
                self.gui.init_client()

        self._update_key_count()

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

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.refresh_work_community_stats)

    def _connect_youtube(self, platform_id: str):
        """Connect YouTube channel via OAuth"""
        from ui.components.custom_dialog import show_info, show_error
        from utils.logging_config import get_logger
        logger = get_logger(__name__)

        try:
            # Check if YouTubeManager is available
            if self.gui and hasattr(self.gui, 'youtube_manager'):
                yt_manager = self.gui.youtube_manager
                if yt_manager:
                    # Attempt OAuth connection
                    success = yt_manager.connect_channel()
                    if success:
                        channel_info = yt_manager.get_channel_info()
                        channel_name = channel_info.get("title", "유튜브 채널")
                        channel_id = channel_info.get("id", "")

                        # Save to settings
                        self._social_settings.set_youtube_connected(
                            True,
                            channel_id=channel_id,
                            channel_name=channel_name
                        )

                        # Update UI
                        self.youtube_card.set_connected(True, {"name": channel_name})

                        # Update app state
                        if hasattr(self.gui, 'state'):
                            self.gui.state.youtube_connected = True
                            self.gui.state.youtube_channel_info = channel_info

                        show_info(self, "연결 성공", f"유튜브 채널 '{channel_name}'이(가) 연결되었습니다.")
                        return

            # Fallback: Show manual connection dialog
            self._show_youtube_oauth_dialog()

        except Exception as e:
            logger.error(f"[Settings] YouTube 연결 실패: {e}")
            show_error(self, "연결 실패", f"유튜브 채널 연결에 실패했습니다.\n\n{e}")

    def _show_youtube_oauth_dialog(self):
        """Show YouTube OAuth connection dialog"""
        from ui.components.custom_dialog import show_info
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout

        dialog = QDialog(self)
        dialog.setWindowTitle("유튜브 채널 연결")
        dialog.setFixedSize(450, 200)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)

        # Instructions
        inst = QLabel("유튜브 데이터 API를 사용하려면 OAuth 인증이 필요합니다.\n\n"
                      "1. 구글 클라우드 콘솔에서 OAuth 클라이언트 ID를 생성하세요.\n"
                      "2. client_secrets.json 파일을 앱 폴더에 저장하세요.\n"
                      "3. 아래 버튼을 클릭하여 인증을 시작하세요.")
        inst.setWordWrap(True)
        layout.addWidget(inst)

        # Manual channel name input for testing
        name_layout = QHBoxLayout()
        name_label = QLabel("채널 이름:")
        name_input = QLineEdit()
        name_input.setPlaceholderText("임시 채널 이름 입력")
        name_layout.addWidget(name_label)
        name_layout.addWidget(name_input)
        layout.addLayout(name_layout)

        # Connect button
        btn_layout = QHBoxLayout()
        connect_btn = QPushButton("연결 (테스트)")
        connect_btn.setStyleSheet(f"background-color: #FF0000; color: white; padding: 8px 16px; border-radius: 4px;")

        def do_connect():
            channel_name = name_input.text().strip() or "테스트 채널"
            self._social_settings.set_youtube_connected(True, channel_id="test_id", channel_name=channel_name)
            self.youtube_card.set_connected(True, {"name": channel_name})
            if self.gui and hasattr(self.gui, 'state'):
                self.gui.state.youtube_connected = True
                self.gui.state.youtube_channel_info = {"name": channel_name}
            dialog.accept()
            show_info(self, "연결 성공", f"유튜브 채널 '{channel_name}'이(가) 연결되었습니다.")

        connect_btn.clicked.connect(do_connect)
        btn_layout.addStretch()
        btn_layout.addWidget(connect_btn)

        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)
        dialog.exec()

    def _disconnect_youtube(self, platform_id: str):
        """Disconnect YouTube channel"""
        from ui.components.custom_dialog import show_question, show_info

        if not show_question(self, "연결 해제", "유튜브 채널 연결을 해제하시겠습니까?\n자동 업로드가 중지됩니다."):
            return

        # Clear settings
        self._social_settings.set_youtube_connected(False, "", "")
        self._social_settings.set_youtube_auto_upload(False)

        # Update UI
        self.youtube_card.set_connected(False)

        # Update app state
        if self.gui and hasattr(self.gui, 'state'):
            self.gui.state.youtube_connected = False
            self.gui.state.youtube_channel_info = None
            self.gui.state.youtube_auto_upload = False

        # Clear YouTubeManager credentials if available
        if self.gui and hasattr(self.gui, 'youtube_manager') and self.gui.youtube_manager:
            try:
                self.gui.youtube_manager.disconnect_channel()
            except Exception:
                pass

        show_info(self, "연결 해제", "유튜브 채널 연결이 해제되었습니다.")

    def _apply_theme(self):
        c = self.ds.colors
        self.setStyleSheet(f"background-color: {c.background};")
