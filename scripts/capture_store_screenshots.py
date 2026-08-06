#!/usr/bin/env python
"""Capture deterministic Microsoft Store screenshots from the SSMaker UI.

Unlike desktop-wide capture utilities, this script grabs the application
widget directly. That prevents unrelated windows, notifications, and account
information from leaking into Store listing assets.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import VideoAnalyzerGUI  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "dist" / "store-listing",
        help="Directory for the generated PNG files",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv[:1])
    window = VideoAnalyzerGUI()
    window.resize(1600, 900)
    window.show()

    captures = [
        ("01-creation-mode.png", "mode", None),
        ("02-video-source.png", "source", "single"),
        ("03-ending-message.png", "cta", "single"),
        ("04-subtitle-font.png", "font", "single"),
        ("05-subtitle-layout.png", "subtitle_settings", "single"),
    ]
    results: list[Path] = []

    def sanitize_runtime_state() -> None:
        """Keep listing images free of local job history and account data."""
        window.overall_numeric_label.setText("0/0 (0%)")
        window.overall_witty_label.setText("만들 목록을 채우면 제작이 시작돼요")
        window.progress_panel.set_current_task("대기 중...", status="idle")
        for step_key in tuple(window.step_indicators):
            window.progress_panel.update_step_status(step_key, "pending")

    def capture(index: int = 0) -> None:
        if index >= len(captures):
            for path in results:
                print(path)
            window.close()
            app.quit()
            return

        filename, step_id, mode = captures[index]
        if mode:
            window._on_mode_selected(mode)
        window._on_step_selected(step_id)
        sanitize_runtime_state()
        app.processEvents()

        output_path = output_dir / filename
        if not window.grab().save(str(output_path), "PNG"):
            raise RuntimeError(f"Unable to save screenshot: {output_path}")
        results.append(output_path)
        QTimer.singleShot(700, lambda: capture(index + 1))

    QTimer.singleShot(1500, capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
