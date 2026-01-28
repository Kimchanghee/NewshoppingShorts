"""
처리 큐 관리 모듈 - URL 상태 관리 중앙화

이 모듈은 URL 큐와 상태를 스레드 안전하게 관리합니다.
기존에 분산되어 있던 URL 상태 관리를 한 곳에서 통합합니다.

This module centralizes URL queue and status management with thread safety.
Previously scattered URL state management is now unified here.
"""
import threading
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable

from utils.logging_config import get_logger

logger = get_logger(__name__)


class UrlStatus(str, Enum):
    """
    URL 처리 상태 열거형

    Attributes:
        WAITING: 대기 중 - 처리 대기열에 있음
        PROCESSING: 처리 중 - 현재 처리 진행 중
        COMPLETED: 완료 - 성공적으로 처리됨
        FAILED: 실패 - 처리 중 오류 발생
        SKIPPED: 건너뜀 - 사용자 또는 시스템에 의해 건너뜀
    """
    WAITING = 'waiting'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    SKIPPED = 'skipped'


class ProcessingQueue:
    """
    URL 처리 큐 및 상태 관리 클래스 (스레드 안전)

    이 클래스는 URL 큐와 상태를 중앙에서 관리합니다.
    모든 상태 변경은 Lock을 통해 스레드 안전하게 처리됩니다.

    This class centrally manages URL queue and status.
    All state changes are thread-safe through Lock mechanism.

    Attributes:
        _url_queue: URL 목록 (순서 유지)
        _url_status: URL별 상태 매핑
        _url_status_message: URL별 상태 메시지
        _url_remarks: URL별 비고/메모
        _url_timestamps: URL별 타임스탬프 (폴더명 생성용)
        _lock: 스레드 동기화를 위한 Lock
        _on_change_callback: 상태 변경 시 호출되는 콜백 함수

    Example:
        >>> queue = ProcessingQueue()
        >>> queue.add_url("https://example.com/video1")
        >>> queue.set_status("https://example.com/video1", UrlStatus.PROCESSING)
        >>> queue.get_status("https://example.com/video1")
        'processing'
    """

    def __init__(self, on_change_callback: Optional[Callable[[], None]] = None):
        """
        ProcessingQueue 초기화

        Args:
            on_change_callback: 상태 변경 시 호출될 콜백 함수 (UI 업데이트 등)
        """
        # URL 큐 (순서 유지 리스트)
        self._url_queue: List[str] = []

        # URL별 상태 매핑
        self._url_status: Dict[str, str] = {}

        # URL별 상태 메시지 (실패 사유, 진행 상황 등)
        self._url_status_message: Dict[str, str] = {}

        # URL별 비고/메모
        self._url_remarks: Dict[str, str] = {}

        # URL별 타임스탬프 (폴더명 일관성 유지용)
        self._url_timestamps: Dict[str, datetime] = {}

        # 스레드 동기화를 위한 RLock (재진입 가능)
        # RLock을 사용하여 같은 스레드에서 중첩 호출 허용
        self._lock = threading.RLock()

        # 상태 변경 콜백
        self._on_change_callback = on_change_callback

        logger.debug("[ProcessingQueue] 초기화 완료")

    # ========================================
    # URL 추가/제거 메서드
    # ========================================

    def add_url(self, url: str, status: str = UrlStatus.WAITING,
                message: str = "", remark: str = "") -> bool:
        """
        URL을 큐에 추가

        이미 존재하는 URL은 추가되지 않습니다.

        Args:
            url: 추가할 URL
            status: 초기 상태 (기본값: waiting)
            message: 상태 메시지
            remark: 비고/메모

        Returns:
            bool: 추가 성공 여부 (중복이면 False)
        """
        if not url or not isinstance(url, str):
            logger.warning("[ProcessingQueue] 유효하지 않은 URL")
            return False

        url = url.strip()
        if not url:
            return False

        with self._lock:
            # 중복 체크
            if url in self._url_queue:
                logger.debug(f"[ProcessingQueue] URL 이미 존재: {url[:50]}...")
                return False

            self._url_queue.append(url)
            self._url_status[url] = status if isinstance(status, str) else status.value
            self._url_timestamps[url] = datetime.now()

            if message:
                self._url_status_message[url] = message
            if remark:
                self._url_remarks[url] = remark

            logger.debug(f"[ProcessingQueue] URL 추가: {url[:50]}... (상태: {status})")

        self._notify_change()
        return True

    def add_urls(self, urls: List[str], status: str = UrlStatus.WAITING) -> int:
        """
        여러 URL을 한 번에 추가

        Args:
            urls: 추가할 URL 목록
            status: 초기 상태 (기본값: waiting)

        Returns:
            int: 실제로 추가된 URL 수
        """
        added_count = 0
        with self._lock:
            for url in urls:
                if self.add_url(url, status):
                    added_count += 1

        logger.info(f"[ProcessingQueue] {added_count}개 URL 추가 (총 {len(urls)}개 중)")
        return added_count

    def remove_url(self, url: str) -> bool:
        """
        URL을 큐에서 제거

        Args:
            url: 제거할 URL

        Returns:
            bool: 제거 성공 여부
        """
        with self._lock:
            if url not in self._url_queue:
                return False

            self._url_queue.remove(url)
            self._url_status.pop(url, None)
            self._url_status_message.pop(url, None)
            self._url_remarks.pop(url, None)
            self._url_timestamps.pop(url, None)

            logger.debug(f"[ProcessingQueue] URL 제거: {url[:50]}...")

        self._notify_change()
        return True

    def clear(self) -> None:
        """
        모든 URL 제거 (큐 초기화)
        """
        with self._lock:
            count = len(self._url_queue)
            self._url_queue.clear()
            self._url_status.clear()
            self._url_status_message.clear()
            self._url_remarks.clear()
            self._url_timestamps.clear()

            logger.info(f"[ProcessingQueue] 큐 초기화 완료 ({count}개 URL 제거)")

        self._notify_change()

    # ========================================
    # 상태 조회/변경 메서드
    # ========================================

    def get_status(self, url: str) -> Optional[str]:
        """
        URL의 현재 상태 조회

        Args:
            url: 조회할 URL

        Returns:
            str 또는 None: URL 상태 (없으면 None)
        """
        with self._lock:
            return self._url_status.get(url)

    def set_status(self, url: str, status: str, message: str = "") -> bool:
        """
        URL 상태 변경

        Args:
            url: 대상 URL
            status: 새 상태 (UrlStatus enum 또는 문자열)
            message: 상태 메시지 (선택사항)

        Returns:
            bool: 변경 성공 여부 (URL이 존재하지 않으면 False)
        """
        status_value = status if isinstance(status, str) else status.value

        with self._lock:
            if url not in self._url_queue:
                logger.warning(f"[ProcessingQueue] 존재하지 않는 URL 상태 변경 시도: {url[:50]}...")
                return False

            old_status = self._url_status.get(url)
            self._url_status[url] = status_value

            if message:
                self._url_status_message[url] = message

            logger.debug(f"[ProcessingQueue] 상태 변경: {url[:30]}... ({old_status} -> {status_value})")

        self._notify_change()
        return True

    def get_status_message(self, url: str) -> Optional[str]:
        """
        URL의 상태 메시지 조회

        Args:
            url: 조회할 URL

        Returns:
            str 또는 None: 상태 메시지
        """
        with self._lock:
            return self._url_status_message.get(url)

    def set_status_message(self, url: str, message: str) -> bool:
        """
        URL 상태 메시지 설정

        Args:
            url: 대상 URL
            message: 상태 메시지

        Returns:
            bool: 설정 성공 여부
        """
        with self._lock:
            if url not in self._url_queue:
                return False
            self._url_status_message[url] = message
        return True

    def get_remark(self, url: str) -> Optional[str]:
        """
        URL의 비고/메모 조회

        Args:
            url: 조회할 URL

        Returns:
            str 또는 None: 비고/메모
        """
        with self._lock:
            return self._url_remarks.get(url)

    def set_remark(self, url: str, remark: str) -> bool:
        """
        URL 비고/메모 설정

        Args:
            url: 대상 URL
            remark: 비고/메모

        Returns:
            bool: 설정 성공 여부
        """
        with self._lock:
            if url not in self._url_queue:
                return False
            self._url_remarks[url] = remark
        return True

    def get_timestamp(self, url: str) -> Optional[datetime]:
        """
        URL의 타임스탬프 조회

        Args:
            url: 조회할 URL

        Returns:
            datetime 또는 None: 타임스탬프
        """
        with self._lock:
            return self._url_timestamps.get(url)

    def set_timestamp(self, url: str, timestamp: datetime) -> bool:
        """
        URL 타임스탬프 설정

        Args:
            url: 대상 URL
            timestamp: 타임스탬프

        Returns:
            bool: 설정 성공 여부
        """
        with self._lock:
            if url not in self._url_queue:
                return False
            self._url_timestamps[url] = timestamp
        return True

    # ========================================
    # 목록 조회 메서드
    # ========================================

    def get_all_urls(self) -> List[str]:
        """
        전체 URL 목록 조회 (순서 유지)

        Returns:
            List[str]: URL 목록 복사본
        """
        with self._lock:
            return list(self._url_queue)

    def get_waiting_urls(self) -> List[str]:
        """
        대기 중인 URL 목록 조회

        Returns:
            List[str]: 대기 중(waiting) 상태인 URL 목록
        """
        with self._lock:
            return [
                url for url in self._url_queue
                if self._url_status.get(url) == UrlStatus.WAITING.value
            ]

    def get_urls_by_status(self, status: str) -> List[str]:
        """
        특정 상태의 URL 목록 조회

        Args:
            status: 조회할 상태 (UrlStatus enum 또는 문자열)

        Returns:
            List[str]: 해당 상태인 URL 목록
        """
        status_value = status if isinstance(status, str) else status.value

        with self._lock:
            return [
                url for url in self._url_queue
                if self._url_status.get(url) == status_value
            ]

    def get_completed_urls(self) -> List[str]:
        """
        완료된 URL 목록 조회

        Returns:
            List[str]: 완료(completed) 상태인 URL 목록
        """
        return self.get_urls_by_status(UrlStatus.COMPLETED)

    def get_failed_urls(self) -> List[str]:
        """
        실패한 URL 목록 조회

        Returns:
            List[str]: 실패(failed) 상태인 URL 목록
        """
        return self.get_urls_by_status(UrlStatus.FAILED)

    def get_processing_urls(self) -> List[str]:
        """
        처리 중인 URL 목록 조회

        Returns:
            List[str]: 처리 중(processing) 상태인 URL 목록
        """
        return self.get_urls_by_status(UrlStatus.PROCESSING)

    # ========================================
    # 통계 및 유틸리티 메서드
    # ========================================

    def get_stats(self) -> Dict[str, int]:
        """
        상태별 통계 조회

        Returns:
            Dict[str, int]: 상태별 URL 수
        """
        with self._lock:
            stats = {
                'waiting': 0,
                'processing': 0,
                'completed': 0,
                'failed': 0,
                'skipped': 0,
                'total': len(self._url_queue)
            }

            for status in self._url_status.values():
                # None 상태를 waiting으로 간주
                if status is None:
                    stats['waiting'] += 1
                elif status in stats:
                    stats[status] += 1

            return stats

    def get_next_waiting_url(self) -> Optional[str]:
        """
        다음 대기 중인 URL 반환 (처리용)

        큐 순서대로 첫 번째 대기 중인 URL을 반환합니다.

        Returns:
            str 또는 None: 다음 대기 중인 URL
        """
        with self._lock:
            for url in self._url_queue:
                if self._url_status.get(url) == UrlStatus.WAITING.value:
                    return url
            return None

    def has_pending_urls(self) -> bool:
        """
        처리 대기 중인 URL이 있는지 확인

        Returns:
            bool: 대기 중이거나 처리 중인 URL이 있으면 True
        """
        with self._lock:
            for status in self._url_status.values():
                if status in (UrlStatus.WAITING.value, UrlStatus.PROCESSING.value):
                    return True
            return False

    def is_empty(self) -> bool:
        """
        큐가 비어있는지 확인

        Returns:
            bool: 큐가 비어있으면 True
        """
        with self._lock:
            return len(self._url_queue) == 0

    def __len__(self) -> int:
        """
        큐의 URL 수 반환

        Returns:
            int: URL 수
        """
        with self._lock:
            return len(self._url_queue)

    def __contains__(self, url: str) -> bool:
        """
        URL이 큐에 있는지 확인

        Args:
            url: 확인할 URL

        Returns:
            bool: URL이 있으면 True
        """
        with self._lock:
            return url in self._url_queue

    # ========================================
    # 세션 저장/복구 지원 메서드
    # ========================================

    def to_dict(self) -> Dict[str, Any]:
        """
        세션 저장을 위한 딕셔너리 변환

        Returns:
            Dict[str, Any]: 직렬화 가능한 딕셔너리
        """
        with self._lock:
            return {
                'url_queue': list(self._url_queue),
                'url_status': dict(self._url_status),
                'url_status_message': dict(self._url_status_message),
                'url_remarks': dict(self._url_remarks),
                'url_timestamps': {
                    url: ts.strftime("%Y-%m-%d %H:%M:%S") if isinstance(ts, datetime) else str(ts)
                    for url, ts in self._url_timestamps.items()
                }
            }

    def from_dict(self, data: Dict[str, Any]) -> bool:
        """
        딕셔너리에서 상태 복구

        Args:
            data: to_dict()로 생성된 딕셔너리

        Returns:
            bool: 복구 성공 여부
        """
        try:
            with self._lock:
                # URL 큐 복구
                url_queue = data.get('url_queue', [])
                if not isinstance(url_queue, list):
                    logger.warning("[ProcessingQueue] url_queue가 list가 아님 - 빈 리스트로 초기화")
                    url_queue = []
                self._url_queue = url_queue

                # URL 상태 복구
                url_status = data.get('url_status', {})
                self._url_status = url_status if isinstance(url_status, dict) else {}

                # 상태 메시지 복구
                url_status_message = data.get('url_status_message', {})
                self._url_status_message = url_status_message if isinstance(url_status_message, dict) else {}

                # 비고 복구
                url_remarks = data.get('url_remarks', {})
                self._url_remarks = url_remarks if isinstance(url_remarks, dict) else {}

                # 타임스탬프 복구
                url_timestamps = data.get('url_timestamps', {})
                self._url_timestamps = {}
                for url, ts_str in url_timestamps.items():
                    try:
                        if isinstance(ts_str, str):
                            self._url_timestamps[url] = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                        elif isinstance(ts_str, datetime):
                            self._url_timestamps[url] = ts_str
                    except ValueError:
                        self._url_timestamps[url] = datetime.now()

                # processing 상태를 waiting으로 변경 (재시작 시)
                # None 상태도 waiting으로 정규화
                processing_count = 0
                for url in self._url_queue:
                    status = self._url_status.get(url)
                    if status is None:
                        self._url_status[url] = UrlStatus.WAITING.value
                    elif status == UrlStatus.PROCESSING.value:
                        self._url_status[url] = UrlStatus.WAITING.value
                        processing_count += 1

                if processing_count > 0:
                    logger.info(f"[ProcessingQueue] {processing_count}개 URL을 processing에서 waiting으로 변경")

                logger.info(f"[ProcessingQueue] 복구 완료: {len(self._url_queue)}개 URL")

            self._notify_change()
            return True

        except Exception as e:
            logger.exception(f"[ProcessingQueue] 복구 실패: {e}")
            return False

    def normalize_processing_to_waiting(self) -> int:
        """
        processing 상태의 URL을 waiting으로 변경

        프로그램 재시작 시 중단된 처리를 재시작하기 위해 사용합니다.

        Returns:
            int: 변경된 URL 수
        """
        changed_count = 0
        with self._lock:
            for url in self._url_queue:
                if self._url_status.get(url) == UrlStatus.PROCESSING.value:
                    self._url_status[url] = UrlStatus.WAITING.value
                    changed_count += 1

        if changed_count > 0:
            logger.info(f"[ProcessingQueue] {changed_count}개 URL을 waiting으로 변경")
            self._notify_change()

        return changed_count

    # ========================================
    # 내부 메서드
    # ========================================

    def _notify_change(self) -> None:
        """
        상태 변경 알림 (콜백 호출)
        """
        if self._on_change_callback:
            try:
                self._on_change_callback()
            except Exception as e:
                logger.debug(f"[ProcessingQueue] 콜백 호출 실패: {e}")

    def set_on_change_callback(self, callback: Optional[Callable[[], None]]) -> None:
        """
        상태 변경 콜백 설정

        Args:
            callback: 상태 변경 시 호출될 함수
        """
        self._on_change_callback = callback

    # ========================================
    # 레거시 호환성 프로퍼티
    # ========================================

    @property
    def url_queue(self) -> List[str]:
        """레거시 호환성: url_queue 프로퍼티"""
        return self.get_all_urls()

    @property
    def url_status(self) -> Dict[str, str]:
        """레거시 호환성: url_status 프로퍼티"""
        with self._lock:
            return dict(self._url_status)

    @property
    def url_status_message(self) -> Dict[str, str]:
        """레거시 호환성: url_status_message 프로퍼티"""
        with self._lock:
            return dict(self._url_status_message)

    @property
    def url_remarks(self) -> Dict[str, str]:
        """레거시 호환성: url_remarks 프로퍼티"""
        with self._lock:
            return dict(self._url_remarks)

    @property
    def url_timestamps(self) -> Dict[str, datetime]:
        """레거시 호환성: url_timestamps 프로퍼티"""
        with self._lock:
            return dict(self._url_timestamps)


# 싱글톤 인스턴스 (선택적 사용)
_processing_queue_instance: Optional[ProcessingQueue] = None


def get_processing_queue() -> ProcessingQueue:
    """
    전역 ProcessingQueue 인스턴스 반환 (싱글톤)

    Returns:
        ProcessingQueue: 전역 인스턴스
    """
    global _processing_queue_instance
    if _processing_queue_instance is None:
        _processing_queue_instance = ProcessingQueue()
    return _processing_queue_instance


def reset_processing_queue() -> None:
    """
    전역 ProcessingQueue 인스턴스 초기화 (테스트용)
    """
    global _processing_queue_instance
    _processing_queue_instance = None
