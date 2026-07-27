# -*- coding: utf-8 -*-
"""
Modern Update Dialogs for PyQt6
- UpdateProgressDialog: 다운로드 진행 UI (버전 + 릴리즈 노트 표시)
- UpdateCompleteDialog: 업데이트 완료 안내 (5초 카운트다운 + 확인 버튼)
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QApplication, QScrollArea, QTextEdit
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

from ui.theme_manager import get_theme_manager


def _build_colors():
    """Build shared color palette from theme manager (dark theme matching main app)."""
    tm = get_theme_manager()
    return {
        "bg": tm.get_color("bg_card"),
        "bg_outer": tm.get_color("bg_main"),
        "primary": tm.get_color("primary"),
        "gradient_start": tm.get_color("gradient_start"),
        "gradient_end": tm.get_color("gradient_end"),
        "text_primary": tm.get_color("text_primary"),
        "text_secondary": tm.get_color("text_secondary"),
        "border": tm.get_color("border_light"),
        "surface": tm.get_color("bg_input"),
        "progress_bg": tm.get_color("progress_bg"),
        "success": tm.get_color("success"),
    }


def _fade_in(widget):
    """Show dialogs without opacity animation to avoid visible flicker."""
    widget.setWindowOpacity(1)
    return None


def _center_widget(widget):
    """Center widget on primary screen."""
    primary = QApplication.primaryScreen()
    if primary is None:
        return
    screen = primary.geometry()
    widget.move(
        (screen.width() - widget.width()) // 2,
        (screen.height() - widget.height()) // 2,
    )


def _release_notes_style(colors):
    """Shared stylesheet for release notes QTextEdit."""
    return f"""
        QTextEdit {{
            color: {colors['text_secondary']};
            background-color: {colors['surface']};
            border: 1px solid {colors['border']};
            border-radius: 8px;
            padding: 12px;
        }}
        QTextEdit:focus {{
            border: 1px solid {colors['border']};
            outline: none;
        }}
        QScrollBar:vertical {{
            background: {colors['surface']};
            width: 8px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical {{
            background: {colors['border']};
            border-radius: 4px;
            min-height: 20px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
    """


def _setup_frameless_window(widget):
    """Shared frameless window setup for update dialogs."""
    widget.setWindowFlags(
        Qt.WindowType.FramelessWindowHint |
        Qt.WindowType.WindowStaysOnTopHint
    )
    widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    widget.setFixedSize(widget.WIN_W, widget.WIN_H)


# ─────────────────────────────────────────────
# UpdateNotesDialog  (업데이트 내역 알림)
# ─────────────────────────────────────────────

class UpdateNotesDialog(QWidget):
    """
    업데이트 내역 알림 다이얼로그.
    프로그램 시작 시 새로운 버전의 업데이트 내역을 보여줍니다.
    """

    closed = pyqtSignal()

    # ── Fixed dimensions ──
    WIN_W, WIN_H = 480, 420
    PAD = 10
    CONT_W = WIN_W - PAD * 2
    CONT_H = WIN_H - PAD * 2

    def __init__(self, version: str = "", release_notes: str = "", parent=None):
        super().__init__(parent)
        self._version = version
        self._release_notes = release_notes

        self.COLORS = _build_colors()
        self._setup_window()
        self._setup_ui()
        _center_widget(self)

    def _setup_window(self):
        _setup_frameless_window(self)

    def _setup_ui(self):
        C = self.COLORS

        # Container (fixed position)
        self.container = QWidget(self)
        self.container.setGeometry(self.PAD, self.PAD, self.CONT_W, self.CONT_H)
        self.container.setStyleSheet(f"""
            QWidget {{
                background-color: {C['bg']};
                border-radius: 16px;
                border: 1px solid {C['border']};
            }}
        """)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(12)

        # Header with icon
        header_layout = QHBoxLayout()

        icon = QLabel("🔔")
        icon.setFont(QFont("Segoe UI Emoji", 28))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("background:transparent; border:none;")
        icon.setFixedWidth(50)
        header_layout.addWidget(icon)

        # Title and version
        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)

        title = QLabel("새로운 업데이트!")
        title.setFont(QFont("Pretendard", 20, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{C['text_primary']}; background:transparent; border:none;")
        title_layout.addWidget(title)

        if self._version:
            ver_label = QLabel(f"v{self._version}")
            ver_label.setFont(QFont("Pretendard", 12, QFont.Weight.Bold))
            ver_label.setStyleSheet(f"color:{C['primary']}; background:transparent; border:none;")
            title_layout.addWidget(ver_label)

        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        layout.addSpacing(8)

        # Release notes header
        notes_header = QLabel("📋 업데이트 내역")
        notes_header.setFont(QFont("Pretendard", 12, QFont.Weight.Bold))
        notes_header.setStyleSheet(f"color:{C['text_primary']}; background:transparent; border:none;")
        layout.addWidget(notes_header)

        # Release notes content (scrollable area simulated with fixed height)
        notes_text = self._release_notes if self._release_notes else "업데이트 내역이 없습니다."
        notes = QLabel(notes_text)
        notes.setFont(QFont("Pretendard", 11))
        notes.setWordWrap(True)
        notes.setStyleSheet(f"""
            color: {C['text_secondary']};
            background-color: {C['surface']};
            padding: 16px;
            border-radius: 10px;
            border: 1px solid {C['border']};
        """)
        notes.setMinimumHeight(180)
        notes.setMaximumHeight(200)
        notes.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(notes)

        layout.addStretch()

        # Close button
        self.close_btn = QPushButton("확인")
        self.close_btn.setFixedSize(200, 46)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setFont(QFont("Pretendard", 13, QFont.Weight.Bold))
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {C['gradient_start']},
                    stop:1 {C['gradient_end']}
                );
                color: white;
                border: none;
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {C['primary']},
                    stop:1 {C['gradient_start']}
                );
            }}
        """)
        self.close_btn.clicked.connect(self._on_close)

        # Center the button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self.close_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _on_close(self):
        self.closed.emit()
        self.close()

    def showEvent(self, event):
        super().showEvent(event)
        self._fade_anim = _fade_in(self)

    def keyPressEvent(self, event):
        """Allow closing with Enter or Escape"""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
            self._on_close()
        super().keyPressEvent(event)


# ─────────────────────────────────────────────
# UpdateProgressDialog  (다운로드 진행)
# ─────────────────────────────────────────────

class UpdateProgressDialog(QWidget):
    """업데이트 다운로드 진행 다이얼로그 (버전 + 릴리즈 노트 포함)"""

    cancelled = pyqtSignal()

    # ── Fixed dimensions ──
    WIN_W, WIN_H = 460, 500
    PAD = 10
    CONT_W = WIN_W - PAD * 2
    CONT_H = WIN_H - PAD * 2

    def __init__(self, version: str = "", release_notes: str = ""):
        super().__init__()
        self._version = version
        self._release_notes = release_notes
        self._progress = 0
        self._status_text = "다운로드 준비 중"
        self._dot_count = 0

        self.COLORS = _build_colors()
        self._setup_window()
        self._setup_ui()
        _center_widget(self)

        self.dot_timer = None

    def _setup_window(self):
        _setup_frameless_window(self)

    def _setup_ui(self):
        C = self.COLORS

        # Container (fixed position)
        self.container = QWidget(self)
        self.container.setGeometry(self.PAD, self.PAD, self.CONT_W, self.CONT_H)
        self.container.setStyleSheet(f"""
            QWidget {{
                background-color: {C['bg']};
                border-radius: 16px;
                border: 1px solid {C['border']};
            }}
        """)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        # Icon
        icon = QLabel("⬇️")
        icon.setFont(QFont("Segoe UI Emoji", 32))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("background:transparent; border:none;")
        layout.addWidget(icon)

        # Title (with version)
        title_text = "업데이트 다운로드 중"
        if self._version:
            title_text = f"v{self._version} 업데이트 다운로드 중"
        title = QLabel(title_text)
        title.setFont(QFont("Pretendard", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{C['text_primary']}; background:transparent; border:none;")
        layout.addWidget(title)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {C['progress_bg']};
                border-radius: 5px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {C['gradient_start']},
                    stop:1 {C['gradient_end']}
                );
                border-radius: 5px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        # Percentage
        self.percent_label = QLabel("0%")
        self.percent_label.setFont(QFont("Pretendard", 28, QFont.Weight.Bold))
        self.percent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.percent_label.setStyleSheet(f"color:{C['primary']}; background:transparent; border:none;")
        layout.addWidget(self.percent_label)

        # Release notes (if available) - using QTextEdit for scrolling
        if self._release_notes:
            notes_header = QLabel("업데이트 내역")
            notes_header.setFont(QFont("Pretendard", 11, QFont.Weight.Bold))
            notes_header.setStyleSheet(f"color:{C['text_primary']}; background:transparent; border:none;")
            layout.addWidget(notes_header)

            notes = QTextEdit()
            notes.setPlainText(self._release_notes)
            notes.setFont(QFont("Pretendard", 10))
            notes.setReadOnly(True)
            notes.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            notes.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            notes.setStyleSheet(_release_notes_style(C))
            notes.setFixedHeight(140)
            layout.addWidget(notes)

        # Status text
        self.status_label = QLabel(self._status_text)
        self.status_label.setFont(QFont("Pretendard", 11))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(f"color:{C['text_secondary']}; background:transparent; border:none;")
        layout.addWidget(self.status_label)

        layout.addStretch()

    # ── Public API ──

    def set_progress(self, value: int):
        self._progress = value
        self.progress_bar.setValue(value)
        self.percent_label.setText(f"{value}%")

        if value < 30:
            self._status_text = "다운로드 중"
        elif value < 70:
            self._status_text = "파일 전송 중"
        elif value < 100:
            self._status_text = "거의 완료"
        else:
            self._status_text = "설치 준비 중"
            if self.dot_timer is not None:
                self.dot_timer.stop()
            self.status_label.setText(self._status_text + "...")

    def set_status(self, text: str):
        self._status_text = text.rstrip(".")
        self.status_label.setText(text)

    # ── Internal ──

    def _update_dots(self):
        self.status_label.setText(self._status_text)

    def showEvent(self, event):
        super().showEvent(event)
        self._fade_anim = _fade_in(self)

    def closeEvent(self, event):
        if self.dot_timer is not None:
            self.dot_timer.stop()
        super().closeEvent(event)


# ─────────────────────────────────────────────
# UpdateCompleteDialog  (업데이트 완료 안내)
# ─────────────────────────────────────────────

class UpdateCompleteDialog(QWidget):
    """업데이트 완료 다이얼로그: 릴리즈 노트 + 5초 카운트다운 + 확인 버튼"""

    confirmed = pyqtSignal()

    # ── Fixed dimensions ──
    WIN_W, WIN_H = 460, 520
    PAD = 10
    CONT_W = WIN_W - PAD * 2
    CONT_H = WIN_H - PAD * 2

    COUNTDOWN_SECONDS = 5

    def __init__(self, version: str = "", release_notes: str = ""):
        super().__init__()
        self._version = version
        self._release_notes = release_notes
        self._remaining = self.COUNTDOWN_SECONDS
        self._already_confirmed = False

        self.COLORS = _build_colors()
        self._setup_window()
        self._setup_ui()
        _center_widget(self)

        # Countdown timer (starts on show)
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._tick)

    def _setup_window(self):
        _setup_frameless_window(self)

    def _setup_ui(self):
        C = self.COLORS

        # Container (fixed position)
        self.container = QWidget(self)
        self.container.setGeometry(self.PAD, self.PAD, self.CONT_W, self.CONT_H)
        self.container.setStyleSheet(f"""
            QWidget {{
                background-color: {C['bg']};
                border-radius: 16px;
                border: 1px solid {C['border']};
            }}
        """)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(12)

        # Success icon
        icon = QLabel("✅")
        icon.setFont(QFont("Segoe UI Emoji", 36))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("background:transparent; border:none;")
        layout.addWidget(icon)

        # Title
        title = QLabel("업데이트 완료!")
        title.setFont(QFont("Pretendard", 22, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{C['text_primary']}; background:transparent; border:none;")
        layout.addWidget(title)

        # Version badge
        if self._version:
            ver_label = QLabel(f"v{self._version}")
            ver_label.setFont(QFont("Pretendard", 13, QFont.Weight.Bold))
            ver_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ver_label.setStyleSheet(f"color:{C['primary']}; background:transparent; border:none;")
            layout.addWidget(ver_label)

        # Release notes - using QTextEdit for scrolling
        if self._release_notes:
            notes_header = QLabel("업데이트 내역")
            notes_header.setFont(QFont("Pretendard", 11, QFont.Weight.Bold))
            notes_header.setStyleSheet(f"color:{C['text_primary']}; background:transparent; border:none;")
            layout.addWidget(notes_header)

            notes = QTextEdit()
            notes.setPlainText(self._release_notes)
            notes.setFont(QFont("Pretendard", 10))
            notes.setReadOnly(True)
            notes.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            notes.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            notes.setStyleSheet(_release_notes_style(C))
            notes.setFixedHeight(140)
            layout.addWidget(notes)

        layout.addStretch()

        # Countdown text
        self.countdown_label = QLabel(f"{self._remaining}초 후 메인 화면으로 진입합니다")
        self.countdown_label.setFont(QFont("Pretendard", 11))
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.setStyleSheet(f"color:{C['text_secondary']}; background:transparent; border:none;")
        layout.addWidget(self.countdown_label)

        layout.addSpacing(4)

        # Confirm button
        self.confirm_btn = QPushButton("확인")
        self.confirm_btn.setFixedSize(200, 46)
        self.confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.confirm_btn.setFont(QFont("Pretendard", 13, QFont.Weight.Bold))
        self.confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {C['gradient_start']},
                    stop:1 {C['gradient_end']}
                );
                color: white;
                border: none;
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {C['primary']},
                    stop:1 {C['gradient_start']}
                );
            }}
        """)
        self.confirm_btn.clicked.connect(self._on_confirm)

        # Center the button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self.confirm_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    # ── Countdown ──

    def _tick(self):
        self._remaining -= 1
        if self._remaining <= 0:
            self._countdown_timer.stop()
            self._on_confirm()
            return
        self.countdown_label.setText(f"{self._remaining}초 후 메인 화면으로 진입합니다")

    def _on_confirm(self):
        if self._already_confirmed:
            return
        self._already_confirmed = True
        self._countdown_timer.stop()
        self.confirmed.emit()
        self.close()

    # ── Qt events ──

    def showEvent(self, event):
        super().showEvent(event)
        self._fade_anim = _fade_in(self)
        self._countdown_timer.start()

    def closeEvent(self, event):
        self._countdown_timer.stop()
        super().closeEvent(event)
