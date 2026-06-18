#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Open the app with the Summer Coupang queue loaded in full automation UI.

When SSMAKER_FULL_AUTO_START=1, start the full automation pipeline directly
after loading the list.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import traceback
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QWidget


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import VideoAnalyzerGUI  # noqa: E402


QUEUE_PATH = Path(r"C:\Users\HOME\.ssmaker\summer_coupang_autosourcing_queue_20260603.json")
SCREENSHOT_PATH = Path(r"C:\Users\HOME\.ssmaker\summer_coupang_full_auto_loaded.png")
LOG_PATH = Path(r"C:\Users\HOME\.ssmaker\summer_coupang_full_auto_loaded.log")


def _log(message: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(message.rstrip() + "\n")


def _load_queue_urls() -> list[str]:
    payload = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    items = payload.get("items") or []
    urls: list[str] = []
    fallback_urls: list[str] = []
    for item in items:
        url = str(item.get("coupang_url") or "").strip()
        if not url:
            continue
        fallback_urls.append(url)
        if str(item.get("status") or "") == "pending":
            urls.append(url)
    return urls or fallback_urls


def _find_sourcing_panel(gui: VideoAnalyzerGUI):
    panel = getattr(gui, "sourcing_panel", None)
    if panel is not None:
        return panel
    page_index = getattr(gui, "page_index", None) or {}
    stack = getattr(gui, "stack", None)
    idx = page_index.get("sourcing")
    if stack is None or idx is None:
        return None
    card = stack.widget(idx)
    if card is None:
        return None
    for child in card.findChildren(QWidget):
        if hasattr(child, "url_input") and hasattr(child, "next_links_input"):
            return child
    return None


def _load_full_auto_list(gui: VideoAnalyzerGUI) -> None:
    _log("loading full automation list")
    urls = _load_queue_urls()
    if not urls:
        raise RuntimeError(f"No queue URLs found in {QUEUE_PATH}")
    _log(f"pending urls: {len(urls)}")

    if hasattr(gui, "_on_mode_selected"):
        gui._on_mode_selected("sourcing")
    if hasattr(gui, "_on_step_selected"):
        gui._on_step_selected("sourcing")

    panel = _find_sourcing_panel(gui)
    if panel is None:
        raise RuntimeError("Could not find sourcing panel")

    panel.url_input.setText(urls[0])
    panel.next_links_input.setPlainText("\n".join(urls[1:]))
    panel.chk_upload.setChecked(True)
    linktree_ready = False
    try:
        from managers.linktree_manager import get_linktree_manager

        linktree_ready = bool(get_linktree_manager().is_connected())
    except Exception as exc:
        _log(f"linktree readiness check failed: {exc}")
    panel.chk_linktree.setChecked(linktree_ready)
    panel.match_threshold_spin.setValue(90)
    panel.chk_auto_skip_low_similarity.setChecked(True)
    panel._sync_next_links_enabled()
    panel._refresh_readiness()
    _log(
        "loaded panel: "
        f"first={urls[0]} next_count={len(urls) - 1} "
        f"upload={panel.chk_upload.isChecked()} linktree={panel.chk_linktree.isChecked()} "
        f"autostart={os.getenv('SSMAKER_FULL_AUTO_START', '').strip()}"
    )

    # Keep the work visibly on the full automation screen and preserve evidence.
    gui.show()
    gui.raise_()
    gui.activateWindow()
    if os.getenv("SSMAKER_FULL_AUTO_START", "").strip() == "1":
        QTimer.singleShot(1000, lambda: _start_full_auto(panel))
    QTimer.singleShot(800, lambda: _save_screenshot(gui))
    QTimer.singleShot(4000, lambda: _save_screenshot(gui))


def _start_full_auto(panel) -> None:
    try:
        url = panel.url_input.text().strip()
        if not url:
            raise RuntimeError("No Coupang URL loaded in the full automation panel")
        if "coupang.com" not in url:
            raise RuntimeError(f"Loaded URL is not a Coupang URL: {url}")
        if getattr(panel, "_running", False):
            _log("direct pipeline already running")
            return

        min_similarity_score = panel._match_threshold_score()
        panel._save_match_policy()
        panel._running = True
        panel.btn_start.setEnabled(False)
        panel.btn_start.setText("Running full automation...")
        panel._apply_button_style(disabled=True)

        for indicator in panel._step_indicators.values():
            indicator.set_state("pending", "")
        panel.results_label.setText("Full automation started.")

        thread = threading.Thread(
            target=panel._run_pipeline,
            args=(url, min_similarity_score),
            daemon=True,
        )
        thread.start()
        _log(
            "direct pipeline started: "
            f"running={getattr(panel, '_running', None)} "
            f"first={url} "
            f"threshold={min_similarity_score:.2f} "
            f"upload={panel.chk_upload.isChecked()} "
            f"linktree={panel.chk_linktree.isChecked()}"
        )
    except Exception:
        _log("ERROR while starting full automation")
        _log(traceback.format_exc())
        raise


def _save_screenshot(gui: VideoAnalyzerGUI) -> None:
    ok = gui.grab().save(str(SCREENSHOT_PATH), "PNG")
    _log(f"screenshot saved={ok} path={SCREENSHOT_PATH}")


def _safe_load(gui: VideoAnalyzerGUI) -> None:
    try:
        _load_full_auto_list(gui)
    except Exception:
        _log("ERROR while loading full automation list")
        _log(traceback.format_exc())
        raise


def main() -> int:
    LOG_PATH.write_text("starting full automation launcher\n", encoding="utf-8")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    gui = VideoAnalyzerGUI()
    gui.resize(1280, 860)
    gui.show()
    QTimer.singleShot(1200, lambda: _safe_load(gui))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
