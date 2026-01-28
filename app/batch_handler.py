"""
Batch Processing Handler

This module handles batch processing control logic, extracted from main.py.
"""

import threading
from typing import TYPE_CHECKING

from ui.components.custom_dialog import show_warning, show_info, show_error, show_question
import core.video.DynamicBatch as DynamicBatch
from utils.logging_config import get_logger
from caller import rest
import config

logger = get_logger(__name__)

if TYPE_CHECKING:
    from app.main_app import VideoAnalyzerGUI


class BatchHandler:
    """Handles batch processing start/stop logic"""

    def __init__(self, app: 'VideoAnalyzerGUI'):
        self.app = app

    def start_batch_processing(self):
        """배치 처리 시작 - 동적 URL 처리 지원 (중복 실행 방지)"""
        # 이미 실행 중인 스레드가 있는지 확인
        if self.app.batch_thread and self.app.batch_thread.is_alive():
            self.app.add_log("[배치] 이미 배치 처리가 실행 중입니다. 기다려주세요.")
            show_warning(self.app.root, "경고", "이미 배치 처리가 실행 중입니다.")
            return

        if not self.app.url_queue:
            show_warning(self.app.root, "경고", "처리할 URL이 없습니다.")
            return

        # 대기 중인 URL만 처리 (thread-safe access)
        with self.app.url_status_lock:
            waiting_urls = [url for url in self.app.url_queue if self.app.url_status.get(url) == 'waiting']

        if not waiting_urls:
            show_info(self.app.root, "알림", "처리할 대기 중인 URL이 없습니다.")
            return

        # TTS 음성 선택 검증 - 실제 선택된 음성 체크
        selected_voices = [vid for vid, state in self.app.voice_vars.items() if state.get()]
        if not selected_voices or len(selected_voices) == 0:
            show_warning(self.app.root, "경고", "TTS 음성을 최소 1개 이상 선택해주세요.")
            return

        # 선택된 음성 확인 로그 (명확한 표시)
        voice_manager = getattr(self.app, "voice_manager", None)
        voice_labels = []
        for vid in selected_voices:
            if voice_manager:
                profile = voice_manager.get_voice_profile(vid)
                if profile:
                    gender = "👩" if profile.get("gender") == "female" else "👨"
                    voice_labels.append(f"{gender}{profile.get('label', vid)}")
                    continue
            voice_labels.append(vid)

        self.app.add_log(f"[음성 확인] 선택된 음성 {len(selected_voices)}개: {', '.join(voice_labels)}")
        self.app.add_log(f"[음성 확인] 각 URL당 {len(selected_voices)}개의 영상이 생성됩니다.")

        # API 키 검증 - 먼저 체크 (빈 dict, None, 또는 모든 값이 빈 문자열인 경우 체크)
        has_valid_api_key = (
            config.GEMINI_API_KEYS
            and isinstance(config.GEMINI_API_KEYS, dict)
            and any(v and v.strip() for v in config.GEMINI_API_KEYS.values())
        )

        if not has_valid_api_key:
            self.app.add_log("[API] API 키가 설정되지 않았습니다.")
            result = show_question(
                self.app.root,
                "🔑 API 키 필요",
                "Gemini API 키가 설정되지 않았습니다.\n\n"
                "작업을 시작하려면 최소 1개 이상의 API 키가 필요합니다.\n\n"
                "API 키를 지금 추가하시겠습니까?\n\n"
                "※ API 키는 https://aistudio.google.com/apikey\n"
                "   에서 무료로 발급받을 수 있습니다."
            )
            if result:
                # 사용자가 "예"를 선택하면 API 키 관리 창 열기
                self.app.show_api_key_manager()
            return

        # 작업 횟수 확인 (Work count check)
        try:
            user_id = self.app.login_data.get('data', {}).get('data', {}).get('id', '')
            if user_id:
                work_check = rest.checkWorkAvailable(user_id)
                if work_check.get('success'):
                    if not work_check.get('can_work', True):
                        self.app.add_log("[작업] 잔여 작업 횟수가 없습니다.")
                        show_warning(
                            self.app.root,
                            "작업 횟수 초과",
                            "잔여 작업 횟수가 없습니다.\n\n"
                            "관리자에게 문의하여 작업 횟수를 추가해 주세요."
                        )
                        return
                    remaining = work_check.get('remaining', -1)
                    if remaining != -1:
                        self.app.add_log(f"[작업] 잔여 작업 횟수: {remaining}회")
                    else:
                        self.app.add_log("[작업] 작업 횟수: 무제한")
        except Exception as e:
            logger.warning(f"Work count check failed (continuing): {e}")
            # 체크 실패 시 계속 진행 (네트워크 오류 등)

        # Gemini 클라이언트 초기화
        if not getattr(self.app, "genai_client", None):
            self.app.add_log("[API] Gemini 클라이언트를 초기화합니다.")
            if not self.app.init_client():
                self.app.add_log("[API] 초기화 실패로 배치 처리를 중단합니다.")
                show_error(
                    self.app.root,
                    "❌ API 초기화 실패",
                    "Gemini API 클라이언트 초기화에 실패했습니다.\n\n"
                    "가능한 원인:\n"
                    "• API 키가 유효하지 않음\n"
                    "• 네트워크 연결 문제\n"
                    "• Gemini SDK 설치 오류\n\n"
                    "API 키 설정을 확인해주세요."
                )
                return

        self.app.add_log(f"배치 처리 시작 - {len(waiting_urls)}개 URL")

        # 동적 처리 플래그 설정
        self.app.dynamic_processing = True
        self.app.batch_processing = True
        self.app.start_batch_button.config(state='disabled')
        self.app.stop_batch_button.config(state='normal')
        self.app.reset_progress_states()

        # 동적 처리 스레드 시작 (순차 실행 보장)
        thread = threading.Thread(
            target=self._batch_processing_wrapper,
            daemon=True
        )
        self.app.batch_thread = thread
        thread.start()

    def _batch_processing_wrapper(self):
        """배치 처리 래퍼 - Lock으로 순차 실행 보장

        Uses timeout-based lock acquisition to prevent deadlock if previous thread crashes.
        타임아웃 기반 락 획득으로 이전 스레드 크래시 시 데드락 방지.
        """
        LOCK_TIMEOUT_SECONDS = 300  # 5분 타임아웃
        MAX_RETRIES = 3

        acquired = self.app.batch_processing_lock.acquire(blocking=False)
        if not acquired:
            self.app.add_log("[배치] 다른 배치 작업이 실행 중이어서 대기합니다...")
            # Timeout-based acquisition to prevent deadlock
            for retry in range(MAX_RETRIES):
                acquired = self.app.batch_processing_lock.acquire(timeout=LOCK_TIMEOUT_SECONDS)
                if acquired:
                    break
                self.app.add_log(f"[배치] Lock 획득 재시도 ({retry + 1}/{MAX_RETRIES})...")

            if not acquired:
                self.app.add_log("[배치] Lock 획득 실패 - 배치 처리를 시작할 수 없습니다.")
                self.app.root.after(0, self._reset_batch_ui_on_complete)
                return

        try:
            self.app.add_log("[배치] 배치 처리 시작 (Lock 획득)")
            DynamicBatch.dynamic_batch_processing_thread(self.app)
        finally:
            self.app.batch_processing_lock.release()
            self.app.add_log("[배치] 배치 처리 완료 (Lock 해제)")
            # 스레드 종료 시 UI 상태 복구
            self.app.root.after(0, self._reset_batch_ui_on_complete)

    def _reset_batch_ui_on_complete(self):
        """배치 처리 완료 시 UI 상태 복구"""
        # 항상 UI 상태를 복구 (에러 발생 시에도)
        try:
            self.app.batch_processing = False
            self.app.dynamic_processing = False
            self.app.start_batch_button.config(state='normal')
            self.app.stop_batch_button.config(state='disabled')
        except Exception as e:
            logger.error(f"Failed to reset batch UI state: {e}")

    def stop_batch_processing(self):
        """배치 처리 중지 (현재 URL 완료 후 중지)"""
        if not self.app.batch_processing:
            self.app.add_log("[배치] 이미 중지된 상태입니다.")
            return

        self.app.batch_processing = False
        self.app.dynamic_processing = False  # 동적 처리도 중지
        self.app.add_log("[배치] 배치 처리 중지 요청 - 현재 작업 완료 후 중지됩니다.")

        # UI 즉시 업데이트 (실제 스레드는 백그라운드에서 정리됨)
        self.app.stop_batch_button.config(state='disabled')

        # 백그라운드에서 스레드 종료 대기
        def wait_for_thread_finish():
            if self.app.batch_thread and self.app.batch_thread.is_alive():
                self.app.batch_thread.join(timeout=30)  # 최대 30초 대기
                self.app.add_log("[배치] 이전 배치 스레드 종료 완료")

            # 세션 저장 (중지된 상태 기록)
            try:
                if hasattr(self.app, 'session_manager'):
                    self.app.session_manager.save_session()
                    self.app.add_log("[세션] 중지 시점 세션 저장 완료")
            except Exception as e:
                self.app.add_log(f"[세션] 저장 실패: {e}")

            # UI 상태 복구
            self.app.root.after(0, lambda: self.app.start_batch_button.config(state='normal'))

        threading.Thread(target=wait_for_thread_finish, daemon=True).start()
