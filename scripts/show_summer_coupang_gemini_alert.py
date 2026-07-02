# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.design_system_v2 import get_design_system, set_dark_mode
from user_facing_errors import friendly_error_message, sanitize_user_message


class GeminiKeyAlertDialog(QDialog):
    def __init__(self, payload: Dict[str, Any], alert_path: Path):
        super().__init__()
        set_dark_mode(True)
        self.ds = get_design_system()
        self.colors = self.ds.colors
        self.payload = payload
        self.alert_path = alert_path

        self.setWindowTitle("SSMaker 자동화 중지")
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setModal(False)
        self.setFixedWidth(560)
        self._build_ui()

    def _build_ui(self) -> None:
        c = self.colors
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c.bg_main};
                color: {c.text_primary};
            }}
            QLabel {{
                background: transparent;
                color: {c.text_primary};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(0)

        card = QFrame()
        card.setObjectName("AlertCard")
        card.setStyleSheet(f"""
            QFrame#AlertCard {{
                background-color: {c.surface};
                border: 1px solid {c.border_medium};
                border-radius: 8px;
            }}
        """)
        root.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(18)

        header = QHBoxLayout()
        header.setSpacing(14)

        badge = QLabel("!")
        badge.setFixedSize(36, 36)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        badge.setStyleSheet(f"""
            background-color: {c.primary_light};
            color: {c.error};
            border: 1px solid {c.error};
            border-radius: 18px;
        """)
        header.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

        title_group = QVBoxLayout()
        title_group.setSpacing(4)

        title = QLabel("Summer Coupang 자동화가 잠시 멈췄어요")
        title.setFont(QFont("Pretendard", 17, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {c.text_primary};")
        title_group.addWidget(title)

        subtitle = QLabel("저장된 Gemini API 키를 지금 사용할 수 없어 다음 상품 처리를 시작하지 않았어요.")
        subtitle.setFont(QFont("Pretendard", 11))
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {c.text_secondary};")
        title_group.addWidget(subtitle)

        header.addLayout(title_group, 1)
        layout.addLayout(header)

        layout.addWidget(self._summary_panel())
        layout.addWidget(self._detail_panel(), 1)
        layout.addLayout(self._buttons())

    def _summary_panel(self) -> QWidget:
        c = self.colors
        panel = QFrame()
        panel.setObjectName("SummaryPanel")
        panel.setStyleSheet(f"""
            QFrame#SummaryPanel {{
                background-color: {c.surface_variant};
                border: 1px solid {c.border};
                border-radius: 8px;
            }}
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        next_number = str(self.payload.get("next_planned_number") or "").strip() or "-"
        next_name = str(self.payload.get("next_product_name") or "").strip()
        next_item = f"{next_number} {next_name}".strip()
        pending_count = str(self.payload.get("pending_count") or 0)

        layout.addLayout(self._kv_row("다음 작업", next_item))
        layout.addLayout(self._kv_row("대기 중", f"{pending_count}개"))
        layout.addLayout(self._kv_row("중지 사유", self._blocking_reason()))
        return panel

    def _detail_panel(self) -> QWidget:
        c = self.colors
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(154)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: 1px solid {c.border};
                border-radius: 8px;
            }}
            QScrollBar:vertical {{
                background: {c.surface};
                width: 8px;
                margin: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {c.border_medium};
                border-radius: 4px;
            }}
        """)

        content = QWidget()
        content.setStyleSheet(f"background-color: {c.surface};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        title = QLabel("키 상태")
        title.setFont(QFont("Pretendard", 11, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {c.text_primary};")
        layout.addWidget(title)

        invalid_lines = self._invalid_key_lines()
        configured_count = self._configured_key_count()
        if configured_count <= 0:
            layout.addWidget(self._detail_line("저장된 Gemini API 키가 없어요. 설정에서 키를 추가한 뒤 다시 실행해 주세요.", c.warning))
        elif invalid_lines:
            for line in invalid_lines:
                layout.addWidget(self._detail_line(line, c.error))
        else:
            layout.addWidget(self._detail_line("저장된 API 키 상태를 다시 확인해 주세요.", c.text_secondary))

        note = QLabel("키 원문은 보안상 표시하지 않습니다. 설정 > API 키에서 새 Gemini API 키로 교체한 뒤 다시 실행해 주세요.")
        note.setWordWrap(True)
        note.setFont(QFont("Pretendard", 10))
        note.setStyleSheet(f"color: {c.text_muted}; padding-top: 6px;")
        layout.addWidget(note)
        layout.addStretch()

        scroll.setWidget(content)
        return scroll

    def _buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()

        file_btn = QPushButton("알림 파일 열기")
        file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        file_btn.clicked.connect(self._open_alert_file)
        file_btn.setStyleSheet(self._button_qss("secondary"))
        file_btn.setFixedHeight(38)
        row.addWidget(file_btn)

        app_btn = QPushButton("SSMaker 열기")
        app_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        app_btn.clicked.connect(self._open_app)
        app_btn.setStyleSheet(self._button_qss("primary"))
        app_btn.setFixedHeight(38)
        row.addWidget(app_btn)

        close_btn = QPushButton("닫기")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet(self._button_qss("ghost"))
        close_btn.setFixedHeight(38)
        row.addWidget(close_btn)
        return row

    def _kv_row(self, label_text: str, value_text: str) -> QHBoxLayout:
        c = self.colors
        row = QHBoxLayout()
        row.setSpacing(10)

        label = QLabel(label_text)
        label.setFixedWidth(76)
        label.setFont(QFont("Pretendard", 10, QFont.Weight.Bold))
        label.setStyleSheet(f"color: {c.text_muted};")
        row.addWidget(label, 0, Qt.AlignmentFlag.AlignTop)

        value = QLabel(value_text)
        value.setWordWrap(True)
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        value.setFont(QFont("Pretendard", 10))
        value.setStyleSheet(f"color: {c.text_primary};")
        row.addWidget(value, 1)
        return row

    def _detail_line(self, text: str, color: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setFont(QFont("JetBrains Mono", 10))
        label.setStyleSheet(f"""
            color: {color};
            background-color: {self.colors.surface_variant};
            border: 1px solid {self.colors.border};
            border-radius: 6px;
            padding: 7px 9px;
        """)
        return label

    def _button_qss(self, variant: str) -> str:
        c = self.colors
        if variant == "primary":
            return f"""
                QPushButton {{
                    background-color: {c.primary};
                    color: {c.text_on_primary};
                    border: none;
                    border-radius: 8px;
                    padding: 0 16px;
                    font-weight: 700;
                }}
                QPushButton:hover {{ background-color: {c.primary_hover}; }}
            """
        if variant == "secondary":
            return f"""
                QPushButton {{
                    background-color: {c.surface_variant};
                    color: {c.text_primary};
                    border: 1px solid {c.border_medium};
                    border-radius: 8px;
                    padding: 0 14px;
                }}
                QPushButton:hover {{ background-color: {c.bg_hover}; }}
            """
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {c.text_secondary};
                border: 1px solid {c.border};
                border-radius: 8px;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                color: {c.text_primary};
                border-color: {c.border_medium};
            }}
        """

    def _blocking_reason(self) -> str:
        preflight = self.payload.get("preflight")
        if isinstance(preflight, dict):
            reason = preflight.get("blocking_reason") or preflight.get("reason")
            if reason:
                return sanitize_user_message(reason, fallback=friendly_error_message(preflight))
        return friendly_error_message(self.payload, fallback="Gemini API 키 확인이 필요해요.")

    def _configured_key_count(self) -> int:
        preflight = self.payload.get("preflight")
        if not isinstance(preflight, dict):
            return 0
        valid = preflight.get("valid_aliases") if isinstance(preflight.get("valid_aliases"), list) else []
        invalid = preflight.get("invalid_aliases") if isinstance(preflight.get("invalid_aliases"), list) else []
        return len(valid) + len(invalid)

    def _invalid_key_lines(self) -> List[str]:
        preflight = self.payload.get("preflight")
        invalid = preflight.get("invalid_aliases") if isinstance(preflight, dict) else []
        if not isinstance(invalid, list):
            return []
        lines: List[str] = []
        has_permission_error = False
        has_quota_error = False
        for item in invalid:
            if not isinstance(item, dict):
                continue
            text = json.dumps(item, ensure_ascii=False)
            lowered = text.lower()
            has_permission_error = (
                has_permission_error
                or "permission_denied" in lowered
                or '"403"' in lowered
                or ": 403" in lowered
            )
            has_quota_error = (
                has_quota_error
                or "resource_exhausted" in lowered
                or '"429"' in lowered
                or ": 429" in lowered
            )
        if has_permission_error:
            lines.append("저장된 Gemini API 키가 Google에서 권한 거절 상태예요. 새 키로 교체하거나 Google AI Studio에서 키 제한을 확인해 주세요.")
        elif has_quota_error:
            lines.append("현재 API 사용량이 한도에 도달했어요. 잠시 후 다시 시도하거나 다른 키를 추가해 주세요.")
        elif invalid:
            lines.append("저장된 Gemini API 키를 지금 사용할 수 없어요. 설정에서 새 키로 교체해 주세요.")
        return lines

    def _missing_aliases(self) -> List[str]:
        preflight = self.payload.get("preflight")
        missing = preflight.get("missing_aliases") if isinstance(preflight, dict) else []
        return [str(alias) for alias in missing] if isinstance(missing, list) else []

    def _open_alert_file(self) -> None:
        try:
            if os.name == "nt":
                subprocess.Popen(["notepad.exe", str(self.alert_path)])
        except Exception:
            pass

    def _open_app(self) -> None:
        try:
            env = os.environ.copy()
            env.pop("QT_QPA_PLATFORM", None)
            subprocess.Popen(
                [sys.executable, str(ROOT / "main.py")],
                cwd=str(ROOT),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            pass
        self.accept()


def load_payload(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alert-json", required=True)
    args = parser.parse_args()

    alert_path = Path(args.alert_json)
    payload = load_payload(alert_path)
    app = QApplication.instance() or QApplication(sys.argv)
    dialog = GeminiKeyAlertDialog(payload, alert_path)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
