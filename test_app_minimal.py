#!/usr/bin/env python3
"""Application minimal execution test (without GUI)"""

import sys
import os
import logging
from unittest.mock import Mock, patch

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_app_initialization():
    """Application initialization test"""
    print("=" * 60)
    print("Application Initialization Test Start")
    print("=" * 60)

    try:
        # Import required modules
        import tkinter as tk
        from main import VideoAnalyzerGUI

        print("[OK] Required modules imported successfully")

        # Mock setup
        with (
            patch("tkinter.Tk") as mock_tk,
            patch("main.get_settings_manager") as mock_settings,
            patch("ui.theme_manager.get_theme_manager") as mock_get_theme_manager,
        ):
            # Mock configuration
            mock_root = Mock()
            mock_tk.return_value = mock_root

            mock_settings_instance = Mock()
            mock_settings_instance.get_theme.return_value = "light"
            mock_settings.return_value = mock_settings_instance

            mock_theme_instance = Mock()
            mock_get_theme_manager.return_value = mock_theme_instance

            print("[OK] Mock setup completed")

            # Try to initialize application
            try:
                app = VideoAnalyzerGUI(mock_root)
                print("[OK] VideoAnalyzerGUI instance created successfully")

                # Check basic attributes
                required_attrs = ["root", "theme_manager", "bg_color", "text_color"]
                for attr in required_attrs:
                    if hasattr(app, attr):
                        print(f"[OK] Attribute '{attr}' exists")
                    else:
                        print(f"[ERROR] Attribute '{attr}' missing")

                # Check methods
                required_methods = [
                    "_apply_theme_colors",
                    "_configure_ttk_styles",
                    "_setup_ui",
                ]
                for method in required_methods:
                    if hasattr(app, method) and callable(getattr(app, method)):
                        print(f"[OK] Method '{method}' exists")
                    else:
                        print(f"[ERROR] Method '{method}' missing")

                return True

            except Exception as e:
                print(f"[ERROR] Application initialization failed: {e}")
                import traceback

                traceback.print_exc()
                return False

    except ImportError as e:
        print(f"[ERROR] Module import failed: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_subscription_components():
    """Subscription components test"""
    print("\n" + "=" * 60)
    print("Subscription Components Test Start")
    print("=" * 60)

    try:
        # Test import of subscription-related modules
        from ui.components.subscription_status import SubscriptionStatusWidget
        from ui.components.subscription_popup import show_subscription_prompt
        from caller.rest import (
            safe_subscription_request,
            get_subscription_status_with_consistency,
        )

        print("[OK] Subscription component modules imported successfully")

        # Check function availability
        subscription_functions = [
            ("safe_subscription_request", safe_subscription_request),
            (
                "get_subscription_status_with_consistency",
                get_subscription_status_with_consistency,
            ),
        ]

        for name, func in subscription_functions:
            if callable(func):
                print(f"[OK] Function '{name}' is available")
            else:
                print(f"[ERROR] Function '{name}' is not available")

        return True

    except ImportError as e:
        print(f"[ERROR] Subscription component import failed: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Subscription component test error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_edge_case_handlers():
    """Edge case handlers test"""
    print("\n" + "=" * 60)
    print("Edge Case Handlers Test Start")
    print("=" * 60)

    try:
        from caller.rest import (
            with_retry,
            handle_token_expiry,
            SubscriptionStateManager,
        )

        print("[OK] Edge case handler modules imported successfully")

        # Test decorator function
        @with_retry(max_retries=2)
        def test_function():
            return "success"

        result = test_function()
        print(f"[OK] with_retry decorator test: {result}")

        # Test state manager
        manager = SubscriptionStateManager()
        print("[OK] SubscriptionStateManager instance created successfully")

        # Check basic methods
        manager.update_state({"status": "active"})
        current_state = manager.get_last_state()
        print(f"[OK] State manager basic operation: {current_state}")

        return True

    except Exception as e:
        print(f"[ERROR] Edge case handler test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main test execution"""
    print("NewshoppingShortsMaker Application Test Start")
    print("=" * 60)

    tests = [
        ("Application Initialization", test_app_initialization),
        ("Subscription Components", test_subscription_components),
        ("Edge Case Handlers", test_edge_case_handlers),
    ]

    results = []
    for test_name, test_func in tests:
        success = test_func()
        results.append((test_name, success))

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    all_passed = True
    for test_name, success in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{test_name}: {status}")
        if not success:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("All tests passed! Application basic functionality is working")
    else:
        print("Some tests failed. Additional debugging needed")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
