# -*- coding: utf-8 -*-
"""Branded recovery dialog shown when Gemini API keys cannot continue."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
)

from core.video.batch.api_key_recovery import is_google_drive_permission_error
from ui.design_system_v2 import get_color, get_design_system
from user_facing_errors import friendly_error_message, friendly_error_title
from utils.logging_config import get_logger


logger = get_logger(__name__)


class ApiKeyErrorDialog(QDialog):
    """Pause a batch and offer recovery actions without blocking Settings."""

    action_selected = pyqtSignal(str)

    def __init__(
        self,
        parent=None,
        step_name: str = "",
        key_name: str = "",
        error_msg: str = "",
        error_type: str = "quota",
    ):
        super().__init__(parent)
        self.ds = get_design_system()
        self._result_action = "stop"
        self.setObjectName("apiKeyRecoveryDialog")
        self.setWindowTitle("API 키 복구")
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setAccessibleName("API 키 복구")
        self.setAccessibleDescription("중단된 영상 작업의 API 키를 확인하고 다시 시작합니다.")
        self.setStyleSheet(
            "QDialog#apiKeyRecoveryDialog { background: transparent; border: none; }"
        )
        self._build_ui(step_name, key_name, error_msg, error_type)

    def _build_ui(
        self,
        step_name: str,
        key_name: str,
        error_msg: str,
        error_type: str,
    ) -> None:
        title = friendly_error_title(
            error_msg or error_type,
            fallback="API 키를 확인해 주세요",
        )
        message = friendly_error_message(
            error_msg or error_type,
            fallback="설정에서 API 키를 확인한 뒤 다시 시도해 주세요.",
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)

        surface = QFrame(self)
        surface.setObjectName("dialogSurface")
        surface.setStyleSheet(
            f"QFrame#dialogSurface {{ background-color: {get_color('surface')}; "
            f"border: 1px solid {get_color('border_medium')}; "
            f"border-radius: {self.ds.radius.lg}px; }}"
        )
        shadow = QGraphicsDropShadowEffect(surface)
        shadow.setBlurRadius(42)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 185))
        surface.setGraphicsEffect(shadow)
        outer.addWidget(surface)

        shell = QVBoxLayout(surface)
        shell.setContentsMargins(0, 0, 0, self.ds.spacing.space_6)
        shell.setSpacing(self.ds.spacing.space_5)
        shell.addWidget(self._build_title_bar(surface))

        body = QFrame(surface)
        body.setObjectName("dialogBody")
        body.setStyleSheet("QFrame#dialogBody { background: transparent; border: none; }")
        content = QVBoxLayout(body)
        content.setContentsMargins(
            self.ds.spacing.space_6,
            0,
            self.ds.spacing.space_6,
            0,
        )
        content.setSpacing(self.ds.spacing.space_4)
        content.addLayout(self._build_header(title))

        detail_panel = QFrame(body)
        detail_panel.setObjectName("dialogMessagePanel")
        detail_panel.setStyleSheet(
            f"QFrame#dialogMessagePanel {{ background-color: {get_color('surface_variant')}; "
            f"border: 1px solid {get_color('border_light')}; "
            f"border-radius: {self.ds.radius.base}px; }}"
        )
        details = QVBoxLayout(detail_panel)
        details.setContentsMargins(16, 14, 16, 14)
        details.setSpacing(9)
        if step_name:
            details.addLayout(self._info_row("작업 단계", step_name))
        if key_name and key_name != "unknown":
            details.addLayout(self._info_row("오류 발생 키", key_name))
        details.addLayout(self._info_row("안내", message))

        detail_scroll = QScrollArea(body)
        detail_scroll.setObjectName("dialogMessageScroll")
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        detail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        detail_scroll.setMaximumHeight(190)
        detail_scroll.setStyleSheet(
            f"QScrollArea#dialogMessageScroll {{ background: transparent; border: none; }} "
            "QScrollBar:vertical { background: transparent; width: 8px; margin: 6px 0; } "
            f"QScrollBar::handle:vertical {{ background: {get_color('border_medium')}; "
            "border-radius: 4px; min-height: 28px; } "
            f"QScrollBar::handle:vertical:hover {{ background: {get_color('primary')}; }} "
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        detail_scroll.setWidget(detail_panel)
        content.addWidget(detail_scroll)

        is_drive_permission = (
            error_type == "permission"
            and is_google_drive_permission_error(error_msg)
        )
        content.addWidget(self._build_guidance(body, is_drive_permission))
        content.addLayout(self._build_actions())
        shell.addWidget(body)

        self.adjustSize()
        screen = self.screen() or QApplication.primaryScreen()
        available_width = screen.availableGeometry().width() if screen else 560
        self.setFixedWidth(min(560, max(420, available_width - 48)))
        self.retry_btn.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def _build_title_bar(self, parent: QFrame) -> QFrame:
        title_bar = QFrame(parent)
        title_bar.setObjectName("dialogTitleBar")
        title_bar.setFixedHeight(54)
        title_bar.setStyleSheet(
            f"QFrame#dialogTitleBar {{ background: transparent; border: none; "
            f"border-bottom: 1px solid {get_color('border_light')}; "
            f"border-top-left-radius: {self.ds.radius.lg}px; "
            f"border-top-right-radius: {self.ds.radius.lg}px; }}"
        )
        row = QHBoxLayout(title_bar)
        row.setContentsMargins(20, 0, 10, 0)
        row.setSpacing(10)

        mark = QFrame(title_bar)
        mark.setFixedSize(9, 9)
        mark.setStyleSheet(
            f"background: {get_color('primary')}; border: none; border-radius: 4px;"
        )
        row.addWidget(mark)
        brand = QLabel("SSMaker", title_bar)
        brand.setStyleSheet(
            f"color: {get_color('text_primary')}; background: transparent; "
            "border: none; font-weight: bold;"
        )
        row.addWidget(brand)
        meta = QLabel("작업 알림", title_bar)
        meta.setStyleSheet(
            f"color: {get_color('text_muted')}; background: transparent; border: none;"
        )
        row.addWidget(meta)
        row.addStretch()

        close = QPushButton("×", title_bar)
        close.setObjectName("dialogCloseButton")
        close.setAccessibleName("API 키 복구 창 닫기")
        close.setFixedSize(44, 44)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet(
            f"QPushButton#dialogCloseButton {{ background: transparent; "
            f"color: {get_color('text_muted')}; border: none; "
            f"border-radius: {self.ds.radius.base}px; font-size: 22px; }} "
            f"QPushButton#dialogCloseButton:hover {{ background: {get_color('surface_variant')}; "
            f"color: {get_color('text_primary')}; }} "
            f"QPushButton#dialogCloseButton:focus {{ border: 2px solid {get_color('primary')}; }}"
        )
        close.clicked.connect(self._on_stop)
        row.addWidget(close)
        return title_bar

    def _build_header(self, title_text: str) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(self.ds.spacing.space_3)
        icon = QLabel("!", self)
        icon.setObjectName("dialogStatusIcon")
        icon.setAccessibleName("주의")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(40, 40)
        icon.setStyleSheet(
            f"background-color: {get_color('surface_variant')}; "
            f"color: {get_color('warning')}; border: 1px solid {get_color('warning')}; "
            f"border-radius: 20px; font-weight: bold; font-size: {self.ds.typography.size_md}px;"
        )
        header.addWidget(icon, alignment=Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(3)
        status = QLabel("API 키 확인 필요", self)
        status.setStyleSheet(
            f"color: {get_color('warning')}; background: transparent; border: none; font-weight: bold;"
        )
        text.addWidget(status)
        title = QLabel(title_text, self)
        title.setWordWrap(True)
        title.setStyleSheet(
            f"color: {get_color('text_primary')}; background: transparent; border: none; "
            f"font-size: {self.ds.typography.size_md}px; font-weight: bold;"
        )
        text.addWidget(title)
        subtitle = QLabel("영상 작업을 안전하게 일시정지했습니다.", self)
        subtitle.setStyleSheet(
            f"color: {get_color('text_secondary')}; background: transparent; border: none;"
        )
        text.addWidget(subtitle)
        header.addLayout(text, 1)
        return header

    def _build_guidance(self, parent: QFrame, is_drive_permission: bool) -> QFrame:
        panel = QFrame(parent)
        panel.setObjectName("apiKeyGuidance")
        status_color = get_color("warning") if is_drive_permission else get_color("info")
        panel.setStyleSheet(
            f"QFrame#apiKeyGuidance {{ background-color: {get_color('surface_variant')}; "
            f"border: 1px solid {status_color}; border-radius: {self.ds.radius.base}px; }}"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 13, 16, 13)
        copy = self._guidance_copy(is_drive_permission)
        label = QLabel(copy, panel)
        label.setObjectName("apiKeyGuidanceText")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setStyleSheet(
            f"color: {get_color('text_secondary')}; background: transparent; border: none;"
        )
        layout.addWidget(label)
        return panel

    def _build_actions(self) -> QVBoxLayout:
        actions = QVBoxLayout()
        actions.setSpacing(10)
        self.retry_btn = self._action_button(
            "API 키 확인 후 작업 계속",
            "dialogPrimaryButton",
            "primary",
            self._on_retry,
        )
        self.retry_btn.setDefault(True)
        actions.addWidget(self.retry_btn)

        secondary = QHBoxLayout()
        secondary.setSpacing(10)
        self.settings_btn = self._action_button(
            "설정에서 API 키 추가",
            "dialogSecondaryButton",
            "secondary",
            self._on_settings,
        )
        secondary.addWidget(self.settings_btn)
        self.stop_btn = self._action_button(
            "작업 중지",
            "dialogDangerButton",
            "danger",
            self._on_stop,
        )
        self.stop_btn.setAccessibleName("영상 작업 중지")
        secondary.addWidget(self.stop_btn)
        actions.addLayout(secondary)
        return actions

    def _action_button(self, text: str, name: str, kind: str, callback) -> QPushButton:
        button = QPushButton(text, self)
        button.setObjectName(name)
        button.setAccessibleName(text)
        button.setMinimumHeight(44)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(self._button_style(kind))
        button.clicked.connect(callback)
        return button

    def _button_style(self, kind: str) -> str:
        if kind == "primary":
            background = get_color("primary")
            hover = get_color("primary_hover")
            foreground = get_color("text_on_primary")
            border = get_color("primary")
        elif kind == "danger":
            background = get_color("surface_variant")
            hover = get_color("border")
            foreground = get_color("error")
            border = get_color("error")
        else:
            background = get_color("surface_variant")
            hover = get_color("border")
            foreground = get_color("text_primary")
            border = get_color("border_medium")
        return (
            f"QPushButton {{ background-color: {background}; color: {foreground}; "
            f"border: 1px solid {border}; border-radius: {self.ds.radius.base}px; "
            f"padding: 0 {self.ds.spacing.space_5}px; font-weight: bold; }} "
            f"QPushButton:hover {{ background-color: {hover}; }} "
            f"QPushButton:focus {{ border: 2px solid {get_color('primary')}; }}"
        )

    def _info_row(self, label_text: str, value_text: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        label = QLabel(f"{label_text}:", self)
        label.setFixedWidth(90)
        label.setStyleSheet(
            f"color: {get_color('text_primary')}; background: transparent; "
            "border: none; font-weight: bold;"
        )
        value = QLabel(value_text, self)
        value.setWordWrap(True)
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        value.setStyleSheet(
            f"color: {get_color('text_secondary')}; background: transparent; border: none;"
        )
        row.addWidget(label, alignment=Qt.AlignmentFlag.AlignTop)
        row.addWidget(value, 1)
        return row

    @staticmethod
    def _guidance_copy(is_drive_permission: bool) -> str:
        if is_drive_permission:
            return (
                "이 문제는 API 키가 아니라 Google Drive 공유 권한 문제입니다.\n"
                "파일을 ‘링크가 있는 모든 사용자’에게 공개하거나 OAuth 연결을 확인한 뒤 다시 시도해 주세요."
            )
        return (
            "설정에서 새 Gemini API 키를 저장한 뒤 ‘API 키 확인 후 작업 계속’을 누르면 "
            "중단 지점부터 안전하게 이어서 진행합니다."
        )

    def _on_retry(self) -> None:
        self._result_action = "retry"
        self.action_selected.emit("retry")
        self.accept()

    def _on_settings(self) -> None:
        self.action_selected.emit("settings")
        gui = self.parent()
        if gui and hasattr(gui, "_on_step_selected"):
            gui._on_step_selected("settings")
        else:
            logger.warning(
                "[ApiKeyErrorDialog] Cannot navigate to settings - parent not available"
            )

    def _on_stop(self) -> None:
        self._result_action = "stop"
        self.action_selected.emit("stop")
        self.reject()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.retry_btn.click()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self._on_stop()
            event.accept()
            return
        super().keyPressEvent(event)

    @property
    def result_action(self) -> str:
        return self._result_action
