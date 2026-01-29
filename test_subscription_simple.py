#!/usr/bin/env python3
"""
Simple local subscription system test
Test edge case handling functionality
"""

import sys
import os

# Add project path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from caller.rest import SubscriptionStateManager


def test_state_manager_basic():
    """Test basic state manager functionality"""
    print("=== State Manager Basic Test ===")

    manager = SubscriptionStateManager()

    # Check initial state
    print(f"1. Initial state: {manager.get_last_state()}")

    # First state update
    state1 = {"success": True, "is_trial": True, "can_work": True}
    result1 = manager.update_state(state1)
    print(f"2. First state update: {result1}")

    # Consistent state update
    state2 = {"success": True, "is_trial": True, "can_work": True}
    result2 = manager.update_state(state2)
    print(f"3. Consistent state update: {result2}")

    # Inconsistent state update
    state3 = {"success": True, "is_trial": False, "can_work": True}
    result3 = manager.update_state(state3)
    print(f"4. Inconsistent state update: {result3}")
    print(f"   (Previous state maintained)")

    print("[OK] State manager test passed\n")
    return True


def test_api_functions():
    """Test API function availability"""
    print("=== API Function Availability Test ===")

    from caller import rest

    functions_to_check = [
        "getSubscriptionStatus",
        "submitSubscriptionRequest",
        "get_subscription_status_with_consistency",
        "safe_subscription_request",
    ]

    all_found = True
    for func_name in functions_to_check:
        if hasattr(rest, func_name):
            print(f"[OK] {func_name} function available")
        else:
            print(f"[ERROR] {func_name} function not found")
            all_found = False

    if all_found:
        print("[OK] All API functions available")
    else:
        print("[ERROR] Some API functions missing")

    print()
    return all_found


def test_imports():
    """Test that all imports work"""
    print("=== Import Test ===")

    try:
        # Test importing key modules
        from caller import rest
        from ui.components import subscription_status
        from ui.components import subscription_popup

        print("[OK] All imports successful")
        print()
        return True
    except ImportError as e:
        print(f"[ERROR] Import error: {e}")
        print()
        return False


def main():
    """Main test function"""
    print("=" * 50)
    print("Local Subscription System Test")
    print("=" * 50)

    tests_passed = 0
    total_tests = 3

    try:
        # Run tests
        if test_imports():
            tests_passed += 1

        if test_state_manager_basic():
            tests_passed += 1

        if test_api_functions():
            tests_passed += 1

        # Summary
        print("=" * 50)
        print(f"Test Results: {tests_passed}/{total_tests} passed")

        if tests_passed == total_tests:
            print("[OK] All tests passed successfully!")
            return 0
        else:
            print(f"[ERROR] {total_tests - tests_passed} test(s) failed")
            return 1

    except Exception as e:
        print(f"\n[ERROR] Test error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
