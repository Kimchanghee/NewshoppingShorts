"""
Progress Panel for PyQt6 - Dark Mode Design
"""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, QWidget, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer
from ui.components.base_widget import ThemedMixin
from ui.design_system_v2 import get_design_system, get_color, is_dark_mode


class ProgressPanel(QFrame, ThemedMixin):
    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.ds = get_design_system()
        self._blink_timer = None
        self._blink_step = None
        self._blink_visible = True
        self.__init_themed__(theme_manager)
        self.create_widgets()
        self.apply_theme()

    def _create_section_divider(self):
        """Create a subtle horizontal divider between sections."""
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #334155; margin: 0 8px;")
        return divider

    def create_widgets(self):
        ds = self.ds
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(6)

        # ══════════════════════════════════════════════
        # Section 1: 전체 영상 진행률 (Overall Queue Progress)
        # ══════════════════════════════════════════════
        overall_section = QFrame()
        overall_section.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 41, 59, 0.6);
                border: 1px solid #334155;
                border-radius: 8px;
            }
        """)
        overall_layout = QVBoxLayout(overall_section)
        overall_layout.setContentsMargins(12, 10, 12, 10)
        overall_layout.setSpacing(4)

        # Section header
        overall_header = QHBoxLayout()
        overall_icon = QLabel("📊")
        overall_icon.setStyleSheet("font-size: 9px; background: transparent; border: none;")
        overall_header.addWidget(overall_icon)
        overall_title = QLabel("전체 영상 진행률")
        overall_title.setStyleSheet("font-size: 9px; font-weight: bold; color: #E2E8F0; background: transparent; border: none;")
        overall_header.addWidget(overall_title)
        overall_header.addStretch()
        overall_layout.addLayout(overall_header)

        # Progress value (X/Y (Z%))
        self.gui.overall_numeric_label = QLabel("0/0 (0%)")
        self.gui.overall_numeric_label.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #22C55E;
            padding: 2px 0;
            background: transparent;
            border: none;
        """)
        overall_layout.addWidget(self.gui.overall_numeric_label)

        # Witty message
        self.gui.overall_witty_label = QLabel("큐를 채우면 제작이 시작됩니다")
        self.gui.overall_witty_label.setStyleSheet("font-size: 10px; color: #64748B; background: transparent; border: none;")
        self.gui.overall_witty_label.setWordWrap(True)
        overall_layout.addWidget(self.gui.overall_witty_label)

        self.main_layout.addWidget(overall_section)

        # ══════════════════════════════════════════════
        # Section 2: 현재 영상 진행율 (Current Video Progress)
        # ══════════════════════════════════════════════
        current_section = QFrame()
        current_section.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 41, 59, 0.4);
                border: 1px solid #334155;
                border-radius: 8px;
            }
        """)
        current_layout = QVBoxLayout(current_section)
        current_layout.setContentsMargins(12, 10, 12, 10)
        current_layout.setSpacing(4)

        # Section header with status icon
        current_header = QHBoxLayout()
        self.status_icon = QLabel("⏳")
        self.status_icon.setStyleSheet("font-size: 9px; color: #FACC15; background: transparent; border: none;")
        current_header.addWidget(self.status_icon)
        self.current_section_title = QLabel("현재 영상 진행율")
        self.current_section_title.setStyleSheet("font-size: 9px; font-weight: bold; color: #E2E8F0; background: transparent; border: none;")
        current_header.addWidget(self.current_section_title)
        current_header.addStretch()
        self.status_title = QLabel("대기 중")
        self.status_title.setStyleSheet("font-size: 8px; color: #94A3B8; font-weight: bold; background: transparent; border: none;")
        current_header.addWidget(self.status_title)
        current_layout.addLayout(current_header)

        # Current task label
        self.gui.current_task_label = QLabel("대기 중...")
        self.gui.current_task_label.setStyleSheet("""
            font-size: 12px;
            font-weight: bold;
            color: #F1F5F9;
            padding: 2px 0;
            background: transparent;
            border: none;
        """)
        self.gui.current_task_label.setWordWrap(True)
        current_layout.addWidget(self.gui.current_task_label)

        # Divider inside current section
        inner_divider = QFrame()
        inner_divider.setFixedHeight(1)
        inner_divider.setStyleSheet("background-color: #334155; border: none;")
        current_layout.addWidget(inner_divider)

        # Steps list (embedded in current section)
        self.steps_scroll = QScrollArea()
        self.steps_scroll.setWidgetResizable(True)
        self.steps_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.steps_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #1E293B;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #475569;
                border-radius: 3px;
            }
        """)

        self.steps_container = QWidget()
        self.steps_container.setStyleSheet("background: transparent; border: none;")
        steps_layout = QVBoxLayout(self.steps_container)
        steps_layout.setSpacing(1)
        steps_layout.setContentsMargins(0, 4, 0, 0)

        step_definitions = [
            ("다운로드", 'download', "⬇"),
            ("AI 분석", 'analysis', "🤖"),
            ("자막 분석", 'ocr_analysis', "📝"),
            ("번역", 'translation', "🌐"),
            ("TTS 생성", 'tts', "🔊"),
            ("블러 처리", 'subtitle', "🔲"),
            ("오디오 싱크", 'audio_analysis', "🎵"),
            ("자막 오버레이", 'subtitle_overlay', "💬"),
            ("영상 합성", 'video', "🎬"),
            ("완료 처리", 'finalize', "✅"),
        ]

        self.gui.step_indicators = {}
        self.gui.step_titles = {}

        for idx, (title, key, icon) in enumerate(step_definitions):
            row = QFrame()
            row.setStyleSheet("""
                QFrame {
                    background-color: transparent;
                    border: none;
                    border-radius: 4px;
                    padding: 2px;
                }
            """)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(6, 2, 6, 2)
            row_layout.setSpacing(6)

            # Status indicator
            status_ico = QLabel("○")
            status_ico.setFixedWidth(14)
            status_ico.setStyleSheet("font-size: 10px; color: #475569;")
            row_layout.addWidget(status_ico)

            # Step title
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet("font-size: 11px; color: #94A3B8;")
            row_layout.addWidget(title_lbl)

            row_layout.addStretch()

            # Progress label
            prog_lbl = QLabel("")
            prog_lbl.setStyleSheet("font-size: 10px; font-weight: bold; color: #475569;")
            row_layout.addWidget(prog_lbl)

            steps_layout.addWidget(row)

            self.gui.step_titles[key] = title
            self.gui.step_indicators[key] = {
                'status_label': status_ico,
                'progress_label': prog_lbl,
                'row_frame': row,
                'title_label': title_lbl,
                'index': idx
            }

        steps_layout.addStretch()
        self.steps_scroll.setWidget(self.steps_container)
        current_layout.addWidget(self.steps_scroll, stretch=1)

        self.main_layout.addWidget(current_section, stretch=1)


    # -----------------------------------------------------------------
    # Step status update
    # -----------------------------------------------------------------
    def update_step_status(self, step_key, status, progress=None):
        if step_key not in self.gui.step_indicators:
            return

        indicator = self.gui.step_indicators[step_key]

        # Status icons and colors
        status_config = {
            'pending': ('○', '#475569', '#94A3B8', 'transparent'),
            'active': ('●', '#FACC15', '#FFFFFF', 'transparent'),
            'completed': ('✓', '#22C55E', '#22C55E', 'transparent'),
            'error': ('✗', '#EF4444', '#EF4444', 'transparent')
        }

        icon, icon_color, text_color, bg_color = status_config.get(status, status_config['pending'])

        indicator['status_label'].setText(icon)
        indicator['status_label'].setStyleSheet(f"font-size: 11px; color: {icon_color}; font-weight: bold;")
        indicator['title_label'].setStyleSheet(f"font-size: 12px; color: {text_color};")
        indicator['row_frame'].setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: none;
                border-radius: 4px;
            }}
        """)

        if progress is not None:
            if progress >= 100 and status != 'completed':
                # 100% 도달 시 자동으로 completed 상태로 전환
                icon, icon_color, text_color, bg_color = status_config['completed']
                indicator['status_label'].setText(icon)
                indicator['status_label'].setStyleSheet(f"font-size: 11px; color: {icon_color}; font-weight: bold;")
                indicator['title_label'].setStyleSheet(f"font-size: 12px; color: {text_color};")
                indicator['progress_label'].setText("100%")
                indicator['progress_label'].setStyleSheet(f"font-size: 11px; font-weight: bold; color: {icon_color};")
                # 블링크 중이면 중지
                if self._blink_step == step_key:
                    self.stop_blink()
            else:
                indicator['progress_label'].setText(f"{progress}%")
                indicator['progress_label'].setStyleSheet(f"font-size: 11px; font-weight: bold; color: {icon_color};")
        elif status == 'completed':
            indicator['progress_label'].setText("100%")
            indicator['progress_label'].setStyleSheet(f"font-size: 11px; font-weight: bold; color: {icon_color};")
        elif status == 'active':
            indicator['progress_label'].setText("진행중")
            indicator['progress_label'].setStyleSheet(f"font-size: 11px; font-weight: bold; color: {icon_color};")
        else:
            indicator['progress_label'].setText("")

    # -----------------------------------------------------------------
    # Current task display
    # -----------------------------------------------------------------
    def set_current_task(self, task_text, status='active'):
        """Update current task display with status icon"""
        self.gui.current_task_label.setText(task_text)

        base_style = "font-size: 9px; background: transparent; border: none;"
        title_style = "font-size: 8px; font-weight: bold; background: transparent; border: none;"

        if status == 'active':
            self.status_icon.setText("⏳")
            self.status_icon.setStyleSheet(f"{base_style} color: #FACC15;")
            self.status_title.setText("진행 중")
            self.status_title.setStyleSheet(f"{title_style} color: #FACC15;")
        elif status == 'completed':
            self.status_icon.setText("✅")
            self.status_icon.setStyleSheet(f"{base_style} color: #22C55E;")
            self.status_title.setText("완료")
            self.status_title.setStyleSheet(f"{title_style} color: #22C55E;")
        elif status == 'error':
            self.status_icon.setText("❌")
            self.status_icon.setStyleSheet(f"{base_style} color: #EF4444;")
            self.status_title.setText("오류")
            self.status_title.setStyleSheet(f"{title_style} color: #EF4444;")
        else:
            self.status_icon.setText("⏸")
            self.status_icon.setStyleSheet(f"{base_style} color: #64748B;")
            self.status_title.setText("대기 중")
            self.status_title.setStyleSheet(f"{title_style} color: #94A3B8;")

    # -----------------------------------------------------------------
    # Blink effect for active step
    # -----------------------------------------------------------------
    def start_blink(self, step_key):
        """Start blinking the active step indicator"""
        if self._blink_step == step_key and self._blink_timer is not None:
            return  # already blinking this step

        self.stop_blink()
        self._blink_step = step_key
        self._blink_visible = True
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._on_blink_tick)
        self._blink_timer.start(500)

    def stop_blink(self):
        """Stop blinking and restore icon"""
        if self._blink_timer is not None:
            self._blink_timer.stop()
            self._blink_timer.deleteLater()
            self._blink_timer = None

        # Restore last blinking step icon to solid
        if self._blink_step and self._blink_step in self.gui.step_indicators:
            indicator = self.gui.step_indicators[self._blink_step]
            indicator['status_label'].setText("●")
            indicator['status_label'].setStyleSheet("font-size: 11px; color: #FACC15; font-weight: bold;")

        self._blink_step = None
        self._blink_visible = True

    def _on_blink_tick(self):
        """Toggle visibility of the active step icon"""
        if not self._blink_step or self._blink_step not in self.gui.step_indicators:
            self.stop_blink()
            return

        indicator = self.gui.step_indicators[self._blink_step]
        self._blink_visible = not self._blink_visible

        if self._blink_visible:
            indicator['status_label'].setText("●")
            indicator['status_label'].setStyleSheet("font-size: 11px; color: #FACC15; font-weight: bold;")
        else:
            indicator['status_label'].setText("○")
            indicator['status_label'].setStyleSheet("font-size: 11px; color: #FACC15; font-weight: bold;")

    # -----------------------------------------------------------------
    # Theme
    # -----------------------------------------------------------------
    def apply_theme(self):
        # Use UI background color for seamless integration
        bg_color = get_color('surface')
        self.setStyleSheet(f"""
            ProgressPanel {{
                background-color: {bg_color};
                border: none;
                border-radius: 8px;
            }}
        """)
