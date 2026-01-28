"""
API Key Manager Module
API 키 관리 모듈

통합된 API 키 관리를 위한 단일 진입점.
SecretsManager를 통해 암호화된 저장소에서 키를 로드합니다.

Unified entry point for API key management.
Loads keys from encrypted storage via SecretsManager.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Optional

import config
from utils.logging_config import get_logger
from utils.secrets_manager import SecretsManager

logger = get_logger(__name__)


class APIKeyManager:
    """
    API 키 관리자 클래스

    기능:
    - SecretsManager를 통한 암호화된 키 로드
    - 키 로테이션 및 부하 분산
    - 차단된 키 관리 (Rate Limit 대응)
    - 사용량 추적

    Features:
    - Encrypted key loading via SecretsManager
    - Key rotation and load balancing
    - Blocked key management (Rate Limit handling)
    - Usage tracking
    """

    # 최대 API 키 개수 (UI와 동기화)
    # Maximum number of API keys (synced with UI)
    MAX_KEYS = 10

    def __init__(self, use_secrets_manager: bool = True):
        """
        API 키 관리자 초기화

        Args:
            use_secrets_manager: SecretsManager 사용 여부 (기본값: True)
                                 False로 설정 시 config.GEMINI_API_KEYS 사용
        """
        self.use_secrets_manager = use_secrets_manager
        self.blocked_keys: Dict[str, datetime] = {}
        self.current_key: Optional[str] = None
        self.usage_count: Dict[str, int] = {}

        # SecretsManager에서 키 로드 또는 config fallback
        # Load keys from SecretsManager or fallback to config
        if use_secrets_manager:
            self.api_keys = self._load_keys_from_secrets()
            # SecretsManager에 키가 없으면 config에서 로드 (마이그레이션 지원)
            # If no keys in SecretsManager, load from config (migration support)
            if not self.api_keys and config.GEMINI_API_KEYS:
                logger.info("[API Manager] SecretsManager에 키 없음, config에서 로드")
                self.api_keys = config.GEMINI_API_KEYS.copy()
        else:
            self.api_keys = config.GEMINI_API_KEYS.copy() if config.GEMINI_API_KEYS else {}

    def _load_keys_from_secrets(self) -> Dict[str, str]:
        """
        SecretsManager에서 API 키 로드 (암호화된 저장소)
        Load API keys from SecretsManager (encrypted storage)

        Returns:
            Dict[str, str]: 키 이름과 값의 딕셔너리 (api_1: value, api_2: value, ...)
        """
        loaded_keys = {}

        try:
            for i in range(1, self.MAX_KEYS + 1):
                # SecretsManager에서 사용하는 키 이름 형식: gemini_api_N
                secret_key_name = f"gemini_api_{i}"
                key_value = SecretsManager.get_api_key(secret_key_name)

                if key_value:
                    # 내부 키 이름 형식: api_N (config와 호환)
                    internal_key_name = f"api_{i}"
                    loaded_keys[internal_key_name] = key_value

            if loaded_keys:
                logger.info(f"[API Manager] SecretsManager에서 {len(loaded_keys)}개 키 로드됨")
            else:
                logger.debug("[API Manager] SecretsManager에 저장된 키 없음")

        except Exception as e:
            logger.warning(f"[API Manager] SecretsManager 로드 실패: {e}")

        return loaded_keys

    def reload_keys_from_secrets(self) -> int:
        """
        SecretsManager에서 키 다시 로드 (외부 호출용)
        Reload keys from SecretsManager (for external calls)

        Returns:
            int: 로드된 키 개수
        """
        if self.use_secrets_manager:
            self.api_keys = self._load_keys_from_secrets()
            # config 동기화
            config.GEMINI_API_KEYS = self.api_keys.copy()
            return len(self.api_keys)
        return 0

    def refresh_keys(self):
        """
        새로 추가된 키를 동적으로 로드 (기존 상태 유지)
        Dynamically load newly added keys (preserve existing state)

        SecretsManager 사용 시 암호화된 저장소에서 로드,
        그렇지 않으면 config에서 로드.
        """
        if self.use_secrets_manager:
            # SecretsManager에서 최신 키 로드
            fresh_keys = self._load_keys_from_secrets()
        else:
            fresh_keys = config.GEMINI_API_KEYS if config.GEMINI_API_KEYS else {}

        if not fresh_keys:
            return

        # 새로 추가된 키만 반영 (기존 키 상태 유지)
        # Only add new keys (preserve existing key states)
        new_keys_added = []
        for key_name, key_value in fresh_keys.items():
            if key_name not in self.api_keys:
                self.api_keys[key_name] = key_value
                new_keys_added.append(key_name)

        if new_keys_added:
            logger.info(f"[API Manager] 새 키 {len(new_keys_added)}개 감지됨: {', '.join(new_keys_added)}")

        # 기존 키 값이 변경된 경우도 업데이트
        # Also update if existing key values have changed
        for key_name, key_value in fresh_keys.items():
            if key_name in self.api_keys and self.api_keys[key_name] != key_value:
                self.api_keys[key_name] = key_value
                logger.info(f"[API Manager] {key_name} 키 값 업데이트됨")

    def get_available_key(self):
        """사용 가능한 API 키 가져오기"""
        # ★ 매번 호출 시 새로 추가된 키 감지
        self.refresh_keys()

        if not self.api_keys:
            raise Exception("등록된 API 키가 없습니다. 헤더의 '🔑 API 키 관리'에서 키를 추가해주세요.")
        
        current_time = datetime.now()
        
        # 차단 해제
        keys_to_unblock = []
        for key_name, unblock_time in self.blocked_keys.items():
            if current_time >= unblock_time:
                keys_to_unblock.append(key_name)
        
        for key_name in keys_to_unblock:
            del self.blocked_keys[key_name]
            logger.info(f"[API Manager] {key_name} 차단 해제됨")
        
        # 사용 가능한 키 찾기
        available_keys = []
        for key_name, key_value in self.api_keys.items():
            if key_value and key_name not in self.blocked_keys:
                available_keys.append((key_name, key_value))
        
        if not available_keys:
            if self.blocked_keys:
                next_unblock = min(self.blocked_keys.values())
                wait_time = (next_unblock - current_time).total_seconds()
                if wait_time <= 60:
                    logger.info(f"[API Manager] {int(wait_time)}초 대기...")
                    time.sleep(wait_time + 1)
                    # 재귀 대신 반복문으로 처리 (스택 오버플로우 방지)
                    return self._get_available_key_after_wait()
                else:
                    raise Exception(f"모든 API 키가 차단됨. {int(wait_time/60)}분 후 재시도 필요")
            else:
                raise Exception("사용 가능한 API 키가 없습니다.")
        
        # 가장 적게 사용된 키 선택
        available_keys.sort(key=lambda x: self.usage_count.get(x[0], 0))
        selected_key_name, selected_key_value = available_keys[0]
        
        self.current_key = selected_key_name
        self.usage_count[selected_key_name] = self.usage_count.get(selected_key_name, 0) + 1
        
        logger.debug(f"[API Manager] {selected_key_name} 선택됨 (사용 횟수: {self.usage_count[selected_key_name]})")
        return selected_key_value

    def _get_available_key_after_wait(self, max_retries: int = 3):
        """대기 후 사용 가능한 키를 찾는 헬퍼 함수 (재귀 방지)"""
        for retry in range(max_retries):
            current_time = datetime.now()

            # 차단 해제
            keys_to_unblock = [k for k, t in self.blocked_keys.items() if current_time >= t]
            for key_name in keys_to_unblock:
                del self.blocked_keys[key_name]
                logger.info(f"[API Manager] {key_name} 차단 해제됨")

            # 사용 가능한 키 찾기
            available_keys = [(k, v) for k, v in self.api_keys.items()
                              if v and k not in self.blocked_keys]

            if available_keys:
                available_keys.sort(key=lambda x: self.usage_count.get(x[0], 0))
                selected_key_name, selected_key_value = available_keys[0]
                self.current_key = selected_key_name
                self.usage_count[selected_key_name] = self.usage_count.get(selected_key_name, 0) + 1
                logger.debug(f"[API Manager] {selected_key_name} 선택됨 (사용 횟수: {self.usage_count[selected_key_name]})")
                return selected_key_value

            # 여전히 사용 가능한 키가 없으면 대기
            if self.blocked_keys:
                next_unblock = min(self.blocked_keys.values())
                wait_time = (next_unblock - current_time).total_seconds()
                if wait_time > 0 and wait_time <= 60:
                    logger.info(f"[API Manager] 재시도 {retry + 1}/{max_retries}: {int(wait_time)}초 대기...")
                    time.sleep(wait_time + 1)
                else:
                    break

        raise Exception("대기 후에도 사용 가능한 API 키가 없습니다.")

    def block_current_key(self, duration_minutes=5):
        if self.current_key:
            unblock_time = datetime.now() + timedelta(minutes=duration_minutes)
            self.blocked_keys[self.current_key] = unblock_time
            logger.warning(f"[API Manager] {self.current_key} 차단됨. 해제 시간: {unblock_time.strftime('%H:%M:%S')}")
            self.current_key = None
    
    def get_status(self):
        status = []
        current_time = datetime.now()
        
        for key_name in self.api_keys:
            if key_name in self.blocked_keys:
                remaining = (self.blocked_keys[key_name] - current_time).total_seconds()
                status.append(f"{key_name}: 차단됨 ({int(remaining/60)}분 남음)")
            else:
                count = self.usage_count.get(key_name, 0)
                status.append(f"{key_name}: 사용가능 (사용횟수: {count})")
        
        return "\n".join(status)
