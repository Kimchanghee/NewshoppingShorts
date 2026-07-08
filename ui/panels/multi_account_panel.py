# -*- coding: utf-8 -*-
"""
Multi-account console panel (TRIAL).

A self-contained console for managing up to 10 upload accounts across
YouTube / Instagram, with niche-based routing. Additive: it reads/writes
``managers.account_registry`` and does not touch the existing
single-account upload flow. Reachable as its own left-nav page.
"""
from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QSizePolicy,
    QDialog, QLineEdit, QComboBox, QSpinBox, QCheckBox, QPlainTextEdit,
    QMessageBox, QDialogButtonBox,
)

from ui.design_system_v2 import get_design_system, get_color
from managers.account_registry import AccountRegistry, Account, MAX_ACCOUNTS

_PLATFORM_LABEL = {"youtube": "YouTube", "instagram": "Instagram"}
_PLATFORM_GLYPH = {"youtube": "▶", "instagram": "◉"}   # ▶ / ◉
_STATUS_COLOR = {"ok": "success", "paused": "warning", "error": "error"}
_STATUS_LABEL = {"ok": "자동 ON", "paused": "일시정지", "error": "오류"}


class _ClickCard(QFrame):
    """A framed card that emits a click callback."""

    def __init__(self, on_click, parent=None):
        super().__init__(parent)
        self._on_click = on_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._on_click:
            self._on_click()
        super().mousePressEvent(event)


class MultiAccountPanel(QWidget):
    def __init__(self, parent=None, gui=None, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.theme_manager = theme_manager
        self.ds = get_design_system()
        self.registry = AccountRegistry()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Keep the scroll viewport transparent so the dark page card shows through
        # (default QScrollArea viewport is white → big white block in dark mode).
        self._scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self._scroll.viewport().setStyleSheet("background:transparent;")
        root.addWidget(self._scroll)

        self._render()

    # ------------------------------------------------------------------ helpers
    def _c(self, key: str) -> str:
        return get_color(key)

    def refresh(self):
        try:
            self.registry.load()
        except Exception:
            pass
        self._render()

    def _label(self, text: str, size: int = 13, color: str = "text_secondary",
               bold: bool = False) -> QLabel:
        lbl = QLabel(text)
        weight = "500" if bold else "400"
        lbl.setStyleSheet(
            f"color: {self._c(color)}; font-size: {size}px; font-weight: {weight};"
            " background: transparent; border: none;"
        )
        return lbl

    def _chip(self, text: str, fg: str, bg: str, border: str = "") -> QLabel:
        lbl = QLabel(text)
        b = f"border: 1px solid {border};" if border else "border: none;"
        lbl.setStyleSheet(
            f"color: {fg}; background-color: {bg}; {b}"
            " font-size: 12px; padding: 2px 8px; border-radius: 6px;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return lbl

    # ------------------------------------------------------------------ render
    def _render(self):
        content = QWidget()
        content.setObjectName("MAContent")
        content.setStyleSheet("#MAContent{background:transparent;}")
        v = QVBoxLayout(content)
        v.setContentsMargins(2, 2, 2, 2)
        v.setSpacing(16)

        v.addLayout(self._header_row())
        v.addWidget(self._flow_explainer())
        v.addLayout(self._metrics_row())

        accounts = self.registry.all()
        if not accounts:
            v.addWidget(self._empty_state())
        else:
            v.addWidget(self._label("계정", size=15, color="text_primary", bold=True))
            v.addWidget(self._account_grid(accounts))
            v.addWidget(self._label("배분 규칙  ·  소싱 상품 → 계정 라우팅",
                                    size=15, color="text_primary", bold=True))
            v.addWidget(self._routing_box())

        v.addStretch(1)
        self._scroll.setWidget(content)

    def _flow_explainer(self) -> QWidget:
        """첫 사용자를 위한 '작업 → 계정 → 자동화' 흐름 안내 스트립."""
        box = QFrame()
        box.setStyleSheet(
            f"background-color:{self._c('surface_variant')}; border:none; border-radius:12px;"
        )
        outer = QVBoxLayout(box)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(8)
        outer.addWidget(self._label(
            "이렇게 자동화됩니다  ·  처음이면 이 순서대로 준비하세요",
            size=13, color="text_secondary",
        ))
        row = QHBoxLayout()
        row.setSpacing(6)
        steps = [
            ("①", "쿠팡 소싱", "상품·영상 자동 수집"),
            ("②", "니치 배분", "상품을 계정별로 분류"),
            ("③", "계정 연결", "YouTube·Instagram 등록"),
            ("④", "자동 업로드", "계정마다 시차 업로드"),
        ]
        for i, (num, title, desc) in enumerate(steps):
            row.addWidget(self._flow_step(num, title, desc), 1)
            if i < len(steps) - 1:
                row.addWidget(self._label("→", size=16, color="text_muted"))
        outer.addLayout(row)
        return box

    def _flow_step(self, num: str, title: str, desc: str) -> QWidget:
        w = QFrame()
        w.setStyleSheet(
            f"background-color:{self._c('surface')};"
            f" border:1px solid {self._c('border_light')}; border-radius:8px;"
        )
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(2)
        lay.addWidget(self._label(f"{num}  {title}", size=13, color="text_primary", bold=True))
        lay.addWidget(self._label(desc, size=12, color="text_muted"))
        return w

    def _header_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        title = self._label("다계정 자동화 콘솔", size=16, color="text_primary", bold=True)
        slot = self._chip(
            f"{self.registry.count()} / {MAX_ACCOUNTS} 슬롯",
            self._c("text_secondary"), self._c("surface_variant"),
        )
        row.addWidget(title)
        row.addWidget(slot)
        row.addStretch(1)

        seed_btn = QPushButton("샘플 채우기")
        seed_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        seed_btn.setStyleSheet(self._btn_style(primary=False))
        seed_btn.clicked.connect(self._on_seed)
        row.addWidget(seed_btn)

        add_btn = QPushButton("＋ 계정 추가")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(self._btn_style(primary=True))
        add_btn.clicked.connect(self._on_add)
        row.addWidget(add_btn)
        return row

    def _btn_style(self, primary: bool) -> str:
        if primary:
            return (
                f"QPushButton {{ color: {self._c('text_on_primary')};"
                f" background-color: {self._c('primary')}; border: none;"
                " border-radius: 8px; padding: 8px 14px; font-size: 13px; font-weight: 500; }}"
                f" QPushButton:hover {{ background-color: {self._c('primary')}; }}"
            )
        return (
            f"QPushButton {{ color: {self._c('text_primary')}; background-color: {self._c('surface_variant')};"
            f" border: 1px solid {self._c('border_light')}; border-radius: 8px;"
            " padding: 8px 14px; font-size: 13px; }}"
            f" QPushButton:hover {{ background-color: {self._c('surface')}; }}"
        )

    def _metrics_row(self) -> QHBoxLayout:
        accts = self.registry.all()
        total = len(accts)
        today = sum(a.today_count for a in accts)
        pending = sum(max(a.daily_limit - a.today_count, 0)
                      for a in accts if a.auto_upload and a.status == "ok")
        errors = sum(1 for a in accts if a.status == "error")

        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self._metric_card("활성 계정", f"{total} / {MAX_ACCOUNTS}"))
        row.addWidget(self._metric_card("오늘 업로드", str(today)))
        row.addWidget(self._metric_card("예약 대기", str(pending)))
        row.addWidget(self._metric_card("오류", str(errors),
                                        value_color="error" if errors else "text_primary"))
        return row

    def _metric_card(self, label: str, value: str, value_color: str = "text_primary") -> QWidget:
        card = QFrame()
        card.setStyleSheet(
            f"background-color: {self._c('surface_variant')}; border: none; border-radius: 8px;"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(4)
        lay.addWidget(self._label(label, size=12, color="text_muted"))
        val = QLabel(value)
        val.setStyleSheet(
            f"color: {self._c(value_color)}; font-size: 22px; font-weight: 500;"
            " background: transparent; border: none;"
        )
        lay.addWidget(val)
        return card

    def _account_grid(self, accounts: List[Account]) -> QWidget:
        wrap = QWidget()
        grid = QGridLayout(wrap)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        cols = 3
        for i, acc in enumerate(accounts):
            grid.addWidget(self._account_card(acc), i // cols, i % cols)
        for c in range(cols):
            grid.setColumnStretch(c, 1)
        return wrap

    def _account_card(self, acc: Account) -> QWidget:
        card = _ClickCard(on_click=lambda a=acc: self._open_detail(a.id))
        card.setStyleSheet(
            f"QFrame {{ background-color: {self._c('surface')};"
            f" border: 1px solid {self._c('border_light')}; border-radius: 12px; }}"
            f" QFrame:hover {{ border: 1px solid {self._c('text_muted')}; }}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        top = QHBoxLayout()
        plat = self._label(
            f"{_PLATFORM_GLYPH.get(acc.platform, '')}  {_PLATFORM_LABEL.get(acc.platform, acc.platform)}",
            size=13, color="text_secondary",
        )
        top.addWidget(plat)
        top.addStretch(1)
        dot = QLabel("●")  # ●
        dot.setStyleSheet(
            f"color: {self._c(_STATUS_COLOR.get(acc.status, 'text_muted'))};"
            " font-size: 12px; background: transparent; border: none;"
        )
        top.addWidget(dot)
        lay.addLayout(top)

        lay.addWidget(self._label(acc.name, size=15, color="text_primary", bold=True))

        badges = QHBoxLayout()
        badges.setSpacing(6)
        badges.addWidget(self._chip(acc.niche or "미지정",
                                    self._c("text_secondary"), self._c("surface_variant")))
        st_key = _STATUS_COLOR.get(acc.status, "text_muted")
        badges.addWidget(self._chip(_STATUS_LABEL.get(acc.status, acc.status),
                                    self._c(st_key), self._c("surface")))
        badges.addStretch(1)
        lay.addLayout(badges)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {self._c('border_light')}; border: none;")
        lay.addWidget(line)

        foot = QHBoxLayout()
        foot.addWidget(self._label(f"오늘 {acc.today_count}/{acc.daily_limit}",
                                   size=12, color="text_muted"))
        foot.addStretch(1)
        foot.addWidget(self._label(f"다음 {acc.next_time}", size=12, color="text_muted"))
        lay.addLayout(foot)
        return card

    def _routing_box(self) -> QWidget:
        box = QFrame()
        box.setStyleSheet(
            f"background-color: {self._c('surface')};"
            f" border: 1px solid {self._c('border_light')}; border-radius: 12px;"
        )
        lay = QVBoxLayout(box)
        lay.setContentsMargins(16, 12, 16, 14)
        lay.setSpacing(0)

        routing = self.registry.routing_map()
        first = True
        for niche, accts in routing.items():
            row = QFrame()
            row.setStyleSheet(
                "background: transparent;"
                + ("" if first else f" border-top: 1px solid {self._c('border_light')};")
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 10, 0, 10)
            rl.addWidget(self._chip(niche, self._c("text_secondary"), self._c("surface_variant")))
            rl.addWidget(self._label("→", size=14, color="text_muted"))
            names = "  ".join(a.name for a in accts)
            rl.addWidget(self._label(names, size=13, color="text_primary"))
            rl.addStretch(1)
            lay.addWidget(row)
            first = False

        note = self._label(
            f"타이밍: 하이브리드  ·  레인 내 {self.registry.stagger_minutes}분 시차  ·  플랫폼 간 병렬",
            size=12, color="text_muted",
        )
        lay.addSpacing(6)
        lay.addWidget(note)
        return box

    def _empty_state(self) -> QWidget:
        box = QFrame()
        box.setStyleSheet(
            f"background-color: {self._c('surface')};"
            f" border: 1px dashed {self._c('text_muted')}; border-radius: 12px;"
        )
        lay = QVBoxLayout(box)
        lay.setContentsMargins(24, 32, 24, 32)
        lay.setSpacing(8)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._label("아직 등록된 계정이 없어요", size=15,
                                  color="text_primary", bold=True),
                      alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._label("‘계정 추가’로 직접 등록하거나, ‘샘플 채우기’로 미리 볼 수 있어요.",
                                  size=13, color="text_secondary"),
                      alignment=Qt.AlignmentFlag.AlignCenter)
        return box

    # ------------------------------------------------------------------ actions
    def _on_seed(self):
        try:
            added = self.registry.seed_samples()
        except Exception as exc:
            QMessageBox.warning(self, "샘플 채우기", str(exc))
            return
        if added == 0:
            QMessageBox.information(self, "샘플 채우기", "추가할 샘플이 없어요 (이미 채워져 있거나 슬롯 가득).")
        self._render()

    def _on_add(self):
        if self.registry.count() >= MAX_ACCOUNTS:
            QMessageBox.information(self, "계정 추가", f"최대 {MAX_ACCOUNTS}개까지 추가할 수 있어요.")
            return
        dlg = _AccountDialog(self, registry=self.registry)
        if dlg.exec():
            data = dlg.values()
            try:
                self.registry.add(**data)
            except Exception as exc:
                QMessageBox.warning(self, "계정 추가", str(exc))
                return
            self._render()

    def _open_detail(self, account_id: str):
        acc = self.registry.get(account_id)
        if acc is None:
            return
        dlg = _AccountDialog(self, registry=self.registry, account=acc)
        result = dlg.exec()
        if result == QDialog.DialogCode.Accepted:
            if dlg.deleted:
                self.registry.remove(account_id)
            else:
                self.registry.update(account_id, **dlg.values())
            self._render()


class _AccountDialog(QDialog):
    """Add / edit an account profile."""

    def __init__(self, parent=None, registry: AccountRegistry = None, account: Optional[Account] = None):
        super().__init__(parent)
        self.registry = registry
        self.account = account
        self.deleted = False
        self.setWindowTitle("계정 설정" if account else "계정 추가")
        self.setMinimumWidth(420)

        form = QFormLayout(self)
        form.setSpacing(10)

        self.name_in = QLineEdit(account.name if account else "")
        self.name_in.setPlaceholderText("예: 가전_리뷰_01")
        form.addRow("계정 이름", self.name_in)

        self.platform_in = QComboBox()
        self.platform_in.addItem("YouTube", "youtube")
        self.platform_in.addItem("Instagram", "instagram")
        if account:
            idx = self.platform_in.findData(account.platform)
            if idx >= 0:
                self.platform_in.setCurrentIndex(idx)
        form.addRow("플랫폼", self.platform_in)

        self.niche_in = QLineEdit(account.niche if account else "")
        self.niche_in.setPlaceholderText("예: 가전, 주방, 뷰티…")
        form.addRow("니치 / 카테고리", self.niche_in)

        self.interval_in = QSpinBox()
        self.interval_in.setRange(1, 24)
        self.interval_in.setSuffix(" 시간")
        self.interval_in.setValue(account.interval_hours if account else 4)
        form.addRow("업로드 간격", self.interval_in)

        self.offset_in = QSpinBox()
        self.offset_in.setRange(0, 120)
        self.offset_in.setSuffix(" 분")
        self.offset_in.setValue(account.offset_minutes if account else 0)
        form.addRow("시차 오프셋", self.offset_in)

        self.limit_in = QSpinBox()
        self.limit_in.setRange(1, 50)
        self.limit_in.setSuffix(" 건 / 24h")
        self.limit_in.setValue(account.daily_limit if account else 5)
        form.addRow("일일 한도", self.limit_in)

        self.auto_in = QCheckBox("자동 업로드 켜기")
        self.auto_in.setChecked(account.auto_upload if account else True)
        form.addRow("", self.auto_in)

        self.title_in = QLineEdit(account.title_prompt if account else "")
        self.title_in.setPlaceholderText("쿠팡 {상품명} 초간단 리뷰 #{키워드}")
        form.addRow("제목 프롬프트", self.title_in)

        self.tag_in = QPlainTextEdit(account.hashtag_prompt if account else "")
        self.tag_in.setPlaceholderText("#가전추천 #자취템 #쿠팡")
        self.tag_in.setFixedHeight(56)
        form.addRow("해시태그 프롬프트", self.tag_in)

        buttons = QDialogButtonBox()
        buttons.addButton("저장", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("취소", QDialogButtonBox.ButtonRole.RejectRole)
        if account:
            del_btn = buttons.addButton("삭제", QDialogButtonBox.ButtonRole.DestructiveRole)
            del_btn.clicked.connect(self._on_delete)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_delete(self):
        confirm = QMessageBox.question(
            self, "계정 삭제",
            f"‘{self.account.name}’ 계정을 삭제할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.deleted = True
            self.accept()

    def values(self) -> dict:
        return {
            "name": self.name_in.text().strip(),
            "platform": self.platform_in.currentData(),
            "niche": self.niche_in.text().strip(),
            "interval_hours": self.interval_in.value(),
            "offset_minutes": self.offset_in.value(),
            "daily_limit": self.limit_in.value(),
            "auto_upload": self.auto_in.isChecked(),
            "title_prompt": self.title_in.text().strip(),
            "hashtag_prompt": self.tag_in.toPlainText().strip(),
        }
