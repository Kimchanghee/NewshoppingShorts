# -*- coding: utf-8 -*-
"""
Full-Automation Readiness Card (PyQt6)
풀 자동화 준비 상태 카드

Mode 3(풀 자동화 소싱) 화면 상단에 표시되어, 쿠팡 링크 1개로 영상 제작 →
Linktree 발행 → YouTube 업로드까지 자동으로 진행하기 위해 필요한 항목이
준비되었는지 한눈에 보여준다.

- AI 분석 엔진 (Vertex/Gemini)        : 항상 필요
- YouTube 채널 연결                   : 'YouTube 자동 업로드'를 켰을 때 필요
- Linktree 자동 발행 (Webhook)        : '링크트리 자동 발행'을 켰을 때 필요
- 쿠팡 파트너스 딥링크 키              : 선택(없으면 원본 쿠팡 링크로 발행)

각 항목은 ✓/⚠/✗ 상태와 함께 "설정하기" 버튼을 제공하여, 사용자가 곧바로
필요한 설정 화면으로 이동할 수 있게 한다. 설정 화면 이동은 생성자에서 받은
``on_navigate(step_id)`` 콜백으로 위임한다(예: "upload", "settings").
"""
from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.design_system_v2 import get_design_system, get_color
from utils.logging_config import get_logger

logger = get_logger(__name__)

# 상태 코드
STATUS_READY = "ready"        # 준비 완료(초록 ✓)
STATUS_MISSING = "missing"    # 필요한데 미설정(빨강 ✗) → 시작 차단/경고
STATUS_OPTIONAL = "optional"  # 선택 항목 미설정(주황 ⚠) → 안내만
STATUS_SKIPPED = "skipped"    # 이번 실행에서 사용 안 함(회색 ○)


class AutomationReadinessCard(QFrame):
    """풀 자동화에 필요한 연동 상태를 보여주는 체크리스트 카드."""

    def __init__(
        self,
        gui=None,
        on_navigate: Optional[Callable[[str], None]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._gui = gui
        self._on_navigate = on_navigate
        self.ds = get_design_system()
        self._rows_container: Optional[QWidget] = None
        self._rows_layout: Optional[QVBoxLayout] = None
        self._summary_label: Optional[QLabel] = None
        self._setup_ui()
        # 최초 1회는 두 옵션 모두 필요한 것으로 가정해 그린다.
        # 어떤 경우에도 카드 생성이 부모 패널 구성을 깨뜨리지 않도록 방어한다.
        try:
            self.refresh(youtube_required=True, linktree_required=True)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("[ReadinessCard] initial refresh failed: %s", exc)

    # ------------------------------------------------------------------ UI
    def _setup_ui(self) -> None:
        ds = self.ds
        self.setObjectName("AutomationReadinessCard")
        self.setStyleSheet(f"""
            QFrame#AutomationReadinessCard {{
                background-color: {get_color('surface')};
                border: 1px solid {get_color('border_light')};
                border-radius: {ds.radius.md}px;
            }}
            QFrame#AutomationReadinessCard QLabel {{
                background: transparent;
                border: none;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # 헤더: 제목 + 전체 요약 칩
        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel("🤖 풀 자동화 준비 상태")
        title.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_base, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {get_color('text_primary')};")
        header.addWidget(title)

        header.addStretch()

        self._summary_label = QLabel("")
        self._summary_label.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs, QFont.Weight.Bold))
        self._summary_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        header.addWidget(self._summary_label)

        layout.addLayout(header)

        helper = QLabel("쿠팡 링크 1개로 영상 제작·발행·업로드까지 자동으로 진행하려면 아래 항목이 준비되어야 합니다.")
        helper.setWordWrap(True)
        helper.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        helper.setStyleSheet(f"color: {get_color('text_muted')};")
        layout.addWidget(helper)

        # 항목 행 컨테이너 (refresh 때마다 재생성)
        self._rows_container = QWidget()
        self._rows_container.setStyleSheet("background: transparent; border: none;")
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 2, 0, 0)
        self._rows_layout.setSpacing(6)
        layout.addWidget(self._rows_container)

    # ------------------------------------------------------------- refresh
    def refresh(self, youtube_required: bool = True, linktree_required: bool = True) -> None:
        """현재 연동 상태를 다시 계산하여 행을 갱신한다.

        Args:
            youtube_required: 'YouTube 자동 업로드' 옵션이 켜져 있는지 여부.
            linktree_required: '링크트리 자동 발행' 옵션이 켜져 있는지 여부.
        """
        if self._rows_layout is None:
            return

        # 기존 행 제거
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        rows: List[Tuple[str, str, str, str, Optional[str]]] = []
        # (key, title, status, detail, navigate_target)

        # 1) AI 분석 엔진 (항상 필요)
        ai_ok, ai_detail = self._ai_status()
        rows.append((
            "ai",
            "AI 분석 엔진 (Vertex/Gemini)",
            STATUS_READY if ai_ok else STATUS_MISSING,
            ai_detail,
            None if ai_ok else "settings",
        ))

        # 2) YouTube 채널 연결 (업로드 옵션 켰을 때만 필요)
        yt_status, yt_detail = self._youtube_status()
        if not youtube_required:
            rows.append((
                "youtube",
                "YouTube 채널 연결",
                STATUS_READY if yt_status == STATUS_READY else STATUS_SKIPPED,
                "‘YouTube 자동 업로드’ 옵션이 꺼져 있어 이번 실행에서는 필요하지 않습니다."
                if yt_status != STATUS_READY else yt_detail,
                "upload" if yt_status != STATUS_READY else None,
            ))
        else:
            rows.append((
                "youtube",
                "YouTube 채널 연결",
                yt_status,
                yt_detail,
                "upload" if yt_status != STATUS_READY else None,
            ))

        # 3) Linktree 자동 발행 (발행 옵션 켰을 때만 필요)
        lt_status, lt_detail = self._linktree_status()
        if not linktree_required:
            rows.append((
                "linktree",
                "Linktree 자동 발행",
                STATUS_READY if lt_status == STATUS_READY else STATUS_SKIPPED,
                "‘링크트리 자동 발행’ 옵션이 꺼져 있어 이번 실행에서는 필요하지 않습니다."
                if lt_status != STATUS_READY else lt_detail,
                "linktree_setup" if lt_status != STATUS_READY else None,
            ))
        else:
            rows.append((
                "linktree",
                "Linktree 자동 발행",
                lt_status,
                lt_detail,
                "linktree_setup" if lt_status != STATUS_READY else None,
            ))

        # 4) 쿠팡 파트너스 딥링크 키 (선택)
        cp_ok, cp_detail = self._coupang_status()
        rows.append((
            "coupang",
            "쿠팡 파트너스 딥링크 키 (선택)",
            STATUS_READY if cp_ok else STATUS_OPTIONAL,
            cp_detail,
            None if cp_ok else "settings",
        ))

        required_missing = 0
        for key, title, status, detail, target in rows:
            if status == STATUS_MISSING:
                required_missing += 1
            self._rows_layout.addWidget(self._build_row(title, status, detail, target))

        self._update_summary(required_missing)

    def _update_summary(self, required_missing: int) -> None:
        if self._summary_label is None:
            return
        if required_missing == 0:
            self._summary_label.setText("✓ 준비 완료")
            self._summary_label.setStyleSheet(f"color: {get_color('success')};")
        else:
            self._summary_label.setText(f"설정 필요 {required_missing}건")
            self._summary_label.setStyleSheet(f"color: {get_color('error')};")

    def _build_row(self, title: str, status: str, detail: str, target: Optional[str]) -> QWidget:
        ds = self.ds
        row = QFrame()
        row.setStyleSheet(
            f"QFrame {{ background-color: {get_color('surface_variant')}; "
            f"border: 1px solid {get_color('border_light')}; "
            f"border-radius: {ds.radius.sm}px; }} "
            f"QFrame QLabel {{ background: transparent; border: none; }}"
        )
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(10, 8, 10, 8)
        row_layout.setSpacing(10)

        icon_char, icon_color = self._status_icon(status)
        icon = QLabel(icon_char)
        icon.setFixedWidth(18)
        icon.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        icon.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_base, QFont.Weight.Bold))
        icon.setStyleSheet(f"color: {icon_color};")
        row_layout.addWidget(icon)

        text_wrap = QVBoxLayout()
        text_wrap.setContentsMargins(0, 0, 0, 0)
        text_wrap.setSpacing(1)

        title_label = QLabel(title)
        title_label.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_sm, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {get_color('text_primary')};")
        text_wrap.addWidget(title_label)

        detail_label = QLabel(detail)
        detail_label.setWordWrap(True)
        detail_label.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        detail_label.setStyleSheet(f"color: {self._detail_color(status)};")
        text_wrap.addWidget(detail_label)

        row_layout.addLayout(text_wrap, 1)

        if target and status in (STATUS_MISSING, STATUS_OPTIONAL, STATUS_SKIPPED):
            action_btn = QPushButton("설정하기")
            action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            action_btn.setFixedHeight(28)
            primary = status == STATUS_MISSING
            if primary:
                action_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {get_color('primary')};
                        color: {get_color('text_on_primary')};
                        border: none;
                        border-radius: {ds.radius.sm}px;
                        padding: 4px 14px;
                        font-weight: 700;
                        font-size: 12px;
                    }}
                    QPushButton:hover {{ background-color: {get_color('primary_hover')}; }}
                """)
            else:
                action_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {get_color('text_secondary')};
                        border: 1px solid {get_color('border_light')};
                        border-radius: {ds.radius.sm}px;
                        padding: 4px 14px;
                        font-weight: 600;
                        font-size: 12px;
                    }}
                    QPushButton:hover {{ background-color: {get_color('surface')}; color: {get_color('text_primary')}; }}
                """)
            action_btn.clicked.connect(lambda _checked=False, t=target: self._navigate(t))
            row_layout.addWidget(action_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        else:
            done = QLabel("확인됨")
            done.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs, QFont.Weight.Bold))
            done.setStyleSheet(f"color: {get_color('success')};")
            row_layout.addWidget(done, 0, Qt.AlignmentFlag.AlignVCenter)

        return row

    @staticmethod
    def _status_icon(status: str) -> Tuple[str, str]:
        if status == STATUS_READY:
            return "✓", get_color('success')      # ✓
        if status == STATUS_MISSING:
            return "✗", get_color('error')         # ✗
        if status == STATUS_OPTIONAL:
            return "⚠", get_color('warning')       # ⚠
        return "○", get_color('text_muted')        # ○ (skipped)

    @staticmethod
    def _detail_color(status: str) -> str:
        if status == STATUS_MISSING:
            return get_color('error')
        if status == STATUS_OPTIONAL:
            return get_color('warning')
        return get_color('text_muted')

    def _navigate(self, target: str) -> None:
        if callable(self._on_navigate):
            try:
                self._on_navigate(target)
                return
            except Exception as exc:
                logger.warning("[ReadinessCard] navigate callback failed: %s", exc)
        # Fallback: try the GUI directly.
        gui = self._gui
        if gui is not None and hasattr(gui, "_on_step_selected"):
            try:
                gui._on_step_selected(target)
            except Exception as exc:
                logger.warning("[ReadinessCard] gui navigate failed: %s", exc)

    # --------------------------------------------------------- status calc
    def _ai_status(self) -> Tuple[bool, str]:
        """AI 분석 엔진(Vertex/Gemini) 준비 여부."""
        gui = self._gui
        if getattr(gui, "genai_client", None) is not None:
            return True, "AI 분석 엔진이 준비되었습니다."
        if getattr(gui, "model_provider", None) is not None:
            return True, "기본 Vertex AI 엔진이 준비되었습니다."
        return False, "AI 키가 설정되지 않았습니다. 설정에서 Gemini API 키를 등록하세요."

    def _youtube_status(self) -> Tuple[str, str]:
        """YouTube 채널 연결/계정 검증 상태."""
        try:
            from managers.settings_manager import get_settings_manager
            s = get_settings_manager()
            if not bool(s.get_youtube_connected()):
                return STATUS_MISSING, "채널이 연결되지 않았습니다. ‘업로드 설정’에서 OAuth JSON으로 연결하세요."
            verification = s.get_youtube_account_verification() or {}
            if verification.get("required") and not verification.get("ok"):
                return STATUS_MISSING, str(verification.get("message") or "YouTube 계정 이메일 검증이 필요합니다.")
            info = s.get_youtube_channel_info() or {}
            name = info.get("channel_name") or info.get("title") or "연결됨"
            return STATUS_READY, f"연결됨: {name}"
        except Exception as exc:
            logger.debug("[ReadinessCard] YouTube status error: %s", exc)
            return STATUS_MISSING, "연결 상태를 확인하지 못했습니다. ‘업로드 설정’에서 확인하세요."

    def _linktree_status(self) -> Tuple[str, str]:
        """Linktree 자동 발행 가능 여부(Webhook + 계정 검증)."""
        try:
            from managers.linktree_manager import get_linktree_manager
            lm = get_linktree_manager()
            ok, message = lm.require_connected_for_publish()
            if ok:
                profile = ""
                try:
                    profile = lm.get_profile_url()
                except Exception:
                    profile = ""
                return STATUS_READY, f"발행 준비됨{f': {profile}' if profile else ''}"
            return STATUS_MISSING, str(message or "설정 > Coupang/Linktree 자동화에서 Webhook URL을 등록하세요.")
        except Exception as exc:
            logger.debug("[ReadinessCard] Linktree status error: %s", exc)
            return STATUS_MISSING, "연결 상태를 확인하지 못했습니다. 설정 > Coupang/Linktree 자동화를 확인하세요."

    def _coupang_status(self) -> Tuple[bool, str]:
        """쿠팡 파트너스 딥링크 키 등록 여부(선택)."""
        try:
            from managers.settings_manager import get_settings_manager
            keys = get_settings_manager().get_coupang_keys() or {}
            if keys.get("access_key") and keys.get("secret_key"):
                return True, "파트너스 딥링크 키가 등록되어 자동 딥링크 변환을 사용합니다."
            return False, "미설정 시 원본 쿠팡 링크로 발행됩니다(딥링크 변환 없음)."
        except Exception as exc:
            logger.debug("[ReadinessCard] Coupang status error: %s", exc)
            return False, "미설정 시 원본 쿠팡 링크로 발행됩니다(딥링크 변환 없음)."
