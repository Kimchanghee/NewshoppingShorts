"""
Progress Panel for PyQt6
"""
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QFrame, QWidget
from PyQt6.QtCore import Qt, QTimer
from ui.components.base_widget import ThemedMixin
from ui.design_system_v2 import get_design_system, get_color, is_dark_mode

class ProgressPanel(QFrame, ThemedMixin):
    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.ds = get_design_system()
        self.__init_themed__(theme_manager)
        self.create_widgets()
        self.apply_theme()

    def create_widgets(self):
        ds = self.ds
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(ds.spacing.space_3, ds.spacing.space_4, ds.spacing.space_3, ds.spacing.space_4)
        
        # Header
        self.title_label = QLabel("제작 진행")
        self.title_label.setStyleSheet(f"font-size: {ds.typography.size_xl}px; font-weight: {ds.typography.weight_bold};")
        self.main_layout.addWidget(self.title_label)
        
        # Current Task Display
        self.status_container = QFrame()
        self.status_container.setStyleSheet(f"background-color: {get_color('error')}; border-radius: {ds.border_radius.radius_sm}px; padding: 2px;")
        status_layout = QVBoxLayout(self.status_container)
        
        self.status_inner = QFrame()
        inner_bg = get_color('surface_variant') if is_dark_mode() else "#FEF2F2"
        self.status_inner.setStyleSheet(f"background-color: {inner_bg}; border-radius: {ds.border_radius.radius_sm - 2}px;")
        inner_layout = QVBoxLayout(self.status_inner)
        
        task_fg = get_color('error') if is_dark_mode() else "#DC2626"
        self.gui.current_task_label = QLabel("대기 중...")
        self.gui.current_task_label.setStyleSheet(f"color: {task_fg}; font-size: {ds.typography.size_sm}px; font-weight: {ds.typography.weight_bold}; padding: {ds.spacing.space_2}px;")
        self.gui.current_task_label.setWordWrap(True)
        inner_layout.addWidget(self.gui.current_task_label)
        status_layout.addWidget(self.status_inner)
        self.main_layout.addWidget(self.status_container)
        
        # Overall Progress
        self.overall_title = QLabel("📊 현재 영상 진행률")
        self.overall_title.setStyleSheet(f"font-weight: {ds.typography.weight_bold}; margin-top: {ds.spacing.space_2}px;")
        self.main_layout.addWidget(self.overall_title)
        
        self.gui.overall_numeric_label = QLabel("0/0 (0%)")
        self.gui.overall_numeric_label.setStyleSheet(f"font-size: {ds.typography.size_lg}px; font-weight: {ds.typography.weight_bold};")
        self.main_layout.addWidget(self.gui.overall_numeric_label)
        
        self.gui.overall_witty_label = QLabel("큐를 채우면 신나는 제작 퍼레이드가 시작됩니다!")
        self.gui.overall_witty_label.setStyleSheet(f"font-size: {ds.typography.size_2xs}px;")
        self.gui.overall_witty_label.setWordWrap(True)
        self.main_layout.addWidget(self.gui.overall_witty_label)
        
        # Steps Grid
        self.steps_container = QFrame()
        steps_layout = QVBoxLayout(self.steps_container)
        steps_layout.setSpacing(0)
        steps_layout.setContentsMargins(0, ds.spacing.space_2, 0, 0)
        
        step_definitions = [
            ("📥 다운로드", 'download'),
            ("🤖 AI 분석", 'analysis'),
            ("🔍 자막 분석", 'ocr_analysis'),
            ("🌐 번역", 'translation'),
            ("🎤 TTS", 'tts'),
            ("🎨 블러", 'subtitle'),
            ("🔊 싱크", 'audio_analysis'),
            ("📝 자막", 'subtitle_overlay'),
            ("🎵 합성", 'video'),
            ("✨ 완료", 'finalize'),
        ]
        
        self.gui.step_indicators = {}
        self.gui.step_titles = {}
        
        for idx, (title, key) in enumerate(step_definitions):
            row = QFrame()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(ds.spacing.space_3, ds.spacing.space_1, ds.spacing.space_3, ds.spacing.space_1)
            
            status_ico = QLabel("⏸")
            status_ico.setFixedWidth(24)
            row_layout.addWidget(status_ico)
            
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet(f"font-size: {ds.typography.size_xs}px;")
            row_layout.addWidget(title_lbl)
            
            row_layout.addStretch()
            
            prog_lbl = QLabel("")
            prog_lbl.setStyleSheet(f"font-weight: {ds.typography.weight_bold};")
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
            
        self.main_layout.addWidget(self.steps_container)
        self.main_layout.addStretch()

    def update_step_status(self, step_key, status, progress=None):
        ds = self.ds
        if step_key not in self.gui.step_indicators:
            return
            
        indicator = self.gui.step_indicators[step_key]
        icons = {'pending': '⏸', 'active': '🔄', 'completed': '✅', 'error': '❌'}
        colors = {
            'pending': get_color('text_muted'), 
            'active': get_color('error'), 
            'completed': get_color('success'), 
            'error': get_color('error')
        }
        
        color = colors.get(status, colors['pending'])
        indicator['status_label'].setText(icons.get(status, '⏸'))
        indicator['status_label'].setStyleSheet(f"color: {color}; font-weight: {ds.typography.weight_bold};")
        
        if status == 'active':
            indicator['title_label'].setStyleSheet(f"color: {color}; font-size: {ds.typography.size_xs}px; font-weight: {ds.typography.weight_bold};")
            indicator['row_frame'].setStyleSheet(f"background-color: {get_color('surface_variant')}; border-radius: {ds.border_radius.radius_sm}px;")
        else:
            indicator['title_label'].setStyleSheet(f"color: {get_color('text_primary')}; font-size: {ds.typography.size_xs}px;")
            indicator['row_frame'].setStyleSheet("background-color: transparent;")

        if progress is not None:
            indicator['progress_label'].setText(f"{progress}%")
        elif status == 'completed':
            indicator['progress_label'].setText("완료")
        elif status == 'active':
            indicator['progress_label'].setText("진행중")
        else:
            indicator['progress_label'].setText("")
        
        indicator['progress_label'].setStyleSheet(f"color: {color};")

    def apply_theme(self):
        ds = self.ds
        bg = get_color('surface')
        border = get_color('border_light')
        text_primary = get_color('text_primary')
        text_secondary = get_color('text_secondary')
        
        self.setStyleSheet(f"background-color: {bg}; border: 1px solid {border}; border-radius: {ds.border_radius.radius_base}px;")
        self.title_label.setStyleSheet(f"color: {text_primary}; font-weight: {ds.typography.weight_bold}; border: none; font-size: {ds.typography.size_xl}px;")
        self.overall_title.setStyleSheet(f"color: {text_primary}; border: none; font-weight: {ds.typography.weight_bold};")
        self.gui.overall_numeric_label.setStyleSheet(f"color: {get_color('primary')}; border: none; font-size: {ds.typography.size_lg}px; font-weight: {ds.typography.weight_bold};")
        self.gui.overall_witty_label.setStyleSheet(f"color: {text_secondary}; border: none; font-size: {ds.typography.size_2xs}px;")
        
        # Current Task Highlight
        inner_bg = "#1F2937" if is_dark_mode() else "#FEF2F2"
        task_fg = get_color('error') if is_dark_mode() else "#DC2626"
        self.status_inner.setStyleSheet(f"background-color: {inner_bg}; border-radius: {ds.border_radius.radius_sm - 2}px; border: none;")
        self.gui.current_task_label.setStyleSheet(f"color: {task_fg}; font-size: {ds.typography.size_sm}px; font-weight: {ds.typography.weight_bold}; padding: {ds.spacing.space_2}px; border: none;")
        self.status_container.setStyleSheet(f"background-color: {get_color('error')}; border-radius: {ds.border_radius.radius_sm}px; padding: 2px; border: none;")
