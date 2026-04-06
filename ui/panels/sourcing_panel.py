"""
Sourcing Panel ??Mode 3 (?꾩껜 ?먮룞?? UI.
Coupang link input ??progress display ??results.
"""
from __future__ import annotations

import asyncio
import os
import threading
from typing import Optional

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QWidget, QCheckBox, QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from ui.design_system_v2 import get_design_system, get_color
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

        self.icon_label = QLabel("\u25CB")  # ??
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
            self.icon_label.setText("\u2713")  # ??
            self.icon_label.setStyleSheet(f"color: {get_color('success')}; font-weight: bold;")
            self.text_label.setStyleSheet(f"color: {get_color('text_secondary')};")
        elif state == "in_progress":
            self.icon_label.setText("\u25CF")  # ??
            self.icon_label.setStyleSheet(f"color: {get_color('primary')}; font-weight: bold;")
            self.text_label.setStyleSheet(f"color: {get_color('text_primary')}; font-weight: bold;")
        elif state == "error":
            self.icon_label.setText("\u2717")  # ??
            self.icon_label.setStyleSheet(f"color: {get_color('error')}; font-weight: bold;")
            self.text_label.setStyleSheet(f"color: {get_color('error')};")
        else:  # pending
            self.icon_label.setText("\u25CB")  # ??
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

        # ?? Input Section ??
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
        url_label = QLabel("荑좏뙜 ?곹뭹 留곹겕")
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

        self.chk_linktree = QCheckBox("留곹겕?몃━ ?먮룞 諛쒗뻾")
        self.chk_linktree.setChecked(True)
        self.chk_linktree.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        opts_layout.addWidget(self.chk_linktree)

        self.chk_upload = QCheckBox("YouTube 자동 업로드")
        self.chk_upload.setChecked(True)
        self.chk_upload.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        opts_layout.addWidget(self.chk_upload)

        opts_layout.addStretch()
        input_layout.addLayout(opts_layout)

        # Start button
        self.btn_start = QPushButton("?뚯떛 ?쒖옉")
        self.btn_start.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_base, QFont.Weight.Bold))
        self.btn_start.setMinimumHeight(42)
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_button_style()
        self.btn_start.clicked.connect(self._on_start_clicked)
        input_layout.addWidget(self.btn_start)

        main_layout.addWidget(input_frame)

        # ?? Progress Section ??
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

        progress_title = QLabel("吏꾪뻾 ?곹솴")
        progress_title.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_sm, QFont.Weight.Bold))
        progress_layout.addWidget(progress_title)

        # Step indicators
        from core.sourcing.pipeline import SourcingPipeline
        for step_id, step_label in SourcingPipeline.STEPS:
            indicator = _StepIndicator(step_id, step_label)
            self._step_indicators[step_id] = indicator
            progress_layout.addWidget(indicator)

        main_layout.addWidget(progress_frame)

        # ?? Results Section ??
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

        results_title = QLabel("寃곌낵")
        results_title.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_sm, QFont.Weight.Bold))
        results_layout.addWidget(results_title)

        self.results_label = QLabel("?뚯떛???쒖옉?섎㈃ 寃곌낵媛 ?ш린???쒖떆?⑸땲??")
        self.results_label.setFont(QFont(ds.typography.font_family_primary, ds.typography.size_xs))
        self.results_label.setStyleSheet(f"color: {get_color('text_muted')};")
        self.results_label.setWordWrap(True)
        results_layout.addWidget(self.results_label)

        main_layout.addWidget(self.results_frame)
        main_layout.addStretch()

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

    def _on_start_clicked(self):
        url = self.url_input.text().strip()
        if not url:
            self.results_label.setText("荑좏뙜 ?곹뭹 留곹겕瑜??낅젰?댁＜?몄슂.")
            self.results_label.setStyleSheet(f"color: {get_color('error')};")
            return
        if "coupang.com" not in url:
            self.results_label.setText("?좏슚??荑좏뙜 留곹겕瑜??낅젰?댁＜?몄슂. (coupang.com)")
            self.results_label.setStyleSheet(f"color: {get_color('error')};")
            return
        if self._running:
            return

        self._running = True
        self.btn_start.setEnabled(False)
        self.btn_start.setText("?뚯떛 吏꾪뻾 以?..")
        self._apply_button_style(disabled=True)

        # Reset indicators
        for ind in self._step_indicators.values():
            ind.set_state("pending", "")
        self.results_label.setText("?뚯떛???쒖옉?⑸땲??..")
        self.results_label.setStyleSheet(f"color: {get_color('text_muted')};")

        # Run in background thread
        thread = threading.Thread(target=self._run_pipeline, args=(url,), daemon=True)
        thread.start()

    def _run_pipeline(self, coupang_url: str):
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
        """Pipeline finished ??update UI and emit results."""
        self._running = False
        self.btn_start.setEnabled(True)
        self.btn_start.setText("?뚯떛 ?쒖옉")
        self._apply_button_style(disabled=False)

        report = pipeline.get_report()

        if success and pipeline.sourced_products:
            # Build results text
            lines = []
            pi = pipeline.product_info or {}
            lines.append(f"[?먮낯] {pi.get('name', 'N/A')[:50]}")
            lines.append(f"  留곹겕: {pipeline.coupang_url}")
            if pipeline.deep_link:
                lines.append(f"  ?뚰듃?덉뒪: {pipeline.deep_link}")
            lines.append("")
            for i, sp in enumerate(pipeline.sourced_products):
                p = sp["product"]
                lines.append(f"[?뚯떛 {i+1}] ({sp['source'].upper()}) ?좎궗?? {p.get('score', 0):.1%}")
                lines.append(f"  ?쒕ぉ: {p.get('title', 'N/A')[:50]}")
                lines.append(f"  留곹겕: {p.get('url', 'N/A')}")
                lines.append(f"  ?곸긽: {sp['video_file']}")
                lines.append(f"  ?ш린: {sp['size_mb']}MB")
                lines.append("")

            if pipeline.description:
                lines.append(f"[?ㅻ챸] {pipeline.description[:100]}")

            self.results_label.setText("\n".join(lines))
            self.results_label.setStyleSheet(f"color: {get_color('text_primary')};")

            # Store in app state
            if hasattr(self.gui, 'state'):
                self.gui.state.sourcing_result = report

            # Feed sourced videos into batch queue as local:// URLs
            self._enqueue_sourced_videos(pipeline)

            self.sourcing_completed.emit(report)
        else:
            error_msg = pipeline.error or "?뚯떛???ㅽ뙣?덉뒿?덈떎."
            self.results_label.setText(f"?뚯떛 ?ㅽ뙣: {error_msg}")
            self.results_label.setStyleSheet(f"color: {get_color('error')};")

    def _enqueue_sourced_videos(self, pipeline):
        """Add sourced video files to the processing queue."""
        video_paths = pipeline.get_video_paths()
        if not video_paths:
            logger.warning("[SourcingPanel] No video files to enqueue")
            self.results_label.setText(
                self.results_label.text() + "\n\n???ㅼ슫濡쒕뱶???곸긽???놁뼱 ?먯뿉 ?깅줉?섏? 紐삵뻽?듬땲??"
            )
            return

        # Add as local:// URLs to the queue
        queue_mgr = getattr(self.gui, 'queue_manager', None)
        enqueued = 0

        if not queue_mgr or not hasattr(queue_mgr, 'add_url_to_queue'):
            logger.error("[SourcingPanel] queue_manager not available, cannot enqueue videos")
            self.results_label.setText(
                self.results_label.text() + "\n\n????留ㅻ땲?瑜?李얠쓣 ???놁뒿?덈떎. ?섎룞?쇰줈 ?곸긽??異붽??댁＜?몄슂."
            )
            return

        for vpath in video_paths:
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
            if len(video_paths) > 1:
                logger.info("[SourcingPanel] One-link policy active: queued only the first valid sourced video")
            # Navigate to voice selection
            if hasattr(self.gui, '_on_step_selected'):
                QTimer.singleShot(500, lambda: self.gui._on_step_selected('voice'))
        else:
            logger.warning("[SourcingPanel] No videos were successfully enqueued")
            self.results_label.setText(
                self.results_label.text() + "\n\n???곸긽 ???깅줉???ㅽ뙣?덉뒿?덈떎. ?곸긽 ?뚯씪???뺤씤?댁＜?몄슂."
            )

    def get_sourcing_result(self) -> Optional[dict]:
        """Return last pipeline report or None."""
        if self._pipeline:
            return self._pipeline.get_report()
        return None
