"""
구독 시스템 에지 케이스 테스트
네트워크 오류, 경쟁 조건, 상태 불일치 등의 시나리오 테스트
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import threading
import time
import requests

# 테스트 대상 모듈 임포트
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from caller.rest import SubscriptionStateManager, with_retry, handle_token_expiry


class TestSubscriptionEdgeCases(unittest.TestCase):
    """구독 시스템 에지 케이스 테스트"""

    def setUp(self):
        """테스트 설정"""
        self.state_manager = SubscriptionStateManager()

    def test_state_manager_initial_state(self):
        """상태 관리자 초기 상태 테스트"""
        self.assertIsNone(self.state_manager.get_last_state())

    def test_state_manager_first_update(self):
        """첫 상태 업데이트 테스트"""
        test_state = {"success": True, "is_trial": True, "can_work": True}
        result = self.state_manager.update_state(test_state)

        self.assertEqual(result, test_state)
        self.assertEqual(self.state_manager.get_last_state(), test_state)

    def test_state_manager_consistent_updates(self):
        """일관된 상태 업데이트 테스트"""
        state1 = {"success": True, "is_trial": True, "can_work": True}
        state2 = {"success": True, "is_trial": True, "can_work": True}

        result1 = self.state_manager.update_state(state1)
        result2 = self.state_manager.update_state(state2)

        self.assertEqual(result1, state1)
        self.assertEqual(result2, state2)
        self.assertEqual(self.state_manager.get_last_state(), state2)

    def test_state_manager_inconsistent_detection(self):
        """상태 불일치 감지 테스트"""
        state1 = {"success": True, "is_trial": True, "can_work": True}
        state2 = {"success": True, "is_trial": False, "can_work": True}  # is_trial 변경

        self.state_manager.update_state(state1)
        result = self.state_manager.update_state(state2)

        # 불일치 감지 시 이전 상태 유지
        self.assertEqual(result, state1)
        self.assertEqual(self.state_manager.get_last_state(), state1)

    def test_state_manager_api_failure_not_inconsistent(self):
        """API 실패는 불일치로 간주하지 않음"""
        state1 = {"success": True, "is_trial": True, "can_work": True}
        state2 = {"success": False, "message": "API 오류"}  # API 실패

        self.state_manager.update_state(state1)
        result = self.state_manager.update_state(state2)

        # API 실패는 불일치로 간주하지 않음
        self.assertEqual(result, state2)
        self.assertEqual(self.state_manager.get_last_state(), state1)  # 이전 상태 유지

    def test_state_manager_reset_after_multiple_inconsistencies(self):
        """여러 불일치 후 상태 재설정 테스트"""
        state1 = {"success": True, "is_trial": True, "can_work": True}

        # 여러 불일치 발생
        for i in range(4):  # max_inconsistent_before_reset = 3
            state2 = {"success": True, "is_trial": False, "can_work": True}
            self.state_manager.update_state(state1)
            result = self.state_manager.update_state(state2)

            if i < 3:
                # 처음 3번은 이전 상태 유지
                self.assertEqual(result, state1)
            else:
                # 4번째는 재설정
                self.assertEqual(result, state2)
                self.assertIsNone(self.state_manager.get_last_state())

    def test_retry_decorator_success(self):
        """재시도 데코레이터 성공 테스트"""
        mock_func = Mock(return_value="success")

        decorated = with_retry(max_retries=2)(mock_func)
        result = decorated()

        self.assertEqual(result, "success")
        mock_func.assert_called_once()

    def test_retry_decorator_with_retries(self):
        """재시도 데코레이터 재시도 테스트"""
        mock_func = Mock(
            side_effect=[
                ConnectionError("첫 시도 실패"),
                ConnectionError("두 번째 시도 실패"),
                "성공",
            ]
        )

        decorated = with_retry(max_retries=3, backoff_factor=0.01)(mock_func)
        result = decorated()

        self.assertEqual(result, "성공")
        self.assertEqual(mock_func.call_count, 3)

    def test_retry_decorator_max_retries_exceeded(self):
        """최대 재시도 횟수 초과 테스트"""
        mock_func = Mock(side_effect=ConnectionError("연결 실패"))

        decorated = with_retry(max_retries=2, backoff_factor=0.01)(mock_func)

        with self.assertRaises(ConnectionError):
            decorated()

        self.assertEqual(mock_func.call_count, 3)  # 초기 시도 + 2회 재시도

    def test_retry_decorator_non_network_error(self):
        """네트워크 오류가 아닌 경우 즉시 실패 테스트"""
        mock_func = Mock(side_effect=ValueError("값 오류"))

        decorated = with_retry(max_retries=2)(mock_func)

        with self.assertRaises(ValueError):
            decorated()

        mock_func.assert_called_once()  # 재시도 없이 즉시 실패

    def test_token_expiry_decorator_401_error(self):
        """토큰 만료(401) 에러 처리 테스트"""
        mock_response = Mock(status_code=401)
        http_err = requests.exceptions.HTTPError("401", response=mock_response)
        mock_func = Mock(side_effect=http_err)

        decorated = handle_token_expiry(mock_func)

        with self.assertRaises(PermissionError) as context:
            decorated()

        self.assertIn("인증 토큰이 만료", str(context.exception))

    def test_token_expiry_decorator_other_http_error(self):
        """다른 HTTP 에러는 그대로 전파"""
        mock_response = Mock(status_code=403)
        http_err = requests.exceptions.HTTPError("403", response=mock_response)
        mock_func = Mock(side_effect=http_err)

        decorated = handle_token_expiry(mock_func)

        with self.assertRaises(requests.exceptions.HTTPError):
            decorated()

    def test_concurrent_state_updates(self):
        """동시 상태 업데이트 테스트 (경쟁 조건)"""
        results = []
        lock = threading.Lock()

        def update_state(state_id):
            state = {
                "success": True,
                "is_trial": True,
                "can_work": True,
                "id": state_id,
            }
            result = self.state_manager.update_state(state)
            with lock:
                results.append((state_id, result))

        # 여러 스레드에서 동시 업데이트
        threads = []
        for i in range(10):
            t = threading.Thread(target=update_state, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 모든 업데이트가 완료되었는지 확인
        self.assertEqual(len(results), 10)

        # 상태 관리자가 마지막 상태를 기억하는지 확인
        last_state = self.state_manager.get_last_state()
        self.assertIsNotNone(last_state)
        self.assertTrue(last_state["success"])

    def test_state_manager_thread_safety(self):
        """상태 관리자 스레드 안전성 테스트"""
        import concurrent.futures

        def stress_test(iterations):
            for _ in range(iterations):
                state = {
                    "success": True,
                    "is_trial": bool(_ % 2),
                    "can_work": True,
                    "timestamp": time.time(),
                }
                self.state_manager.update_state(state)
                time.sleep(0.001)  # 컨텍스트 스위칭 유도

        # 여러 스레드에서 스트레스 테스트
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(stress_test, 20) for _ in range(5)]
            concurrent.futures.wait(futures)

        # 데드락이나 경쟁 조건 없이 완료되었는지 확인
        last_state = self.state_manager.get_last_state()
        self.assertIsNotNone(last_state)
        self.assertTrue(last_state["success"])

    def test_partial_state_comparison(self):
        """부분 상태 비교 테스트 (일부 필드만 있는 경우)"""
        state1 = {"success": True, "is_trial": True}  # can_work 없음
        state2 = {"success": True, "is_trial": True, "can_work": True}

        result1 = self.state_manager.update_state(state1)
        result2 = self.state_manager.update_state(state2)

        # can_work 필드가 하나에만 있어도 불일치로 간주하지 않음
        self.assertEqual(result1, state1)
        self.assertEqual(result2, state2)

    def test_none_values_in_state(self):
        """상태에 None 값이 있는 경우 테스트"""
        state1 = {"success": True, "is_trial": None, "can_work": True}
        state2 = {"success": True, "is_trial": False, "can_work": True}

        result1 = self.state_manager.update_state(state1)
        result2 = self.state_manager.update_state(state2)

        # None 값은 비교에서 제외
        self.assertEqual(result1, state1)
        self.assertEqual(result2, state2)


class TestNetworkErrorScenarios(unittest.TestCase):
    """네트워크 오류 시나리오 테스트"""

    @patch("caller.rest._secure_session")
    @patch("caller.rest._get_auth_token", return_value="token")
    def test_subscription_status_network_timeout(self, _mock_token, mock_session):
        """구독 상태 조회 네트워크 타임아웃 테스트"""
        from caller.rest import getSubscriptionStatus

        mock_session.get.side_effect = requests.exceptions.Timeout()

        result = getSubscriptionStatus("test_user")

        self.assertFalse(result["success"])
        self.assertTrue(result["is_trial"])  # 타임아웃 시 기본값
        self.assertFalse(result["can_work"])  # 보안: 검증 실패 시 작업 불가
        self.assertIn("요청 시간이 초과", result["message"])

    @patch("caller.rest._secure_session")
    @patch("caller.rest._get_auth_token", return_value="token")
    def test_subscription_status_connection_error(self, _mock_token, mock_session):
        """구독 상태 조회 연결 오류 테스트"""
        from caller.rest import getSubscriptionStatus

        mock_session.get.side_effect = requests.exceptions.ConnectionError()

        result = getSubscriptionStatus("test_user")

        self.assertFalse(result["success"])
        self.assertTrue(result["is_trial"])
        self.assertFalse(result["can_work"])  # 보안: 검증 실패 시 작업 불가
        self.assertIn("서버 접속이 불안정", result["message"])

    @patch("caller.rest._secure_session")
    @patch("caller.rest._get_auth_token", return_value="token")
    def test_subscription_request_rate_limit(self, _mock_token, mock_session):
        """구독 신청 속도 제한 테스트"""
        from caller.rest import submitSubscriptionRequest

        mock_response = Mock()
        mock_response.status_code = 429  # Too Many Requests
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "429", response=mock_response
        )
        mock_session.post.return_value = mock_response

        result = submitSubscriptionRequest("test_user", "테스트 메시지")

        self.assertFalse(result["success"])
        self.assertIn("서버 접속이 불안정", result["message"])


if __name__ == "__main__":
    unittest.main()
