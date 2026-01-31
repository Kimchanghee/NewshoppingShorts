#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Page Capture Utility - ????ëª¨ë“  ?˜ì´ì§€ ìº¡ì²˜
Shopping Shorts Maker ?±ì˜ ëª¨ë“  UI ?˜ì´ì§€ë¥?ìº¡ì²˜?˜ì—¬ ë¡œì»¬???€??
Usage in app:
    from utils.page_capture import capture_all_app_pages
    capture_all_app_pages(gui_instance)

Or from command line:
    python -m utils.page_capture
"""

import os
import sys
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class PageCapture:
    """???˜ì´ì§€ ìº¡ì²˜ ? í‹¸ë¦¬í‹°"""

    # ìº¡ì²˜???˜ì´ì§€ ?•ì˜
    PAGES = [
        {"id": "url_tab", "name": "URL ?…ë ¥", "tab_index": 0},
        {"id": "style_tab", "name": "?¤í????¤ì •", "tab_index": 1},
        {"id": "queue_tab", "name": "?‘ì—… ??, "tab_index": 2},
    ]

    THEMES = ["light", "dark"]

    def __init__(self, output_dir: Optional[str] = None):
        """
        Args:
            output_dir: ?¤í¬ë¦°ìƒ· ?€???”ë ‰? ë¦¬
        """
        if output_dir is None:
            # ?„ë¡œ?íŠ¸ ë£¨íŠ¸??screenshots ?´ë”
            project_root = Path(__file__).parent.parent
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = project_root / "screenshots" / timestamp

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.captured_files: List[Path] = []

        logger.info(f"?¤í¬ë¦°ìƒ· ?€??ê²½ë¡œ: {self.output_dir}")

    def _save_screenshot(self, image, name: str) -> Optional[Path]:
        """?¤í¬ë¦°ìƒ· ?€??""
        try:
            safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in name)
            idx = len(self.captured_files) + 1
            filepath = self.output_dir / f"{idx:02d}_{safe_name}.png"

            image.save(str(filepath))
            self.captured_files.append(filepath)

            logger.info(f"[{idx}] ìº¡ì²˜: {name} -> {filepath.name}")
            return filepath

        except Exception as e:
            logger.error(f"?€???¤íŒ¨ ({name}): {e}")
            return None

    def None -> Optional[Path]:
        """Tkinter ?„ì ¯ ìº¡ì²˜"""
        try:
            from PIL import ImageGrab

            widget.update_idletasks()
            widget.update()

            x = widget.winfo_rootx()
            y = widget.winfo_rooty()
            w = widget.winfo_width()
            h = widget.winfo_height()

            screenshot = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            return self._save_screenshot(screenshot, name)

        except ImportError:
            logger.error("PIL/Pillowê°€ ?¤ì¹˜?˜ì? ?Šì•˜?µë‹ˆ?? pip install Pillow")
            return None
        except Exception as e:
            logger.error(f"Tkinter ?„ì ¯ ìº¡ì²˜ ?¤íŒ¨: {e}")
            return None

    def capture_full_screen(self, name: str) -> Optional[Path]:
        """?„ì²´ ?”ë©´ ìº¡ì²˜"""
        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            return self._save_screenshot(screenshot, name)
        except Exception as e:
            logger.error(f"?„ì²´ ?”ë©´ ìº¡ì²˜ ?¤íŒ¨: {e}")
            return None

    def get_results(self) -> Dict[str, Any]:
        """ìº¡ì²˜ ê²°ê³¼ ë°˜í™˜"""
        return {
            "total": len(self.captured_files),
            "directory": str(self.output_dir),
            "files": [str(f) for f in self.captured_files]
        }


def capture_all_app_pages(gui_instance, include_themes: bool = True) -> Dict[str, Any]:
    """
    ?±ì˜ ëª¨ë“  ?˜ì´ì§€ ìº¡ì²˜

    Args:
        gui_instance: VideoAnalyzerGUI ?¸ìŠ¤?´ìŠ¤
        include_themes: ?Œë§ˆ ë³€?•ë„ ìº¡ì²˜? ì? ?¬ë?

    Returns:
        ìº¡ì²˜ ê²°ê³¼ ?•ì…”?ˆë¦¬
    """
    capture = PageCapture()
    root = gui_instance.root

    def update_ui():
        root.update_idletasks()
        root.update()
        time.sleep(0.3)

    logger.info("=== ëª¨ë“  ?˜ì´ì§€ ìº¡ì²˜ ?œì‘ ===")

    try:
        # 1. ?„ì¬ ë©”ì¸ ?”ë©´ ìº¡ì²˜
        update_ui()
        capture.None

        # 2. ê°???ìº¡ì²˜
        if hasattr(gui_instance, 'sidebar_container'):
            sidebar = gui_instance.sidebar_container

            for page in PageCapture.PAGES:
                try:
                    # ??? íƒ
                    tab_method = getattr(sidebar, f"select_{page['id']}", None)
                    if tab_method:
                        tab_method()
                    elif hasattr(sidebar, 'show_content'):
                        sidebar.show_content(page['tab_index'])

                    update_ui()
                    time.sleep(0.2)

                    capture.None

                except Exception as e:
                    logger.warning(f"??ìº¡ì²˜ ?¤íŒ¨ ({page['name']}): {e}")

        # 3. ?¤ì • ëª¨ë‹¬ ìº¡ì²˜
        try:
            if hasattr(gui_instance, 'show_settings'):
                gui_instance.show_settings()
                update_ui()
                time.sleep(0.3)
                capture.capture_full_screen("?¤ì •_ëª¨ë‹¬")

                # ESCë¡??«ê¸°
                root.event_generate('<Escape>')
                update_ui()

        except Exception as e:
            logger.warning(f"?¤ì • ëª¨ë‹¬ ìº¡ì²˜ ?¤íŒ¨: {e}")

        # 4. ?Œë§ˆ ë³€??ìº¡ì²˜
        if include_themes:
            try:
                from ui.theme_manager import get_theme_manager
                theme_manager = get_theme_manager()
                original_theme = theme_manager.current_theme

                for theme in PageCapture.THEMES:
                    theme_manager.set_theme(theme)
                    update_ui()
                    time.sleep(0.3)
                    capture.None

                # ?ë˜ ?Œë§ˆ ë³µì›
                theme_manager.set_theme(original_theme)
                update_ui()

            except Exception as e:
                logger.warning(f"?Œë§ˆ ìº¡ì²˜ ?¤íŒ¨: {e}")

    except Exception as e:
        logger.error(f"?˜ì´ì§€ ìº¡ì²˜ ì¤??¤ë¥˜: {e}")

    results = capture.get_results()
    logger.info(f"=== ìº¡ì²˜ ?„ë£Œ: {results['total']}ê°??Œì¼ ===")
    logger.info(f"?€???„ì¹˜: {results['directory']}")

    return results


def add_capture_menu_to_app(gui_instance):
    """
    ?±ì— ?¤í¬ë¦°ìƒ· ìº¡ì²˜ ë©”ë‰´/ë²„íŠ¼ ì¶”ê?

    Args:
        gui_instance: VideoAnalyzerGUI ?¸ìŠ¤?´ìŠ¤
    """
    

    def on_capture_click():
        """ìº¡ì²˜ ë²„íŠ¼ ?´ë¦­ ?¸ë“¤??""
        try:
            # ì§„í–‰ ?œì‹œ
            if hasattr(gui_instance, 'update_status'):
                gui_instance.update_status("?¤í¬ë¦°ìƒ· ìº¡ì²˜ ì¤?..")

            # ìº¡ì²˜ ?¤í–‰
            results = capture_all_app_pages(gui_instance, include_themes=True)

            # ê²°ê³¼ ?œì‹œ
            from ui.components.custom_dialog import show_info
            show_info(
                gui_instance.root,
                "ìº¡ì²˜ ?„ë£Œ",
                f"ì´?{results['total']}ê°œì˜ ?¤í¬ë¦°ìƒ·???€?¥ë˜?ˆìŠµ?ˆë‹¤.\n\n"
                f"?€???„ì¹˜:\n{results['directory']}"
            )

            # ?´ë” ?´ê¸°
            if sys.platform == 'win32':
                os.startfile(results['directory'])

        except Exception as e:
            logger.error(f"ìº¡ì²˜ ?¤íŒ¨: {e}")
            from ui.components.custom_dialog import show_error
            show_error(gui_instance.root, "ìº¡ì²˜ ?¤íŒ¨", str(e))

    # ?¤ë³´???¨ì¶•??ë°”ì¸??(Ctrl+Shift+S)
    gui_instance.root.bind('<Control-Shift-s>', lambda e: on_capture_click())
    gui_instance.root.bind('<Control-Shift-S>', lambda e: on_capture_click())

    logger.info("?¤í¬ë¦°ìƒ· ìº¡ì²˜ ?¨ì¶•???±ë¡: Ctrl+Shift+S")

    return on_capture_click


def capture_login_screen():
    """ë¡œê·¸???”ë©´ ìº¡ì²˜ (PyQt5)"""
    try:
        from PyQt5.QtWidgets import QApplication

        capture = PageCapture()
        app = QApplication.instance()

        if app:
            for widget in app.topLevelWidgets():
                if widget.isVisible():
                    pixmap = widget.grab()

                    # PILë¡?ë³€??                    from PIL import Image
                    import io

                    buffer = io.BytesIO()
                    pixmap.save(buffer, "PNG")
                    buffer.seek(0)
                    image = Image.open(buffer)

                    capture._save_screenshot(image, f"ë¡œê·¸??{widget.objectName() or 'window'}")

        return capture.get_results()

    except Exception as e:
        logger.error(f"ë¡œê·¸???”ë©´ ìº¡ì²˜ ?¤íŒ¨: {e}")
        return {"total": 0, "directory": "", "files": []}


if __name__ == "__main__":
    # ?…ë¦½ ?¤í–‰ ???„ì¬ ?”ë©´ ìº¡ì²˜
    import argparse

    parser = argparse.ArgumentParser(description="?˜ì´ì§€ ìº¡ì²˜ ? í‹¸ë¦¬í‹°")
    parser.add_argument("--delay", type=float, default=2.0, help="ìº¡ì²˜ ???€ê¸??œê°„(ì´?")
    args = parser.parse_args()

    print(f"\n{args.delay}ì´????„ì¬ ?”ë©´??ìº¡ì²˜?©ë‹ˆ??..")
    time.sleep(args.delay)

    capture = PageCapture()
    capture.capture_full_screen("screen_capture")

    results = capture.get_results()
    print(f"\nìº¡ì²˜ ?„ë£Œ: {results['total']}ê°?)
    print(f"?€???„ì¹˜: {results['directory']}")

    # Windows?ì„œ ?´ë” ?´ê¸°
    if sys.platform == 'win32':
        os.startfile(results['directory'])
