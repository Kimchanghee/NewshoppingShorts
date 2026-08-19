# -*- coding: utf-8 -*-
"""Consistent update surfaces used before, during, and after an update."""

import re

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui.design_system_v2 import get_color
from user_facing_errors import sanitize_user_message


_PUBLIC_RELEASE_NOTES_FALLBACK = "안정성과 사용성을 개선했습니다."
_VERSION_PREFIX = re.compile(
    r"^SSMaker\s+v?\d+(?:\.\d+){1,3}\s*(?::|[-–—])?\s*",
    re.IGNORECASE,
)


def _public_release_notes(notes: str) -> str:
    """Keep only customer-facing Korean release-note lines.

    Release metadata is also used by internal publication tooling, so commit
    subjects and build notes can occasionally reach this UI. The desktop app
    must fail to a useful generic message instead of exposing those details.
    """
    public_lines = []
    for raw_line in str(notes or "").splitlines():
        line = _VERSION_PREFIX.sub("", raw_line.strip()).strip()
        if line and re.search(r"[가-힣]", line):
            public_lines.append(line)
    return "\n".join(public_lines) or _PUBLIC_RELEASE_NOTES_FALLBACK


def _font_family() -> str:
    """Choose a Korean UI font that is actually available on this machine."""
    installed = set(QFontDatabase.families())
    for family in ("Pretendard", "Malgun Gothic", "맑은 고딕", "Segoe UI"):
        if family in installed:
            return family
    return QApplication.font().family()


def _font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    return QFont(_font_family(), size, weight)


def _colors() -> dict[str, str]:
    return {
        "card": get_color("surface"),
        "outer": get_color("background"),
        "primary": get_color("primary"),
        "primary_hover": get_color("primary_hover"),
        "primary_soft": get_color("primary_light"),
        "text": get_color("text_primary"),
        "muted": get_color("text_secondary"),
        "border": get_color("border_medium"),
        "surface": get_color("surface_variant"),
        "progress": get_color("border"),
        "success": get_color("success"),
        "secondary": get_color("surface_variant"),
        "secondary_hover": get_color("border"),
        "secondary_text": get_color("text_primary"),
    }


def _center(widget: QWidget) -> None:
    screen = QApplication.screenAt(widget.frameGeometry().center()) or QApplication.primaryScreen()
    if screen is None:
        return
    area = screen.availableGeometry()
    widget.move(
        area.x() + (area.width() - widget.width()) // 2,
        area.y() + (area.height() - widget.height()) // 2,
    )


def _setup_window(widget: QWidget) -> None:
    widget.setWindowFlags(
        Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
    )
    widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    widget.setFixedSize(widget.WIN_W, widget.WIN_H)
    widget.setWindowTitle("SSMaker 업데이트")
    widget.setAccessibleName("SSMaker 업데이트")


def _button_style(colors: dict[str, str], *, primary: bool) -> str:
    if primary:
        return f"""
            QPushButton {{
                color: #ffffff;
                background-color: {colors['primary']};
                border: 1px solid {colors['primary']};
                border-radius: 10px;
                padding: 0 20px;
            }}
            QPushButton:hover {{ background-color: {colors['primary_hover']}; }}
            QPushButton:pressed {{ background-color: {colors['primary_hover']}; }}
            QPushButton:focus {{ border: 2px solid {colors['text']}; }}
        """
    return f"""
        QPushButton {{
            color: {colors['secondary_text']};
            background-color: {colors['secondary']};
            border: 1px solid {colors['border']};
            border-radius: 10px;
            padding: 0 20px;
        }}
        QPushButton:hover {{ background-color: {colors['secondary_hover']}; }}
        QPushButton:focus {{ border: 2px solid {colors['primary']}; }}
    """


class _UpdateSurface(QWidget):
    """Shared visual foundation with a restrained, readable card layout."""

    def _build_surface(self) -> QVBoxLayout:
        _setup_window(self)
        self.COLORS = _colors()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        self.container = QWidget(self)
        self.container.setObjectName("updateCard")
        self.container.setStyleSheet(
            f"""
            QWidget#updateCard {{
                background-color: {self.COLORS['card']};
                border: 1px solid {self.COLORS['border']};
                border-radius: 18px;
            }}
            QLabel {{ background: transparent; border: none; }}
            """
        )
        outer.addWidget(self.container)

        content = QVBoxLayout(self.container)
        content.setContentsMargins(32, 28, 32, 28)
        content.setSpacing(14)
        return content

    def _header(
        self,
        layout: QVBoxLayout,
        eyebrow: str,
        title: str,
        subtitle: str,
        *,
        on_close=None,
    ) -> QToolButton | None:
        top = QHBoxLayout()
        top.setSpacing(14)

        mark = QLabel("S")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(42, 42)
        mark.setFont(_font(15, QFont.Weight.Bold))
        mark.setStyleSheet(
            f"color:#ffffff; background-color:{self.COLORS['primary']}; border-radius:12px;"
        )
        top.addWidget(mark, alignment=Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        meta = QLabel(eyebrow)
        meta.setFont(_font(9, QFont.Weight.DemiBold))
        meta.setStyleSheet(f"color:{self.COLORS['primary']}; letter-spacing:0.4px;")
        text_col.addWidget(meta)

        heading = QLabel(title)
        heading.setFont(_font(19, QFont.Weight.Bold))
        heading.setStyleSheet(f"color:{self.COLORS['text']};")
        text_col.addWidget(heading)

        description = QLabel(subtitle)
        description.setFont(_font(10))
        description.setWordWrap(True)
        description.setStyleSheet(f"color:{self.COLORS['muted']};")
        text_col.addWidget(description)
        top.addLayout(text_col, 1)

        close_button = None
        if on_close is not None:
            close_button = QToolButton()
            close_button.setText("×")
            close_button.setAccessibleName("업데이트 안내 닫기")
            close_button.setCursor(Qt.CursorShape.PointingHandCursor)
            close_button.setFont(_font(16, QFont.Weight.Normal))
            close_button.setFixedSize(44, 44)
            close_button.setStyleSheet(
                f"""
                QToolButton {{
                    color:{self.COLORS['muted']};
                    background:transparent;
                    border:1px solid transparent;
                    border-radius:8px;
                }}
                QToolButton:hover {{
                    color:{self.COLORS['text']};
                    background:{self.COLORS['surface']};
                    border-color:{self.COLORS['border']};
                }}
                QToolButton:focus {{ border:2px solid {self.COLORS['primary']}; }}
                """
            )
            close_button.clicked.connect(on_close)
            top.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignTop)

        layout.addLayout(top)
        return close_button

    def _notes(self, layout: QVBoxLayout, notes: str, *, height: int) -> QTextEdit:
        editor = QTextEdit()
        editor.setObjectName("releaseNotes")
        editor.setReadOnly(True)
        editor.setPlainText(_public_release_notes(notes))
        editor.setFont(_font(10))
        editor.setFixedHeight(height)
        editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        editor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        editor.setStyleSheet(
            f"""
            QTextEdit#releaseNotes {{
                color: {self.COLORS['muted']};
                background-color: {self.COLORS['surface']};
                border: 1px solid {self.COLORS['border']};
                border-radius: 10px;
                padding: 11px 13px;
            }}
            QScrollBar:vertical {{ background:transparent; width:8px; margin:4px; }}
            QScrollBar::handle:vertical {{
                background:{self.COLORS['border']}; border-radius:4px; min-height:24px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
            """
        )
        layout.addWidget(editor)
        return editor

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.setWindowOpacity(1.0)
        _center(self)


class UpdateNotesDialog(_UpdateSurface):
    closed = pyqtSignal()
    WIN_W, WIN_H = 560, 430

    def __init__(self, version: str = "", release_notes: str = "", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._version = version
        self._closed_emitted = False
        layout = self._build_surface()
        self.close_x_btn = self._header(
            layout,
            f"SSMAKER · VERSION {version}" if version else "SSMAKER · UPDATE",
            "업데이트가 완료됐어요",
            "최신 버전이 적용되었습니다.",
            on_close=self._on_close,
        )
        self._notes(layout, release_notes, height=190)

        self.close_btn = QPushButton("닫기")
        self.close_btn.setAccessibleName("업데이트 안내 닫기")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setFont(_font(11, QFont.Weight.DemiBold))
        self.close_btn.setFixedHeight(46)
        self.close_btn.setDefault(True)
        self.close_btn.setAutoDefault(True)
        self.close_btn.setStyleSheet(_button_style(self.COLORS, primary=True))
        self.close_btn.clicked.connect(self._on_close)
        layout.addWidget(self.close_btn)

    def _on_close(self) -> None:
        self.hide()
        self.close()

    def closeEvent(self, event) -> None:
        self.hide()
        super().closeEvent(event)
        if not self._closed_emitted:
            self._closed_emitted = True
            self.closed.emit()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self.close_btn.setFocus)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
            self._on_close()
            return
        super().keyPressEvent(event)


class UpdateProgressDialog(_UpdateSurface):
    cancelled = pyqtSignal()
    WIN_W, WIN_H = 560, 330

    def __init__(self, version: str = "", release_notes: str = ""):
        super().__init__()
        self._version = version
        self._progress = 0
        self._status_text = "다운로드 준비 중"
        self.dot_timer = None

        layout = self._build_surface()
        self._header(
            layout,
            f"SSMAKER · VERSION {version}" if version else "SSMAKER · UPDATE",
            "업데이트를 준비하고 있어요",
            "안전하게 내려받은 뒤 자동으로 설치하고 다시 시작합니다.",
        )
        layout.addSpacing(8)

        value_row = QHBoxLayout()
        self.status_label = QLabel(self._status_text)
        self.status_label.setFont(_font(10, QFont.Weight.DemiBold))
        self.status_label.setStyleSheet(f"color:{self.COLORS['text']};")
        value_row.addWidget(self.status_label)
        value_row.addStretch()
        self.percent_label = QLabel("0%")
        self.percent_label.setFont(_font(22, QFont.Weight.Bold))
        self.percent_label.setStyleSheet(f"color:{self.COLORS['primary']};")
        value_row.addWidget(self.percent_label)
        layout.addLayout(value_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(14)
        self.progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background-color:{self.COLORS['progress']}; border:none; border-radius:7px;
            }}
            QProgressBar::chunk {{
                background-color:{self.COLORS['primary']}; border-radius:7px;
            }}
            """
        )
        layout.addWidget(self.progress_bar)

        detail = QLabel("작업 중인 파일은 그대로 유지됩니다.")
        detail.setFont(_font(9))
        detail.setStyleSheet(f"color:{self.COLORS['muted']};")
        layout.addWidget(detail)
        layout.addStretch()

    def set_progress(self, value: int) -> None:
        value = max(0, min(100, int(value)))
        self._progress = value
        self.progress_bar.setValue(value)
        self.percent_label.setText(f"{value}%")
        if value < 30:
            self.set_status("업데이트 파일을 내려받는 중")
        elif value < 80:
            self.set_status("파일 무결성을 확인하는 중")
        elif value < 100:
            self.set_status("설치를 준비하는 중")
        else:
            self.set_status("설치를 시작합니다")

    def set_status(self, text: str) -> None:
        self._status_text = sanitize_user_message(
            text,
            fallback="업데이트를 준비하고 있어요.",
        ).rstrip(".")
        self.status_label.setText(self._status_text)

    def _update_dots(self) -> None:
        self.status_label.setText(self._status_text)

    def closeEvent(self, event) -> None:
        if self.dot_timer is not None:
            self.dot_timer.stop()
        super().closeEvent(event)


class UpdateCompleteDialog(_UpdateSurface):
    confirmed = pyqtSignal()
    WIN_W, WIN_H = 560, 440
    COUNTDOWN_SECONDS = 12

    def __init__(self, version: str = "", release_notes: str = ""):
        super().__init__()
        self._version = version
        self._remaining = self.COUNTDOWN_SECONDS
        self._already_confirmed = False

        layout = self._build_surface()
        self._header(
            layout,
            f"SSMAKER · VERSION {version}" if version else "SSMAKER · READY",
            "최신 버전으로 준비됐어요",
            "업데이트가 안전하게 적용되었습니다.",
        )
        self._notes(layout, release_notes, height=150)

        self.countdown_label = QLabel(
            f"{self._remaining}초 후 SSMaker를 자동으로 시작합니다"
        )
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.setFont(_font(9))
        self.countdown_label.setStyleSheet(f"color:{self.COLORS['muted']};")
        layout.addWidget(self.countdown_label)

        self.confirm_btn = QPushButton("SSMaker 시작")
        self.confirm_btn.setAccessibleName("SSMaker 시작")
        self.confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.confirm_btn.setFont(_font(11, QFont.Weight.DemiBold))
        self.confirm_btn.setFixedHeight(48)
        self.confirm_btn.setMinimumWidth(320)
        self.confirm_btn.setStyleSheet(_button_style(self.COLORS, primary=True))
        self.confirm_btn.clicked.connect(self._on_confirm)
        layout.addWidget(self.confirm_btn)

        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._tick)

    def _tick(self) -> None:
        self._remaining -= 1
        if self._remaining <= 0:
            self._countdown_timer.stop()
            self._on_confirm()
            return
        self.countdown_label.setText(
            f"{self._remaining}초 후 SSMaker를 자동으로 시작합니다"
        )

    def _on_confirm(self) -> None:
        if self._already_confirmed:
            return
        self._already_confirmed = True
        self._countdown_timer.stop()
        self.confirmed.emit()
        self.close()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._countdown_timer.start()

    def closeEvent(self, event) -> None:
        self._countdown_timer.stop()
        super().closeEvent(event)


class UpdateReadyDialog(_UpdateSurface):
    """Non-blocking choice shown when a runtime update must wait for idle time."""

    install_requested = pyqtSignal()
    deferred = pyqtSignal()
    WIN_W, WIN_H = 560, 350

    def __init__(self, version: str = "", *, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._emitted = False
        layout = self._build_surface()
        self._header(
            layout,
            f"SSMAKER · VERSION {version}" if version else "SSMAKER · UPDATE",
            "새 업데이트가 준비됐어요",
            "현재 작업이 끝나면 자동으로 업데이트합니다. 지금 바로 시작할 수도 있어요.",
        )
        layout.addSpacing(8)

        info = QLabel(
            "진행 중인 영상 작업은 중단하지 않으며, 업데이트 전 안전한 시점까지 기다립니다."
        )
        info.setWordWrap(True)
        info.setFont(_font(10))
        info.setStyleSheet(
            f"color:{self.COLORS['muted']}; background:{self.COLORS['surface']};"
            f"border:1px solid {self.COLORS['border']}; border-radius:10px; padding:14px;"
        )
        layout.addWidget(info)
        layout.addStretch()

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        later = QPushButton("작업 계속하기")
        later.setAccessibleName("업데이트를 미루고 작업 계속하기")
        later.setFont(_font(10, QFont.Weight.DemiBold))
        later.setFixedHeight(46)
        later.setCursor(Qt.CursorShape.PointingHandCursor)
        later.setStyleSheet(_button_style(self.COLORS, primary=False))
        later.clicked.connect(self._defer)
        buttons.addWidget(later, 1)

        now = QPushButton("지금 업데이트")
        now.setAccessibleName(now.text())
        now.setFont(_font(10, QFont.Weight.DemiBold))
        now.setFixedHeight(46)
        now.setCursor(Qt.CursorShape.PointingHandCursor)
        now.setStyleSheet(_button_style(self.COLORS, primary=True))
        now.clicked.connect(self._install)
        buttons.addWidget(now, 1)
        layout.addLayout(buttons)

    def _install(self) -> None:
        if self._emitted:
            return
        self._emitted = True
        self.install_requested.emit()
        self.close()

    def _defer(self) -> None:
        if self._emitted:
            return
        self._emitted = True
        self.deferred.emit()
        self.close()

    def closeEvent(self, event) -> None:
        if not self._emitted:
            self._emitted = True
            self.deferred.emit()
        super().closeEvent(event)
