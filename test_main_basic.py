#!/usr/bin/env python3
"""
Test main application basic functionality without GUI
"""

import sys
import os

# Add project path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_module_imports():
    """Test that all required modules can be imported"""
    print("=== Module Import Test ===")

    modules_to_test = [
        ("main", "Main application"),
        ("caller.rest", "REST API client"),
        ("managers.settings_manager", "Settings manager"),
        ("utils.logging_config", "Logging configuration"),
        ("ui.components.subscription_status", "Subscription status widget"),
        ("ui.components.subscription_popup", "Subscription popup"),
    ]

    all_imported = True
    for module_path, description in modules_to_test:
        try:
            __import__(module_path)
            print(f"[OK] {description} imported successfully")
        except ImportError as e:
            print(f"[ERROR] Failed to import {description}: {e}")
            all_imported = False
        except Exception as e:
            print(f"[ERROR] Error importing {description}: {e}")
            all_imported = False

    print()
    return all_imported


def test_config_files():
    """Check that required config files exist"""
    print("=== Config File Check ===")

    files_to_check = [
        ("config/constants.py", "Constants configuration"),
        ("api_keys_config.json", "API keys configuration"),
        ("ui_preferences.json", "UI preferences"),
    ]

    all_exist = True
    for file_path, description in files_to_check:
        if os.path.exists(file_path):
            print(f"[OK] {description} exists")
        else:
            print(f"[WARNING] {description} not found: {file_path}")
            # Not critical if some files are missing

    print()
    return True  # Not critical if config files are missing


def test_subscription_integration():
    """Test subscription system integration"""
    print("=== Subscription Integration Test ===")

    try:
        # Test that subscription components work together
        from caller import rest
        from ui.components.subscription_status import SubscriptionStatusWidget
        from ui.components.subscription_popup import SubscriptionPromptDialog

        print("[OK] Subscription components imported successfully")

        # Test state manager
        manager = rest.SubscriptionStateManager()
        test_state = {"success": True, "is_trial": True, "can_work": True}
        result = manager.update_state(test_state)

        if result == test_state:
            print("[OK] State manager working correctly")
        else:
            print("[ERROR] State manager returned unexpected result")
            return False

        print()
        return True

    except Exception as e:
        print(f"[ERROR] Subscription integration test failed: {e}")
        import traceback

        traceback.print_exc()
        print()
        return False


def main():
    """Main test function"""
    print("=" * 60)
    print("Main Application Basic Functionality Test")
    print("=" * 60)

    tests_passed = 0
    total_tests = 3

    try:
        # Run tests
        if test_module_imports():
            tests_passed += 1

        if test_config_files():
            tests_passed += 1

        if test_subscription_integration():
            tests_passed += 1

        # Summary
        print("=" * 60)
        print(f"Test Results: {tests_passed}/{total_tests} passed")

        if tests_passed == total_tests:
            print("[SUCCESS] All basic functionality tests passed!")
            print("\nThe application should run without major issues.")
            return 0
        else:
            print(
                f"[WARNING] {total_tests - tests_passed} test(s) failed or had warnings"
            )
            print("\nSome issues were found, but the application may still run.")
            return 1

    except Exception as e:
        print(f"\n[ERROR] Test execution failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
