"""Compact, token-driven production progress panel for the app sidebar."""
from __future__ import annotations

import re

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.components.base_widget import ThemedMixin
from ui.design_system_v2 import get_color, get_design_system
from user_facing_errors import sanitize_user_message


class _OverallProgressLabel(QLabel):
    """Keep the visual progress bar in sync with the existing label API."""

    percentage_changed = pyqtSignal(int)
    _PERCENT_PATTERN = re.compile(r"(\d{1,3})\s*%")

    def setText(self, text: str) -> None:  # noqa: N802 - Qt API
        super().setText(text)
        match = self._PERCENT_PATTERN.search(text or "")
        if match:
            self.percentage_changed.emit(max(0, min(100, int(match.group(1)))))


class ProgressPanel(QFrame, ThemedMixin):
    """Two-level queue and current-item progress shown below the sidebar."""

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

    def _card_style(self) -> str:
        return f"""
            QFrame#progressCard {{
                background-color: {get_color('surface')};
                border: 1px solid {get_color('border_light')};
                border-radius: {self.ds.radius.base}px;
            }}
        """

    def _text_style(self, *, size: int, color: str, bold: bool = False) -> str:
        weight = self.ds.typography.weight_bold if bold else self.ds.typography.weight_normal
        return (
            f"font-family: {self.ds.typography.font_family_primary}; "
            f"font-size: {size}px; font-weight: {weight}; color: {color}; "
            "background: transparent; border: none;"
        )

    def create_widgets(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 6, 8, 8)
        self.main_layout.setSpacing(6)

        overall_section = QFrame(self)
        overall_section.setObjectName("progressCard")
        overall_section.setStyleSheet(self._card_style())
        overall_layout = QVBoxLayout(overall_section)
        overall_layout.setContentsMargins(12, 10, 12, 10)
        overall_layout.setSpacing(6)

        overall_header = QHBoxLayout()
        overall_header.setSpacing(6)
        overall_dot = QLabel("●")
        overall_dot.setFixedWidth(10)
        overall_dot.setStyleSheet(self._text_style(size=8, color=get_color("primary"), bold=True))
        overall_header.addWidget(overall_dot)
        overall_title = QLabel("전체 영상 진행률")
        overall_title.setStyleSheet(self._text_style(size=10, color=get_color("text_secondary"), bold=True))
        overall_header.addWidget(overall_title)
        overall_header.addStretch()
        self.overall_status_badge = QLabel("대기")
        self.overall_status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overall_status_badge.setMinimumWidth(42)
        self.overall_status_badge.setMinimumHeight(22)
        self.overall_status_badge.setStyleSheet(f"""
            background: {get_color('surface_variant')};
            color: {get_color('text_muted')};
            border: 1px solid {get_color('border_light')};
            border-radius: 11px;
            font-size: 9px;
            font-weight: {self.ds.typography.weight_bold};
        """)
        overall_header.addWidget(self.overall_status_badge)
        overall_layout.addLayout(overall_header)

        self.gui.overall_numeric_label = _OverallProgressLabel("0/0 (0%)")
        self.gui.overall_numeric_label.setStyleSheet(
            self._text_style(size=17, color=get_color("text_primary"), bold=True)
        )
        overall_layout.addWidget(self.gui.overall_numeric_label)

        self.overall_bar = QProgressBar()
        self.overall_bar.setRange(0, 100)
        self.overall_bar.setValue(0)
        self.overall_bar.setTextVisible(False)
        self.overall_bar.setFixedHeight(7)
        self.overall_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {get_color('surface_variant')};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: {get_color('success')};
                border-radius: 3px;
            }}
        """)
        self.gui.overall_numeric_label.percentage_changed.connect(self._set_overall_percentage)
        overall_layout.addWidget(self.overall_bar)

        self.gui.overall_witty_label = QLabel("만들 목록을 채우면 제작이 시작돼요")
        self.gui.overall_witty_label.setWordWrap(True)
        self.gui.overall_witty_label.setStyleSheet(
            self._text_style(size=9, color=get_color("text_muted")) + " padding-bottom: 1px;"
        )
        overall_layout.addWidget(self.gui.overall_witty_label)
        self.main_layout.addWidget(overall_section)

        current_section = QFrame(self)
        current_section.setObjectName("progressCard")
        current_section.setStyleSheet(self._card_style())
        current_layout = QVBoxLayout(current_section)
        current_layout.setContentsMargins(12, 10, 12, 10)
        current_layout.setSpacing(6)

        current_header = QHBoxLayout()
        current_header.setSpacing(6)
        self.status_icon = QLabel("●")
        self.status_icon.setFixedWidth(10)
        current_header.addWidget(self.status_icon)
        self.current_section_title = QLabel("현재 영상 진행률")
        self.current_section_title.setStyleSheet(
            self._text_style(size=10, color=get_color("text_secondary"), bold=True)
        )
        current_header.addWidget(self.current_section_title)
        current_header.addStretch()
        self.status_title = QLabel("대기 중")
        self.status_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_title.setMinimumWidth(48)
        self.status_title.setMinimumHeight(22)
        current_header.addWidget(self.status_title)
        current_layout.addLayout(current_header)

        self.gui.current_task_label = QLabel("대기 중...")
        self.gui.current_task_label.setWordWrap(True)
        self.gui.current_task_label.setMinimumHeight(26)
        self.gui.current_task_label.setStyleSheet(
            self._text_style(size=11, color=get_color("text_primary"), bold=True)
        )
        current_layout.addWidget(self.gui.current_task_label)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {get_color('border_light')}; border: none;")
        current_layout.addWidget(divider)

        self.steps_scroll = QScrollArea()
        self.steps_scroll.setWidgetResizable(True)
        self.steps_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.steps_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.steps_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.steps_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self.steps_container = QWidget()
        self.steps_container.setStyleSheet("background: transparent; border: none;")
        self._steps_layout = QVBoxLayout(self.steps_container)
        self._steps_layout.setSpacing(1)
        self._steps_layout.setContentsMargins(0, 1, 0, 0)

        self.video_step_defs = [
            ("영상 받기", "download", "download"),
            ("AI 분석", "analysis", "analysis"),
            ("자막 읽기", "ocr_analysis", "ocr"),
            ("번역", "translation", "translation"),
            ("목소리 만들기", "tts", "tts"),
            ("원본 자막 가리기", "subtitle", "subtitle"),
            ("소리 맞추기", "audio_analysis", "audio"),
            ("자막 입히기", "subtitle_overlay", "overlay"),
            ("영상 만들기", "video", "video"),
            ("마무리", "finalize", "finalize"),
        ]
        self._populate_steps(self.video_step_defs)
        self.steps_scroll.setWidget(self.steps_container)
        current_layout.addWidget(self.steps_scroll, stretch=1)
        self.main_layout.addWidget(current_section, stretch=1)
        self.set_current_task("대기 중...", status="idle")

    def _set_overall_percentage(self, value: int) -> None:
        self.overall_bar.setValue(value)
        if value <= 0:
            self.overall_status_badge.setText("대기")
        elif value >= 100:
            self.overall_status_badge.setText("완료")
        else:
            self.overall_status_badge.setText("진행 중")

    def _populate_steps(self, step_defs):
        self.gui.step_indicators = {}
        self.gui.step_titles = {}
        for idx, (title, key, _icon) in enumerate(step_defs):
            row = QFrame()
            row.setMinimumHeight(max(24, QFontMetrics(self.font()).height() + 8))
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(5, 0, 5, 0)
            row_layout.setSpacing(6)

            status_label = QLabel("○")
            status_label.setFixedWidth(12)
            row_layout.addWidget(status_label)
            title_label = QLabel(title)
            title_label.setToolTip(title)
            row_layout.addWidget(title_label)
            row_layout.addStretch()
            progress_label = QLabel("")
            progress_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row_layout.addWidget(progress_label)
            self._steps_layout.addWidget(row)

            self.gui.step_titles[key] = title
            self.gui.step_indicators[key] = {
                "status_label": status_label,
                "progress_label": progress_label,
                "row_frame": row,
                "title_label": title_label,
                "index": idx,
            }
            self.update_step_status(key, "pending")

    def set_step_definitions(self, step_defs, section_title=None):
        self.stop_blink()
        while self._steps_layout.count():
            item = self._steps_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._populate_steps(step_defs)
        if section_title:
            self.current_section_title.setText(section_title.replace("진행율", "진행률"))

    def update_step_status(self, step_key, status, progress=None):
        indicator = self.gui.step_indicators.get(step_key)
        if indicator is None:
            return

        states = {
            "pending": ("○", get_color("text_muted"), get_color("text_muted"), "transparent"),
            "active": ("●", get_color("warning"), get_color("text_primary"), get_color("surface_variant")),
            "completed": ("✓", get_color("success"), get_color("success"), "transparent"),
            "error": ("×", get_color("error"), get_color("error"), get_color("surface_variant")),
        }
        if progress is not None and progress >= 100:
            status = "completed"
        icon, accent, text_color, background = states.get(status, states["pending"])

        indicator["status_label"].setText(icon)
        indicator["status_label"].setStyleSheet(self._text_style(size=9, color=accent, bold=True))
        indicator["title_label"].setStyleSheet(self._text_style(size=9, color=text_color, bold=status == "active"))
        indicator["row_frame"].setStyleSheet(f"""
            QFrame {{
                background: {background};
                border: none;
                border-radius: 5px;
            }}
        """)

        if status == "completed":
            progress_text = "100%"
        elif status == "active":
            progress_text = f"{progress}%" if progress is not None else "진행 중"
        elif progress is not None and progress > 0:
            progress_text = f"{progress}%"
        else:
            progress_text = ""
        indicator["progress_label"].setText(progress_text)
        indicator["progress_label"].setStyleSheet(self._text_style(size=8, color=accent, bold=True))

        if status == "completed" and self._blink_step == step_key:
            self.stop_blink()

    def _set_status_visual(self, label: str, color: str) -> None:
        self.status_icon.setText("●")
        self.status_icon.setStyleSheet(self._text_style(size=8, color=color, bold=True))
        self.status_title.setText(label)
        self.status_title.setStyleSheet(f"""
            background: {get_color('surface_variant')};
            color: {color};
            border: 1px solid {get_color('border_light')};
            border-radius: 11px;
            font-size: 9px;
            font-weight: {self.ds.typography.weight_bold};
        """)

    def set_current_task(self, task_text, status="active"):
        self.gui.current_task_label.setText(
            sanitize_user_message(task_text, fallback="작업 상태를 확인해 주세요.")
        )
        visuals = {
            "active": ("진행 중", get_color("warning")),
            "completed": ("완료", get_color("success")),
            "error": ("오류", get_color("error")),
            "idle": ("대기 중", get_color("text_muted")),
        }
        label, color = visuals.get(status, visuals["idle"])
        self._set_status_visual(label, color)

    def start_blink(self, step_key):
        self.stop_blink()
        self._blink_step = step_key
        self._blink_visible = True
        indicator = self.gui.step_indicators.get(step_key)
        if indicator:
            indicator["status_label"].setText("●")
            indicator["status_label"].setStyleSheet(
                self._text_style(size=9, color=get_color("warning"), bold=True)
            )

    def stop_blink(self):
        if self._blink_timer is not None:
            self._blink_timer.stop()
            self._blink_timer.deleteLater()
            self._blink_timer = None
        self._blink_step = None
        self._blink_visible = True

    def _on_blink_tick(self):
        """Legacy hook retained for callers; progress no longer blinks."""

    def apply_theme(self):
        self.setStyleSheet(f"""
            ProgressPanel {{
                background: {get_color('background')};
                border: none;
            }}
        """)
