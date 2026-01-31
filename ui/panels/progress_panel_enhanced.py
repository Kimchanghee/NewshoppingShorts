# -*- coding: utf-8 -*-
"""
Enhanced Progress Panel - Content Creator's Studio Theme

Features:
- Timeline-inspired progress visualization
- Smooth step animations
- Professional status indicators
- Real-time progress updates
"""

from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QFrame, QWidget, QProgressBar
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont

from ui.components.base_widget_enhanced import ThemedMixin, create_label, EnhancedCard


class StepIndicatorRow(QFrame, ThemedMixin):
    """Single step row in the progress timeline"""

    def __init__(self, title: str, key: str, parent=None):
        super().__init__(parent)
        self.__init_themed__()

        self.title = title
        self.key = key
        self.status = "pending"  # pending, active, completed, error

        self._create_widgets()
        self.apply_theme()

    def _create_widgets(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            self.spacing.md,
            self.spacing.sm,
            self.spacing.md,
            self.spacing.sm
        )
        layout.setSpacing(self.spacing.md)

        # Status icon
        self.status_icon = QLabel("⏸")
        self.status_icon.setFixedWidth(28)
        self.status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_icon)

        # Title
        self.title_label = QLabel(self.title)
        layout.addWidget(self.title_label)

        layout.addStretch()

        # Progress text
        self.progress_label = QLabel("")
        layout.addWidget(self.progress_label)

    def set_status(self, status: str, progress_text: str = ""):
        """Update status with animation"""
        self.status = status
        self.progress_label.setText(progress_text)

        # Update icon
        icons = {
            "pending": "⏸",
            "active": "▶",
            "completed": "✅",
            "error": "❌",
            "skipped": "⏭"
        }
        self.status_icon.setText(icons.get(status, "⏸"))

        self.apply_theme()

    def apply_theme(self):
        """Apply step row styling"""
        c = self.colors
        t = self.typography
        r = self.ds.radius

        # Background based on status
        bg_color = c.bg_card
        if self.status == "active":
            bg_color = c.primary_light
        elif self.status == "completed":
            bg_color = c.success_light
        elif self.status == "error":
            bg_color = c.error_light

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border-radius: {r.sm}px;
                border: 1px solid {c.border_light if self.status == 'pending' else 'transparent'};
            }}
        """)

        # Icon color
        icon_colors = {
            "pending": c.text_tertiary,
            "active": c.primary,
            "completed": c.success,
            "error": c.error,
            "skipped": c.warning
        }
        self.status_icon.setStyleSheet(f"""
            QLabel {{
                color: {icon_colors.get(self.status, c.text_tertiary)};
                font-size: {t.font_size_lg}px;
                font-weight: {t.font_weight_bold};
                background: transparent;
                border: none;
            }}
        """)

        # Title
        text_color = c.text_primary if self.status in ["active", "completed"] else c.text_secondary
        self.title_label.setStyleSheet(f"""
            QLabel {{
                color: {text_color};
                font-family: {t.font_family_body};
                font-size: {t.font_size_base}px;
                font-weight: {t.font_weight_medium if self.status == 'active' else t.font_weight_normal};
                background: transparent;
                border: none;
            }}
        """)

        # Progress label
        self.progress_label.setStyleSheet(f"""
            QLabel {{
                color: {c.primary if self.status == 'active' else c.text_secondary};
                font-family: {t.font_family_mono};
                font-size: {t.font_size_sm}px;
                font-weight: {t.font_weight_bold};
                background: transparent;
                border: none;
            }}
        """)


class EnhancedProgressPanel(QFrame, ThemedMixin):
    """
    Enhanced progress tracking panel with timeline visualization

    Features:
    - Current task banner
    - Overall progress bar (timeline-style)
    - Step-by-step progress indicators
    - Real-time status updates
    """

    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.__init_themed__(theme_manager)
        self.create_widgets()
        self.apply_theme()

    def create_widgets(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(
            self.spacing.xl2,
            self.spacing.lg,
            self.spacing.xl2,
            self.spacing.lg
        )
        self.main_layout.setSpacing(self.spacing.lg)

        # Header
        self._create_header()

        # Current Task Banner
        self._create_current_task_banner()

        # Overall Progress
        self._create_overall_progress()

        # Steps Timeline
        self._create_steps_timeline()

    def _create_header(self):
        """Create panel header"""
        self.title_label = QLabel("제작 진행")
        self.main_layout.addWidget(self.title_label)

    def _create_current_task_banner(self):
        """Create current task status banner"""
        # Banner container with gradient
        self.status_banner = EnhancedCard(elevation="md")
        banner_layout = QVBoxLayout(self.status_banner)
        banner_layout.setContentsMargins(
            self.spacing.lg,
            self.spacing.md,
            self.spacing.lg,
            self.spacing.md
        )

        self.gui.current_task_label = QLabel("대기 중...")
        self.gui.current_task_label.setWordWrap(True)
        banner_layout.addWidget(self.gui.current_task_label)

        self.main_layout.addWidget(self.status_banner)

    def _create_overall_progress(self):
        """Create overall progress section"""
        progress_section = QWidget()
        progress_layout = QVBoxLayout(progress_section)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(self.spacing.sm)

        # Progress title
        self.overall_title = QLabel("📊 현재 영상 진행률")
        progress_layout.addWidget(self.overall_title)

        # Numeric progress
        self.gui.overall_numeric_label = QLabel("0/0 (0%)")
        progress_layout.addWidget(self.gui.overall_numeric_label)

        # Witty message
        self.gui.overall_witty_label = QLabel("큐를 채우면 신나는 제작 퍼레이드가 시작됩니다!")
        self.gui.overall_witty_label.setWordWrap(True)
        progress_layout.addWidget(self.gui.overall_witty_label)

        # Progress bar (timeline-style)
        self.gui.overall_progress_bar = QProgressBar()
        self.gui.overall_progress_bar.setRange(0, 100)
        self.gui.overall_progress_bar.setValue(0)
        self.gui.overall_progress_bar.setTextVisible(False)
        self.gui.overall_progress_bar.setFixedHeight(24)
        progress_layout.addWidget(self.gui.overall_progress_bar)

        self.main_layout.addWidget(progress_section)

    def _create_steps_timeline(self):
        """Create steps timeline visualization"""
        steps_container = QWidget()
        steps_layout = QVBoxLayout(steps_container)
        steps_layout.setContentsMargins(0, self.spacing.md, 0, 0)
        steps_layout.setSpacing(self.spacing.xs)

        # Step definitions
        step_definitions = [
            ("📥 다운로드", 'download'),
            ("🤖 AI 분석", 'analysis'),
            ("🔍 자막 분석", 'ocr_analysis'),
            ("🌐 번역", 'translation'),
            ("🎤 TTS", 'tts'),
            ("🎨 블러", 'blur'),
            ("🔊 싱크", 'audio_analysis'),
            ("📝 자막", 'subtitle_overlay'),
            ("🎵 합성", 'video'),
            ("✨ 완료", 'finalize'),
        ]

        self.gui.step_indicators = {}
        self.gui.step_titles = {}

        for title, key in step_definitions:
            step_row = StepIndicatorRow(title, key, self)
            steps_layout.addWidget(step_row)

            self.gui.step_titles[key] = title
            self.gui.step_indicators[key] = {
                'widget': step_row,
                'status_label': step_row.status_icon,
                'progress_label': step_row.progress_label,
                'title_label': step_row.title_label
            }

        self.main_layout.addWidget(steps_container)
        self.main_layout.addStretch()

    def apply_theme(self):
        """Apply panel styling"""
        c = self.colors
        t = self.typography
        r = self.ds.radius

        # Panel background
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {c.bg_card};
                border: 1px solid {c.border_card};
                border-radius: {r.xl}px;
            }}
        """)

        # Title
        self.title_label.setStyleSheet(f"""
            QLabel {{
                color: {c.text_primary};
                font-family: {t.font_family_heading};
                font-size: {t.font_size_2xl}px;
                font-weight: {t.font_weight_bold};
                background: transparent;
                border: none;
            }}
        """)

        # Current task banner
        self.status_banner.setStyleSheet(f"""
            EnhancedCard {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {c.error_light},
                    stop:1 {c.bg_card}
                );
                border: 2px solid {c.error};
                border-radius: {r.lg}px;
            }}
        """)

        self.gui.current_task_label.setStyleSheet(f"""
            QLabel {{
                color: {c.error};
                font-family: {t.font_family_body};
                font-size: {t.font_size_md}px;
                font-weight: {t.font_weight_bold};
                background: transparent;
                border: none;
            }}
        """)

        # Progress section
        self.overall_title.setStyleSheet(f"""
            QLabel {{
                color: {c.text_primary};
                font-family: {t.font_family_body};
                font-size: {t.font_size_md}px;
                font-weight: {t.font_weight_semibold};
                background: transparent;
                border: none;
            }}
        """)

        self.gui.overall_numeric_label.setStyleSheet(f"""
            QLabel {{
                color: {c.primary};
                font-family: {t.font_family_mono};
                font-size: {t.font_size_xl}px;
                font-weight: {t.font_weight_bold};
                background: transparent;
                border: none;
            }}
        """)

        self.gui.overall_witty_label.setStyleSheet(f"""
            QLabel {{
                color: {c.text_secondary};
                font-family: {t.font_family_body};
                font-size: {t.font_size_sm}px;
                background: transparent;
                border: none;
            }}
        """)

        # Timeline-style progress bar
        progress_style = self.ds.get_progressbar_style()
        self.gui.overall_progress_bar.setStyleSheet(progress_style)
