"""
Sourcing Panel - Mode 3 (전체 자동화) UI.
Coupang link input → progress display → results.
"""
from __future__ import annotations

import asyncio
import os
import re
import threading
from typing import List, Optional

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QWidget, QCheckBox, QScrollArea, QSizePolicy,
    QTextEdit, QSpinBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from ui.design_system_v2 import get_design_system, get_color, checkbox_qss
from ui.components.automation_readiness import AutomationReadinessCard
from utils.logging_config import get_logger

logger = get_logger(__name__)


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
            self.status_label.setText(message[:60])

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

    def __init__(self, parent, gui, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.ds = get_design_system()
        self.theme_manager = theme_manager
        self._pipeline = None
        self._running = False
        self._step_indicators = {}
        self.pipeline_progress.connect(self._update_step)
        self.pipeline_finished.connect(self._on_pipeline_done)
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

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(ds.spacing.space_6, ds.spacing.space_4, ds.spacing.space_6, ds.spacing.space_4)
        main_layout.setSpacing(ds.spacing.space_4)

        # ── Full-automation readiness checklist (top) ──
        # 사용자가 '소싱 시작'을 누르기 전에 AI·YouTube·Linktree·쿠팡 연동이
        # 준비됐는지 한눈에 보여주고, 바로 설정 화면으로 이동하게 한다.
        self.readiness_card = AutomationReadinessCard(
            self.gui, on_navigate=self._navigate_to_setup
        )
        main_layout.addWidget(self.readiness_card)

        # ── Input Section ──
        input_frame = QFrame()
        input_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {get_color('surface')};
                border: 1px solid {get_color('border_light')};
                border-radius: {ds.radius.md}px;
            }}
        """)
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(ds.spacing.space_4, ds.spacing.space_4, ds.spacing.space_4, ds.spacing.space_4)
        input_layout.setSpacing(ds.spacing.space_3)

        # URL input
        url_label = QLabel("쿠팡 상품 링크")
        url_label.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_base, QFont.Weight.Bold))
        input_layout.addWidget(url_label)

        url_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.coupang.com/vp/products/...")
        self.url_input.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_sm))
        self.url_input.setMinimumHeight(36)
        self.url_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {get_color('background')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border_light')};
                border-radius: {ds.radius.sm}px;
                padding: 4px 8px;
            }}
            QLineEdit:focus {{
                border-color: {get_color('primary')};
            }}
        """)
        url_row.addWidget(self.url_input, 1)
        input_layout.addLayout(url_row)

        # Options
        opts_layout = QHBoxLayout()
        opts_layout.setSpacing(ds.spacing.space_4)

        # 다크 테마에서 기본 팔레트(검정 텍스트)로 렌더링되면 라벨이 보이지 않으므로
        # 공통 체크박스 스타일(외곽선 박스 + 빨간 체크 표시)을 사용한다.
        checkbox_style = checkbox_qss()

        self.chk_linktree = QCheckBox("Linktree에 자동 등록")
        self.chk_linktree.setChecked(True)
        self.chk_linktree.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        self.chk_linktree.setStyleSheet(checkbox_style)
        opts_layout.addWidget(self.chk_linktree)

        self.chk_upload = QCheckBox("YouTube 자동 업로드")
        self.chk_upload.setChecked(True)
        self.chk_upload.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        self.chk_upload.setStyleSheet(checkbox_style)
        opts_layout.addWidget(self.chk_upload)

        opts_layout.addStretch()
        input_layout.addLayout(opts_layout)

        # Product match guard
        match_policy = self._load_match_policy()
        match_header = QHBoxLayout()
        match_header.setSpacing(ds.spacing.space_2)

        match_label = QLabel("상품이 얼마나 비슷해야 통과")
        match_label.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs, QFont.Weight.Bold))
        match_header.addWidget(match_label)

        self.match_threshold_spin = QSpinBox()
        self.match_threshold_spin.setRange(0, 100)
        self.match_threshold_spin.setSingleStep(5)
        self.match_threshold_spin.setSuffix("%")
        self.match_threshold_spin.setValue(int(match_policy.get("min_similarity_percent", 90)))
        self.match_threshold_spin.setFixedWidth(84)
        self.match_threshold_spin.setToolTip("이 기준보다 덜 비슷한 영상은 자동 업로드와 Linktree 등록을 막아요.")
        self.match_threshold_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: {get_color('background')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border_light')};
                border-radius: {ds.radius.sm}px;
                padding: 4px 6px;
            }}
            QSpinBox:focus {{
                border-color: {get_color('primary')};
            }}
        """)
        match_header.addWidget(self.match_threshold_spin)

        self.chk_auto_skip_low_similarity = QCheckBox("기준에 못 미치면 다음 링크로 자동 넘어가기")
        self.chk_auto_skip_low_similarity.setChecked(bool(match_policy.get("auto_skip_low_similarity", False)))
        self.chk_auto_skip_low_similarity.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        self.chk_auto_skip_low_similarity.setStyleSheet(checkbox_style)
        self.chk_auto_skip_low_similarity.setToolTip("켜면 상품을 못 찾았을 때 알림창을 띄우지 않고, 아래 '다음 쿠팡 링크 목록'의 첫 링크로 자동으로 넘어가요.")
        match_header.addWidget(self.chk_auto_skip_low_similarity)
        match_header.addStretch()
        input_layout.addLayout(match_header)

        match_hint = QLabel("기준을 통과하지 못하면 영상 만들기, YouTube 올리기, Linktree 등록을 멈춰요.")
        match_hint.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        match_hint.setStyleSheet(f"color: {get_color('text_muted')}; padding-bottom: 3px;")
        match_hint.setWordWrap(True)
        input_layout.addWidget(match_hint)

        next_links_label = QLabel("다음 쿠팡 링크 목록")
        next_links_label.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs, QFont.Weight.Bold))
        input_layout.addWidget(next_links_label)

        self.next_links_input = QTextEdit()
        self.next_links_input.setPlaceholderText("자동으로 넘어갈 때 쓸 링크를 한 줄에 하나씩 적어 주세요.")
        self.next_links_input.setAcceptRichText(False)
        self.next_links_input.setMaximumHeight(72)
        self.next_links_input.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        self._next_links_input_style = f"""
            QTextEdit {{
                background-color: {get_color('background')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border_light')};
                border-radius: {ds.radius.sm}px;
                padding: 6px 8px;
            }}
            QTextEdit:focus {{
                border-color: {get_color('primary')};
            }}
        """
        self.next_links_input.setStyleSheet(self._next_links_input_style)
        input_layout.addWidget(self.next_links_input)
        self._sync_next_links_enabled()

        self.match_threshold_spin.valueChanged.connect(self._save_match_policy)
        self.chk_auto_skip_low_similarity.toggled.connect(self._save_match_policy)
        self.chk_auto_skip_low_similarity.toggled.connect(lambda _checked: self._sync_next_links_enabled())

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

        main_layout.addWidget(self.results_frame)
        main_layout.addStretch()

        # Refresh readiness when automation options toggle, and paint once now.
        self.chk_upload.toggled.connect(lambda _checked=False: self._refresh_readiness())
        self.chk_linktree.toggled.connect(lambda _checked=False: self._refresh_readiness())
        self._refresh_readiness()

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
        """Open the guided Linktree webhook setup dialog and refresh on save."""
        try:
            from ui.components.linktree_setup_dialog import LinktreeSetupDialog

            dialog = LinktreeSetupDialog(self, on_saved=self._refresh_readiness)
            dialog.exec()
        except Exception as exc:
            logger.warning("[SourcingPanel] Linktree setup dialog failed: %s", exc)
            try:
                # Fallback: at least take the user to the settings tab.
                gui = self.gui
                if gui is not None and hasattr(gui, "_on_step_selected"):
                    gui._on_step_selected("settings")
            except Exception:
                pass
        self._refresh_readiness()

    def _refresh_readiness(self) -> None:
        """Recompute the readiness checklist from current options + connections."""
        card = getattr(self, "readiness_card", None)
        if card is None:
            return
        youtube_required = bool(getattr(self, "chk_upload", None) and self.chk_upload.isChecked())
        linktree_required = bool(getattr(self, "chk_linktree", None) and self.chk_linktree.isChecked())
        try:
            card.refresh(youtube_required=youtube_required, linktree_required=linktree_required)
        except Exception as exc:
            logger.debug("[SourcingPanel] readiness refresh skipped: %s", exc)

    def showEvent(self, event):
        """Refresh readiness whenever the panel becomes visible."""
        super().showEvent(event)
        self._refresh_readiness()

    def _load_match_policy(self) -> dict:
        try:
            from managers.settings_manager import get_settings_manager

            return get_settings_manager().get_sourcing_match_policy()
        except Exception as exc:
            logger.warning("[SourcingPanel] Failed to load match policy: %s", exc)
            return {
                "min_similarity_percent": 90,
                "min_similarity_score": 0.9,
                "auto_skip_low_similarity": False,
            }

    def _save_match_policy(self, *_args):
        if not hasattr(self, "match_threshold_spin"):
            return
        try:
            from managers.settings_manager import get_settings_manager

            get_settings_manager().set_sourcing_match_policy(
                min_similarity_percent=self.match_threshold_spin.value(),
                auto_skip_low_similarity=self.chk_auto_skip_low_similarity.isChecked(),
            )
        except Exception as exc:
            logger.warning("[SourcingPanel] Failed to save match policy: %s", exc)

    def refresh_match_policy(self):
        """Reload match controls after account settings sync."""
        if not hasattr(self, "match_threshold_spin"):
            return
        policy = self._load_match_policy()
        try:
            self.match_threshold_spin.blockSignals(True)
            self.chk_auto_skip_low_similarity.blockSignals(True)
            self.match_threshold_spin.setValue(
                int(policy.get("min_similarity_percent", 90))
            )
            self.chk_auto_skip_low_similarity.setChecked(
                bool(policy.get("auto_skip_low_similarity", False))
            )
        finally:
            self.match_threshold_spin.blockSignals(False)
            self.chk_auto_skip_low_similarity.blockSignals(False)
        self._sync_next_links_enabled()

    def _match_threshold_score(self) -> float:
        if hasattr(self, "match_threshold_spin"):
            return max(0.0, min(1.0, self.match_threshold_spin.value() / 100.0))
        return float(self._load_match_policy().get("min_similarity_score", 0.9))

    def _sync_next_links_enabled(self):
        enabled = bool(
            hasattr(self, "chk_auto_skip_low_similarity")
            and self.chk_auto_skip_low_similarity.isChecked()
        )
        if hasattr(self, "next_links_input"):
            self.next_links_input.setEnabled(enabled)
            if hasattr(self, "_next_links_input_style"):
                self.next_links_input.setStyleSheet(self._next_links_input_style)

    def _extract_next_links(self) -> List[str]:
        if not hasattr(self, "next_links_input"):
            return []
        raw = self.next_links_input.toPlainText()
        links = []
        for token in re.split(r"[\s,]+", raw):
            url = token.strip()
            if url and "coupang.com" in url:
                links.append(url)
        return links

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
        return next_url

    @staticmethod
    def _format_similarity(score: Optional[float]) -> str:
        if score is None:
            return "없음"
        try:
            return f"{float(score):.1%}"
        except (TypeError, ValueError):
            return "없음"

    def _is_match_gate_failure(self, pipeline) -> bool:
        return getattr(pipeline, "match_status", "") in {"below_threshold", "not_found"}

    def _handle_match_gate_failure(self, pipeline, report: dict):
        threshold = getattr(pipeline, "min_similarity_score", self._match_threshold_score())
        best = getattr(pipeline, "best_similarity_score", None)
        product_name = ((pipeline.product_info or {}).get("name") or "상품")[:80]
        reason = getattr(pipeline, "match_error", None) or pipeline.error or "비슷한 상품을 찾지 못했어요."
        message = (
            f"비슷한 상품을 찾지 못했어요.\n"
            f"상품: {product_name}\n"
            f"통과 기준: {threshold:.0%}\n"
            f"가장 비슷했던 정도: {self._format_similarity(best)}\n\n"
            "자동 업로드와 Linktree 등록을 멈췄어요."
        )

        if hasattr(self.gui, "state"):
            self.gui.state.sourcing_result = report

        if self.chk_auto_skip_low_similarity.isChecked():
            next_url = self._pop_next_sourcing_url()
            if next_url:
                self.results_label.setText(
                    message
                    + "\n\n다음 링크로 자동으로 넘어갈게요.\n"
                    + next_url
                )
                self.results_label.setStyleSheet(f"color: {get_color('warning')};")
                self.url_input.setText(next_url)
                QTimer.singleShot(800, self._on_start_clicked)
                return

            self.results_label.setText(
                message + "\n\n자동으로 넘어가기가 켜져 있지만, 다음 링크 목록이 비어 있어 멈췄어요."
            )
            self.results_label.setStyleSheet(f"color: {get_color('warning')};")
            try:
                from ui.components.custom_dialog import show_warning

                show_warning(self, "비슷한 상품을 찾지 못했어요", message + "\n\n다음 링크 목록이 비어 있어요.")
            except Exception:
                pass
            return

        self.results_label.setText(message + f"\n\n자세히: {reason}")
        self.results_label.setStyleSheet(f"color: {get_color('error')};")
        try:
            from ui.components.custom_dialog import show_warning

            show_warning(self, "비슷한 상품을 찾지 못했어요", message)
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
        """Block full automation when Linktree publish is requested but disconnected."""
        if not getattr(self, "chk_linktree", None) or not self.chk_linktree.isChecked():
            return True

        try:
            from managers.linktree_manager import get_linktree_manager

            ok, message = get_linktree_manager().require_connected_for_publish()
        except Exception as exc:
            logger.warning("[SourcingPanel] Linktree preflight failed: %s", exc)
            ok = False
            message = (
                "Linktree 자동 등록 상태를 확인하지 못했어요. "
                "설정 > Coupang/Linktree 자동화에서 연결을 확인한 뒤 다시 시작해 주세요."
            )

        if ok:
            return True

        self.results_label.setText(message)
        self.results_label.setStyleSheet(f"color: {get_color('warning')};")
        # 단순 경고로 끝내지 않고, 지금 바로 연결할지 물어보고 설정 화면으로 안내한다.
        try:
            from ui.components.custom_dialog import show_question

            go_now = show_question(
                self,
                "Linktree 연결이 필요해요",
                message + "\n\n지금 Linktree를 연결할까요?",
            )
        except Exception:
            go_now = False
        if go_now:
            self._open_linktree_setup_dialog()
        return False

    def _validate_youtube_upload_ready(self) -> bool:
        """Block full automation when YouTube auto-upload is requested but the
        channel is not connected (or the account-email guard fails).

        Mirrors :meth:`_validate_linktree_publish_ready` so the user is told up
        front instead of the upload step being silently skipped at the end.
        """
        if not getattr(self, "chk_upload", None) or not self.chk_upload.isChecked():
            return True

        message = ""
        try:
            from managers.settings_manager import get_settings_manager

            settings = get_settings_manager()
            if not bool(settings.get_youtube_connected()):
                message = (
                    "YouTube 자동 업로드가 켜져 있는데 아직 채널이 연결되지 않았어요.\n"
                    "‘업로드 설정’ 탭에서 채널을 연결하거나, YouTube 자동 업로드 체크를 끄고 다시 시작해 주세요."
                )
            else:
                verification = settings.get_youtube_account_verification() or {}
                if verification.get("required") and not verification.get("ok"):
                    message = str(
                        verification.get("message")
                        or "올릴 YouTube 계정 이메일 확인이 필요해요. ‘업로드 설정’ 탭에서 확인해 주세요."
                    )
        except Exception as exc:
            logger.warning("[SourcingPanel] YouTube preflight failed: %s", exc)
            # 예기치 못한 오류로는 차단하지 않는다(소싱/제작은 계속 가능).
            return True

        if not message:
            return True

        self.results_label.setText(message)
        self.results_label.setStyleSheet(f"color: {get_color('warning')};")
        # 단순 경고로 끝내지 않고, 지금 바로 연결할지 물어보고 업로드 설정 화면으로 안내한다.
        try:
            from ui.components.custom_dialog import show_question

            go_now = show_question(
                self,
                "YouTube 연결이 필요해요",
                message + "\n\n지금 YouTube 채널을 연결할까요?",
            )
        except Exception:
            go_now = False
        if go_now:
            gui = self.gui
            if gui is not None and hasattr(gui, "open_youtube_connect"):
                try:
                    gui.open_youtube_connect()
                except Exception as exc:
                    logger.warning("[SourcingPanel] open YouTube connect failed: %s", exc)
            elif gui is not None and hasattr(gui, "_on_step_selected"):
                gui._on_step_selected("upload")
        self._refresh_readiness()
        return False

    def _on_start_clicked(self):
        url = self.url_input.text().strip()
        if not url:
            self.results_label.setText("쿠팡 상품 링크를 붙여넣어 주세요.")
            self.results_label.setStyleSheet(f"color: {get_color('error')};")
            return
        if "coupang.com" not in url:
            self.results_label.setText("쿠팡 링크가 맞는지 확인해 주세요. (coupang.com 주소여야 해요)")
            self.results_label.setStyleSheet(f"color: {get_color('error')};")
            return
        if self._running:
            return

        min_similarity_score = self._match_threshold_score()
        self._save_match_policy()
        if not self._validate_linktree_publish_ready():
            return
        if not self._validate_youtube_upload_ready():
            return
        self._running = True
        self.btn_start.setEnabled(False)
        self.btn_start.setText("자동으로 만드는 중...")
        self._apply_button_style(disabled=True)

        # Reset indicators
        for ind in self._step_indicators.values():
            ind.set_state("pending", "")
        self.results_label.setText("자동 만들기를 시작할게요...")
        self.results_label.setStyleSheet(f"color: {get_color('text_muted')};")

        # Run in background thread
        thread = threading.Thread(
            target=self._run_pipeline,
            args=(url, min_similarity_score),
            daemon=True,
        )
        thread.start()

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

    def _on_pipeline_progress(self, step_id: str, message: str, pct: float):
        """Called from pipeline thread; forwards to UI thread by signal."""
        self.pipeline_progress.emit(step_id, message, pct)

    def _update_step(self, step_id: str, message: str, pct: float):
        """Update step indicator on the main thread."""
        indicator = self._step_indicators.get(step_id)
        if not indicator:
            return

        if pct >= 1.0:
            indicator.set_state("completed", message)
        elif pct > 0:
            indicator.set_state("in_progress", message)
        else:
            # Check if message indicates error
            if any(kw in message for kw in ["실패", "오류", "없습니다", "못"]):
                indicator.set_state("error", message)
            else:
                indicator.set_state("in_progress", message)

    def _on_pipeline_done(self, success: bool, pipeline):
        """Pipeline finished - update UI and emit results."""
        self._running = False
        self.btn_start.setEnabled(True)
        self.btn_start.setText("자동 만들기 시작")
        self._apply_button_style(disabled=False)

        report = pipeline.get_report()

        if not success and self._is_match_gate_failure(pipeline):
            self._handle_match_gate_failure(pipeline, report)
            return

        if success and pipeline.sourced_products:
            # Build results text
            lines = []
            pi = pipeline.product_info or {}
            lines.append(f"[원본 상품] {pi.get('name', 'N/A')[:50]}")
            lines.append(f"  링크: {pipeline.coupang_url}")
            if pipeline.deep_link:
                lines.append(f"  수수료 추적 링크: {pipeline.deep_link}")
            lines.append("")
            for i, sp in enumerate(pipeline.sourced_products):
                p = sp["product"]
                lines.append(f"[찾은 영상 {i+1}] ({sp['source'].upper()}) 비슷한 정도: {p.get('score', 0):.1%}")
                lines.append(f"  제목: {p.get('title', 'N/A')[:50]}")
                lines.append(f"  링크: {p.get('url', 'N/A')}")
                lines.append(f"  영상 파일: {sp['video_file']}")
                lines.append(f"  크기: {sp['size_mb']}MB")
                lines.append("")

            if pipeline.description:
                lines.append(f"[설명] {pipeline.description[:100]}")

            self.results_label.setText("\n".join(lines))
            self.results_label.setStyleSheet(f"color: {get_color('text_primary')};")

            # Store in app state
            report["linktree_auto_publish_requested"] = self.chk_linktree.isChecked()
            report["youtube_auto_upload_requested"] = self.chk_upload.isChecked()
            if hasattr(self.gui, 'state'):
                self.gui.state.sourcing_result = report

            # Feed sourced videos into batch queue as local:// URLs
            self._enqueue_sourced_videos(pipeline)

            self.sourcing_completed.emit(report)
        else:
            error_msg = pipeline.error or "자동 만들기에 실패했어요."
            self.results_label.setText(f"자동 만들기 실패: {error_msg}")
            self.results_label.setStyleSheet(f"color: {get_color('error')};")

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

        if self.chk_upload.isChecked():
            safe_items = [
                item for item in source_items
                if bool(item.get("auto_publish_safe", item.get("source") != "coupang_image"))
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
                logger.info("[SourcingPanel] One-link policy active: queued only the first valid sourced video")

            # Linktree auto-publish (prefer Partners deep link, fall back to
            # the original Coupang URL so the action is not silently skipped
            # when Coupang Partners keys are not configured yet).
            publish_url = pipeline.deep_link or pipeline.coupang_url
            if self.chk_linktree.isChecked() and publish_url and not self.chk_upload.isChecked():
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
            elif self.chk_linktree.isChecked() and publish_url:
                logger.info("[SourcingPanel] Linktree publish deferred until render integrity passes")

            # Full automation: chain to batch processing if YouTube auto-upload is checked
            if self.chk_upload.isChecked():
                logger.info("[SourcingPanel] 풀 자동화 모드 - 영상 제작 자동 시작")
                self._enable_youtube_auto_upload_for_pipeline()
                if hasattr(self.gui, '_on_step_selected'):
                    QTimer.singleShot(500, lambda: self.gui._on_step_selected('queue'))
                if hasattr(self.gui, 'start_batch_processing'):
                    QTimer.singleShot(1000, self.gui.start_batch_processing)
            else:
                # Manual mode: stop at voice selection so user can configure
                if hasattr(self.gui, '_on_step_selected'):
                    QTimer.singleShot(500, lambda: self.gui._on_step_selected('voice'))
        else:
            logger.warning("[SourcingPanel] No videos were successfully enqueued")
            self.results_label.setText(
                self.results_label.text() + "\n\n※ 만들 목록에 담지 못했어요. 영상 파일을 확인해 주세요."
            )

    def _enable_youtube_auto_upload_for_pipeline(self):
        """Synchronize the sourcing checkbox with the actual YouTube manager."""
        try:
            from managers.settings_manager import get_settings_manager

            settings = get_settings_manager()
            settings.set_youtube_auto_upload(True)
            yt_manager = getattr(self.gui, "youtube_manager", None)
            if yt_manager and hasattr(yt_manager, "set_upload_interval"):
                try:
                    yt_manager.set_upload_interval(settings.get_youtube_upload_interval())
                except Exception:
                    pass
            if yt_manager and hasattr(yt_manager, "set_upload_enabled"):
                yt_manager.set_upload_enabled(True)
                logger.info("[SourcingPanel] YouTube auto-upload enabled for full pipeline")
        except Exception as exc:
            logger.warning("[SourcingPanel] Failed to enable YouTube auto-upload: %s", exc)

    def get_sourcing_result(self) -> Optional[dict]:
        """Return last pipeline report or None."""
        if self._pipeline:
            return self._pipeline.get_report()
        return None
