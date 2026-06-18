#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Open the app directly on the live Summer Coupang queue status page."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import VideoAnalyzerGUI  # noqa: E402

SCREENSHOT_PATH = Path.home() / ".ssmaker" / "summer_coupang_queue_status.png"
LOG_PATH = Path.home() / ".ssmaker" / "summer_coupang_queue_status.log"


def _log(message: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(message.rstrip() + "\n")


def _save_screenshot(gui: VideoAnalyzerGUI) -> None:
    ok = gui.grab().save(str(SCREENSHOT_PATH), "PNG")
    _log(f"screenshot saved={ok} path={SCREENSHOT_PATH}")


def _open_queue_status(gui: VideoAnalyzerGUI) -> None:
    try:
        if hasattr(gui, "_on_step_selected"):
            gui._on_step_selected("queue")
        gui.resize(1280, 820)
        update = getattr(gui, "update_url_listbox", None)
        if callable(update):
            update()
        gui.show()
        gui.raise_()
        gui.activateWindow()
        QTimer.singleShot(800, lambda: _save_screenshot(gui))
        QTimer.singleShot(3000, lambda: _save_screenshot(gui))
        _log("opened queue status page")
    except Exception:
        _log("ERROR while opening queue status page")
        _log(traceback.format_exc())
        raise


def main() -> int:
    LOG_PATH.write_text("starting queue status launcher\n", encoding="utf-8")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    gui = VideoAnalyzerGUI()
    gui.resize(1280, 560)
    gui.show()
    QTimer.singleShot(1500, lambda: _open_queue_status(gui))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
