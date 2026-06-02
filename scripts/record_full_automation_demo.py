#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI demo recorder for Shopping Shorts Maker.

Flow:
1) Launch app window
2) Replay tutorial and advance "Next" steps automatically
3) Go to sourcing panel and run full automation with a Coupang link
4) Wait until sourcing/batch stops (or timeout)
5) Show upload panel and link automation(settings) panel
6) Save an mp4 recording of the app window
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import cv2

from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication, QWidget


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import VideoAnalyzerGUI  # noqa: E402
from utils.logging_config import get_logger  # noqa: E402


logger = get_logger(__name__)


class WindowRecorder(QObject):
    """Record a QWidget using QWidget.grab() frames."""

    def __init__(self, target: QWidget, output_path: str, fps: int = 10):
        super().__init__(target)
        self.target = target
        self.output_path = output_path
        self.fps = max(1, int(fps))
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._capture_frame)
        self._timer.setInterval(int(1000 / self.fps))
        self._writer: Optional[cv2.VideoWriter] = None
        self._size: Optional[tuple[int, int]] = None
        self._frames = 0

    def start(self):
        logger.info("[Recorder] start: %s", self.output_path)
        self._timer.start()

    def stop(self):
        self._timer.stop()
        if self._writer is not None:
            self._writer.release()
            self._writer = None
        logger.info("[Recorder] stop: frames=%d file=%s", self._frames, self.output_path)

    def _capture_frame(self):
        if self.target is None or not self.target.isVisible():
            return

        pixmap = self.target.grab()
        if pixmap.isNull():
            return

        qimg = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        w, h = qimg.width(), qimg.height()
        if w <= 1 or h <= 1:
            return

        ptr = qimg.bits()
        ptr.setsize(qimg.sizeInBytes())
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, w, 4)
        frame = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)

        if self._writer is None:
            # mp4 codec requires even size on many players
            out_w = w - (w % 2)
            out_h = h - (h % 2)
            self._size = (out_w, out_h)
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self._writer = cv2.VideoWriter(self.output_path, fourcc, float(self.fps), self._size)
            if not self._writer.isOpened():
                raise RuntimeError(f"Failed to open video writer: {self.output_path}")

        if self._size is None:
            return
        if (frame.shape[1], frame.shape[0]) != self._size:
            frame = cv2.resize(frame, self._size, interpolation=cv2.INTER_AREA)

        self._writer.write(frame)
        self._frames += 1


class DemoController(QObject):
    """Run scripted UI demo scenario."""

    def __init__(
        self,
        gui: VideoAnalyzerGUI,
        recorder: WindowRecorder,
        coupang_url: str,
        max_total_wait: int = 14 * 60,
        max_pipeline_wait: int = 12 * 60,
    ):
        super().__init__(gui)
        self.gui = gui
        self.recorder = recorder
        self.coupang_url = coupang_url
        self._finished = False

        self._tutorial_ticks = 0
        self._tutorial_timer = QTimer(self)
        self._tutorial_timer.timeout.connect(self._tutorial_next)

        self._monitor_timer = QTimer(self)
        self._monitor_timer.timeout.connect(self._monitor_pipeline)
        self._started_batch = False
        self._batch_start_retries = 0
        self._pipeline_started_at = 0.0
        self._max_pipeline_wait = max_pipeline_wait

        self._hard_timeout = QTimer(self)
        self._hard_timeout.setSingleShot(True)
        self._hard_timeout.timeout.connect(self._on_hard_timeout)
        self._max_total_wait = max_total_wait

    def start(self):
        print("[DEMO] start")
        self.gui.show()
        self.gui.raise_()
        self.gui.activateWindow()
        self.recorder.start()
        self._hard_timeout.start(self._max_total_wait * 1000)
        QTimer.singleShot(1200, self._start_tutorial)

    def _start_tutorial(self):
        print("[DEMO] tutorial start")
        try:
            self.gui.show_tutorial_manual()
        except Exception as e:
            logger.warning("[Demo] tutorial start failed: %s", e)
            print(f"[DEMO] tutorial start failed: {e}")
            QTimer.singleShot(500, self._start_sourcing)
            return

        # Advance tutorial like clicking "다음"
        self._tutorial_ticks = 0
        self._tutorial_timer.start(1200)

    def _tutorial_next(self):
        mgr = getattr(self.gui, "_tutorial_manager", None)
        if mgr is None or not getattr(mgr, "is_running", False):
            self._tutorial_timer.stop()
            print("[DEMO] tutorial done")
            QTimer.singleShot(800, self._start_sourcing)
            return

        try:
            mgr._go_next()
            self._tutorial_ticks += 1
        except Exception as e:
            logger.warning("[Demo] tutorial next failed: %s", e)
            print(f"[DEMO] tutorial next failed: {e}")
            self._tutorial_timer.stop()
            QTimer.singleShot(500, self._start_sourcing)
            return

        if self._tutorial_ticks >= 14:
            self._tutorial_timer.stop()
            QTimer.singleShot(1000, self._start_sourcing)

    def _start_sourcing(self):
        print("[DEMO] sourcing start")
        try:
            if hasattr(self.gui, "_on_mode_selected"):
                self.gui._on_mode_selected("sourcing")
            if hasattr(self.gui, "_on_step_selected"):
                self.gui._on_step_selected("sourcing")
        except Exception as e:
            logger.warning("[Demo] navigate sourcing failed: %s", e)

        panel = self._get_sourcing_panel()
        if panel is None:
            logger.error("[Demo] sourcing_panel not found")
            print("[DEMO] sourcing panel not found")
            QTimer.singleShot(2000, self._show_upload_panel)
            return

        panel.url_input.setText(self.coupang_url)
        panel.chk_upload.setChecked(True)
        panel.chk_linktree.setChecked(True)
        QTimer.singleShot(800, panel._on_start_clicked)

        self._pipeline_started_at = time.time()
        self._monitor_timer.start(3000)

    def _monitor_pipeline(self):
        if self._finished:
            return

        panel = self._get_sourcing_panel()
        if panel is None:
            self._monitor_timer.stop()
            QTimer.singleShot(1000, self._show_upload_panel)
            return

        running = bool(getattr(panel, "_running", False))
        batch_running = bool(getattr(self.gui, "batch_processing", False))
        queue_active = False
        yt_queue_count = 0
        try:
            qm = getattr(self.gui, "queue_manager", None)
            if qm and hasattr(qm, "has_active_queue_item"):
                queue_active = bool(qm.has_active_queue_item())
        except Exception:
            pass
        try:
            ym = getattr(self.gui, "youtube_manager", None)
            if ym and hasattr(ym, "get_queue_count"):
                yt_queue_count = int(ym.get_queue_count())
        except Exception:
            yt_queue_count = 0
        active_steps = []
        try:
            states = getattr(self.gui, "progress_states", {}) or {}
            for key in ("download", "analysis", "translation", "tts", "subtitle", "subtitle_overlay", "finalize"):
                state = states.get(key, {}) if isinstance(states, dict) else {}
                status = state.get("status")
                progress = state.get("progress")
                if status and status not in ("waiting", None):
                    active_steps.append(f"{key}:{status}:{progress}")
        except Exception:
            active_steps = []

        if batch_running:
            self._started_batch = True
        elif queue_active and (not running) and (not self._started_batch) and self._batch_start_retries < 5:
            self._batch_start_retries += 1
            try:
                print(f"[DEMO] retry batch start #{self._batch_start_retries}")
                self.gui.start_batch_processing()
            except Exception as exc:
                logger.warning("[Demo] batch start retry failed: %s", exc)

        elapsed = time.time() - self._pipeline_started_at
        print(
            "[DEMO] monitor "
            f"sourcing={running} batch={batch_running} "
            f"queue_active={queue_active} yt_q={yt_queue_count} "
            f"started_batch={self._started_batch} elapsed={elapsed:.1f}s "
            f"steps={'|'.join(active_steps[-4:])}"
        )

        if (
            self._started_batch
            and (not running)
            and (not batch_running)
            and (not queue_active)
            and yt_queue_count == 0
        ):
            self._monitor_timer.stop()
            # Give YouTube upload thread some time to work
            QTimer.singleShot(15000, self._show_upload_panel)
            return

        if (not self._started_batch) and (not running) and (not queue_active) and elapsed > 20:
            self._monitor_timer.stop()
            QTimer.singleShot(5000, self._show_upload_panel)
            return

        if elapsed >= self._max_pipeline_wait:
            logger.warning("[Demo] pipeline timeout reached")
            print("[DEMO] pipeline timeout reached")
            self._monitor_timer.stop()
            QTimer.singleShot(2000, self._show_upload_panel)

    def _show_upload_panel(self):
        if self._finished:
            return
        print("[DEMO] show upload panel")
        try:
            if hasattr(self.gui, "_on_step_selected"):
                self.gui._on_step_selected("upload")
        except Exception as e:
            logger.warning("[Demo] navigate upload failed: %s", e)
        QTimer.singleShot(7000, self._show_linktree_panel)

    def _show_linktree_panel(self):
        if self._finished:
            return
        print("[DEMO] show linktree/settings panel")
        try:
            if hasattr(self.gui, "_on_step_selected"):
                self.gui._on_step_selected("settings")
        except Exception as e:
            logger.warning("[Demo] navigate settings failed: %s", e)

        # Try to bring link automation section into view
        try:
            st = getattr(self.gui, "settings_tab", None)
            if st is not None and hasattr(st, "scroll_area"):
                sb = st.scroll_area.verticalScrollBar()
                if sb is not None:
                    sb.setValue(int(sb.maximum() * 0.45))
        except Exception as e:
            logger.debug("[Demo] settings scroll skipped: %s", e)

        QTimer.singleShot(7000, self.finish)

    def finish(self):
        if self._finished:
            return
        self._finished = True
        print("[DEMO] finish")
        if self._monitor_timer.isActive():
            self._monitor_timer.stop()
        if self._tutorial_timer.isActive():
            self._tutorial_timer.stop()
        if self._hard_timeout.isActive():
            self._hard_timeout.stop()
        self.recorder.stop()
        print(f"[DEMO] recording saved: {self.recorder.output_path}")
        logger.info("[Demo] finished")
        app = QApplication.instance()
        if app is not None:
            app.quit()
        # Some background threads can keep Python alive; force-exit after recorder release.
        QTimer.singleShot(300, lambda: os._exit(0))

    def _on_hard_timeout(self):
        if self._finished:
            return
        print("[DEMO] hard-timeout reached, forcing wrap-up screens")
        if self._monitor_timer.isActive():
            self._monitor_timer.stop()
        self._show_upload_panel()

    def _get_sourcing_panel(self):
        panel = getattr(self.gui, "sourcing_panel", None)
        if panel is not None:
            return panel

        page_index = getattr(self.gui, "page_index", None) or {}
        stack = getattr(self.gui, "stack", None)
        idx = page_index.get("sourcing")
        if stack is None or idx is None:
            return None

        try:
            card = stack.widget(idx)
        except Exception:
            return None
        if card is None:
            return None

        for child in card.findChildren(QWidget):
            if hasattr(child, "url_input") and hasattr(child, "_on_start_clicked"):
                return child
        return None


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    output_dir = Path(os.environ.get("SSMAKER_DEMO_OUTPUT_DIR") or (Path.home() / "Desktop"))
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = str(output_dir / f"ssmaker_demo_{ts}.mp4")

    coupang_url = os.environ.get("SSMAKER_DEMO_URL") or "https://link.coupang.com/a/dTH6WefOMu"
    gui = VideoAnalyzerGUI()
    demo_privacy = os.environ.get("SSMAKER_DEMO_PRIVACY", "").strip()
    if demo_privacy:
        try:
            gui.youtube_manager.get_upload_settings().default_privacy = demo_privacy
        except Exception as exc:
            logger.warning("[Demo] failed to apply demo privacy setting: %s", exc)
    fps = int(os.environ.get("SSMAKER_DEMO_FPS") or "10")
    max_minutes = int(os.environ.get("SSMAKER_DEMO_MAX_MINUTES") or "14")
    pipeline_minutes = int(os.environ.get("SSMAKER_DEMO_PIPELINE_MINUTES") or str(max(1, max_minutes - 2)))
    recorder = WindowRecorder(gui, output_path=output_path, fps=fps)
    controller = DemoController(
        gui,
        recorder,
        coupang_url=coupang_url,
        max_total_wait=max_minutes * 60,
        max_pipeline_wait=pipeline_minutes * 60,
    )

    QTimer.singleShot(0, controller.start)
    rc = app.exec()
    print(f"[DEMO] recording saved: {output_path}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
