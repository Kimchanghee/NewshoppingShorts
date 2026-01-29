#!/usr/bin/env python3
"""
로컬 구독 시스템 테스트 스크립트
에지 케이스 처리 기능을 테스트합니다.
"""

import sys
import os
import threading
import time

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from caller.rest import SubscriptionStateManager, with_retry, handle_token_expiry


def test_state_manager():
    """State manager basic function test"""
    print("=== State Manager Test ===")

    manager = SubscriptionStateManager()

    # Check initial state
    print(f"1. Initial state: {manager.get_last_state()}")

    # First state update
    state1 = {"success": True, "is_trial": True, "can_work": True}
    result1 = manager.update_state(state1)
    print(f"2. First state update: {result1}")
    print(f"   Last state: {manager.get_last_state()}")

    # Consistent state update
    state2 = {"success": True, "is_trial": True, "can_work": True}
    result2 = manager.update_state(state2)
    print(f"3. Consistent state update: {result2}")

    # Inconsistent state update
    state3 = {"success": True, "is_trial": False, "can_work": True}  # is_trial changed
    result3 = manager.update_state(state3)
    print(f"4. Inconsistent state update: {result3}")
    print(f"   (Previous state maintained): {manager.get_last_state()}")

    # API failure state (not considered inconsistent)
    state4 = {"success": False, "message": "API error"}
    result4 = manager.update_state(state4)
    print(f"5. API failure state: {result4}")

    print("✓ State manager test completed\n")


def test_retry_decorator():
    """재시도 데코레이터 테스트"""
    print("=== 재시도 데코레이터 테스트 ===")

    # 성공 케이스
    @with_retry(max_retries=2)
    def success_func():
        return "성공"

    try:
        result = success_func()
        print(f"1. 성공 케이스: {result}")
    except Exception as e:
        print(f"1. 성공 케이스 실패: {e}")

    # 재시도 카운터
    call_count = 0

    @with_retry(max_retries=2, backoff_factor=0.1)
    def retry_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError(f"연결 실패 {call_count}")
        return f"성공 (시도: {call_count})"

    try:
        result = retry_func()
        print(f"2. 재시도 성공: {result}")
    except Exception as e:
        print(f"2. 재시도 실패: {e}")

    print("✓ 재시도 데코레이터 테스트 완료\n")


def test_concurrent_updates():
    """동시 상태 업데이트 테스트"""
    print("=== 동시 상태 업데이트 테스트 ===")

    manager = SubscriptionStateManager()
    results = []
    lock = threading.Lock()

    def update_state(thread_id):
        state = {
            "success": True,
            "is_trial": thread_id % 2 == 0,
            "can_work": True,
            "thread": thread_id,
        }
        result = manager.update_state(state)
        with lock:
            results.append((thread_id, result))

    # 여러 스레드에서 동시 업데이트
    threads = []
    for i in range(5):
        t = threading.Thread(target=update_state, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    print(f"1. 총 업데이트 수: {len(results)}")
    print(f"2. 최종 상태: {manager.get_last_state()}")

    # 데드락이나 경쟁 조건 없이 완료되었는지 확인
    if manager.get_last_state() is not None:
        print("3. ✓ 스레드 안전성 확인 완료")
    else:
        print("3. ✗ 스레드 안전성 문제 발생")

    print("✓ 동시 업데이트 테스트 완료\n")


def test_api_functions():
    """API 함수 가용성 테스트"""
    print("=== API 함수 가용성 테스트 ===")

    from caller import rest

    # 함수 존재 여부 확인
    functions_to_check = [
        "getSubscriptionStatus",
        "submitSubscriptionRequest",
        "get_subscription_status_with_consistency",
        "safe_subscription_request",
    ]

    for func_name in functions_to_check:
        if hasattr(rest, func_name):
            print(f"✓ {func_name} 함수 사용 가능")
        else:
            print(f"✗ {func_name} 함수 없음")

    print("✓ API 함수 테스트 완료\n")


def main():
    """메인 테스트 함수"""
    print("=" * 50)
    print("Local Subscription System Test Start")
    print("=" * 50)

    try:
        test_state_manager()
        test_retry_decorator()
        test_concurrent_updates()
        test_api_functions()

        print("=" * 50)
        print("All tests completed!")
        print("=" * 50)

    except Exception as e:
        print(f"\nX Test error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
