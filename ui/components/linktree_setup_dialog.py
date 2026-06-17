# -*- coding: utf-8 -*-
"""
Linktree 자동 발행 간편 설정 (PyQt6)

Linktree는 공식 '자동 등록 API'가 없어, 자동 발행은 웹훅(Make/Zapier/n8n 등)을
통해 이뤄진다. 일반 사용자가 이 개념을 몰라도 한 번만 따라 하면 연결되도록,
단계별 안내 + 예시 데이터 복사 + 테스트 발행 + 저장을 한 화면에 모았다.

구성:
- ``LinktreeSetupPanel(QWidget)`` — 3단계 안내 UI와 로드/저장/테스트 로직을 모두
  담은 재사용 위젯(소스 오브 트루스). 설정 탭의 '연결 도우미'에 인라인으로 들어간다.
- ``LinktreeSetupDialog(QDialog)`` — 위 패널을 그대로 임베드하고 '닫기' 버튼만
  덧붙인 다이얼로그(하위 호환용; 다른 코드가 import 할 수 있어 유지한다).

진입점(기존):
- 풀 자동화(소싱) 화면의 준비 상태 카드 → Linktree "설정하기"
- 설정 탭 Coupang/Linktree 자동화 섹션 → "간편 설정 가이드"
"""
from __future__ import annotations

import json
import threading
from typing import Callable, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QTextEdit, QFrame, QWidget, QScrollArea, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtGui import QFont, QDesktopServices

from ui.design_system_v2 import get_design_system, get_color, checkbox_qss
from utils.logging_config import get_logger

logger = get_logger(__name__)

MAKE_WEBHOOK_HELP_URL = "https://www.make.com/en/help/tools/webhooks"
ZAPIER_WEBHOOK_URL = "https://zapier.com/apps/webhook/integrations"
LINKTREE_ADMIN_URL = "https://linktr.ee/admin/links"

# 웹훅이 받게 되는 데이터의 예시(실제 발행 시 전송되는 형식과 동일).
EXAMPLE_PAYLOAD = {
    "title": "[001] 상품명 예시",
    "url": "https://link.coupang.com/a/abcd123",
    "description": "이 게시물은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.",
    "source_url": "https://www.coupang.com/vp/products/...",
    "platform": "coupang",
    "extra": {"channel": "shopping_shorts_maker", "publish_index": 1, "display_number": "[001]"},
}


class LinktreeSetupPanel(QWidget):
    """Linktree 웹훅 자동 발행을 단계별로 연결하는 간편 설정 위젯(인라인용).

    설정 탭에 직접 임베드하거나 :class:`LinktreeSetupDialog` 안에서 사용한다.
    저장이 성공하면 ``on_saved`` 콜백을 호출해 호스트가 상태를 갱신할 수 있게 한다.
    """

    _test_finished = pyqtSignal(bool, str)

    def __init__(self, parent: Optional[QWidget] = None, on_saved: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.ds = get_design_system()
        self._on_saved = on_saved
        self._testing = False
        self._test_finished.connect(self._on_test_finished)
        self._build_ui()
        self._load_existing()

    # --------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        ds = self.ds
        c = get_color
        self.setStyleSheet("background: transparent;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        outer.addWidget(scroll, 1)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        scroll.setWidget(body)

        # 헤더
        title = QLabel("Linktree 자동 등록, 한 번만 연결하면 끝나요")
        title.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_lg, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {c('text_primary')};")
        layout.addWidget(title)

        intro = QLabel(
            "Linktree에는 자동 등록 기능이 따로 없어, ‘자동 등록 주소(Webhook)’라는 중계 주소를 통해 "
            "쿠팡 링크 카드가 자동으로 추가돼요. 아래 3단계만 따라 하시면 됩니다. "
            "한 번 연결해 두면 이후에는 알아서 등록돼요."
        )
        intro.setWordWrap(True)
        intro.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_sm))
        intro.setStyleSheet(f"color: {c('text_muted')}; padding-bottom: 3px;")
        layout.addWidget(intro)

        # STEP 1 — 공개 주소
        step1 = self._step_box("1단계", "내 Linktree 주소")
        s1 = step1.body
        s1_desc = QLabel("영상 설명이나 확인 화면에 보여줄 내 Linktree 주소를 적어 주세요.")
        s1_desc.setWordWrap(True)
        s1_desc.setStyleSheet(f"color: {c('text_muted')}; font-size: 12px; border: none; background: transparent; padding-bottom: 3px;")
        s1.addWidget(s1_desc)

        self.profile_input = QLineEdit()
        self.profile_input.setPlaceholderText("예) https://linktr.ee/myshop")
        self.profile_input.setStyleSheet(self._input_style())
        s1.addWidget(self.profile_input)

        open_lt_btn = QPushButton("내 Linktree 관리자 열기")
        open_lt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_lt_btn.setStyleSheet(self._ghost_button_style())
        open_lt_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(LINKTREE_ADMIN_URL)))
        s1.addWidget(open_lt_btn, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(step1)

        # STEP 2 — 웹훅 연결
        step2 = self._step_box("2단계", "자동 등록 주소(Webhook) 연결")
        s2 = step2.body
        s2_desc = QLabel(
            "Make·Zapier·n8n 같은 서비스에서 ‘Webhook’을 만들면 주소가 하나 생겨요. "
            "그 주소를 아래에 붙여넣으세요. 자동 등록할 때 이 주소로 아래 예시 같은 정보가 전달돼요. "
            "그 정보를 받아 Linktree 카드로 추가하도록 설정해 두면 됩니다."
        )
        s2_desc.setWordWrap(True)
        s2_desc.setStyleSheet(f"color: {c('text_muted')}; font-size: 12px; border: none; background: transparent; padding-bottom: 3px;")
        s2.addWidget(s2_desc)

        helper_row = QHBoxLayout()
        helper_row.setSpacing(8)
        make_btn = QPushButton("Make 웹훅 가이드")
        make_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        make_btn.setStyleSheet(self._ghost_button_style())
        make_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(MAKE_WEBHOOK_HELP_URL)))
        helper_row.addWidget(make_btn)
        zapier_btn = QPushButton("Zapier 웹훅 가이드")
        zapier_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        zapier_btn.setStyleSheet(self._ghost_button_style())
        zapier_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(ZAPIER_WEBHOOK_URL)))
        helper_row.addWidget(zapier_btn)
        helper_row.addStretch()
        s2.addLayout(helper_row)

        payload_label = QLabel("이 주소로 전달되는 정보 예시")
        payload_label.setStyleSheet(f"color: {c('text_secondary')}; font-size: 12px; font-weight: 600; border: none; background: transparent;")
        s2.addWidget(payload_label)

        self.payload_view = QTextEdit()
        self.payload_view.setReadOnly(True)
        self.payload_view.setPlainText(json.dumps(EXAMPLE_PAYLOAD, ensure_ascii=False, indent=2))
        self.payload_view.setFixedHeight(120)
        self.payload_view.setStyleSheet(
            f"QTextEdit {{ background-color: {c('surface_variant')}; color: {c('text_primary')}; "
            f"border: 1px solid {c('border_light')}; border-radius: {self.ds.radius.sm}px; "
            f"padding: 8px; font-size: 11px; }}"
        )
        s2.addWidget(self.payload_view)

        copy_btn = QPushButton("예시 데이터 복사")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet(self._ghost_button_style())
        copy_btn.clicked.connect(self._copy_payload)
        s2.addWidget(copy_btn, 0, Qt.AlignmentFlag.AlignLeft)

        webhook_label = QLabel("자동 등록 주소(Webhook)")
        webhook_label.setStyleSheet(f"color: {c('text_secondary')}; font-size: 12px; font-weight: 600; border: none; background: transparent;")
        s2.addWidget(webhook_label)
        self.webhook_input = QLineEdit()
        self.webhook_input.setPlaceholderText("예) https://hook.make.com/abcd1234...")
        self.webhook_input.setStyleSheet(self._input_style())
        s2.addWidget(self.webhook_input)

        key_label = QLabel("보안 키 (안 넣어도 돼요)")
        key_label.setStyleSheet(f"color: {c('text_secondary')}; font-size: 12px; font-weight: 600; border: none; background: transparent;")
        s2.addWidget(key_label)
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("주소를 보호하는 비밀 키예요. 없으면 비워 두세요.")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setStyleSheet(self._input_style())
        s2.addWidget(self.api_key_input)
        layout.addWidget(step2)

        # STEP 3 — 테스트 & 저장
        step3 = self._step_box("3단계", "한번 보내 보고 켜기")
        s3 = step3.body
        s3_desc = QLabel("입력한 주소로 테스트 카드를 한 번 보내, 연결이 잘 되는지 확인해요.")
        s3_desc.setWordWrap(True)
        s3_desc.setStyleSheet(f"color: {c('text_muted')}; font-size: 12px; border: none; background: transparent; padding-bottom: 3px;")
        s3.addWidget(s3_desc)

        self.auto_publish_checkbox = QCheckBox("쿠팡 링크가 만들어지면 Linktree에 자동으로 등록하기")
        self.auto_publish_checkbox.setChecked(True)
        self.auto_publish_checkbox.setStyleSheet(checkbox_qss())
        s3.addWidget(self.auto_publish_checkbox)

        test_row = QHBoxLayout()
        test_row.setSpacing(8)
        self.test_btn = QPushButton("테스트로 보내 보기")
        self.test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.test_btn.setStyleSheet(self._ghost_button_style())
        self.test_btn.clicked.connect(self._on_test_clicked)
        test_row.addWidget(self.test_btn)
        self.test_status = QLabel("")
        self.test_status.setWordWrap(True)
        self.test_status.setStyleSheet(f"color: {c('text_muted')}; font-size: 12px; border: none; background: transparent; padding-bottom: 3px;")
        test_row.addWidget(self.test_status, 1)
        s3.addLayout(test_row)

        # 인라인 저장 액션(다이얼로그 푸터를 대체) — Step 3 영역 하단에 배치한다.
        save_row = QHBoxLayout()
        save_row.setSpacing(8)
        save_row.addStretch()
        self.save_btn = QPushButton("저장")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setStyleSheet(self._primary_button_style())
        self.save_btn.clicked.connect(self._on_save_clicked)
        save_row.addWidget(self.save_btn)
        s3.addLayout(save_row)
        layout.addWidget(step3)

        layout.addStretch()

    class _StepBox(QFrame):
        def __init__(self, body_layout: QVBoxLayout):
            super().__init__()
            self.body = body_layout

    def _step_box(self, badge: str, title: str) -> "LinktreeSetupPanel._StepBox":
        ds = self.ds
        c = get_color
        frame_body = QVBoxLayout()
        box = LinktreeSetupPanel._StepBox(frame_body)
        box.setStyleSheet(
            f"LinktreeSetupPanel__StepBox, QFrame {{ background-color: {c('surface')}; "
            f"border: 1px solid {c('border_light')}; border-radius: {ds.radius.md}px; }} "
            f"QFrame QLabel {{ border: none; background: transparent; }}"
        )
        wrap = QVBoxLayout(box)
        wrap.setContentsMargins(14, 12, 14, 12)
        wrap.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)
        chip = QLabel(badge)
        chip.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs, QFont.Weight.Bold))
        chip.setStyleSheet(
            f"background-color: {c('primary_light')}; color: {c('primary')}; "
            f"border: 1px solid {c('primary')}; border-radius: 10px; padding: 2px 10px;"
        )
        header.addWidget(chip, 0, Qt.AlignmentFlag.AlignVCenter)
        title_label = QLabel(title)
        title_label.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_base, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {c('text_primary')};")
        header.addWidget(title_label, 1)
        wrap.addLayout(header)
        wrap.addLayout(frame_body)
        return box

    # ----------------------------------------------------------- styles
    def _input_style(self) -> str:
        c = get_color
        return (
            f"QLineEdit {{ background-color: {c('surface_variant')}; color: {c('text_primary')}; "
            f"padding: 8px 10px; border: 1px solid {c('border_light')}; "
            f"border-radius: {self.ds.radius.sm}px; font-size: 13px; }} "
            f"QLineEdit:focus {{ border: 1px solid {c('primary')}; }}"
        )

    def _primary_button_style(self) -> str:
        c = get_color
        return (
            f"QPushButton {{ background-color: {c('primary')}; color: {c('text_on_primary')}; "
            f"border: none; border-radius: {self.ds.radius.sm}px; padding: 8px 18px; font-weight: 700; }} "
            f"QPushButton:hover {{ background-color: {c('primary_hover')}; }} "
            f"QPushButton:disabled {{ background-color: {c('surface_variant')}; color: {c('text_muted')}; }}"
        )

    def _ghost_button_style(self) -> str:
        c = get_color
        return (
            f"QPushButton {{ background-color: {c('surface_variant')}; color: {c('text_primary')}; "
            f"border: 1px solid {c('border_light')}; border-radius: {self.ds.radius.sm}px; "
            f"padding: 7px 14px; font-weight: 600; font-size: 12px; }} "
            f"QPushButton:hover {{ background-color: {c('surface')}; }} "
            f"QPushButton:disabled {{ color: {c('text_muted')}; }}"
        )

    # ------------------------------------------------------------ logic
    def _load_existing(self) -> None:
        try:
            from managers.settings_manager import get_settings_manager
            s = get_settings_manager().get_linktree_settings() or {}
            self.profile_input.setText(str(s.get("profile_url", "") or ""))
            self.webhook_input.setText(str(s.get("webhook_url", "") or ""))
            self.api_key_input.setText(str(s.get("api_key", "") or ""))
            self.auto_publish_checkbox.setChecked(bool(s.get("auto_publish", True)))
        except Exception as exc:
            logger.debug("[LinktreeSetup] load existing skipped: %s", exc)

    def _copy_payload(self) -> None:
        try:
            QApplication.clipboard().setText(self.payload_view.toPlainText())
            self.test_status.setText("예시 정보를 복사했어요. 만들어 둔 Webhook 설정에 붙여넣어 연결하세요.")
            self.test_status.setStyleSheet(f"color: {get_color('success')}; font-size: 12px; border: none; background: transparent;")
        except Exception as exc:
            logger.debug("[LinktreeSetup] copy payload failed: %s", exc)

    def _persist(self) -> None:
        from managers.settings_manager import get_settings_manager
        get_settings_manager().set_linktree_settings(
            webhook_url=self.webhook_input.text().strip(),
            api_key=self.api_key_input.text().strip(),
            profile_url=self.profile_input.text().strip(),
            auto_publish=self.auto_publish_checkbox.isChecked(),
        )

    def _on_test_clicked(self) -> None:
        if self._testing:
            return
        webhook = self.webhook_input.text().strip()
        if not webhook.lower().startswith(("http://", "https://")):
            self.test_status.setText("먼저 올바른 자동 등록 주소(https://...)를 입력하세요.")
            self.test_status.setStyleSheet(f"color: {get_color('warning')}; font-size: 12px; border: none; background: transparent;")
            return

        # 테스트는 현재 입력값 기준으로 동작하도록 먼저 저장한다.
        try:
            self._persist()
        except Exception as exc:
            logger.warning("[LinktreeSetup] persist before test failed: %s", exc)

        self._testing = True
        self.test_btn.setEnabled(False)
        self.test_btn.setText("보내는 중...")
        self.test_status.setText("테스트 카드를 보내는 중이에요...")
        self.test_status.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 12px; border: none; background: transparent;")

        def _run():
            ok = False
            detail = ""
            try:
                from managers.linktree_manager import get_linktree_manager
                ok = bool(get_linktree_manager().test_connection())
            except Exception as exc:  # pragma: no cover - network/runtime
                detail = str(exc)
                ok = False
            self._test_finished.emit(ok, detail)

        threading.Thread(target=_run, daemon=True).start()

    def _on_test_finished(self, ok: bool, detail: str) -> None:
        self._testing = False
        self.test_btn.setEnabled(True)
        self.test_btn.setText("테스트로 보내 보기")
        if ok:
            self.test_status.setText("성공! 연결이 잘 돼요. ‘저장’을 누르면 자동 등록이 켜져요.")
            self.test_status.setStyleSheet(f"color: {get_color('success')}; font-size: 12px; border: none; background: transparent;")
        else:
            msg = "테스트에 실패했어요. 자동 등록 주소와 설정 상태를 확인한 뒤 다시 시도하세요."
            if detail:
                msg += f" (상세: {detail[:120]})"
            self.test_status.setText(msg)
            self.test_status.setStyleSheet(f"color: {get_color('error')}; font-size: 12px; border: none; background: transparent;")

    def _on_save_clicked(self) -> None:
        from ui.components.custom_dialog import show_info, show_warning
        webhook = self.webhook_input.text().strip()
        if self.auto_publish_checkbox.isChecked() and not webhook.lower().startswith(("http://", "https://")):
            show_warning(
                self,
                "자동 등록 주소가 필요해요",
                "자동 등록을 켜려면 올바른 자동 등록 주소(Webhook)가 필요해요.\n"
                "주소 없이 저장하려면 위의 '자동으로 등록하기' 체크를 꺼 주세요.",
            )
            return
        try:
            self._persist()
        except Exception as exc:
            logger.error("[LinktreeSetup] save failed: %s", exc)
            show_warning(self, "저장 실패", f"설정을 저장하지 못했어요.\n{exc}")
            return

        if callable(self._on_saved):
            try:
                self._on_saved()
            except Exception as exc:
                logger.debug("[LinktreeSetup] on_saved callback failed: %s", exc)

        show_info(self, "저장 완료", "Linktree 자동 등록 설정을 저장했어요.")


class LinktreeSetupDialog(QDialog):
    """Linktree 간편 설정 패널을 그대로 임베드한 다이얼로그(하위 호환용).

    UI/로직은 모두 :class:`LinktreeSetupPanel`에 있다. 이 다이얼로그는 패널을
    감싸고 '닫기' 버튼만 덧붙인다. ``on_saved`` 콜백은 패널을 통해 그대로 동작한다.
    """

    def __init__(self, parent: Optional[QWidget] = None, on_saved: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.ds = get_design_system()
        c = get_color
        self.setWindowTitle("Linktree 자동 등록 간편 설정")
        self.setMinimumWidth(580)
        self.setMinimumHeight(560)
        self.setStyleSheet(
            f"QDialog {{ background-color: {c('background')}; color: {c('text_primary')}; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 저장이 끝나면 호스트 콜백을 부르고 다이얼로그를 닫는다(기존 동작 유지).
        self.panel = LinktreeSetupPanel(parent=self, on_saved=self._handle_saved)
        self._external_on_saved = on_saved

        panel_wrap = QWidget()
        panel_wrap.setStyleSheet("background: transparent;")
        panel_layout = QVBoxLayout(panel_wrap)
        panel_layout.setContentsMargins(24, 20, 24, 8)
        panel_layout.setSpacing(0)
        panel_layout.addWidget(self.panel, 1)
        outer.addWidget(panel_wrap, 1)

        # 하단 액션 바(닫기). 저장은 패널 내부 버튼이 담당한다.
        footer = QWidget()
        footer.setStyleSheet(f"background-color: {c('surface')}; border-top: 1px solid {c('border_light')};")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 12, 24, 12)
        footer_layout.setSpacing(8)
        footer_layout.addStretch()

        close_btn = QPushButton("닫기")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(self.panel._ghost_button_style())
        close_btn.clicked.connect(self.reject)
        footer_layout.addWidget(close_btn)

        outer.addWidget(footer)

    def _handle_saved(self) -> None:
        if callable(self._external_on_saved):
            try:
                self._external_on_saved()
            except Exception as exc:
                logger.debug("[LinktreeSetup] dialog on_saved callback failed: %s", exc)
        self.accept()
