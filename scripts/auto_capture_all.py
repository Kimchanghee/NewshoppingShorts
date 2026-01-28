#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Auto Capture All Pages - PyAutoGUI based
Automatically captures all UI pages by controlling the app
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime

# Fix encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from PIL import ImageGrab
    import pyautogui
    pyautogui.FAILSAFE = False
except ImportError:
    print("Installing required packages...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pillow", "pyautogui", "-q"])
    from PIL import ImageGrab
    import pyautogui
    pyautogui.FAILSAFE = False


class AutoCapture:
    """Automated screenshot capture for all app pages"""

    def __init__(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = PROJECT_ROOT / "screenshots" / f"all_pages_{timestamp}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.count = 0
        print(f"Output: {self.output_dir}")

    def capture(self, name: str) -> Path:
        """Capture full screen"""
        time.sleep(0.5)  # Wait for UI to render
        self.count += 1
        screenshot = ImageGrab.grab()
        filepath = self.output_dir / f"{self.count:02d}_{name}.png"
        screenshot.save(str(filepath))
        print(f"  [{self.count}] {name}")
        return filepath

    def click(self, x: int, y: int):
        """Click at position"""
        pyautogui.click(x, y)
        time.sleep(0.3)

    def press(self, key: str):
        """Press a key"""
        pyautogui.press(key)
        time.sleep(0.2)

    def hotkey(self, *keys):
        """Press hotkey combination"""
        pyautogui.hotkey(*keys)
        time.sleep(0.3)


def find_window_by_title(title: str):
    """Find window position by title (Windows)"""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32

        # Find window
        hwnd = user32.FindWindowW(None, None)

        # Enumerate windows
        windows = []

        def callback(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    if title.lower() in buff.value.lower():
                        rect = wintypes.RECT()
                        user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        windows.append({
                            'hwnd': hwnd,
                            'title': buff.value,
                            'rect': (rect.left, rect.top, rect.right, rect.bottom)
                        })
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(callback), 0)

        return windows[0] if windows else None

    except Exception as e:
        print(f"Window search error: {e}")
        return None


def capture_with_running_app():
    """Capture all pages from running app"""
    capture = AutoCapture()

    print("\n=== Starting Auto Capture ===\n")

    # 1. Current screen (whatever is visible)
    capture.capture("01_current_screen")

    # 2. Try to find app window
    app_window = None
    for title in ["Shopping", "SSMaker", "Shorts Maker", "login", "Login"]:
        app_window = find_window_by_title(title)
        if app_window:
            print(f"Found window: {app_window['title']}")
            break

    if app_window:
        # Focus the window
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.SetForegroundWindow(app_window['hwnd'])
            time.sleep(0.5)
        except Exception:
            pass

        capture.capture("02_app_window")

    # 3. Capture with keyboard navigation (if app is focused)
    print("\nTrying keyboard navigation...")

    # Tab 1 (usually selected by default)
    capture.capture("03_tab1_url_input")

    # Tab 2 - try clicking or keyboard
    try:
        pyautogui.hotkey('ctrl', '2')  # Some apps use Ctrl+number for tabs
        time.sleep(0.5)
        capture.capture("04_tab2_style")
    except Exception:
        pass

    # Tab 3
    try:
        pyautogui.hotkey('ctrl', '3')
        time.sleep(0.5)
        capture.capture("05_tab3_queue")
    except Exception:
        pass

    # Settings (try common shortcuts)
    try:
        pyautogui.hotkey('ctrl', 'comma')  # Ctrl+, for settings
        time.sleep(0.5)
        capture.capture("06_settings")
        pyautogui.press('escape')
        time.sleep(0.3)
    except Exception:
        pass

    # Theme toggle (if available)
    try:
        pyautogui.hotkey('ctrl', 't')  # Try Ctrl+T for theme
        time.sleep(0.5)
        capture.capture("07_theme_toggled")
    except Exception:
        pass

    # Final summary
    print(f"\n=== Capture Complete ===")
    print(f"Total: {capture.count} screenshots")
    print(f"Location: {capture.output_dir}")

    # List files
    print("\nFiles:")
    for f in sorted(capture.output_dir.glob("*.png")):
        print(f"  - {f.name}")

    # Open folder
    if sys.platform == 'win32':
        os.startfile(capture.output_dir)

    return capture.output_dir


def capture_manual_sequence():
    """Manual capture with prompts"""
    capture = AutoCapture()

    pages = [
        ("login", "Login Screen"),
        ("loading", "Loading/Init Screen"),
        ("main", "Main Window"),
        ("tab1", "URL Input Tab"),
        ("tab2", "Style Settings Tab"),
        ("tab3", "Queue Tab"),
        ("settings", "Settings Modal"),
        ("theme_light", "Light Theme"),
        ("theme_dark", "Dark Theme"),
    ]

    print("\n=== Manual Capture Mode ===")
    print("Show each screen, then press Enter to capture.")
    print("Type 's' to skip, 'q' to quit.\n")

    for key, name in pages:
        user_input = input(f"[{name}] Ready? (Enter/s/q): ").strip().lower()

        if user_input == 'q':
            break
        elif user_input == 's':
            print(f"  Skipped: {name}")
            continue

        time.sleep(0.3)
        capture.capture(f"{key}_{name.replace(' ', '_')}")

    print(f"\n=== Capture Complete ===")
    print(f"Total: {capture.count} screenshots")
    print(f"Location: {capture.output_dir}")

    if sys.platform == 'win32':
        os.startfile(capture.output_dir)

    return capture.output_dir


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Auto capture all pages")
    parser.add_argument("--mode", choices=["auto", "manual"], default="auto",
                       help="Capture mode")
    parser.add_argument("--delay", type=float, default=2.0,
                       help="Initial delay in seconds")

    args = parser.parse_args()

    print(f"\nStarting in {args.delay} seconds...")
    print("Make sure the app is running and visible.\n")
    time.sleep(args.delay)

    if args.mode == "auto":
        capture_with_running_app()
    else:
        capture_manual_sequence()
