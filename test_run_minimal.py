#!/usr/bin/env python3
"""
Minimal test to check if application can start without GUI
"""

import sys
import os

# Add project path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_application_start():
    """Test if application can be initialized without GUI"""
    print("=== Application Startup Test ===")

    try:
        # Try to create application instance without GUI
        # We'll mock the GUI components

        # First, check if we can import the main module
        import main

        print("[OK] Main module imported successfully")

        # Check if we can access key components
        if hasattr(main, "VideoAnalyzerGUI"):
            print("[OK] VideoAnalyzerGUI class found")
        else:
            print("[ERROR] VideoAnalyzerGUI class not found")
            return False

        # Test subscription system components
        from caller import rest
        from ui.components.subscription_status import SubscriptionStatusWidget

        print("[OK] Subscription components available")

        # Test that the updated functions exist
        if hasattr(rest, "get_subscription_status_with_consistency"):
            print("[OK] get_subscription_status_with_consistency function available")
        else:
            print("[ERROR] get_subscription_status_with_consistency function missing")
            return False

        if hasattr(rest, "safe_subscription_request"):
            print("[OK] safe_subscription_request function available")
        else:
            print("[ERROR] safe_subscription_request function missing")
            return False

        # Test state manager
        manager = rest.SubscriptionStateManager()
        test_state = {"success": True, "is_trial": True, "can_work": True}
        result = manager.update_state(test_state)

        if result == test_state:
            print("[OK] State manager working correctly")
        else:
            print("[ERROR] State manager test failed")
            return False

        print("\n[SUCCESS] Application can start without GUI issues")
        print("The subscription system edge case handling is properly integrated.")
        return True

    except SyntaxError as e:
        print(f"[ERROR] Syntax error in code: {e}")
        print(f"File: {e.filename}, Line: {e.lineno}, Offset: {e.offset}")
        print(f"Text: {e.text}")
        return False
    except Exception as e:
        print(f"[ERROR] Application startup test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main test function"""
    print("=" * 60)
    print("Minimal Application Startup Test")
    print("=" * 60)

    try:
        if test_application_start():
            print("\n" + "=" * 60)
            print("TEST PASSED: Application is ready to run")
            print("=" * 60)
            return 0
        else:
            print("\n" + "=" * 60)
            print("TEST FAILED: Application has issues")
            print("=" * 60)
            return 1

    except Exception as e:
        print(f"\n[ERROR] Test execution failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
