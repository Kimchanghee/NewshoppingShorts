"""
Settings tab implementation (PyQt6).
Provides API key management, output folder settings, theme settings, and app info.
Uses design system v2 for consistent styling.
"""
import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QLineEdit, QPushButton, QScrollArea, QFileDialog
)
from PyQt6.QtCore import Qt
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
    
    def _create_widgets(self):
        ds = self.ds
        c = ds.colors
        
        # Main scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        scroll = QScrollArea()
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
                padding: 10px 20px;
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
        
        output_section.add_row("저장 위치", folder_container)
        content_layout.addWidget(output_section)
        
        # =================== SECTION: API Key Management ===================
        self.api_section = SettingsSection("API 키 설정 (최대 20개)")

        # 설명 라벨
        desc_label = QLabel("여러 개의 API 키를 등록하면 자동으로 로테이션됩니다. Rate Limit 발생 시 다음 키로 자동 전환됩니다.")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"color: {c.text_muted}; border: none; background: transparent; font-size: 11px;")
        self.api_section.content_layout.addWidget(desc_label)

        # API 키 입력 필드들 (20개)
        self.api_key_inputs = []
        MAX_API_KEYS = 20

        # 스크롤 영역 (API 키 입력 필드용)
        api_scroll = QScrollArea()
        api_scroll.setWidgetResizable(True)
        api_scroll.setFrameShape(QFrame.Shape.NoFrame)
        api_scroll.setMaximumHeight(300)
        api_scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {c.surface_variant};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {c.border};
                border-radius: 4px;
                min-height: 20px;
            }}
        """)

        api_keys_container = QWidget()
        api_keys_layout = QVBoxLayout(api_keys_container)
        api_keys_layout.setContentsMargins(0, 0, 8, 0)
        api_keys_layout.setSpacing(8)

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
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            # 라벨
            label = QLabel(f"키 {i:02d}")
            label.setFixedWidth(45)
            label.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent; font-size: 11px;")
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

            api_keys_layout.addWidget(row_widget)
            self.api_key_inputs.append(key_input)

        api_scroll.setWidget(api_keys_container)
        self.api_section.content_layout.addWidget(api_scroll)

        # 버튼 영역
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 8, 0, 0)
        btn_layout.setSpacing(12)

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
        self.api_count_label = QLabel("등록된 키: 0개")
        self.api_count_label.setStyleSheet(f"color: {c.text_muted}; border: none; background: transparent; font-size: 11px;")
        self.api_section.content_layout.addWidget(self.api_count_label)

        content_layout.addWidget(self.api_section)

        # 저장된 키 로드
        self._load_saved_api_keys()
        
        # =================== SECTION: App Info ===================
        info_section = SettingsSection("앱 정보")

        version_label = QLabel("버전: 1.0.0")
        version_label.setStyleSheet(f"color: {c.text_secondary}; border: none; background: transparent;")
        info_section.content_layout.addWidget(version_label)

        dev_label = QLabel("개발: Shopping Shorts Team")
        dev_label.setStyleSheet(f"color: {c.text_muted}; border: none; background: transparent;")
        info_section.content_layout.addWidget(dev_label)

        content_layout.addWidget(info_section)

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
                if hasattr(self.gui, 'output_folder_label') and self.gui.output_folder_label:
                    self.gui.output_folder_label.setText(folder)
    
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
            for i in range(1, 21):
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
        """등록된 키 개수 업데이트"""
        count = sum(1 for inp in self.api_key_inputs if inp.text().strip())
        self.api_count_label.setText(f"등록된 키: {count}개")

    def _save_all_api_keys(self):
        """모든 API 키 저장"""
        from ui.components.custom_dialog import show_info, show_warning

        saved_count = 0
        invalid_keys = []
        new_keys = {}

        for i, key_input in enumerate(self.api_key_inputs, start=1):
            key_value = key_input.text().strip()
            if not key_value:
                continue

            # 키 형식 검증
            if not GEMINI_API_KEY_PATTERN.match(key_value):
                invalid_keys.append(i)
                continue

            # SecretsManager에 저장
            try:
                if SecretsManager.store_api_key(f"gemini_api_{i}", key_value):
                    saved_count += 1
                    new_keys[f"api_{i}"] = key_value
            except Exception as e:
                from utils.logging_config import get_logger
                logger = get_logger(__name__)
                logger.error(f"[Settings] API 키 {i} 저장 실패: {e}")

        # config 업데이트
        if new_keys:
            config.GEMINI_API_KEYS = new_keys

            # APIKeyManager 재초기화
            if self.gui and hasattr(self.gui, 'api_key_manager'):
                self.gui.api_key_manager = APIKeyManager(use_secrets_manager=True)
                # genai client 재초기화
                if hasattr(self.gui, 'init_client'):
                    self.gui.init_client()

        self._update_key_count()

        if invalid_keys:
            show_warning(
                self,
                "일부 키 저장 실패",
                f"저장 완료: {saved_count}개\n"
                f"잘못된 형식 (키 번호): {invalid_keys}\n\n"
                "Gemini API 키는 'AIza'로 시작해야 합니다."
            )
        elif saved_count > 0:
            show_info(self, "저장 완료", f"{saved_count}개의 API 키가 저장되었습니다.")
        else:
            show_warning(self, "저장 실패", "저장할 API 키가 없습니다.")

    def _clear_all_api_keys(self):
        """모든 API 키 삭제"""
        from ui.components.custom_dialog import show_question, show_info

        if not show_question(self, "확인", "모든 API 키를 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다."):
            return

        # 입력 필드 초기화
        for key_input in self.api_key_inputs:
            key_input.clear()

        # SecretsManager에서 삭제
        for i in range(1, 21):
            try:
                SecretsManager.delete_api_key(f"gemini_api_{i}")
            except Exception:
                pass

        # config 초기화
        config.GEMINI_API_KEYS = {}

        self._update_key_count()
        show_info(self, "삭제 완료", "모든 API 키가 삭제되었습니다.")
    
    def _replay_tutorial(self):
        """튜토리얼 재실행"""
        if self.gui and hasattr(self.gui, 'show_tutorial_manual'):
            self.gui.show_tutorial_manual()

    def _apply_theme(self):
        c = self.ds.colors
        self.setStyleSheet(f"background-color: {c.background};")
