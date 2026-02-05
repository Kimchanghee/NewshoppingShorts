#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Page Capture Utility - 앱 내 모든 페이지 캡처
Shopping Shorts Maker 앱의 모든 UI 페이지를 캡처하여 로컬에 저장

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
    """앱 페이지 캡처 유틸리티"""

    # 캡처할 페이지 정의
    PAGES = [
        {"id": "url_tab", "name": "URL 입력", "tab_index": 0},
        {"id": "style_tab", "name": "스타일 설정", "tab_index": 1},
        {"id": "queue_tab", "name": "작업 큐", "tab_index": 2},
    ]

    THEMES = ["light", "dark"]

    def __init__(self, output_dir: Optional[str] = None):
        """
        Args:
            output_dir: 스크린샷 저장 디렉토리
        """
        if output_dir is None:
            # 프로젝트 루트의 screenshots 폴더
            project_root = Path(__file__).parent.parent
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = project_root / "screenshots" / timestamp

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.captured_files: List[Path] = []

        logger.info(f"스크린샷 저장 경로: {self.output_dir}")

    def _save_screenshot(self, image, name: str) -> Optional[Path]:
        """스크린샷 저장"""
        try:
            safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in name)
            idx = len(self.captured_files) + 1
            filepath = self.output_dir / f"{idx:02d}_{safe_name}.png"

            image.save(str(filepath))
            self.captured_files.append(filepath)

            logger.info(f"[{idx}] 캡처: {name} -> {filepath.name}")
            return filepath

        except Exception as e:
            logger.error(f"저장 실패 ({name}): {e}")
            return None

    def capture_tkinter_widget(self, widget, name: str) -> Optional[Path]:
        """Tkinter 위젯 캡처"""
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
            logger.error("PIL/Pillow가 설치되지 않았습니다. pip install Pillow")
            return None
        except Exception as e:
            logger.error(f"Tkinter 위젯 캡처 실패: {e}")
            return None

    def capture_full_screen(self, name: str) -> Optional[Path]:
        """전체 화면 캡처"""
        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            return self._save_screenshot(screenshot, name)
        except Exception as e:
            logger.error(f"전체 화면 캡처 실패: {e}")
            return None

    def get_results(self) -> Dict[str, Any]:
        """캡처 결과 반환"""
        return {
            "total": len(self.captured_files),
            "directory": str(self.output_dir),
            "files": [str(f) for f in self.captured_files]
        }


def capture_all_app_pages(gui_instance, include_themes: bool = True) -> Dict[str, Any]:
    """
    앱의 모든 페이지 캡처

    Args:
        gui_instance: VideoAnalyzerGUI 인스턴스
        include_themes: 테마 변형도 캡처할지 여부

    Returns:
        캡처 결과 딕셔너리
    """
    capture = PageCapture()
    root = gui_instance.root

    def update_ui():
        root.update_idletasks()
        root.update()
        time.sleep(0.3)

    logger.info("=== 모든 페이지 캡처 시작 ===")

    try:
        # 1. 현재 메인 화면 캡처
        update_ui()
        capture.capture_tkinter_widget(root, "00_메인화면")

        # 2. 각 탭 캡처
        if hasattr(gui_instance, 'sidebar_container'):
            sidebar = gui_instance.sidebar_container

            for page in PageCapture.PAGES:
                try:
                    # 탭 선택
                    tab_method = getattr(sidebar, f"select_{page['id']}", None)
                    if tab_method:
                        tab_method()
                    elif hasattr(sidebar, 'show_content'):
                        sidebar.show_content(page['tab_index'])

                    update_ui()
                    time.sleep(0.2)

                    capture.capture_tkinter_widget(root, f"탭_{page['name']}")

                except Exception as e:
                    logger.warning(f"탭 캡처 실패 ({page['name']}): {e}")

        # 3. 설정 모달 캡처
        try:
            if hasattr(gui_instance, 'show_settings'):
                gui_instance.show_settings()
                update_ui()
                time.sleep(0.3)
                capture.capture_full_screen("설정_모달")

                # ESC로 닫기
                root.event_generate('<Escape>')
                update_ui()

        except Exception as e:
            logger.warning(f"설정 모달 캡처 실패: {e}")

        # 4. 테마 변형 캡처
        if include_themes:
            try:
                from ui.theme_manager import get_theme_manager
                theme_manager = get_theme_manager()
                original_theme = theme_manager.current_theme

                for theme in PageCapture.THEMES:
                    theme_manager.set_theme(theme)
                    update_ui()
                    time.sleep(0.3)
                    capture.capture_tkinter_widget(root, f"테마_{theme}")

                # 원래 테마 복원
                theme_manager.set_theme(original_theme)
                update_ui()

            except Exception as e:
                logger.warning(f"테마 캡처 실패: {e}")

    except Exception as e:
        logger.error(f"페이지 캡처 중 오류: {e}")

    results = capture.get_results()
    logger.info(f"=== 캡처 완료: {results['total']}개 파일 ===")
    logger.info(f"저장 위치: {results['directory']}")

    return results


def add_capture_menu_to_app(gui_instance):
    """
    앱에 스크린샷 캡처 메뉴/버튼 추가

    Args:
        gui_instance: VideoAnalyzerGUI 인스턴스
    """
    import tkinter as tk

    def on_capture_click():
        """캡처 버튼 클릭 핸들러"""
        try:
            # 진행 표시
            if hasattr(gui_instance, 'update_status'):
                gui_instance.update_status("스크린샷 캡처 중...")

            # 캡처 실행
            results = capture_all_app_pages(gui_instance, include_themes=True)

            # 결과 표시
            from ui.components.custom_dialog import show_info
            show_info(
                gui_instance.root,
                "캡처 완료",
                f"총 {results['total']}개의 스크린샷이 저장되었습니다.\n\n"
                f"저장 위치:\n{results['directory']}"
            )

            # 폴더 열기
            if sys.platform == 'win32':
                os.startfile(results['directory'])

        except Exception as e:
            logger.error(f"캡처 실패: {e}")
            from ui.components.custom_dialog import show_error
            show_error(gui_instance.root, "캡처 실패", str(e))

    # 키보드 단축키 바인딩 (Ctrl+Shift+S)
    gui_instance.root.bind('<Control-Shift-s>', lambda e: on_capture_click())
    gui_instance.root.bind('<Control-Shift-S>', lambda e: on_capture_click())

    logger.info("스크린샷 캡처 단축키 등록: Ctrl+Shift+S")

    return on_capture_click


def capture_login_screen():
    """로그인 화면 캡처 (PyQt6)"""
    try:
        from PyQt6.QtWidgets import QApplication

        capture = PageCapture()
        app = QApplication.instance()

        if app:
            for widget in app.topLevelWidgets():
                if widget.isVisible():
                    pixmap = widget.grab()

                    # PIL로 변환
                    from PIL import Image
                    import io

                    buffer = io.BytesIO()
                    pixmap.save(buffer, "PNG")
                    buffer.seek(0)
                    image = Image.open(buffer)

                    capture._save_screenshot(image, f"로그인_{widget.objectName() or 'window'}")

        return capture.get_results()

    except Exception as e:
        logger.error(f"로그인 화면 캡처 실패: {e}")
        return {"total": 0, "directory": "", "files": []}


if __name__ == "__main__":
    # 독립 실행 시 현재 화면 캡처
    import argparse

    parser = argparse.ArgumentParser(description="페이지 캡처 유틸리티")
    parser.add_argument("--delay", type=float, default=2.0, help="캡처 전 대기 시간(초)")
    args = parser.parse_args()

    print(f"\n{args.delay}초 후 현재 화면을 캡처합니다...")
    time.sleep(args.delay)

    capture = PageCapture()
    capture.capture_full_screen("screen_capture")

    results = capture.get_results()
    print(f"\n캡처 완료: {results['total']}개")
    print(f"저장 위치: {results['directory']}")

    # Windows에서 폴더 열기
    if sys.platform == 'win32':
        os.startfile(results['directory'])
