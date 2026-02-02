"""
Settings tab implementation (PyQt6).
Provides API key management, output folder settings, theme settings, and app info.
Uses design system v2 for consistent styling.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QLineEdit, QPushButton, QScrollArea, QFileDialog, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from ui.design_system_v2 import get_design_system
from ui.components.base_widget import ThemedMixin


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
        api_section = SettingsSection("API 키 설정")
        
        # Vertex AI API Key input
        api_container = QWidget()
        api_layout = QHBoxLayout(api_container)
        api_layout.setContentsMargins(0, 0, 0, 0)
        api_layout.setSpacing(ds.spacing.space_3)
        
        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("Gemini API 키를 입력하세요")
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {c.surface_variant};
                color: {c.text_primary};
                padding: 10px 14px;
                border: 1px solid {c.border_light};
                border-radius: {ds.radius.sm}px;
                font-size: {ds.typography.size_sm}px;
            }}
        """)
        api_layout.addWidget(self.api_input, stretch=1)
        
        self.api_save_btn = QPushButton("저장")
        self.api_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.api_save_btn.setStyleSheet(f"""
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
        self.api_save_btn.clicked.connect(self._save_api_key)
        api_layout.addWidget(self.api_save_btn)
        
        api_section.add_row("API 키", api_container)
        
        # API Status button
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
        api_section.content_layout.addWidget(self.api_status_btn)
        content_layout.addWidget(api_section)
        
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
    
    def _save_api_key(self):
        """Save API key to config"""
        import os
        from ui.components.custom_dialog import show_info, show_warning
        
        api_key = self.api_input.text().strip()
        if not api_key:
            show_warning(self, "API 키 오류", "API 키를 입력해주세요.")
            return
        
        try:
            # Save to environment variable (for current session)
            os.environ['GEMINI_API_KEY'] = api_key
            
            # Save to config file
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.py')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Update or add API key
                if 'GEMINI_API_KEY' in content:
                    import re
                    content = re.sub(r'GEMINI_API_KEY\s*=\s*["\'][^"\']*["\']', f'GEMINI_API_KEY = "{api_key}"', content)
                else:
                    content += f'\n\n# Gemini API Key\nGEMINI_API_KEY = "{api_key}"\n'
                
                with open(config_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            show_info(self, "저장 완료", "API 키가 저장되었습니다.")
            self.api_input.clear()
        except Exception as e:
            show_warning(self, "저장 실패", f"API 키 저장 중 오류가 발생했습니다: {e}")
    
    def _replay_tutorial(self):
        """튜토리얼 재실행"""
        if self.gui and hasattr(self.gui, 'show_tutorial_manual'):
            self.gui.show_tutorial_manual()

    def _apply_theme(self):
        c = self.ds.colors
        self.setStyleSheet(f"background-color: {c.background};")
