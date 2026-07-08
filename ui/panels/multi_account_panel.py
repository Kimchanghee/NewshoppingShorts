# -*- coding: utf-8 -*-
"""
Multi-account console panel (TRIAL) — connect-first, popup-free UX ("방안 B").

Accounts are added via inline platform "연결 카드" (no modal dialog), niche and
on/off are edited inline on each card, deletion is inline with an undo toast, and
ALL feedback is an inline toast bar — no QDialog / QMessageBox anywhere. Additive:
reads/writes managers.account_registry only; does not touch existing upload flow.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import List, Optional

import os
import shutil

from PyQt6.QtCore import Qt, QTimer, QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QComboBox,
)

from ui.design_system_v2 import get_design_system, get_color
from managers.account_registry import AccountRegistry, Account, MAX_ACCOUNTS, data_dir


class _ConnectWorker(QObject):
    """Runs the blocking OAuth connect (real browser login) off the UI thread."""

    finished = pyqtSignal(bool, object, str)  # success, info_dict, error

    def __init__(self, manager, platform: str):
        super().__init__()
        self._manager = manager
        self._platform = platform

    def run(self):
        try:
            if self._platform == "youtube":
                ok = bool(self._manager.connect_channel())
                info = self._manager.get_channel_info() if ok else {}
            else:
                ok = bool(self._manager.connect_account())
                info = self._manager.get_account_info() if ok else {}
            if not ok:
                try:
                    err = self._manager.get_last_error() or ""
                except Exception:
                    err = ""
                self.finished.emit(False, {}, err or "연결에 실패했어요.")
                return
            self.finished.emit(True, info or {}, "")
        except Exception as exc:  # pragma: no cover - defensive
            self.finished.emit(False, {}, str(exc))

_PLATFORM_LABEL = {"youtube": "YouTube", "instagram": "Instagram"}
_PLATFORM_GLYPH = {"youtube": "▶", "instagram": "◉"}
_STATUS_COLOR = {"ok": "success", "paused": "warning", "error": "error"}
_STATUS_LABEL = {"ok": "자동 ON", "paused": "일시정지", "error": "오류"}
_NICHES = ["가전", "주방", "뷰티", "반려동물", "캠핑", "홈오피스", "헬스", "육아", "패션", "기타"]


class MultiAccountPanel(QWidget):
    def __init__(self, parent=None, gui=None, theme_manager=None):
        super().__init__(parent)
        self.gui = gui
        self.theme_manager = theme_manager
        self.ds = get_design_system()
        self.registry = AccountRegistry()
        self._last_deleted: Optional[dict] = None
        self._expanded: set = set()   # 대기열이 펼쳐진 계정 id들

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Inline toast bar (replaces every popup / alert dialog).
        self._toast_bar = QFrame()
        self._toast_bar.setVisible(False)
        tl = QHBoxLayout(self._toast_bar)
        tl.setContentsMargins(12, 8, 12, 8)
        tl.setSpacing(10)
        self._toast_msg = QLabel("")
        self._toast_msg.setWordWrap(True)
        self._toast_msg.setStyleSheet("background:transparent;border:none;")
        tl.addWidget(self._toast_msg, 1)
        self._toast_action = QPushButton("")
        self._toast_action.setVisible(False)
        self._toast_action.setCursor(Qt.CursorShape.PointingHandCursor)
        tl.addWidget(self._toast_action)
        root.addWidget(self._toast_bar)
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(lambda: self._toast_bar.setVisible(False))

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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

    def _rerender_soon(self):
        # Defer so we never delete the widget that is mid-signal (combo/button).
        QTimer.singleShot(0, self._render)

    def _label(self, text: str, size: int = 13, color: str = "text_secondary",
               bold: bool = False) -> QLabel:
        lbl = QLabel(text)
        weight = "500" if bold else "400"
        lbl.setStyleSheet(
            f"color:{self._c(color)};font-size:{size}px;font-weight:{weight};"
            "background:transparent;border:none;"
        )
        return lbl

    def _chip(self, text: str, fg: str, bg: str, border: str = "") -> QLabel:
        lbl = QLabel(text)
        b = f"border:1px solid {border};" if border else "border:none;"
        lbl.setStyleSheet(
            f"color:{fg};background-color:{bg};{b}"
            "font-size:12px;padding:2px 8px;border-radius:6px;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return lbl

    def _show_toast(self, msg: str, kind: str = "info",
                    action_text: str = None, action_cb=None, ms: int = 3500):
        accent = {"info": "text_secondary", "success": "success",
                  "warning": "warning", "error": "error"}.get(kind, "text_secondary")
        self._toast_bar.setStyleSheet(
            f"QFrame{{background:{self._c('surface_variant')};"
            f"border:1px solid {self._c(accent)};border-radius:8px;}}"
        )
        self._toast_bar.setMinimumHeight(38)
        self._toast_msg.setStyleSheet(
            f"color:{self._c('text_primary')};background:transparent;border:none;font-size:13px;"
        )
        self._toast_msg.setText(msg)
        try:
            self._toast_action.clicked.disconnect()
        except Exception:
            pass
        if action_text and action_cb:
            self._toast_action.setText(action_text)
            self._toast_action.setStyleSheet(
                f"QPushButton{{color:{self._c('primary')};background:transparent;"
                "border:none;font-size:13px;font-weight:500;}"
            )
            self._toast_action.clicked.connect(action_cb)
            self._toast_action.setVisible(True)
        else:
            self._toast_action.setVisible(False)
        self._toast_bar.setVisible(True)
        self._toast_timer.start(ms)

    def _btn_style(self, primary: bool) -> str:
        if primary:
            return (
                f"QPushButton {{ color:{self._c('text_on_primary')};"
                f" background-color:{self._c('primary')}; border:none;"
                " border-radius:8px; padding:8px 16px; font-size:13px; font-weight:500; }}"
                f" QPushButton:hover {{ background-color:{self._c('primary')}; }}"
            )
        return (
            f"QPushButton {{ color:{self._c('text_primary')}; background-color:{self._c('surface_variant')};"
            f" border:1px solid {self._c('border_light')}; border-radius:8px;"
            " padding:8px 14px; font-size:13px; }}"
            f" QPushButton:hover {{ background-color:{self._c('surface')}; }}"
        )

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
        v.addWidget(self._connect_cards())
        v.addLayout(self._metrics_row())

        accounts = self.registry.all()
        if accounts:
            v.addWidget(self._label("계정  ·  카드를 펼치면 그 채널 전용 대기열을 관리해요",
                                    size=15, color="text_primary", bold=True))
            v.addWidget(self._account_list(accounts))
            v.addWidget(self._label("배분 규칙  ·  소싱 상품 → 계정 라우팅",
                                    size=15, color="text_primary", bold=True))
            v.addWidget(self._routing_box())
        else:
            v.addWidget(self._empty_state())

        v.addStretch(1)
        self._scroll.setWidget(content)

    def _flow_explainer(self) -> QWidget:
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
        row.addWidget(self._label("다계정 자동화 콘솔", size=16, color="text_primary", bold=True))
        row.addWidget(self._chip(f"{self.registry.count()} / {MAX_ACCOUNTS} 슬롯",
                                 self._c("text_secondary"), self._c("surface_variant")))
        row.addStretch(1)
        seed_btn = QPushButton("샘플 채우기")
        seed_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        seed_btn.setStyleSheet(self._btn_style(primary=False))
        seed_btn.clicked.connect(self._on_seed)
        row.addWidget(seed_btn)
        return row

    def _connect_cards(self) -> QWidget:
        box = QFrame()
        box.setStyleSheet("background:transparent;border:none;")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(self._label(
            "계정 연결  ·  연결할 플랫폼을 누르면 계정이 추가돼요 (팝업 없음)",
            size=13, color="text_secondary",
        ))
        r = QHBoxLayout()
        r.setSpacing(12)
        r.addWidget(self._connect_card("youtube"))
        r.addWidget(self._connect_card("instagram"))
        lay.addLayout(r)
        return box

    def _connect_card(self, platform: str) -> QWidget:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame{{background:{self._c('surface_variant')};border:none;border-radius:12px;}}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)
        glyph = QLabel(_PLATFORM_GLYPH.get(platform, ""))
        glyph.setStyleSheet(
            f"color:{self._c('text_secondary')};font-size:26px;background:transparent;border:none;"
        )
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(glyph)
        lay.addWidget(self._label(f"{_PLATFORM_LABEL[platform]} 계정 연결", size=15,
                                  color="text_primary", bold=True),
                      alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._label("브라우저 로그인 → 자동 등록", size=12, color="text_muted"),
                      alignment=Qt.AlignmentFlag.AlignCenter)
        btn = QPushButton("연결하기")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(self._btn_style(primary=True))
        btn.clicked.connect(lambda _=False, p=platform: self._on_connect(p))
        lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
        return card

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
            f"background-color:{self._c('surface_variant')};border:none;border-radius:8px;"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(4)
        lay.addWidget(self._label(label, size=12, color="text_muted"))
        val = QLabel(value)
        val.setStyleSheet(
            f"color:{self._c(value_color)};font-size:22px;font-weight:500;"
            "background:transparent;border:none;"
        )
        lay.addWidget(val)
        return card

    def _account_list(self, accounts: List[Account]) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        for acc in accounts:
            lay.addWidget(self._account_card(acc))
        return wrap

    def _account_card(self, acc: Account) -> QWidget:
        expanded = acc.id in self._expanded
        qlen = len(acc.queue) if isinstance(acc.queue, list) else 0
        card = QFrame()
        card.setStyleSheet(
            f"QFrame{{background:{self._c('surface')};"
            f"border:1px solid {self._c('border_light')};border-radius:12px;}}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(10)
        head.addWidget(self._label(
            f"{_PLATFORM_GLYPH.get(acc.platform, '')}  {_PLATFORM_LABEL.get(acc.platform, acc.platform)}",
            size=13, color="text_secondary"))
        head.addWidget(self._label(acc.name, size=15, color="text_primary", bold=True))
        if getattr(acc, "connected", False):
            head.addWidget(self._chip("연결됨", self._c("success"), self._c("surface")))
        else:
            head.addWidget(self._chip("연결 대기", self._c("warning"), self._c("surface")))
        head.addWidget(self._niche_combo(acc))
        head.addWidget(self._auto_toggle(acc))
        head.addWidget(self._chip(f"대기열 {qlen}", self._c("primary"), self._c("surface_variant")))
        head.addStretch(1)

        chev = QPushButton("▴ 접기" if expanded else "▾ 대기열")
        chev.setCursor(Qt.CursorShape.PointingHandCursor)
        chev.setStyleSheet(
            f"QPushButton{{color:{self._c('text_secondary')};background:transparent;"
            f"border:1px solid {self._c('border_light')};border-radius:6px;padding:4px 10px;font-size:12px;}}"
            f"QPushButton:hover{{background:{self._c('surface_variant')};}}"
        )
        chev.clicked.connect(lambda _=False, a=acc: self._toggle_expand(a.id))
        head.addWidget(chev)

        del_btn = QPushButton("✕")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setFixedSize(28, 26)
        del_btn.setToolTip("이 계정 삭제")
        del_btn.setStyleSheet(
            f"QPushButton{{color:{self._c('text_muted')};background:transparent;border:none;"
            f"border-radius:6px;font-size:15px;}}"
            f"QPushButton:hover{{color:{self._c('error')};background:{self._c('surface_variant')};}}"
        )
        del_btn.clicked.connect(lambda _=False, a=acc: self._on_delete(a))
        head.addWidget(del_btn)
        lay.addLayout(head)

        if expanded:
            lay.addWidget(self._queue_section(acc))
        else:
            foot = QHBoxLayout()
            foot.addWidget(self._label(
                f"오늘 {acc.today_count}/{acc.daily_limit}  ·  대기 {qlen}",
                size=12, color="text_muted"))
            foot.addStretch(1)
            foot.addWidget(self._label(f"다음 {acc.next_time}", size=12, color="text_muted"))
            lay.addLayout(foot)
        return card

    def _queue_section(self, acc: Account) -> QWidget:
        box = QFrame()
        box.setStyleSheet(
            f"QFrame{{background:{self._c('surface_variant')};border:none;border-radius:10px;}}"
        )
        lay = QVBoxLayout(box)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(0)
        q = acc.queue if isinstance(acc.queue, list) else []
        lay.addWidget(self._label(
            f"대기열 · {len(q)}개 · 다음 {acc.next_time} · {self.registry.stagger_minutes}분 시차",
            size=12, color="text_muted"))
        if not q:
            lay.addSpacing(6)
            lay.addWidget(self._label("대기 항목이 없어요. ‘소싱에서 더 담기’로 추가하세요.",
                                      size=12, color="text_muted"))
        else:
            for i, item in enumerate(q):
                lay.addWidget(self._queue_row(acc, i, item, len(q)))

        ctl = QHBoxLayout()
        ctl.setSpacing(8)
        ctl.setContentsMargins(0, 10, 0, 0)
        ctl.addWidget(self._pill_btn(
            "전체 재개" if acc.status == "paused" else "전체 일시정지",
            lambda a=acc: self._on_toggle(a)))
        ctl.addWidget(self._pill_btn("대기열 비우기", lambda a=acc: self._on_clear_queue(a)))
        ctl.addWidget(self._pill_btn("＋ 소싱에서 더 담기", lambda a=acc: self._on_add_queue_item(a)))
        ctl.addStretch(1)
        lay.addLayout(ctl)
        return box

    def _queue_row(self, acc: Account, i: int, item, total: int) -> QWidget:
        row = QFrame()
        row.setStyleSheet(
            f"QFrame{{background:transparent;border-top:1px solid {self._c('border_light')};}}"
        )
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 8, 0, 8)
        rl.setSpacing(8)
        title = item.get("title", "항목") if isinstance(item, dict) else str(item)
        tm = item.get("time", "") if isinstance(item, dict) else ""
        status = item.get("status", "대기") if isinstance(item, dict) else "대기"
        rl.addWidget(self._label(str(i + 1), size=12, color="text_muted"))
        rl.addWidget(self._label(title, size=13, color="text_primary"))
        if tm:
            rl.addWidget(self._label(f"· {tm}", size=12, color="text_muted"))
        rl.addStretch(1)
        st_fg = {"처리중": "primary", "완료": "success", "실패": "error"}.get(status, "text_secondary")
        rl.addWidget(self._chip(status, self._c(st_fg), self._c("surface")))
        rl.addWidget(self._icon_btn("▲", (lambda a=acc, idx=i: self._on_q_move(a, idx, -1)) if i > 0 else None, "위로"))
        rl.addWidget(self._icon_btn("▼", (lambda a=acc, idx=i: self._on_q_move(a, idx, 1)) if i < total - 1 else None, "아래로"))
        rl.addWidget(self._pill_btn("지금 올리기", lambda a=acc, idx=i: self._on_q_now(a, idx)))
        rl.addWidget(self._icon_btn("✕", lambda a=acc, idx=i: self._on_q_remove(a, idx), "삭제", danger=True))
        return row

    def _pill_btn(self, text: str, cb) -> QPushButton:
        b = QPushButton(text)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(
            f"QPushButton{{color:{self._c('text_primary')};background:{self._c('surface')};"
            f"border:1px solid {self._c('border_light')};border-radius:6px;padding:5px 10px;font-size:12px;}}"
            f"QPushButton:hover{{background:{self._c('surface_variant')};}}"
        )
        b.clicked.connect(lambda _=False: cb())
        return b

    def _icon_btn(self, glyph: str, cb, tip: str, danger: bool = False) -> QPushButton:
        b = QPushButton(glyph)
        b.setFixedSize(24, 24)
        b.setToolTip(tip)
        hover = "error" if danger else "text_primary"
        base = "text_muted" if cb else "border_light"
        b.setStyleSheet(
            f"QPushButton{{color:{self._c(base)};background:transparent;border:none;border-radius:6px;font-size:12px;}}"
            f"QPushButton:hover{{color:{self._c(hover)};background:{self._c('surface')};}}"
        )
        if cb:
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False: cb())
        else:
            b.setEnabled(False)
        return b

    def _niche_combo(self, acc: Account) -> QComboBox:
        combo = QComboBox()
        combo.setCursor(Qt.CursorShape.PointingHandCursor)
        combo.setStyleSheet(
            f"QComboBox{{background:{self._c('surface_variant')};color:{self._c('text_primary')};"
            f"border:1px solid {self._c('border_light')};border-radius:7px;padding:4px 8px;font-size:12px;}}"
            f"QComboBox::drop-down{{border:none;width:18px;}}"
            f"QComboBox QAbstractItemView{{background:{self._c('surface')};color:{self._c('text_primary')};"
            f"selection-background-color:{self._c('surface_variant')};border:1px solid {self._c('border_light')};}}"
        )
        combo.addItem("니치 선택")
        for n in _NICHES:
            combo.addItem(n)
        cur = (acc.niche or "").strip()
        if cur:
            if cur not in _NICHES:
                combo.insertItem(1, cur)
            combo.setCurrentText(cur)
        else:
            combo.setCurrentIndex(0)
        # Connect AFTER setting the current value so setup doesn't fire the handler.
        combo.currentTextChanged.connect(lambda t, aid=acc.id: self._on_niche(aid, t))
        return combo

    def _auto_toggle(self, acc: Account) -> QPushButton:
        text = _STATUS_LABEL.get(acc.status, acc.status)
        kind = _STATUS_COLOR.get(acc.status, "text_muted")
        btn = QPushButton(text)
        btn.setStyleSheet(
            f"QPushButton{{color:{self._c(kind)};background:{self._c('surface')};"
            f"border:1px solid {self._c('border_light')};border-radius:6px;padding:3px 10px;font-size:12px;}}"
        )
        if acc.status != "error":
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, a=acc: self._on_toggle(a))
        return btn

    def _routing_box(self) -> QWidget:
        box = QFrame()
        box.setStyleSheet(
            f"background-color:{self._c('surface')};"
            f"border:1px solid {self._c('border_light')};border-radius:12px;"
        )
        lay = QVBoxLayout(box)
        lay.setContentsMargins(16, 12, 16, 14)
        lay.setSpacing(0)
        routing = self.registry.routing_map()
        first = True
        for niche, accts in routing.items():
            r = QFrame()
            r.setStyleSheet(
                "background:transparent;"
                + ("" if first else f"border-top:1px solid {self._c('border_light')};")
            )
            rl = QHBoxLayout(r)
            rl.setContentsMargins(0, 10, 0, 10)
            rl.addWidget(self._chip(niche, self._c("text_secondary"), self._c("surface_variant")))
            rl.addWidget(self._label("→", size=14, color="text_muted"))
            rl.addWidget(self._label("  ".join(a.name for a in accts), size=13, color="text_primary"))
            rl.addStretch(1)
            lay.addWidget(r)
            first = False
        lay.addSpacing(6)
        lay.addWidget(self._label(
            f"타이밍: 하이브리드  ·  레인 내 {self.registry.stagger_minutes}분 시차  ·  플랫폼 간 병렬",
            size=12, color="text_muted",
        ))
        return box

    def _empty_state(self) -> QWidget:
        box = QFrame()
        box.setStyleSheet(
            f"background-color:{self._c('surface')};"
            f"border:1px dashed {self._c('text_muted')};border-radius:12px;"
        )
        lay = QVBoxLayout(box)
        lay.setContentsMargins(24, 28, 24, 28)
        lay.setSpacing(8)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._label("아직 등록된 계정이 없어요", size=15,
                                  color="text_primary", bold=True),
                      alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._label("위 ‘계정 연결’에서 플랫폼을 누르거나, ‘샘플 채우기’로 미리 볼 수 있어요.",
                                  size=13, color="text_secondary"),
                      alignment=Qt.AlignmentFlag.AlignCenter)
        return box

    # ------------------------------------------------------------------ actions
    def _on_seed(self):
        try:
            added = self.registry.seed_samples()
        except Exception as exc:
            self._show_toast(str(exc), "warning")
            return
        if added == 0:
            self._show_toast("추가할 샘플이 없어요 (이미 채워졌거나 슬롯이 가득 찼어요).", "info")
        else:
            self._show_toast(f"샘플 계정 {added}개를 채웠어요.", "success")
        self._rerender_soon()

    def _on_connect(self, platform: str):
        if getattr(self, "_connecting", False):
            return
        if self.registry.count() >= MAX_ACCOUNTS:
            self._show_toast(f"최대 {MAX_ACCOUNTS}개까지 연결할 수 있어요.", "warning")
            return
        manager = self._platform_manager(platform)
        connect_attr = "connect_channel" if platform == "youtube" else "connect_account"
        if manager is None or not hasattr(manager, connect_attr):
            # Manager unavailable (e.g. detached) → register a pending profile inline.
            self._register_pending(platform)
            return
        self._connecting = True
        self._show_toast(
            f"{_PLATFORM_LABEL.get(platform, platform)} 로그인 창이 열려요 · 브라우저에서 계속 진행하세요",
            "info", ms=15000,
        )
        worker = _ConnectWorker(manager, platform)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(
            lambda ok, info, err, p=platform: self._on_connect_finished(ok, info, err, p)
        )
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        if not hasattr(self, "_threads"):
            self._threads = []
        self._threads.append((thread, worker))
        thread.start()

    def _platform_manager(self, platform: str):
        if self.gui is None:
            return None
        attr = "youtube_manager" if platform == "youtube" else "instagram_manager"
        return getattr(self.gui, attr, None)

    def _register_pending(self, platform: str):
        n = len(self.registry.by_platform(platform)) + 1
        name = f"{_PLATFORM_LABEL.get(platform, platform)} 계정 {n}"
        try:
            acc = self.registry.add(platform=platform, name=name, niche="", connected=False)
        except Exception as exc:
            self._show_toast(str(exc), "warning")
            return
        self._show_toast(f"‘{acc.name}’ 추가됨(연결 대기) · 니치를 골라 주세요.", "info")
        self._rerender_soon()

    def _on_connect_finished(self, ok: bool, info, err: str, platform: str):
        self._connecting = False
        if not ok:
            self._show_toast(
                (err or "연결에 실패했어요.")
                + "  설정 > 영상 올리기에서 먼저 준비됐는지 확인해 주세요.",
                "warning", ms=7000,
            )
            self._rerender_soon()
            return
        info = info or {}
        name = (info.get("channel_name") or info.get("title") or info.get("username")
                or info.get("name") or f"{_PLATFORM_LABEL.get(platform, platform)} 계정")
        try:
            acc = self.registry.add(platform=platform, name=str(name).strip(),
                                    niche="", connected=True)
        except Exception as exc:
            self._show_toast(str(exc), "warning")
            return
        self._persist_account_token(platform, acc.id)
        self._show_toast(f"‘{acc.name}’ 연결됨 · 니치를 골라 주세요.", "success")
        self._rerender_soon()

    def _persist_account_token(self, platform: str, account_id: str) -> bool:
        """Copy the just-connected single token to a per-account path so future
        per-account upload routing can use the right credential."""
        try:
            src_name = "youtube_token.json" if platform == "youtube" else "instagram_settings.json"
            src = os.path.join(data_dir(), src_name)
            if not os.path.exists(src):
                return False
            dst = os.path.join(data_dir(), f"{platform}_token_{account_id}.json")
            shutil.copy2(src, dst)
            return True
        except Exception:
            return False

    def _on_niche(self, account_id: str, text: str):
        niche = "" if text == "니치 선택" else text.strip()
        self.registry.update(account_id, niche=niche)
        self._rerender_soon()

    def _on_toggle(self, acc: Account):
        new_status = "paused" if acc.status == "ok" else "ok"
        self.registry.update(acc.id, status=new_status)
        self._show_toast("자동 업로드를 " + ("켰어요." if new_status == "ok" else "멈췄어요."), "info")
        self._rerender_soon()

    def _on_delete(self, acc: Account):
        self._last_deleted = asdict(acc)
        self.registry.remove(acc.id)
        self._show_toast(f"‘{acc.name}’ 삭제됨", "info",
                         action_text="되돌리기", action_cb=self._undo_delete, ms=6000)
        self._rerender_soon()

    def _undo_delete(self):
        data = self._last_deleted or {}
        self._last_deleted = None
        self._toast_bar.setVisible(False)
        if data:
            fields = set(Account.__dataclass_fields__.keys())
            payload = {k: v for k, v in data.items() if k in fields and k != "id"}
            platform = payload.pop("platform", "youtube")
            name = payload.pop("name", "계정")
            niche = payload.pop("niche", "")
            try:
                self.registry.add(platform=platform, name=name, niche=niche, **payload)
            except Exception as exc:
                self._show_toast(str(exc), "warning")
        self._rerender_soon()

    # ---------- per-account queue actions ----------
    def _toggle_expand(self, account_id: str):
        if account_id in self._expanded:
            self._expanded.discard(account_id)
        else:
            self._expanded.add(account_id)
        self._rerender_soon()

    def _on_clear_queue(self, acc: Account):
        self.registry.clear_queue(acc.id)
        self._show_toast(f"‘{acc.name}’ 대기열을 비웠어요.", "info")
        self._rerender_soon()

    def _on_add_queue_item(self, acc: Account):
        self.registry.add_queue_item(acc.id, "새 소싱 항목", "예약 대기", "대기")
        self._show_toast(f"‘{acc.name}’ 대기열에 항목을 담았어요.", "success")
        self._rerender_soon()

    def _on_q_move(self, acc: Account, index: int, delta: int):
        self.registry.move_queue_item(acc.id, index, delta)
        self._rerender_soon()

    def _on_q_remove(self, acc: Account, index: int):
        self.registry.remove_queue_item(acc.id, index)
        self._show_toast("대기열 항목을 삭제했어요.", "info")
        self._rerender_soon()

    def _on_q_now(self, acc: Account, index: int):
        self.registry.set_queue_item_status(acc.id, index, "처리중")
        self._show_toast("지금 올리는 중… (실제 업로드 연동은 준비 중)", "info")
        self._rerender_soon()
