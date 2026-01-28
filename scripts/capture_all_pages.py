#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Screenshot Capture Utility for Shopping Shorts Maker

Usage:
    python scripts/capture_all_pages.py

Output:
    screenshots/ folder with all page screenshots
"""

import os
import sys
import time
import logging

# Fix console encoding for Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, List, Tuple

# 프로젝트 루트 경로 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ScreenshotCapture:
    """모든 UI 페이지 스크린샷 캡처 클래스"""

    def __init__(self, output_dir: Optional[str] = None):
        """
        Args:
            output_dir: 스크린샷 저장 디렉토리 (기본: screenshots/)
        """
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = PROJECT_ROOT / "screenshots" / timestamp

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.captured_count = 0

        logger.info(f"스크린샷 저장 경로: {self.output_dir}")

    def _get_screenshot_path(self, name: str) -> Path:
        """스크린샷 파일 경로 생성"""
        # 파일명에 사용할 수 없는 문자 제거
        safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in name)
        return self.output_dir / f"{self.captured_count:02d}_{safe_name}.png"

    def capture_widget(self, widget, name: str) -> Optional[Path]:
        """
        Tkinter 위젯 캡처

        Args:
            widget: Tkinter 위젯
            name: 스크린샷 이름

        Returns:
            저장된 파일 경로
        """
        try:
            from PIL import ImageGrab

            # 위젯의 화면 좌표 가져오기
            widget.update_idletasks()
            x = widget.winfo_rootx()
            y = widget.winfo_rooty()
            width = widget.winfo_width()
            height = widget.winfo_height()

            # 스크린샷 캡처
            screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))

            # 저장
            self.captured_count += 1
            filepath = self._get_screenshot_path(name)
            screenshot.save(filepath)

            logger.info(f"[{self.captured_count}] 캡처 완료: {name} -> {filepath.name}")
            return filepath

        except Exception as e:
            logger.error(f"캡처 실패 ({name}): {e}")
            return None

    def capture_pyqt_widget(self, widget, name: str) -> Optional[Path]:
        """
        PyQt5 위젯 캡처

        Args:
            widget: PyQt5 위젯
            name: 스크린샷 이름

        Returns:
            저장된 파일 경로
        """
        try:
            from PyQt5.QtWidgets import QApplication
            from PyQt5.QtCore import QRect

            # 위젯의 스크린샷
            pixmap = widget.grab()

            # 저장
            self.captured_count += 1
            filepath = self._get_screenshot_path(name)
            pixmap.save(str(filepath))

            logger.info(f"[{self.captured_count}] 캡처 완료: {name} -> {filepath.name}")
            return filepath

        except Exception as e:
            logger.error(f"PyQt 캡처 실패 ({name}): {e}")
            return None

    def capture_full_screen(self, name: str) -> Optional[Path]:
        """
        전체 화면 캡처

        Args:
            name: 스크린샷 이름

        Returns:
            저장된 파일 경로
        """
        try:
            from PIL import ImageGrab

            screenshot = ImageGrab.grab()

            self.captured_count += 1
            filepath = self._get_screenshot_path(name)
            screenshot.save(filepath)

            logger.info(f"[{self.captured_count}] 전체 화면 캡처: {name} -> {filepath.name}")
            return filepath

        except Exception as e:
            logger.error(f"전체 화면 캡처 실패 ({name}): {e}")
            return None

    def capture_window_by_title(self, title: str, name: str) -> Optional[Path]:
        """
        윈도우 제목으로 특정 창 캡처 (Windows)

        Args:
            title: 윈도우 제목 (부분 일치)
            name: 스크린샷 이름

        Returns:
            저장된 파일 경로
        """
        try:
            import ctypes
            from ctypes import wintypes
            from PIL import ImageGrab

            user32 = ctypes.windll.user32

            # 윈도우 찾기
            hwnd = user32.FindWindowW(None, title)
            if not hwnd:
                # 부분 일치로 찾기
                def enum_windows_callback(hwnd, results):
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            if title.lower() in buff.value.lower():
                                results.append(hwnd)
                    return True

                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, ctypes.py_object)
                results = []
                user32.EnumWindows(WNDENUMPROC(enum_windows_callback), results)

                if results:
                    hwnd = results[0]

            if not hwnd:
                logger.warning(f"윈도우를 찾을 수 없음: {title}")
                return None

            # 윈도우 좌표 가져오기
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))

            # 스크린샷 캡처
            screenshot = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom))

            self.captured_count += 1
            filepath = self._get_screenshot_path(name)
            screenshot.save(filepath)

            logger.info(f"[{self.captured_count}] 윈도우 캡처: {name} -> {filepath.name}")
            return filepath

        except Exception as e:
            logger.error(f"윈도우 캡처 실패 ({name}): {e}")
            return None

    def get_summary(self) -> dict:
        """캡처 요약 정보 반환"""
        return {
            "total_captured": self.captured_count,
            "output_directory": str(self.output_dir),
            "files": list(self.output_dir.glob("*.png"))
        }


class TkinterPageCapture:
    """Tkinter 앱의 모든 페이지 자동 캡처"""

    def __init__(self, root, capture: ScreenshotCapture):
        """
        Args:
            root: Tkinter 루트 윈도우
            capture: ScreenshotCapture 인스턴스
        """
        self.root = root
        self.capture = capture
        self.pages_captured = []

    def capture_main_window(self, name: str = "main_window"):
        """메인 윈도우 캡처"""
        self.root.update_idletasks()
        self.root.update()
        time.sleep(0.3)  # UI 렌더링 대기

        path = self.capture.capture_widget(self.root, name)
        if path:
            self.pages_captured.append(name)
        return path

    def capture_all_tabs(self, gui_instance):
        """모든 탭 페이지 캡처"""
        try:
            # SidebarContainer 접근
            if hasattr(gui_instance, 'sidebar_container'):
                sidebar = gui_instance.sidebar_container

                # 각 탭 순회
                tabs = [
                    ("url_tab", "01_URL_Input_Page"),
                    ("style_tab", "02_Style_Settings_Page"),
                    ("queue_tab", "03_Queue_Page"),
                ]

                for tab_name, screenshot_name in tabs:
                    try:
                        # 탭 선택
                        if hasattr(sidebar, 'select_tab'):
                            sidebar.select_tab(tab_name)
                        elif hasattr(sidebar, f'show_{tab_name}'):
                            getattr(sidebar, f'show_{tab_name}')()

                        self.root.update_idletasks()
                        self.root.update()
                        time.sleep(0.5)  # 탭 전환 애니메이션 대기

                        path = self.capture.capture_widget(self.root, screenshot_name)
                        if path:
                            self.pages_captured.append(screenshot_name)

                    except Exception as e:
                        logger.warning(f"탭 캡처 실패 ({tab_name}): {e}")

        except Exception as e:
            logger.error(f"탭 캡처 중 오류: {e}")

    def capture_dialogs(self, gui_instance):
        """설정 다이얼로그 등 캡처"""
        try:
            # 설정 모달 열기 및 캡처
            if hasattr(gui_instance, 'show_settings') or hasattr(gui_instance, 'open_settings'):
                try:
                    # 설정 창 열기
                    if hasattr(gui_instance, 'show_settings'):
                        gui_instance.show_settings()
                    else:
                        gui_instance.open_settings()

                    self.root.update_idletasks()
                    self.root.update()
                    time.sleep(0.5)

                    # 설정 모달 캡처
                    self.capture.capture_full_screen("04_Settings_Modal")
                    self.pages_captured.append("settings_modal")

                    # 설정 창 닫기 (ESC 키 시뮬레이션)
                    self.root.event_generate('<Escape>')
                    self.root.update()
                    time.sleep(0.3)

                except Exception as e:
                    logger.warning(f"설정 다이얼로그 캡처 실패: {e}")

        except Exception as e:
            logger.error(f"다이얼로그 캡처 중 오류: {e}")

    def capture_theme_variants(self, gui_instance):
        """라이트/다크 테마 모두 캡처"""
        try:
            from ui.theme_manager import get_theme_manager
            theme_manager = get_theme_manager()

            original_theme = theme_manager.current_theme

            # 라이트 테마 캡처
            theme_manager.set_theme("light")
            self.root.update_idletasks()
            self.root.update()
            time.sleep(0.5)
            self.capture.capture_widget(self.root, "theme_light")

            # 다크 테마 캡처
            theme_manager.set_theme("dark")
            self.root.update_idletasks()
            self.root.update()
            time.sleep(0.5)
            self.capture.capture_widget(self.root, "theme_dark")

            # 원래 테마로 복원
            theme_manager.set_theme(original_theme)
            self.root.update()

        except Exception as e:
            logger.warning(f"테마 변형 캡처 실패: {e}")


def capture_running_app():
    """현재 실행 중인 앱 캡처"""
    capture = ScreenshotCapture()

    # 앱 윈도우 제목으로 찾기
    app_titles = [
        "Shopping Shorts Maker",
        "SSMaker",
        "영상 생성",
        "비디오",
    ]

    for title in app_titles:
        path = capture.capture_window_by_title(title, f"app_{title}")
        if path:
            break

    # 전체 화면도 캡처
    capture.capture_full_screen("full_screen")

    summary = capture.get_summary()
    logger.info(f"\n캡처 완료: {summary['total_captured']}개 파일")
    logger.info(f"저장 위치: {summary['output_directory']}")

    return summary


def capture_with_app_integration():
    """앱과 통합하여 모든 페이지 캡처"""
    import tkinter as tk

    capture = ScreenshotCapture()

    # 로그인 화면 캡처 (PyQt5)
    logger.info("\n=== PyQt5 로그인 화면 캡처 ===")
    try:
        from PyQt5.QtWidgets import QApplication

        # PyQt 앱 확인
        app = QApplication.instance()
        if app:
            for widget in app.topLevelWidgets():
                if widget.isVisible():
                    capture.capture_pyqt_widget(widget, f"pyqt_{widget.objectName() or 'window'}")
    except Exception as e:
        logger.info(f"PyQt5 화면 없음 또는 오류: {e}")

    # Tkinter 메인 앱 캡처
    logger.info("\n=== Tkinter 메인 앱 캡처 ===")
    try:
        # 현재 Tkinter 루트 윈도우 찾기
        root = tk._default_root
        if root and root.winfo_exists():
            tk_capture = TkinterPageCapture(root, capture)

            # 메인 윈도우 캡처
            tk_capture.capture_main_window("00_Main_Window")

            # GUI 인스턴스 찾기
            for child in root.winfo_children():
                if hasattr(child, 'sidebar_container'):
                    tk_capture.capture_all_tabs(child)
                    tk_capture.capture_dialogs(child)
                    tk_capture.capture_theme_variants(child)
                    break
        else:
            logger.info("Tkinter 루트 윈도우 없음 - 윈도우 타이틀로 캡처 시도")
            capture_running_app()

    except Exception as e:
        logger.warning(f"Tkinter 통합 캡처 실패: {e}")
        # 폴백: 윈도우 타이틀로 캡처
        capture_running_app()

    summary = capture.get_summary()
    return summary


def manual_capture_guide():
    """수동 캡처 가이드 및 대화형 캡처"""
    print("\n" + "="*60)
    print("  Shopping Shorts Maker - 스크린샷 캡처 도구")
    print("="*60)

    capture = ScreenshotCapture()

    print(f"\n저장 위치: {capture.output_dir}\n")

    pages = [
        ("login", "로그인 화면"),
        ("loading", "로딩/초기화 화면"),
        ("main", "메인 화면"),
        ("url_tab", "URL 입력 탭"),
        ("style_tab", "스타일 설정 탭"),
        ("queue_tab", "작업 큐 탭"),
        ("settings", "설정 모달"),
        ("theme_light", "라이트 테마"),
        ("theme_dark", "다크 테마"),
    ]

    print("캡처할 페이지 목록:")
    for i, (key, name) in enumerate(pages, 1):
        print(f"  {i}. {name}")

    print("\n각 페이지를 화면에 표시한 후 Enter를 누르세요.")
    print("'q'를 입력하면 종료합니다.\n")

    for key, name in pages:
        user_input = input(f"[{name}] 캡처 준비되면 Enter (건너뛰기: s, 종료: q): ").strip().lower()

        if user_input == 'q':
            break
        elif user_input == 's':
            print(f"  -> {name} 건너뜀")
            continue

        time.sleep(0.5)  # 포커스 전환 대기
        path = capture.capture_full_screen(f"{key}_{name}")

        if path:
            print(f"  -> 저장됨: {path.name}")

    summary = capture.get_summary()
    print(f"\n캡처 완료: {summary['total_captured']}개 파일")
    print(f"저장 위치: {summary['output_directory']}")

    return summary


def auto_capture_all_pages():
    """자동으로 모든 페이지 캡처 (앱 실행 중)"""
    logger.info("자동 페이지 캡처 시작...")

    capture = ScreenshotCapture()

    # 1. 현재 활성 윈도우 캡처
    time.sleep(1)
    capture.capture_full_screen("00_current_screen")

    # 2. 앱 윈도우 찾아서 캡처
    app_keywords = ["Shopping", "SSMaker", "Shorts", "영상", "비디오", "로그인"]

    for keyword in app_keywords:
        path = capture.capture_window_by_title(keyword, f"window_{keyword}")
        if path:
            time.sleep(0.3)

    # 3. 결과 출력
    summary = capture.get_summary()

    print("\n" + "="*60)
    print("  캡처 완료 요약")
    print("="*60)
    print(f"  총 캡처 수: {summary['total_captured']}개")
    print(f"  저장 위치: {summary['output_directory']}")
    print("\n  캡처된 파일:")
    for f in summary['files']:
        print(f"    - {f.name}")
    print("="*60 + "\n")

    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Shopping Shorts Maker 스크린샷 캡처")
    parser.add_argument(
        "--mode",
        choices=["auto", "manual", "running"],
        default="auto",
        help="캡처 모드 (auto: 자동, manual: 수동 가이드, running: 실행 중인 앱)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="캡처 전 대기 시간 (초)"
    )

    args = parser.parse_args()

    print(f"\nStarting capture in {args.delay} seconds...")
    print("Prepare the screen you want to capture.\n")
    time.sleep(args.delay)

    if args.mode == "auto":
        auto_capture_all_pages()
    elif args.mode == "manual":
        manual_capture_guide()
    elif args.mode == "running":
        capture_with_app_integration()
