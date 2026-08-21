"""
Sourcing Panel - Mode 3 (전체 자동화) UI.
Coupang link input → progress display → results.
"""
from __future__ import annotations

import asyncio
import os
import threading
from typing import List, Optional

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QWidget, QCheckBox, QScrollArea,
    QTextEdit, QSpinBox, QRadioButton, QButtonGroup,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from ui.design_system_v2 import get_design_system, get_color, checkbox_qss
from ui.components.automation_readiness import AutomationReadinessCard
from utils.logging_config import get_logger
from utils.url_security import (
    MAX_PARTNER_LINK_HTTP_TOKENS,
    PartnerLinkParseResult,
    extract_coupang_partner_links,
    parse_coupang_partner_links,
)
from utils.auth_helpers import extract_user_id
from managers.work_quota import DurableWorkReservation
from user_facing_errors import sanitize_user_message

logger = get_logger(__name__)


DELIVERY_FILE_ONLY = "file_only"
DELIVERY_YOUTUBE = "youtube"


class _DeliveryModeCard(QFrame):
    """Large, keyboard-selectable radio card for the automation result scope."""

    selected = pyqtSignal(str)

    def __init__(
        self,
        mode_id: str,
        title: str,
        description: str,
        result_text: str,
        badge: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.mode_id = mode_id
        self.ds = get_design_system()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(146)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.radio = QRadioButton(title)
        self.radio.setFont(QFont(
            self.ds.typography.font_family_primary,
            self.ds.typography.size_sm,
            QFont.Weight.Bold,
        ))
        self.radio.setAccessibleName(f"{title}{', 권장' if badge else ''}")
        self.radio.setAccessibleDescription(f"{description} 결과: {result_text}")
        self.radio.toggled.connect(self._on_toggled)
        header.addWidget(self.radio, 1)

        if badge:
            badge_label = QLabel(badge)
            badge_label.setFont(QFont(
                self.ds.typography.font_family_primary,
                self.ds.typography.size_xs,
                QFont.Weight.Bold,
            ))
            badge_label.setStyleSheet(
                f"color: {get_color('success')}; background: transparent; border: none;"
            )
            header.addWidget(badge_label)
        layout.addLayout(header)

        description_label = QLabel(description)
        description_label.setWordWrap(True)
        description_label.setFont(QFont(
            self.ds.typography.font_family_primary,
            self.ds.typography.size_xs,
        ))
        description_label.setStyleSheet(f"color: {get_color('text_secondary')};")
        description_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(description_label, 1)

        result_label = QLabel(result_text)
        result_label.setWordWrap(True)
        result_label.setFont(QFont(
            self.ds.typography.font_family_primary,
            self.ds.typography.size_xs,
            QFont.Weight.Bold,
        ))
        result_label.setStyleSheet(f"color: {get_color('text_muted')};")
        result_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(result_label)

        self.set_selected(False)

    def _on_toggled(self, checked: bool) -> None:
        self.set_selected(checked)
        if checked:
            self.selected.emit(self.mode_id)

    def set_selected(self, selected: bool) -> None:
        border = get_color('primary') if selected else get_color('border_light')
        background = get_color('surface_variant') if selected else get_color('surface')
        width = 2 if selected else 1
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {background};
                border: {width}px solid {border};
                border-radius: {self.ds.radius.md}px;
            }}
            QFrame QLabel, QFrame QRadioButton {{
                background: transparent;
                border: none;
                color: {get_color('text_primary')};
            }}
            QFrame:focus {{ border: 2px solid {get_color('primary')}; }}
        """)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.radio.setChecked(True)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.radio.setChecked(True)
            event.accept()
            return
        super().keyPressEvent(event)


class _StepIndicator(QFrame):
    """Single step row in the progress list."""

    def __init__(self, step_id: str, label: str, parent=None):
        super().__init__(parent)
        self.step_id = step_id
        self.ds = get_design_system()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self.icon_label = QLabel("\u25CB")  # ○
        self.icon_label.setFixedWidth(20)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)

        self.text_label = QLabel(label)
        self.text_label.setFont(QFont(self.ds.typography.font_family_primary, self.ds.typography.size_sm))
        layout.addWidget(self.text_label, 1)

        self.status_label = QLabel("")
        self.status_label.setFont(QFont(self.ds.typography.font_family_primary, self.ds.typography.size_xs))
        self.status_label.setStyleSheet(f"color: {get_color('text_muted')};")
        layout.addWidget(self.status_label)

        self._apply_style("pending")

    def set_state(self, state: str, message: str = ""):
        self._apply_style(state)
        if message:
            safe_message = sanitize_user_message(
                message,
                fallback="상태를 확인해 주세요.",
            )
            self.status_label.setText(safe_message[:60])

    def _apply_style(self, state: str):
        if state == "completed":
            self.icon_label.setText("\u2713")  # ✓
            self.icon_label.setStyleSheet(f"color: {get_color('success')}; font-weight: bold;")
            self.text_label.setStyleSheet(f"color: {get_color('text_secondary')};")
        elif state == "in_progress":
            self.icon_label.setText("\u25CF")  # ●
            self.icon_label.setStyleSheet(f"color: {get_color('primary')}; font-weight: bold;")
            self.text_label.setStyleSheet(f"color: {get_color('text_primary')}; font-weight: bold;")
        elif state == "error":
            self.icon_label.setText("\u2717")  # ✗
            self.icon_label.setStyleSheet(f"color: {get_color('error')}; font-weight: bold;")
            self.text_label.setStyleSheet(f"color: {get_color('error')};")
        else:  # pending
            self.icon_label.setText("\u25CB")  # ○
            self.icon_label.setStyleSheet(f"color: {get_color('text_muted')};")
            self.text_label.setStyleSheet(f"color: {get_color('text_muted')};")


class SourcingPanel(QWidget):
    """Mode 3: Full automation sourcing panel."""

    sourcing_completed = pyqtSignal(dict)  # emits report dict when done
    log_message = pyqtSignal(str)
    pipeline_progress = pyqtSignal(str, str, float)
    pipeline_finished = pyqtSignal(bool, object)
    platform_result_ready = pyqtSignal(str)
    platform_failure_ready = pyqtSignal(dict)
    platform_reset_requested = pyqtSignal()

    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.ds = get_design_system()
        self.theme_manager = theme_manager
        self._pipeline = None
        self._running = False
        self._step_indicators = {}
        saved_delivery_mode = getattr(
            getattr(gui, "state", None),
            "automation_delivery_mode",
            DELIVERY_FILE_ONLY,
        )
        self._delivery_mode = (
            saved_delivery_mode
            if saved_delivery_mode in (DELIVERY_FILE_ONLY, DELIVERY_YOUTUBE)
            else DELIVERY_FILE_ONLY
        )
        self.pipeline_progress.connect(self._update_step)
        self.pipeline_finished.connect(self._on_pipeline_done)
        self.platform_result_ready.connect(self._set_platform_result)
        self.platform_failure_ready.connect(self._set_platform_failure)
        self.platform_reset_requested.connect(self._reset_platform_controls)
        self._setup_ui()

    def _setup_ui(self):
        ds = self.ds

        self.setStyleSheet(f"""
            SourcingPanel {{
                background-color: {get_color('background')};
            }}
            SourcingPanel QLabel {{
                color: {get_color('text_primary')};
            }}
        """)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Wrap all content in a scroll area so tall content scrolls instead of
        # compressing the flexible widgets.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        scroll.viewport().setStyleSheet("background:transparent;")
        outer_layout.addWidget(scroll)

        content = QWidget()
        content.setObjectName("SourcingScrollContent")
        content.setStyleSheet(f"#SourcingScrollContent {{ background-color: {get_color('background')}; }}")
        scroll.setWidget(content)

        main_layout = QVBoxLayout(content)
        main_layout.setContentsMargins(ds.spacing.space_6, ds.spacing.space_4, ds.spacing.space_6, ds.spacing.space_4)
        main_layout.setSpacing(ds.spacing.space_4)

        # 무엇을 자동화할지 먼저 결정한다. 연결이 필요 없는 파일 제작을
        # 안전한 기본값으로 두고, YouTube 업로드는 명시적으로 선택하게 한다.
        main_layout.addWidget(self._build_delivery_mode_selector())

        # 선택한 범위에 필요한 준비 항목만 보여준다.
        self.readiness_card = AutomationReadinessCard(
            self.gui, on_navigate=self._navigate_to_setup
        )
        main_layout.addWidget(self.readiness_card)

        # ── Input Section ──
        input_frame = QFrame()
        input_frame.setObjectName("SourcingInputFrame")
        input_frame.setMinimumHeight(330)
        input_frame.setStyleSheet(f"""
            QFrame#SourcingInputFrame {{
                background-color: {get_color('surface')};
                border: 1px solid {get_color('border_light')};
                border-radius: {ds.radius.md}px;
            }}
        """)
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(ds.spacing.space_4, ds.spacing.space_4, ds.spacing.space_4, ds.spacing.space_4)
        input_layout.setSpacing(ds.spacing.space_3)

        # 사용자는 내부 검색 방식을 고를 필요 없이 파트너스 링크만 넣는다.
        links_header = QHBoxLayout()
        url_label = QLabel("2. 쿠팡 파트너스 상품 링크")
        url_label.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_base, QFont.Weight.Bold))
        links_header.addWidget(url_label)
        links_header.addStretch()
        self.next_links_count_label = QLabel("0개")
        self.next_links_count_label.setFont(QFont(
            ds.typography.font_family_primary,
            ds.typography.size_xs,
            QFont.Weight.Bold,
        ))
        self.next_links_count_label.setStyleSheet(f"color: {get_color('text_secondary')};")
        links_header.addWidget(self.next_links_count_label)
        input_layout.addLayout(links_header)

        links_help = QLabel("쿠팡 파트너스에서 만든 상품 링크를 한 줄에 하나씩 붙여넣으세요.")
        links_help.setWordWrap(True)
        links_help.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        links_help.setStyleSheet(f"color: {get_color('text_muted')};")
        input_layout.addWidget(links_help)

        self.partner_links_input = QTextEdit()
        self.partner_links_input.setAcceptRichText(False)
        self.partner_links_input.setAccessibleName("쿠팡 파트너스 상품 링크 목록")
        self.partner_links_input.setAccessibleDescription(
            "쿠팡 파트너스 상품 링크를 한 줄에 하나씩 여러 개 입력하세요."
        )
        self.partner_links_input.setPlaceholderText(
            "https://link.coupang.com/a/...\n"
            "https://link.coupang.com/a/...\n"
            "https://link.coupang.com/a/..."
        )
        self.partner_links_input.setToolTip(
            "쿠팡 파트너스에서 생성한 link.coupang.com 상품 링크만 입력해 주세요."
        )
        self.partner_links_input.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_sm))
        self.partner_links_input.setMinimumHeight(132)
        self.partner_links_input.setMaximumHeight(240)
        self.partner_links_input.setStyleSheet(f"""
            QTextEdit {{
                background-color: {get_color('background')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border_light')};
                border-radius: {ds.radius.sm}px;
                padding: 10px 12px;
            }}
            QTextEdit:focus {{
                border-color: {get_color('primary')};
            }}
        """)
        input_layout.addWidget(self.partner_links_input)

        # 기존 단일 링크 처리 코드와 외부 통합을 위한 숨은 호환 상태다.
        self.url_input = QLineEdit(input_frame)
        self.url_input.setVisible(False)
        self.next_links_input = QTextEdit(input_frame)
        self.next_links_input.setVisible(False)
        self._partner_batch_active = False
        self._partner_batch_total = 0
        self._partner_batch_completed = 0
        self._platform_batch_can_continue = False
        self._platform_item_succeeded = False

        timer_frame = QFrame()
        self.upload_timer_frame = timer_frame
        timer_frame.setObjectName("UploadTimerFrame")
        timer_frame.setMinimumHeight(44)
        timer_frame.setStyleSheet(f"""
            QFrame#UploadTimerFrame {{
                background-color: {get_color('background')};
                border: 1px solid {get_color('border_light')};
                border-radius: {ds.radius.sm}px;
            }}
            QFrame#UploadTimerFrame QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        timer_layout = QHBoxLayout(timer_frame)
        timer_layout.setContentsMargins(10, 8, 10, 8)
        timer_layout.setSpacing(ds.spacing.space_2)

        timer_title = QLabel("업로드 타이머")
        timer_title.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs, QFont.Weight.Bold))
        timer_title.setStyleSheet(f"color: {get_color('text_primary')};")
        timer_layout.addWidget(timer_title)

        self.upload_interval_spin = QSpinBox()
        self.upload_interval_spin.setRange(1, 4)
        self.upload_interval_spin.setSingleStep(1)
        self.upload_interval_spin.setSuffix("시간")
        self.upload_interval_spin.setValue(self._load_upload_interval_hours())
        self.upload_interval_spin.setFixedWidth(92)
        self.upload_interval_spin.setToolTip("각 Coupang 링크로 만든 영상의 YouTube 자동 업로드 간격입니다.")
        self.upload_interval_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: {get_color('surface')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border_light')};
                border-radius: {ds.radius.sm}px;
                padding: 4px 6px;
            }}
            QSpinBox:focus {{
                border-color: {get_color('primary')};
            }}
        """)
        timer_layout.addWidget(self.upload_interval_spin)

        self.upload_timer_summary = QLabel("")
        self.upload_timer_summary.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        self.upload_timer_summary.setStyleSheet(f"color: {get_color('text_muted')};")
        self.upload_timer_summary.setWordWrap(True)
        timer_layout.addWidget(self.upload_timer_summary, 1)

        input_layout.addWidget(timer_frame)

        self._sync_partner_links_from_input()
        self._sync_upload_timer_enabled()
        self._update_next_links_count()

        self.partner_links_input.textChanged.connect(self._sync_partner_links_from_input)
        self.upload_interval_spin.valueChanged.connect(self._on_upload_interval_changed)

        # Start button
        self.btn_start = QPushButton("자동 만들기 시작")
        self.btn_start.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_base, QFont.Weight.Bold))
        self.btn_start.setMinimumHeight(42)
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_button_style()
        self.btn_start.clicked.connect(self._on_start_clicked)
        input_layout.addWidget(self.btn_start)

        main_layout.addWidget(input_frame)

        # ── Progress Section ──
        progress_frame = QFrame()
        progress_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {get_color('surface')};
                border: 1px solid {get_color('border_light')};
                border-radius: {ds.radius.md}px;
            }}
        """)
        progress_layout = QVBoxLayout(progress_frame)
        progress_layout.setContentsMargins(ds.spacing.space_4, ds.spacing.space_3, ds.spacing.space_4, ds.spacing.space_3)
        progress_layout.setSpacing(2)

        progress_title = QLabel("진행 상황")
        progress_title.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_sm, QFont.Weight.Bold))
        progress_layout.addWidget(progress_title)

        # Step indicators
        from core.sourcing.pipeline import SourcingPipeline
        for step_id, step_label in SourcingPipeline.STEPS:
            indicator = _StepIndicator(step_id, step_label)
            self._step_indicators[step_id] = indicator
            progress_layout.addWidget(indicator)

        # 진행 상황은 좌측 하단 패널 한 곳으로 통일 → 페이지 안 중복 섹션은 숨긴다.
        # (인디케이터 객체는 유지되어 내부 상태 갱신에는 계속 쓰인다.)
        progress_frame.setVisible(False)
        self._inpage_progress_frame = progress_frame
        main_layout.addWidget(progress_frame)

        # ── Results Section ──
        self.results_frame = QFrame()
        self.results_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {get_color('surface')};
                border: 1px solid {get_color('border_light')};
                border-radius: {ds.radius.md}px;
            }}
        """)
        results_layout = QVBoxLayout(self.results_frame)
        results_layout.setContentsMargins(ds.spacing.space_4, ds.spacing.space_3, ds.spacing.space_4, ds.spacing.space_3)
        results_layout.setSpacing(ds.spacing.space_2)

        results_title = QLabel("결과")
        results_title.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_sm, QFont.Weight.Bold))
        results_layout.addWidget(results_title)

        self.results_label = QLabel("자동 만들기를 시작하면 여기에 결과가 나와요.")
        self.results_label.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        self.results_label.setStyleSheet(f"color: {get_color('text_muted')};")
        self.results_label.setWordWrap(True)
        results_layout.addWidget(self.results_label)

        self.search_recovery_frame = QFrame()
        self.search_recovery_frame.setStyleSheet("QFrame { border: none; background: transparent; }")
        recovery_layout = QHBoxLayout(self.search_recovery_frame)
        recovery_layout.setContentsMargins(0, 4, 0, 0)
        recovery_layout.setSpacing(ds.spacing.space_2)

        self.btn_retry_search = QPushButton("같은 상품 다시 검색")
        self.btn_retry_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_retry_search.setToolTip("현재 파트너스 링크로 검색을 처음부터 다시 시도합니다.")
        self.btn_retry_search.clicked.connect(self._retry_last_search)
        recovery_layout.addWidget(self.btn_retry_search)

        self.btn_choose_other_product = QPushButton("다른 상품 선택")
        self.btn_choose_other_product.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_choose_other_product.setToolTip(
            "다음 링크 목록의 상품을 선택하거나 새 파트너스 링크를 입력합니다."
        )
        self.btn_choose_other_product.clicked.connect(self._choose_other_product)
        recovery_layout.addWidget(self.btn_choose_other_product)
        recovery_layout.addStretch()
        self.search_recovery_frame.setVisible(False)
        results_layout.addWidget(self.search_recovery_frame)

        main_layout.addWidget(self.results_frame)
        main_layout.addStretch()

        # Refresh readiness when optional integration changes, and paint once now.
        self.chk_linktree.toggled.connect(lambda _checked=False: self._refresh_readiness())
        self.chk_linktree.toggled.connect(lambda _checked=False: self._update_delivery_status())
        self._sync_delivery_ui()

    def _build_delivery_mode_selector(self) -> QWidget:
        """Build the two explicit automation result paths."""
        ds = self.ds
        section = QFrame()
        section.setObjectName("DeliveryModeSelector")
        section.setStyleSheet(f"""
            QFrame#DeliveryModeSelector {{
                background-color: {get_color('surface')};
                border: 1px solid {get_color('border_light')};
                border-radius: {ds.radius.md}px;
            }}
            QFrame#DeliveryModeSelector QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("1. 어디까지 자동으로 진행할까요?")
        title.setFont(QFont(
            ds.typography.font_family_primary,
            ds.typography.size_base,
            QFont.Weight.Bold,
        ))
        layout.addWidget(title)

        helper = QLabel("결과 범위를 먼저 선택해 주세요. 영상 파일 제작은 외부 서비스 연결 없이 시작할 수 있어요.")
        helper.setWordWrap(True)
        helper.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        helper.setStyleSheet(f"color: {get_color('text_muted')};")
        layout.addWidget(helper)

        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.delivery_file_card = _DeliveryModeCard(
            DELIVERY_FILE_ONLY,
            "영상 파일까지 자동 제작",
            "상품 영상 찾기부터 편집·음성·자막까지 자동으로 진행하고 완성 파일을 저장합니다.",
            "결과: 완성 MP4 · YouTube·Linktree 연결 필요 없음",
            badge="권장",
        )
        self.delivery_youtube_card = _DeliveryModeCard(
            DELIVERY_YOUTUBE,
            "제작 후 YouTube까지 업로드",
            "완성 영상을 만든 뒤 연결된 채널의 업로드 대기열에 자동으로 추가합니다.",
            "결과: 완성 MP4 + YouTube 예약 업로드",
        )
        cards.addWidget(self.delivery_file_card, 1)
        cards.addWidget(self.delivery_youtube_card, 1)
        layout.addLayout(cards)

        self._delivery_group = QButtonGroup(section)
        self._delivery_group.setExclusive(True)
        self._delivery_group.addButton(self.delivery_file_card.radio)
        self._delivery_group.addButton(self.delivery_youtube_card.radio)
        self.delivery_file_card.selected.connect(self._on_delivery_mode_changed)
        self.delivery_youtube_card.selected.connect(self._on_delivery_mode_changed)

        # Compatibility state used by the existing pipeline. It is intentionally
        # hidden because upload is now selected through the two result cards.
        self.chk_upload = QCheckBox(section)
        self.chk_upload.setVisible(False)

        self.delivery_options_frame = QFrame()
        self.delivery_options_frame.setObjectName("DeliveryOptionsFrame")
        self.delivery_options_frame.setStyleSheet(f"""
            QFrame#DeliveryOptionsFrame {{
                background-color: {get_color('background')};
                border: 1px solid {get_color('border_light')};
                border-radius: {ds.radius.sm}px;
            }}
            QFrame#DeliveryOptionsFrame QLabel,
            QFrame#DeliveryOptionsFrame QCheckBox {{
                background: transparent;
                border: none;
            }}
        """)
        options_layout = QVBoxLayout(self.delivery_options_frame)
        options_layout.setContentsMargins(12, 10, 12, 10)
        options_layout.setSpacing(8)

        status_row = QHBoxLayout()
        self.delivery_status_label = QLabel("")
        self.delivery_status_label.setWordWrap(True)
        self.delivery_status_label.setFont(QFont(
            ds.typography.font_family_primary,
            ds.typography.size_xs,
            QFont.Weight.Bold,
        ))
        status_row.addWidget(self.delivery_status_label, 1)
        self.btn_youtube_setup = QPushButton("YouTube 연결")
        self.btn_youtube_setup.setMinimumHeight(34)
        self.btn_youtube_setup.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_youtube_setup.setStyleSheet(f"""
            QPushButton {{
                color: {get_color('text_on_primary')};
                background-color: {get_color('primary')};
                border: none;
                border-radius: {ds.radius.sm}px;
                padding: 5px 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background-color: {get_color('primary_hover')}; }}
        """)
        self.btn_youtube_setup.clicked.connect(lambda: self._navigate_to_setup("upload"))
        status_row.addWidget(self.btn_youtube_setup)
        options_layout.addLayout(status_row)

        self.chk_linktree = QCheckBox("Linktree에도 상품 링크 등록 (선택)")
        self.chk_linktree.setChecked(False)
        self.chk_linktree.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        self.chk_linktree.setStyleSheet(checkbox_qss())
        options_layout.addWidget(self.chk_linktree)

        linktree_hint = QLabel("연결되지 않았거나 등록에 실패해도 영상 제작과 YouTube 업로드는 계속됩니다.")
        linktree_hint.setWordWrap(True)
        linktree_hint.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        linktree_hint.setStyleSheet(f"color: {get_color('text_muted')}; padding-left: 24px;")
        options_layout.addWidget(linktree_hint)
        layout.addWidget(self.delivery_options_frame)

        self.delivery_outcome_label = QLabel("")
        self.delivery_outcome_label.setWordWrap(True)
        self.delivery_outcome_label.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        layout.addWidget(self.delivery_outcome_label)

        if self._delivery_mode == DELIVERY_YOUTUBE:
            self.delivery_youtube_card.radio.setChecked(True)
        else:
            self.delivery_file_card.radio.setChecked(True)
        return section

    def _on_delivery_mode_changed(self, mode_id: str) -> None:
        if mode_id not in (DELIVERY_FILE_ONLY, DELIVERY_YOUTUBE):
            return
        self._delivery_mode = mode_id
        if hasattr(self.gui, "state"):
            try:
                self.gui.state.automation_delivery_mode = mode_id
            except Exception:
                pass
        self._sync_delivery_ui()

    def _is_upload_mode(self) -> bool:
        return self._delivery_mode == DELIVERY_YOUTUBE

    def _is_linktree_requested(self) -> bool:
        return bool(
            self._is_upload_mode()
            and getattr(self, "chk_linktree", None)
            and self.chk_linktree.isChecked()
        )

    def _youtube_readiness(self) -> tuple[bool, str]:
        try:
            from managers.settings_manager import get_settings_manager

            settings = get_settings_manager()
            if not bool(settings.get_youtube_connected()):
                return False, "YouTube 채널이 연결되지 않았어요. 이 모드를 쓰려면 먼저 채널을 연결해 주세요."
            verification = settings.get_youtube_account_verification() or {}
            if verification.get("required") and not verification.get("ok"):
                return False, str(
                    verification.get("message")
                    or "YouTube 계정 이메일 확인이 필요해요."
                )
            info = settings.get_youtube_channel_info() or {}
            channel_name = info.get("channel_name") or info.get("title") or "연결된 채널"
            return True, f"✓ YouTube 연결됨 · {channel_name}"
        except Exception as exc:
            logger.debug("[SourcingPanel] YouTube readiness lookup failed: %s", exc)
            return False, "YouTube 연결 상태를 확인하지 못했어요. 업로드 설정을 확인해 주세요."

    def _sync_delivery_ui(self) -> None:
        upload_mode = self._is_upload_mode()
        if hasattr(self, "chk_upload"):
            self.chk_upload.blockSignals(True)
            self.chk_upload.setChecked(upload_mode)
            self.chk_upload.blockSignals(False)
        if hasattr(self, "delivery_file_card"):
            self.delivery_file_card.set_selected(not upload_mode)
        if hasattr(self, "delivery_youtube_card"):
            self.delivery_youtube_card.set_selected(upload_mode)
        if hasattr(self, "delivery_options_frame"):
            self.delivery_options_frame.setVisible(upload_mode)
        if hasattr(self, "upload_timer_frame"):
            self.upload_timer_frame.setVisible(upload_mode)
        self._sync_upload_timer_enabled()
        self._update_delivery_status()
        self._refresh_readiness()

    def _update_delivery_status(self) -> None:
        if not hasattr(self, "delivery_outcome_label"):
            # Minimal/test UIs created by integrations may not include the new
            # selector; keep the legacy control reset behavior in that case.
            if hasattr(self, "btn_start") and not self._running:
                self.btn_start.setEnabled(True)
                self.btn_start.setText("자동화 시작")
            return

        if not self._is_upload_mode():
            self.delivery_outcome_label.setText(
                "✓ 현재 저장된 음성·자막 설정으로 영상 파일까지 자동 제작합니다. 외부 서비스에는 올리지 않습니다."
            )
            self.delivery_outcome_label.setStyleSheet(f"color: {get_color('success')};")
            if hasattr(self, "btn_start") and not self._running:
                self.btn_start.setEnabled(True)
                self.btn_start.setText("영상 파일 만들기 시작")
                self.btn_start.setToolTip("")
                self._apply_button_style(disabled=False)
            return

        ready, message = self._youtube_readiness()
        if hasattr(self, "delivery_status_label"):
            self.delivery_status_label.setText(message)
            self.delivery_status_label.setStyleSheet(
                f"color: {get_color('success') if ready else get_color('warning')};"
            )
        if hasattr(self, "btn_youtube_setup"):
            self.btn_youtube_setup.setVisible(not ready)
        if self._is_linktree_requested():
            message += " · Linktree 등록은 선택이며 실패해도 업로드는 계속됩니다."
        self.delivery_outcome_label.setText(message)
        self.delivery_outcome_label.setStyleSheet(
            f"color: {get_color('success') if ready else get_color('warning')};"
        )
        if hasattr(self, "btn_start") and not self._running:
            self.btn_start.setEnabled(ready)
            self.btn_start.setText(
                "영상 만들고 YouTube에 올리기" if ready else "YouTube 연결 후 시작 가능"
            )
            self.btn_start.setToolTip("" if ready else message)
            self._apply_button_style(disabled=not ready)

    def _navigate_to_setup(self, target: str) -> None:
        """Jump to the settings/upload step (or guided dialog) that fixes a gap.

        'linktree_setup', 'ai_key', 'coupang_key'는 정식 페이지 ID가 아니라
        특정 입력칸으로 바로 데려가는 가상 타깃이다. 일반 step_id는
        gui._on_step_selected로 위임한다.
        """
        gui = self.gui

        if target == "linktree_setup":
            self._open_linktree_setup_dialog()
            return
        if target == "ai_key" and gui is not None and hasattr(gui, "open_api_key_settings"):
            try:
                gui.open_api_key_settings()
            except Exception as exc:
                logger.warning("[SourcingPanel] open API key settings failed: %s", exc)
            return
        if target == "coupang_key" and gui is not None and hasattr(gui, "open_coupang_settings"):
            try:
                gui.open_coupang_settings()
            except Exception as exc:
                logger.warning("[SourcingPanel] open Coupang settings failed: %s", exc)
            return

        if gui is not None and hasattr(gui, "_on_step_selected"):
            try:
                gui._on_step_selected(target)
            except Exception as exc:
                logger.warning("[SourcingPanel] navigate to %s failed: %s", target, exc)

    def _open_linktree_setup_dialog(self) -> None:
        """Linktree 설정으로 사용자를 보낸다.

        예전에는 팝업(LinktreeSetupDialog)을 띄웠지만, 이제 같은 3단계 안내가
        설정 → '연결 도우미' 탭에 인라인으로 들어가 있다. 따라서 설정 화면으로
        이동한 뒤 해당 탭을 선택한다. (메서드 이름은 호출부 호환을 위해 유지)"""
        gui = self.gui
        try:
            if gui is not None and hasattr(gui, "_on_step_selected"):
                gui._on_step_selected("settings")
        except Exception as exc:
            logger.warning("[SourcingPanel] navigate to settings failed: %s", exc)
        try:
            settings_tab = getattr(gui, "settings_tab", None) if gui is not None else None
            if settings_tab is not None and hasattr(settings_tab, "select_connect_tab"):
                settings_tab.select_connect_tab()
        except Exception as exc:
            logger.warning("[SourcingPanel] select connect tab failed: %s", exc)
        self._refresh_readiness()

    def _refresh_readiness(self) -> None:
        """Recompute the readiness checklist from current options + connections."""
        card = getattr(self, "readiness_card", None)
        if card is None:
            return
        youtube_required = self._is_upload_mode()
        show_linktree = self._is_linktree_requested()
        try:
            card.refresh(
                youtube_required=youtube_required,
                linktree_required=False,
                show_youtube=youtube_required,
                show_linktree=show_linktree,
                mode_label="upload" if youtube_required else "file_only",
            )
        except Exception as exc:
            logger.debug("[SourcingPanel] readiness refresh skipped: %s", exc)

    def showEvent(self, event):
        """Refresh readiness whenever the panel becomes visible."""
        super().showEvent(event)
        self._sync_delivery_ui()

    def _save_match_policy(self, *_args):
        """Compatibility no-op: product verification is automatic, not a UI setting."""
        return None

    def refresh_match_policy(self):
        """Compatibility no-op retained for settings synchronization callers."""
        return None

    def _match_threshold_score(self) -> float:
        # Keep the safety gate internal. Users expect the correct product and
        # should not have to understand or tune a model-specific percentage.
        return 0.9

    def _load_upload_interval_hours(self) -> int:
        try:
            from managers.settings_manager import get_settings_manager

            minutes = int(get_settings_manager().get_youtube_upload_interval())
        except Exception as exc:
            logger.warning("[SourcingPanel] Failed to load upload interval: %s", exc)
            minutes = 240
        return max(1, min(4, int(round(minutes / 60)) or 1))

    def _on_upload_interval_changed(self, hours: int):
        interval_minutes = max(1, min(4, int(hours))) * 60
        try:
            from managers.settings_manager import get_settings_manager

            get_settings_manager().set_youtube_upload_interval(interval_minutes)
        except Exception as exc:
            logger.warning("[SourcingPanel] Failed to save upload interval: %s", exc)

        yt_manager = getattr(self.gui, "youtube_manager", None)
        if yt_manager and hasattr(yt_manager, "set_upload_interval"):
            try:
                yt_manager.set_upload_interval(interval_minutes)
            except Exception as exc:
                logger.warning("[SourcingPanel] YouTube interval sync failed: %s", exc)

        if hasattr(self.gui, "state"):
            try:
                self.gui.state.youtube_upload_interval_minutes = interval_minutes
            except Exception:
                pass
        self._update_upload_timer_summary()

    def _sync_upload_timer_enabled(self):
        enabled = bool(
            hasattr(self, "chk_upload")
            and self.chk_upload.isChecked()
        )
        if hasattr(self, "upload_interval_spin"):
            self.upload_interval_spin.setEnabled(enabled)
        if hasattr(self, "upload_timer_summary"):
            self.upload_timer_summary.setEnabled(enabled)
        self._update_upload_timer_summary()

    def _current_coupang_link_count(
        self,
        parse_result: Optional[PartnerLinkParseResult] = None,
    ) -> int:
        if parse_result is not None:
            return len(parse_result.links)
        if hasattr(self, "partner_links_input"):
            return len(
                parse_coupang_partner_links(
                    self.partner_links_input.toPlainText()
                ).links
            )
        if not hasattr(self, "url_input"):
            return 0
        return len(parse_coupang_partner_links(self.url_input.text()).links)

    def _update_next_links_count(
        self,
        parse_result: Optional[PartnerLinkParseResult] = None,
    ):
        total_count = self._current_coupang_link_count(parse_result)
        if hasattr(self, "next_links_count_label"):
            self.next_links_count_label.setText(f"{total_count}개")
        self._update_upload_timer_summary(total_count=total_count)

    def _update_upload_timer_summary(self, total_count: Optional[int] = None):
        if not hasattr(self, "upload_timer_summary"):
            return
        hours = (
            self.upload_interval_spin.value()
            if hasattr(self, "upload_interval_spin")
            else self._load_upload_interval_hours()
        )
        if total_count is None:
            total_count = self._current_coupang_link_count()
        if not (hasattr(self, "chk_upload") and self.chk_upload.isChecked()):
            self.upload_timer_summary.setText("YouTube 자동 업로드를 켜면 링크마다 타이머가 적용됩니다.")
            return
        if total_count <= 0:
            self.upload_timer_summary.setText(f"링크를 넣으면 각 업로드가 {hours}시간 간격으로 예약됩니다.")
            return
        if total_count == 1:
            self.upload_timer_summary.setText(f"현재 링크 1개 · 업로드 간격 {hours}시간")
            return
        last_after_hours = (total_count - 1) * hours
        self.upload_timer_summary.setText(
            f"링크마다 {hours}시간 간격 · 총 {total_count}개면 마지막 업로드까지 약 {last_after_hours}시간"
        )

    def _sync_next_links_enabled(self):
        """Compatibility wrapper for callers from older settings screens."""
        self._update_next_links_count()

    @staticmethod
    def _extract_partner_links(raw: str) -> List[str]:
        return extract_coupang_partner_links(raw)

    def _sync_partner_links_from_input(self) -> None:
        if not hasattr(self, "partner_links_input"):
            return
        parse_result = parse_coupang_partner_links(
            self.partner_links_input.toPlainText()
        )
        links = list(parse_result.links)
        self._partner_links_parse_result = parse_result
        if not self._running and not getattr(self, "_partner_batch_active", False):
            self.url_input.setText(links[0] if links else "")
            self.next_links_input.setPlainText("\n".join(links[1:]))
        self._update_next_links_count(parse_result)

    def _set_partner_links_display(
        self,
        links: List[str],
        parse_result: Optional[PartnerLinkParseResult] = None,
    ) -> None:
        if not hasattr(self, "partner_links_input"):
            return
        self.partner_links_input.blockSignals(True)
        self.partner_links_input.setPlainText("\n".join(links))
        self.partner_links_input.blockSignals(False)
        if parse_result is None:
            parse_result = parse_coupang_partner_links("\n".join(links))
        self._partner_links_parse_result = parse_result
        self._update_next_links_count(parse_result)

    def _extract_next_links(self) -> List[str]:
        if not hasattr(self, "next_links_input"):
            return []
        return self._extract_partner_links(self.next_links_input.toPlainText())

    def _pop_next_sourcing_url(self) -> Optional[str]:
        links = self._extract_next_links()
        if not links:
            return None
        next_url = links[0]
        remaining = links[1:]
        if hasattr(self, "next_links_input"):
            self.next_links_input.blockSignals(True)
            self.next_links_input.setPlainText("\n".join(remaining))
            self.next_links_input.blockSignals(False)
        self.url_input.setText(next_url)
        self._set_partner_links_display([next_url, *remaining])
        self._update_next_links_count()
        return next_url

    def _is_match_gate_failure(self, pipeline) -> bool:
        return getattr(pipeline, "match_status", "") in {"below_threshold", "not_found"}

    def _handle_match_gate_failure(self, pipeline, report: dict):
        message = (
            "상품 영상을 찾지 못했어요.\n"
            "잠시 후 다시 시도하거나 다른 상품 링크를 사용해 주세요."
        )

        logger.info(
            "[SourcingPanel] match gate stopped the run: status=%s best=%s threshold=%s",
            getattr(pipeline, "match_status", ""),
            getattr(pipeline, "best_similarity_score", None),
            getattr(pipeline, "min_similarity_score", None),
        )

        if hasattr(self.gui, "state"):
            self.gui.state.sourcing_result = report

        next_url = self._pop_next_sourcing_url()
        if next_url:
            self.results_label.setText(message + "\n\n다음 상품으로 자동으로 넘어갈게요.")
            self.results_label.setStyleSheet(f"color: {get_color('warning')};")
            QTimer.singleShot(800, self._on_start_clicked)
            return

        self.results_label.setText(message)
        self.results_label.setStyleSheet(f"color: {get_color('error')};")
        try:
            from ui.components.custom_dialog import show_warning

            show_warning(self, "상품 영상을 찾지 못했어요", message)
        except Exception:
            pass

    def _apply_button_style(self, disabled: bool = False):
        ds = self.ds
        if disabled:
            self.btn_start.setStyleSheet(f"""
                QPushButton {{
                    background-color: {get_color('text_muted')};
                    color: {get_color('background')};
                    border: none;
                    border-radius: {ds.radius.md}px;
                }}
            """)
        else:
            self.btn_start.setStyleSheet(f"""
                QPushButton {{
                    background-color: {get_color('primary')};
                    color: white;
                    border: none;
                    border-radius: {ds.radius.md}px;
                }}
                QPushButton:hover {{
                    background-color: {get_color('primary_hover')};
                }}
            """)

    def _validate_linktree_publish_ready(self) -> bool:
        """Compatibility preflight: Linktree is optional and never blocks."""
        if not self._is_linktree_requested():
            return True
        try:
            from managers.linktree_manager import get_linktree_manager

            ok, message = get_linktree_manager().require_connected_for_publish()
            if not ok:
                logger.info("[SourcingPanel] Optional Linktree step will be skipped: %s", message)
        except Exception as exc:
            logger.warning("[SourcingPanel] Optional Linktree preflight skipped: %s", exc)
        return True

    def _validate_youtube_upload_ready(self) -> bool:
        """Safety preflight for the explicitly selected YouTube delivery mode."""
        if not self._is_upload_mode():
            return True
        ready, message = self._youtube_readiness()
        if ready:
            return True

        self.results_label.setText(message)
        self.results_label.setStyleSheet(f"color: {get_color('warning')};")
        self._sync_delivery_ui()
        return False

    def _current_sourcing_method(self) -> str:
        # Full automation has one automatic sourcing path. The implementation
        # choice is deliberately not exposed as a customer-facing mode.
        return "platform_video"

    def _on_start_clicked(self):
        if bool(getattr(self.gui, "offline_mode", False)):
            self.results_label.setText(
                "오프라인 설정 모드에서는 영상 제작을 시작할 수 없습니다. 다시 로그인해 주세요."
            )
            self.results_label.setStyleSheet(f"color: {get_color('warning')};")
            return
        self._on_start_platform_video()

    def _on_start_platform_video(self):
        """Create videos for the entered partner links in sequence."""
        if not getattr(self, "_partner_batch_active", False):
            raw_links = (
                self.partner_links_input.toPlainText()
                if hasattr(self, "partner_links_input")
                else self.url_input.text()
            )
            parse_result = parse_coupang_partner_links(raw_links)
            if parse_result.reason_code != "ok":
                self.results_label.setText(
                    self._partner_link_error_message(parse_result)
                )
                self.results_label.setStyleSheet(f"color: {get_color('error')};")
                return
            links = list(parse_result.links)
            url = links[0]
            if hasattr(self, "partner_links_input") and hasattr(self, "next_links_input"):
                self._partner_batch_active = True
                self._partner_batch_total = len(links)
                self._partner_batch_completed = 0
                self.url_input.setText(url)
                self.next_links_input.setPlainText("\n".join(links[1:]))
                self._set_partner_links_display(links, parse_result=parse_result)
        else:
            parse_result = parse_coupang_partner_links(self.url_input.text())
            if parse_result.reason_code != "ok" or len(parse_result.links) != 1:
                self._partner_batch_active = False
                self.results_label.setText(
                    self._partner_link_error_message(parse_result)
                )
                self.results_label.setStyleSheet(f"color: {get_color('error')};")
                return
            url = parse_result.links[0]
        self.url_input.setText(url)
        if self._running:
            return
        # YouTube 모드에서만 채널 연결을 필수로 검증한다. Linktree는 선택이며
        # 연결/발행 실패가 제작이나 업로드를 막지 않는다.
        if not self._validate_youtube_upload_ready():
            self._partner_batch_active = False
            return

        self._running = True
        self._platform_batch_can_continue = False
        self._platform_item_succeeded = False
        if hasattr(self, "partner_links_input"):
            self.partner_links_input.setEnabled(False)
        self._set_search_recovery_visible(False)
        self.btn_start.setEnabled(False)
        self.btn_start.setText("영상 찾아 만드는 중...")
        self._apply_button_style(disabled=True)
        self._reset_step_indicators()
        self.results_label.setText(
            "상품 영상을 찾고 있어요..."
        )
        self.results_label.setStyleSheet(f"color: {get_color('text_muted')};")

        min_similarity_score = self._match_threshold_score()
        linktree_enabled = self._is_linktree_requested()
        upload_enabled = self._is_upload_mode()
        gemini_client = getattr(self.gui, "genai_client", None)
        youtube_manager = getattr(self.gui, "youtube_manager", None)
        user_id = extract_user_id(getattr(self.gui, "login_data", None))
        if not user_id:
            self._reset_platform_controls()
            self.results_label.setText("사용자 인증 정보를 확인할 수 없습니다. 다시 로그인해 주세요.")
            self.results_label.setStyleSheet(f"color: {get_color('error')};")
            return
        work_job_key = f"platform:{url}"
        threading.Thread(
            target=self._run_platform_pipeline,
            args=(
                url,
                min_similarity_score,
                linktree_enabled,
                upload_enabled,
                gemini_client,
                youtube_manager,
                str(user_id),
                work_job_key,
            ),
            daemon=True,
        ).start()

    def _run_platform_pipeline(
        self,
        coupang_url: str,
        min_similarity_score: float,
        linktree_enabled: bool,
        upload_enabled: bool,
        gemini_client,
        youtube_manager,
        user_id: str,
        work_job_key: str,
    ):
        """백그라운드: 쿠팡 링크 → (core.platform_pipeline) 소싱·딥링크·재편집 → 링크트리 → YouTube 큐."""
        import asyncio as _aio
        from core.sourcing.platform_pipeline import run_platform_sourcing

        def progress(step_id: str, msg: str, pct: float):
            try:
                self._on_pipeline_progress(step_id, msg, pct)
            except Exception:
                pass

        try:
            from managers.settings_manager import get_settings_manager
            platforms = get_settings_manager().get_platform_video_sources()
        except Exception:
            platforms = None

        work_reservation = None
        work_reserved = False
        work_finalized = False
        loop = _aio.new_event_loop()
        try:
            work_reservation, reservation = DurableWorkReservation.begin(
                user_id, work_job_key
            )
            if not reservation.get("success"):
                self._safe_set_results(
                    str(
                        reservation.get("message")
                        or "작업 사용량을 예약하지 못해 자동 제작을 시작하지 않았어요."
                    )
                )
                return
            if reservation.get("reservation_status") == "completed":
                work_finalized = True
                self._platform_batch_can_continue = True
                self._platform_item_succeeded = True
                if reservation.get("recovered_pending_delivery"):
                    work_reserved = False
                    self._safe_set_results(
                        "영상 생성과 사용량 확정은 완료됐지만 전달 완료 여부가 불명확해요. "
                        "중복 제작·발행 방지를 위해 자동 재실행하지 않았습니다. 저장된 영상을 확인해 주세요."
                    )
                    return
                else:
                    self._safe_set_results(
                        "이 작업은 이전 실행에서 이미 완료 처리되었습니다. 중복 제작하지 않았어요."
                    )
                    return
            else:
                work_reserved = True

            def finalize_before_commit(_video_path: str) -> None:
                nonlocal work_finalized, work_reserved
                if work_reservation.finalized:
                    return
                work_reservation.mark_pending_finalize()
                transition = work_reservation.finalize()
                if not transition.get("success"):
                    raise RuntimeError(
                        str(
                            transition.get("message")
                            or "완성 영상의 사용량 확정 응답을 기다리고 있습니다."
                        )
                    )
                work_finalized = True
                work_reserved = False

            report = loop.run_until_complete(run_platform_sourcing(
                coupang_url,
                progress=progress,
                platforms=platforms,
                gemini_client=gemini_client,
                min_similarity_score=min_similarity_score,
                before_commit=finalize_before_commit,
                allow_image_fallback=False,
            ))
            if not report.get("ok"):
                self._platform_batch_can_continue = bool(
                    (report.get("failure") or {}).get("can_choose_other_product", True)
                )
                self._safe_set_platform_failure(report)
                return

            product_name = str((report.get("product_info") or {}).get("name") or "")
            hit = report.get("hit") or {}
            edited = report.get("final_video") or ""
            deep_link = str(report.get("deep_link") or "")
            # 수동 링크 > API 딥링크 > 원본 — platform_pipeline이 이미 결정.
            purchase_url = str(report.get("purchase_url") or deep_link or coupang_url)

            # A usable edited file exists. Persist recovery intent and complete
            # quota finalization before Linktree or any upload queue is touched.
            if not work_reservation.finalized:
                work_reservation.mark_pending_finalize()
                finalized = work_reservation.finalize()
                if not finalized.get("success"):
                    self._safe_set_results(
                        str(
                            finalized.get("message")
                            or "영상은 완성했지만 사용량 확정 응답이 없어 발행하지 않고 복구 대기합니다."
                        )
                    )
                    return
            work_finalized = True
            work_reserved = False

            publish_safe = (
                report.get("auto_publish_safe") is True
                and report.get("requires_review") is False
            )
            review_only = not publish_safe
            if review_only:
                self._platform_batch_can_continue = True
                self._platform_item_succeeded = True
                progress(
                    "review_only",
                    "검토용 영상 파일 완료 · 자동 게시 건너뜀",
                    1.0,
                )
                work_reservation.complete_delivery()
                self._safe_set_results(
                    "검토가 필요한 영상 파일을 만들었어요. 자동 게시는 진행하지 않았습니다.\n"
                    f"파일: {edited}"
                )
                return

            # ── 링크트리 발행(체크 시) — 기존 coupang 흐름과 동일 정책 ──
            linktree_url = ""
            if linktree_enabled:
                progress("linktree_publish", "링크트리 발행 중...", 0.1)
                try:
                    from managers.linktree_manager import get_linktree_manager
                    lm = get_linktree_manager()
                    if lm.is_connected():
                        ok = lm.publish_coupang_link(
                            product_name=product_name,
                            coupang_url=purchase_url,
                            source_url=coupang_url,
                        )
                        if ok:
                            linktree_url = lm.get_profile_url()
                        progress("linktree_publish",
                                 "링크트리 발행 완료" if ok else "링크트리 발행 실패", 1.0)
                        if not ok:
                            logger.warning(
                                "[Sourcing] Linktree publish failed; continuing without Linktree"
                            )
                    else:
                        progress("linktree_publish", "링크트리 미연결 · 이 단계만 건너뜀", 1.0)
                        logger.info(
                            "[Sourcing] Linktree is not connected; continuing without Linktree"
                        )
                except Exception as e:
                    logger.warning("[Sourcing] platform linktree publish 실패: %s", e)
                    progress("linktree_publish", "링크트리 오류 · 이 단계만 건너뜀", 1.0)

            if upload_enabled:
                if youtube_manager is None or not hasattr(
                    youtube_manager, "add_to_upload_queue"
                ):
                    self._safe_set_results("YouTube 업로드 관리자를 사용할 수 없어 큐 등록을 중단했어요.")
                    return
                queued = youtube_manager.add_to_upload_queue(
                    video_path=edited, title="", description="",
                    product_info=product_name,
                    source_url=coupang_url,
                    marketplace_source_url=str(
                        report.get("selected_source_url") or hit.get("video_url") or ""
                    ),
                    coupang_deep_link=deep_link,
                    linktree_url=linktree_url,
                    render_integrity=report.get("render_integrity") or {"ok": False, "source": "platform_video"},
                    render_integrity_required=True,
                )
                if queued is not True:
                    self._safe_set_results(
                        "YouTube 업로드 큐가 영상을 승인하지 않아 전달 복구 상태로 보관했어요."
                    )
                    return
                progress("upload", "업로드 큐 등록 완료", 1.0)
                result_tail = "재편집·업로드 큐 등록했어요."
            else:
                progress("upload", "YouTube 자동 업로드 꺼짐 — 제작만 완료", 1.0)
                result_tail = "재편집을 완료했어요. YouTube 자동 업로드는 꺼져 있어요."

            work_reservation.complete_delivery()
            self._platform_batch_can_continue = True
            self._platform_item_succeeded = True
            self._safe_set_results(
                f"'{product_name[:20]}' 상품 영상 제작을 완료했어요. {result_tail}"
            )
        except Exception as e:
            logger.warning("[Sourcing] platform pipeline 실패: %s", e)
            self._safe_set_platform_failure({
                "error": (
                    "상품 검색 처리 중 오류가 발생했어요.\n"
                    "원인: 상품 검색을 완료하지 못했어요.\n"
                    "해결: 같은 상품을 다시 검색해 주세요. 계속 실패하면 다른 상품을 선택해 주세요."
                ),
                "failure": {
                    "code": "unexpected_search_error",
                    "cause": "상품 검색을 완료하지 못했어요.",
                    "action": "같은 상품을 다시 검색하거나 다른 상품을 선택해 주세요.",
                    "retriable": True,
                    "can_choose_other_product": True,
                },
            })
        finally:
            try:
                loop.close()
            except Exception:
                pass
            if (
                work_reserved
                and not work_finalized
                and work_reservation is not None
                and work_reservation.can_release()
            ):
                work_reservation.release()
            self._reset_start_button()

    def _safe_set_results(self, text: str):
        """Queue a platform result update onto the Qt UI thread."""
        self.platform_result_ready.emit(
            sanitize_user_message(text, fallback="작업 결과를 확인하지 못했어요.")
        )

    def _safe_set_platform_failure(self, report: dict):
        """Queue a structured search failure onto the Qt UI thread."""
        self.platform_failure_ready.emit(dict(report or {}))

    def _set_platform_result(self, text: str):
        self._set_search_recovery_visible(False)
        self.results_label.setText(
            sanitize_user_message(text, fallback="작업 결과를 확인하지 못했어요.")
        )
        self.results_label.setStyleSheet(f"color: {get_color('text_secondary')};")

    def _set_platform_failure(self, report: dict):
        failure = dict((report or {}).get("failure") or {})
        report_path = str((report or {}).get("report_path") or "").strip()
        if report_path:
            logger.info("[SourcingPanel] failure report: %s", report_path)
        if failure:
            logger.info(
                "[SourcingPanel] search failure details: code=%s diagnostics=%s",
                failure.get("code"),
                failure.get("diagnostics"),
            )
        self.results_label.setText(
            sanitize_user_message(
                {
                    "reason": failure.get("code") or "no_search_results",
                    "message": (report or {}).get("error") or "",
                },
                fallback="상품 영상을 찾지 못했어요. 잠시 후 다시 시도해 주세요.",
            )
        )
        self.results_label.setStyleSheet(f"color: {get_color('error')};")
        self._set_search_recovery_visible(True)

    def _set_search_recovery_visible(self, visible: bool) -> None:
        if hasattr(self, "search_recovery_frame"):
            self.search_recovery_frame.setVisible(bool(visible))

    @staticmethod
    def _partner_link_error_message(
        value: object | PartnerLinkParseResult,
    ) -> str:
        parsed = (
            value
            if isinstance(value, PartnerLinkParseResult)
            else parse_coupang_partner_links(value)
        )
        if parsed.reason_code == "empty":
            return "쿠팡 파트너스 상품 링크를 한 줄에 하나씩 붙여넣어 주세요."
        if parsed.reason_code == "normal_coupang_product":
            return (
                "일반 쿠팡 상품 링크는 사용할 수 없습니다.\n"
                "원인: 이 주소에는 쿠팡 파트너스 수익 추적 정보가 없습니다.\n"
                "해결: 쿠팡 파트너스에서 생성한 https://link.coupang.com/... 링크를 입력해 주세요."
            )
        if parsed.reason_code == "mixed_http_urls":
            return (
                "쿠팡 파트너스 링크와 함께 다른 주소 또는 잘못된 주소가 들어 있습니다.\n"
                "해결: 공식 파트너스 단축 링크만 남기고 다시 입력해 주세요."
            )
        if parsed.reason_code == "input_too_large":
            return (
                "붙여넣은 내용이 너무 깁니다.\n"
                "해결: 쿠팡 파트너스 링크만 나누어 입력해 주세요."
            )
        if parsed.reason_code == "too_many_links":
            return (
                f"한 번에 {MAX_PARTNER_LINK_HTTP_TOKENS}개를 초과하는 링크는 처리할 수 없습니다.\n"
                "해결: 링크 목록을 나누어 입력해 주세요."
            )
        if parsed.reason_code == "invalid_partner_link":
            return (
                "쿠팡 파트너스 단축 링크 형식이 올바르지 않습니다.\n"
                "해결: 링크 뒤의 추가 경로, 물음표·# 문자 또는 숨은 문자를 제거해 주세요."
            )
        return (
            "지원하지 않는 웹 주소입니다.\n"
            "해결: https://link.coupang.com/... 형식의 공식 파트너스 링크만 입력해 주세요."
        )

    def _retry_last_search(self) -> None:
        if self._running:
            return
        self._set_search_recovery_visible(False)
        self._on_start_clicked()

    def _choose_other_product(self) -> None:
        if self._running:
            return
        next_url = self._pop_next_sourcing_url()
        self.url_input.setText(next_url or "")
        if hasattr(self, "partner_links_input"):
            self.partner_links_input.setFocus()
        else:
            self.url_input.setFocus()
        self._set_search_recovery_visible(False)
        if next_url:
            self.results_label.setText(
                "다음 상품의 파트너스 링크를 선택했습니다. 내용을 확인하고 자동 만들기를 시작해 주세요."
            )
        else:
            self.results_label.setText(
                "다른 상품을 선택해 쿠팡 파트너스 링크를 붙여넣어 주세요."
            )
        self.results_label.setStyleSheet(f"color: {get_color('text_secondary')};")

    def _reset_start_button(self):
        """Queue platform controls reset onto the Qt UI thread."""
        self.platform_reset_requested.emit()

    def _reset_platform_controls(self):
        self._running = False
        if getattr(self, "_partner_batch_active", False):
            self._partner_batch_completed += 1
            pending = self._extract_next_links()
            if self._platform_batch_can_continue and pending:
                self._pop_next_sourcing_url()
                self._update_delivery_status()
                self.btn_start.setEnabled(False)
                self.btn_start.setText(
                    f"다음 상품 준비 중 ({self._partner_batch_completed + 1}/{self._partner_batch_total})"
                )
                QTimer.singleShot(500, self._on_start_clicked)
                return

            completed = self._partner_batch_completed
            total = self._partner_batch_total
            self._partner_batch_active = False
            if hasattr(self, "partner_links_input"):
                self.partner_links_input.setEnabled(True)

            if self._platform_batch_can_continue and not pending and self._platform_item_succeeded:
                self.url_input.clear()
                self.next_links_input.clear()
                self._set_partner_links_display([])
                summary = f"입력한 상품 {total}개의 처리를 마쳤어요."
            elif self._platform_batch_can_continue and not pending:
                summary = (
                    f"입력한 상품 {total}개를 모두 확인했어요. "
                    "영상을 찾지 못한 상품은 링크를 남겨 두었습니다."
                )
            else:
                summary = (
                    f"상품 {completed}/{total} 처리 후 멈췄어요. "
                    "안내 내용을 확인한 뒤 다시 시작해 주세요."
                )
            current_text = self.results_label.text().strip()
            if summary not in current_text:
                self.results_label.setText(
                    f"{current_text}\n\n{summary}" if current_text else summary
                )
        self._update_delivery_status()

    def _run_pipeline(self, coupang_url: str, min_similarity_score: float):
        """Run sourcing pipeline in background thread with its own event loop."""
        from core.sourcing.pipeline import SourcingPipeline

        output_dir = os.path.join(
            os.path.expanduser("~"), ".ssmaker", "sourcing_output"
        )

        gemini_client = getattr(self.gui, 'genai_client', None)
        pipeline = SourcingPipeline(
            coupang_url=coupang_url,
            output_dir=output_dir,
            on_progress=self._on_pipeline_progress,
            gemini_client=gemini_client,
            min_similarity_score=min_similarity_score,
            enforce_min_similarity=True,
            allow_product_image_fallback=False,
        )
        self._pipeline = pipeline

        loop = asyncio.new_event_loop()
        try:
            success = loop.run_until_complete(pipeline.run_sourcing())
        except Exception as e:
            logger.error("[SourcingPanel] Pipeline error: %s", e, exc_info=True)
            success = False
            pipeline.error = str(e)
        finally:
            loop.close()

        # Emit signal so UI updates run on the main thread
        self.pipeline_finished.emit(success, pipeline)

    def _reset_step_indicators(self):
        """페이지 안(숨김) 인디케이터와 통일된 좌측 하단 패널을 모두 pending으로 초기화."""
        for ind in self._step_indicators.values():
            ind.set_state("pending", "")
        pp = getattr(self.gui, "progress_panel", None) if self.gui else None
        if pp is not None and hasattr(pp, "update_step_status"):
            try:
                from core.sourcing.pipeline import SourcingPipeline
                for sid, _label in SourcingPipeline.STEPS:
                    pp.update_step_status(sid, "pending", 0)
            except Exception:
                pass

    def _on_pipeline_progress(self, step_id: str, message: str, pct: float):
        """Called from pipeline thread; forwards to UI thread by signal."""
        self.pipeline_progress.emit(step_id, message, pct)

    def _update_step(self, step_id: str, message: str, pct: float):
        """Update the (hidden) in-page indicator and mirror progress to the
        unified left-bottom progress panel (풀 자동화 진행 표시 통일)."""
        is_error = (pct <= 0 and any(kw in message for kw in ["실패", "오류", "없습니다", "못"]))
        safe_message = sanitize_user_message(
            message,
            fallback=(
                "이 단계를 완료하지 못했어요."
                if is_error
                else "작업을 진행하고 있어요."
            ),
        )
        if pct >= 1.0:
            state = "completed"
        elif is_error:
            state = "error"
        else:
            state = "in_progress"

        indicator = self._step_indicators.get(step_id)
        if indicator:
            indicator.set_state(state, safe_message)

        pp = getattr(self.gui, "progress_panel", None) if self.gui else None
        if pp is not None:
            panel_status = {"completed": "completed", "error": "error"}.get(state, "active")
            try:
                if hasattr(pp, "update_step_status"):
                    pp.update_step_status(step_id, panel_status,
                                          int(max(0.0, min(pct, 1.0)) * 100))
                if hasattr(pp, "set_current_task") and safe_message:
                    pp.set_current_task(
                        safe_message,
                        panel_status if panel_status in ("completed", "error") else "active")
            except Exception:
                pass

    def _on_pipeline_done(self, success: bool, pipeline):
        """Pipeline finished - update UI and emit results."""
        self._running = False
        self._update_delivery_status()

        report = pipeline.get_report()

        if not success and self._is_match_gate_failure(pipeline):
            self._handle_match_gate_failure(pipeline, report)
            return

        if success and pipeline.sourced_products:
            pi = pipeline.product_info or {}
            lines = [
                "상품 영상을 찾았어요.",
                f"상품: {pi.get('name', '상품')[:50]}",
                f"영상: {len(pipeline.sourced_products)}개",
            ]
            for i, sp in enumerate(pipeline.sourced_products):
                lines.append(f"저장 파일 {i + 1}: {sp['video_file']}")

            self.results_label.setText("\n".join(lines))
            self.results_label.setStyleSheet(f"color: {get_color('text_primary')};")

            # Store in app state
            report["automation_delivery_mode"] = self._delivery_mode
            report["linktree_auto_publish_requested"] = self._is_linktree_requested()
            report["youtube_auto_upload_requested"] = self._is_upload_mode()
            if hasattr(self.gui, 'state'):
                self.gui.state.sourcing_result = report

            # Feed sourced videos into batch queue as local:// URLs
            self._enqueue_sourced_videos(pipeline)

            self.sourcing_completed.emit(report)
        else:
            error_msg = pipeline.error or "자동 만들기에 실패했어요."
            logger.warning("[SourcingPanel] automatic sourcing failed: %s", error_msg)
            self._set_platform_failure({
                "error": "상품 영상을 찾지 못했어요.",
                "failure": {
                    "code": "no_search_results",
                    "cause": error_msg,
                    "retriable": True,
                    "can_choose_other_product": True,
                },
            })

    def _enqueue_sourced_videos(self, pipeline):
        """Add sourced video files to the processing queue."""
        source_items = [
            item for item in (pipeline.sourced_products or [])
            if os.path.isfile(str(item.get("video_file", "")))
        ]
        if not source_items:
            logger.warning("[SourcingPanel] No video files to enqueue")
            self.results_label.setText(
                self.results_label.text() + "\n\n※ 받아 온 영상이 없어 만들 목록에 담지 못했어요."
            )
            return

        if self._is_upload_mode():
            safe_items = [
                item for item in source_items
                if item.get("auto_publish_safe") is True
                and item.get("requires_review") is False
            ]
            if not safe_items:
                logger.warning("[SourcingPanel] Auto-upload blocked: only image fallback videos were sourced")
                self.results_label.setText(
                    self.results_label.text()
                    + "\n\n※ 실제 상품 영상을 찾지 못해, 쿠팡 상품 이미지로만 영상을 만들었어요."
                    + "\n※ 직접 확인하기 전에는 YouTube 자동 올리기와 Linktree 등록을 하지 않아요."
                )
                return
            if len(safe_items) < len(source_items):
                logger.warning("[SourcingPanel] Skipping %d review-only fallback video(s)", len(source_items) - len(safe_items))
            source_items = safe_items

        # Add as local:// URLs to the queue
        queue_mgr = getattr(self.gui, 'queue_manager', None)
        enqueued = 0

        if not queue_mgr or not hasattr(queue_mgr, 'add_url_to_queue'):
            logger.error("[SourcingPanel] queue_manager not available, cannot enqueue videos")
            self.results_label.setText(
                self.results_label.text() + "\n\n※ 만들 목록 기능을 찾지 못했어요. 영상을 직접 추가해 주세요."
            )
            return

        for item in source_items:
            vpath = str(item.get("video_file", ""))
            if not os.path.isfile(vpath):
                logger.warning("[SourcingPanel] Video file missing: %s", vpath)
                continue
            local_url = f"local://{vpath}"
            try:
                result = queue_mgr.add_url_to_queue(local_url)
                if result is not False:  # add_url_to_queue returns None or True on success
                    enqueued += 1
                    logger.info("[SourcingPanel] Enqueued: %s", os.path.basename(vpath))
                    # Enforce one-link policy consistently across all modes.
                    break
                else:
                    logger.warning("[SourcingPanel] Failed to enqueue: %s", os.path.basename(vpath))
            except Exception as e:
                logger.error("[SourcingPanel] Enqueue error for %s: %s", os.path.basename(vpath), e)

        if enqueued > 0:
            logger.info("[SourcingPanel] Total %d videos enqueued", enqueued)
            if len(source_items) > 1:
                logger.info("[SourcingPanel] 단일 작업 정책: 첫 번째 유효 영상만 목록에 추가")

            # Linktree auto-publish (prefer Partners deep link, fall back to
            # the original Coupang URL so the action is not silently skipped
            # when Coupang Partners keys are not configured yet).
            publish_url = pipeline.deep_link or pipeline.coupang_url
            if self._is_linktree_requested() and publish_url and not self._is_upload_mode():
                try:
                    from managers.linktree_manager import get_linktree_manager
                    lm = get_linktree_manager()
                    if lm.is_connected():
                        product_name = (pipeline.product_info or {}).get("name", "")
                        ok = lm.publish_coupang_link(
                            product_name=product_name,
                            coupang_url=publish_url,
                            source_url=pipeline.coupang_url,
                        )
                        logger.info("[SourcingPanel] Linktree publish: %s", "성공" if ok else "실패")
                    else:
                        logger.info("[SourcingPanel] Linktree 미연결 - 자동 발행 건너뜀")
                except Exception as e:
                    logger.warning("[SourcingPanel] Linktree publish error: %s", e)
            elif self._is_linktree_requested() and publish_url:
                logger.info("[SourcingPanel] Linktree publish deferred until render integrity passes")

            # Both delivery modes are fully automatic through final rendering.
            # The selected scope only controls whether the completed file is
            # also handed to the YouTube upload queue.
            upload_enabled = self._is_upload_mode()
            logger.info(
                "[SourcingPanel] Full automation render start (delivery=%s)",
                self._delivery_mode,
            )
            self._set_youtube_auto_upload_for_pipeline(upload_enabled)
            if hasattr(self.gui, '_on_step_selected'):
                QTimer.singleShot(500, lambda: self.gui._on_step_selected('queue'))
            if hasattr(self.gui, 'start_batch_processing'):
                QTimer.singleShot(1000, self.gui.start_batch_processing)
        else:
            logger.warning("[SourcingPanel] No videos were successfully enqueued")
            self.results_label.setText(
                self.results_label.text() + "\n\n※ 만들 목록에 담지 못했어요. 영상 파일을 확인해 주세요."
            )

    def _set_youtube_auto_upload_for_pipeline(self, enabled: bool):
        """Enable upload for this run without disabling the user's global setting."""
        try:
            from managers.settings_manager import get_settings_manager

            settings = get_settings_manager()
            yt_manager = getattr(self.gui, "youtube_manager", None)
            if not enabled:
                logger.info(
                    "[SourcingPanel] External delivery disabled for this file-only run"
                )
                return

            settings.set_youtube_auto_upload(True)
            if yt_manager and hasattr(yt_manager, "set_upload_interval"):
                try:
                    yt_manager.set_upload_interval(settings.get_youtube_upload_interval())
                except Exception:
                    pass
            if yt_manager and hasattr(yt_manager, "set_upload_enabled"):
                yt_manager.set_upload_enabled(True)
                logger.info("[SourcingPanel] YouTube auto-upload enabled for this run")
        except Exception as exc:
            logger.warning("[SourcingPanel] Failed to sync YouTube auto-upload: %s", exc)

    def _enable_youtube_auto_upload_for_pipeline(self):
        """Backward-compatible wrapper for older tests/integrations."""
        self._set_youtube_auto_upload_for_pipeline(True)

    def get_sourcing_result(self) -> Optional[dict]:
        """Return last pipeline report or None."""
        if self._pipeline:
            return self._pipeline.get_report()
        return None
