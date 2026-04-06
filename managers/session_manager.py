"""
세션 관리 모듈 - 프로그램 재시작 시 작업 복구 지원
"""
import os
import sys
import json
import stat
from contextlib import nullcontext
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from caller import ui_controller
from utils.logging_config import get_logger

logger = get_logger(__name__)



class SessionManager:
    """작업 세션을 저장하고 복구하는 관리 클래스"""

    def __init__(self, gui):
        """
        Args:
            gui: VideoAnalyzerGUI 인스턴스
        """
        self.gui = gui
        # 세션 파일을 앱 데이터 폴더에 저장 (실행 경로 무관하게 일관된 위치)
        app_data_dir = self._get_app_data_dir()
        self.session_file = os.path.join(app_data_dir, "session_data.json")
        self.backup_file = os.path.join(app_data_dir, "session_backup.json")

    def _get_app_data_dir(self) -> str:
        """앱 데이터 디렉토리 경로 반환 (없으면 생성)"""
        if os.name == 'nt':  # Windows
            app_data = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
            app_dir = os.path.join(app_data, 'ShoppingShortsMaker')
        else:  # macOS, Linux
            app_dir = os.path.join(os.path.expanduser('~'), '.shoppingShortsMaker')

        os.makedirs(app_dir, exist_ok=True)
        return app_dir

    def has_saved_session(self) -> bool:
        """저장된 세션이 있는지 확인"""
        return os.path.exists(self.session_file)

    def get_session_info(self) -> Optional[Dict[str, Any]]:
        """저장된 세션 정보를 읽어옴 (복구가 필요한 경우만)"""
        try:
            if not os.path.exists(self.session_file):
                return None

            with open(self.session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 세션 유효성 검증 및 타입 정규화
            url_queue = data.get('url_queue', [])
            if not isinstance(url_queue, list):
                url_queue = []

            url_status = data.get('url_status', {})
            if not isinstance(url_status, dict):
                url_status = {}

            if not url_queue and not url_status:
                logger.debug("[세션] 세션이 비어있음 - 복구 불필요")
                self.clear_session()  # 빈 세션 파일 삭제
                return None

            # 복구가 필요한지 확인
            has_pending = False  # 대기 중이거나 재시도가 필요한 작업이 있는지

            # 1. url_queue에 있는 URL 중 완료되지 않은 것이 있는지 확인
            for url in url_queue:
                status = url_status.get(url, 'waiting')
                # None을 'waiting'으로 간주 (상태가 없으면 대기 중으로 처리)
                if status is None:
                    status = 'waiting'
                if status in ('waiting', 'processing', 'failed', 'skipped'):
                    has_pending = True
                    break

            # 2. url_status에 미완료 상태가 있는지 확인 (큐가 비어도 복구 가능한 작업)
            if not has_pending:
                for status in url_status.values():
                    # None을 'waiting'으로 간주
                    if status is None:
                        status = 'waiting'
                    # waiting/processing도 체크하여 큐가 비었어도 상태 정보가 있으면 보존
                    if status in ('waiting', 'processing', 'failed', 'skipped'):
                        has_pending = True
                        break

            if not has_pending:
                logger.debug("[세션] 모든 작업 완료됨 - 복구 불필요")
                self.clear_session()  # 완료된 세션 파일 삭제
                return None

            return data

        except Exception as e:
            ui_controller.write_error_log(e)
            logger.error(f"[세션] 세션 정보 읽기 실패: {e}")
            return None

    def save_session(self, force: bool = False) -> bool:
        """
        현재 작업 세션을 파일로 저장

        Args:
            force: True면 큐가 비어있어도 저장 (기본: False)

        Returns:
            저장 성공 여부
        """
        try:
            # 저장할 데이터가 없으면 스킵
            if not force and not self.gui.url_queue:
                return False

            # 백업 파일 생성 (기존 세션 파일이 있으면)
            if os.path.exists(self.session_file):
                try:
                    with open(self.session_file, 'r', encoding='utf-8') as f:
                        backup_data = json.load(f)
                    with open(self.backup_file, 'w', encoding='utf-8') as f:
                        json.dump(backup_data, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    logger.debug(f"[세션] 백업 파일 생성 실패 (무시됨): {e}")

            # 세션 데이터 구성
            session_data = {
                'saved_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'url_queue': list(self.gui.url_queue),
                'url_status': dict(self.gui.url_status),
                'url_status_message': dict(self.gui.url_status_message),
                'url_remarks': dict(getattr(self.gui, 'url_remarks', {})),
                'current_processing_index': self.gui.current_processing_index,
                'batch_processing': self.gui.batch_processing,
                'dynamic_processing': self.gui.dynamic_processing,
                'processing_mode': getattr(
                    getattr(self.gui, 'state', None),
                    'processing_mode',
                    getattr(self.gui, 'processing_mode', 'single'),
                ),
                'mix_jobs': dict(getattr(self.gui, 'mix_jobs', {})),

                # 음성 선택 정보
                'selected_voices': [
                    vid for vid, var in self.gui.voice_vars.items()
                    if var.get()
                ],

                # 출력 폴더
                'output_folder_path': self.gui.output_folder_path,

                # URL별 타임스탬프 (폴더명 일관성 유지)
                'url_timestamps': {
                    url: timestamp.strftime("%Y-%m-%d %H:%M:%S") if isinstance(timestamp, datetime) else str(timestamp)
                    for url, timestamp in getattr(self.gui, 'url_timestamps', {}).items()
                },

                # 통계 정보
                'stats': self._get_session_stats()
            }

            # 파일로 저장 with secure permissions
            # 보안 권한으로 파일 저장
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)

            # Set restrictive permissions (owner only) on non-Windows
            # Windows 외 시스템에서 제한적 권한 설정 (소유자만)
            if sys.platform != 'win32':
                os.chmod(self.session_file, stat.S_IRUSR | stat.S_IWUSR)  # 0o600

            logger.info(f"[세션] 저장 완료: {len(self.gui.url_queue)}개 URL")
            return True

        except Exception as e:
            ui_controller.write_error_log(e)
            logger.error(f"[세션] 저장 실패: {e}")
            return False

    def restore_session(self, session_data: Dict[str, Any]) -> bool:
        """
        저장된 세션 데이터를 복구

        Args:
            session_data: 복구할 세션 데이터

        Returns:
            복구 성공 여부
        """
        try:
            # UI 준비 여부 확인 (방어 코드)
            if not self._is_ui_ready():
                logger.warning("[세션] UI가 아직 준비되지 않음 - 복구 불가")
                return False
            # URL 큐 복구 (타입 검증으로 안정성 강화)
            url_queue = session_data.get('url_queue', [])
            if not isinstance(url_queue, list):
                logger.warning(f"[세션] 경고: url_queue가 list가 아님 (타입: {type(url_queue).__name__}) - 빈 리스트로 초기화")
                url_queue = []
            self.gui.url_queue.clear()
            self.gui.url_queue.extend(url_queue)

            # url_status: null이나 잘못된 타입이면 빈 dict로 대체
            # Thread-safe access to url_status
            url_status = session_data.get('url_status', {})
            url_status_lock = getattr(self.gui, 'url_status_lock', None)
            if url_status_lock is not None:
                with url_status_lock:
                    self.gui.url_status.clear()
                    self.gui.url_status.update(url_status if isinstance(url_status, dict) else {})
            else:
                self.gui.url_status.clear()
                self.gui.url_status.update(url_status if isinstance(url_status, dict) else {})

            # url_status_message: null이나 잘못된 타입이면 빈 dict로 대체
            url_status_msg = session_data.get('url_status_message', {})
            self.gui.url_status_message.clear()
            self.gui.url_status_message.update(url_status_msg if isinstance(url_status_msg, dict) else {})

            # url_remarks: null이나 잘못된 타입이면 빈 dict로 대체
            url_remarks = session_data.get('url_remarks', {})
            self.gui.url_remarks.clear()
            self.gui.url_remarks.update(url_remarks if isinstance(url_remarks, dict) else {})
            self.gui.current_processing_index = session_data.get('current_processing_index', -1)
            self.gui.processing_mode = session_data.get('processing_mode', 'single')

            # mix job metadata restore
            saved_mix_jobs = session_data.get('mix_jobs', {})
            normalized_mix_jobs = {}
            if isinstance(saved_mix_jobs, dict):
                for key, urls in saved_mix_jobs.items():
                    if not isinstance(key, str):
                        continue
                    if not isinstance(urls, list):
                        continue
                    normalized = [u for u in urls if isinstance(u, str) and u.strip()]
                    if normalized:
                        normalized_mix_jobs[key] = normalized

            if isinstance(getattr(self.gui, 'mix_jobs', None), dict):
                self.gui.mix_jobs.clear()
                self.gui.mix_jobs.update(normalized_mix_jobs)
            else:
                self.gui.mix_jobs = dict(normalized_mix_jobs)
            queue_manager = getattr(self.gui, 'queue_manager', None)
            if queue_manager is not None and hasattr(queue_manager, '_ensure_mix_store'):
                store = queue_manager._ensure_mix_store()
                store.clear()
                store.update(normalized_mix_jobs)
                self.gui.mix_jobs = store

            if hasattr(self.gui, 'state'):
                self.gui.state.processing_mode = self.gui.processing_mode
                self.gui.state.mix_jobs = self.gui.mix_jobs

            # 처리 중이던 URL만 waiting으로 변경 (실패/건너뜀은 상태 유지)
            # None 상태값도 waiting으로 정규화
            processing_count = 0
            none_normalized_count = 0

            # Thread-safe iteration and modification
            url_status_lock = getattr(self.gui, 'url_status_lock', None)
            if url_status_lock is not None:
                with url_status_lock:
                    for url in self.gui.url_queue:
                        status = self.gui.url_status.get(url)
                        if status is None:
                            self.gui.url_status[url] = 'waiting'
                            none_normalized_count += 1
                        elif status == 'processing':
                            self.gui.url_status[url] = 'waiting'
                            processing_count += 1
                            logger.info(f"[세션] 처리 중단된 URL 재시작: {url[:50]}...")
            else:
                for url in self.gui.url_queue:
                    status = self.gui.url_status.get(url)
                    if status is None:
                        self.gui.url_status[url] = 'waiting'
                        none_normalized_count += 1
                    elif status == 'processing':
                        self.gui.url_status[url] = 'waiting'
                        processing_count += 1
                        logger.info(f"[세션] 처리 중단된 URL 재시작: {url[:50]}...")
            # failed/skipped 상태는 그대로 유지 (상태 메시지도 함께 표시됨)

            if none_normalized_count > 0:
                logger.debug(f"[세션] {none_normalized_count}개 URL의 None 상태를 waiting으로 정규화")

            # url_queue에 없는 URL 중 processing 상태만 큐에 추가
            # Thread-safe iteration with snapshot
            url_status_lock = getattr(self.gui, 'url_status_lock', None)
            if url_status_lock is not None:
                with url_status_lock:
                    status_items = list(self.gui.url_status.items())
            else:
                status_items = list(self.gui.url_status.items())

            for url, status in status_items:
                if status == 'processing' and url not in self.gui.url_queue:
                    self.gui.url_queue.append(url)
                    if url_status_lock is not None:
                        with url_status_lock:
                            self.gui.url_status[url] = 'waiting'
                    else:
                        self.gui.url_status[url] = 'waiting'
                    processing_count += 1
                    logger.info(f"[세션] 처리 중단된 URL 재시작: {url[:50]}...")

            # ── 1-link policy enforcement ──
            # After normalisation the queue may contain multiple waiting items
            # saved from a previous version.  Keep only the first active
            # (waiting) item; demote the rest to 'skipped'.
            first_active_found = False
            demoted_count = 0
            _lock = getattr(self.gui, 'url_status_lock', None)
            _ctx = _lock if _lock is not None else nullcontext()
            with _ctx:
                for url in self.gui.url_queue:
                    st = self.gui.url_status.get(url)
                    if st == 'waiting':
                        if not first_active_found:
                            first_active_found = True
                        else:
                            self.gui.url_status[url] = 'skipped'
                            self.gui.url_status_message[url] = '1-link 정책: 세션 복구 시 초과 항목 건너뜀'
                            demoted_count += 1
            if demoted_count > 0:
                logger.info(f"[세션] 1-link 정책: 복구 시 초과 대기 항목 {demoted_count}개를 skipped 처리")

            # 처리 상태 플래그는 복구하지 않음 (재시작 시 자동으로 시작되지 않도록)
            self.gui.batch_processing = False
            self.gui.dynamic_processing = False

            # 음성 선택 복구 (기존 선택 초기화 후 적용)
            selected_voices = session_data.get('selected_voices', [])
            max_voices = getattr(self.gui, 'max_voice_selection', 10)
            if len(selected_voices) > max_voices:
                logger.warning(f"[세션] 저장된 음성 수({len(selected_voices)})가 최대 선택 수({max_voices})를 초과합니다. 처음 {max_voices}개만 복구합니다.")
                selected_voices = selected_voices[:max_voices]

            # voice_vars 존재 여부 확인 (방어 코드)
            if hasattr(self.gui, 'voice_vars') and self.gui.voice_vars:
                # Clear existing selections first to prevent union of old+restored voices
                for voice_id, var in self.gui.voice_vars.items():
                    var.set(False)

                # Apply restored selections
                for voice_id in selected_voices:
                    if voice_id in self.gui.voice_vars:
                        self.gui.voice_vars[voice_id].set(True)

                # Sync multi_voice_presets and available_tts_voices with restored selections
                if hasattr(self.gui, 'voice_manager'):
                    selected_profiles = [self.gui.voice_manager.get_voice_profile(vid) for vid in selected_voices]
                    selected_profiles = [p for p in selected_profiles if p]
                    if selected_profiles:
                        self.gui.multi_voice_presets = [p["voice_name"] for p in selected_profiles]
                        self.gui.available_tts_voices = list(self.gui.multi_voice_presets)
                    else:
                        self.gui.multi_voice_presets = []
                        self.gui.available_tts_voices = []
                else:
                    # voice_manager가 아직 초기화되지 않은 경우 빈 리스트로 초기화
                    self.gui.multi_voice_presets = []
                    self.gui.available_tts_voices = []
                    logger.debug("[세션] voice_manager 미초기화 상태 - TTS 목록 임시 초기화")
            else:
                logger.debug("[세션] voice_vars 미초기화 상태 - 음성 선택 복구 건너뜀")

            # 출력 폴더 복구 (방어 코드 추가)
            output_folder = session_data.get('output_folder_path')
            if output_folder and os.path.exists(output_folder):
                self.gui.output_folder_path = output_folder
                if hasattr(self.gui, 'output_folder_var'):
                    self.gui.output_folder_var.set(output_folder)
                logger.info(f"[세션] 출력 폴더 복구: {output_folder}")

            # URL별 타임스탬프 복구 (폴더명 일관성 유지)
            url_timestamps = session_data.get('url_timestamps', {})
            if url_timestamps:
                if not hasattr(self.gui, 'url_timestamps'):
                    self.gui.url_timestamps = {}
                # 저장된 타임스탬프를 datetime 객체로 변환
                for url, timestamp_str in url_timestamps.items():
                    try:
                        # ISO 형식 또는 일반 형식 모두 지원
                        if isinstance(timestamp_str, str):
                            # "YYYY-MM-DD HH:MM:SS" 형식
                            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                        else:
                            # 이미 datetime 객체인 경우
                            timestamp = timestamp_str
                        self.gui.url_timestamps[url] = timestamp
                    except Exception as e:
                        ui_controller.write_error_log(e)
                        logger.warning(f"[세션] URL 타임스탬프 복원 실패: {url[:50]}... - {e}")
                        # 실패 시 현재 시각 사용
                        self.gui.url_timestamps[url] = datetime.now()

                logger.debug(f"[세션] {len(self.gui.url_timestamps)}개 URL 타임스탬프 복구 완료")

            # UI 업데이트 (방어 코드 추가)
            update_url_listbox = getattr(self.gui, 'update_url_listbox', None)
            if update_url_listbox is not None:
                update_url_listbox()
            update_voice_card_styles = getattr(self.gui, 'update_voice_card_styles', None)
            if update_voice_card_styles is not None:
                update_voice_card_styles()
            update_voice_summary = getattr(self.gui, 'update_voice_summary', None)
            if update_voice_summary is not None:
                update_voice_summary()
            refresh_output_folder_display = getattr(self.gui, 'refresh_output_folder_display', None)
            if refresh_output_folder_display is not None:
                refresh_output_folder_display()
            url_input_panel = getattr(self.gui, 'url_input_panel', None)
            if url_input_panel is not None and hasattr(url_input_panel, 'refresh_mode'):
                url_input_panel.refresh_mode()

            # 추가 동기화: voice_manager가 초기화된 후 한 번 더 TTS 목록 동기화
            voice_mgr = getattr(self.gui, 'voice_manager', None)
            if voice_mgr is not None:
                # UI 선택과 일치하도록 재동기화
                actual_selected_ids = [vid for vid, state in self.gui.voice_vars.items() if state.get()]
                if actual_selected_ids:
                    selected_profiles = [voice_mgr.get_voice_profile(vid) for vid in actual_selected_ids]
                    selected_profiles = [p for p in selected_profiles if p]
                    if selected_profiles:
                        self.gui.multi_voice_presets = [p["voice_name"] for p in selected_profiles]
                        self.gui.available_tts_voices = list(self.gui.multi_voice_presets)
                        logger.debug(f"[세션] TTS 목록 재동기화 완료 - {len(selected_profiles)}개 음성")

            # 복구 정보 로그
            saved_at = session_data.get('saved_at', '알 수 없음')
            stats = session_data.get('stats', {})
            total_urls = len(self.gui.url_queue)

            # 현재 복구된 상태 통계
            current_stats = self._get_session_stats()
            failed_count = current_stats.get('failed', 0)
            skipped_count = current_stats.get('skipped', 0)

            logger.info(f"[세션] 복구 완료:")
            logger.info(f"  - 저장 시각: {saved_at}")
            logger.info(f"  - 복구된 URL: {total_urls}개")
            logger.info(f"  - 현재 상태 - 대기: {current_stats.get('waiting', 0)}개, 완료: {current_stats.get('completed', 0)}개")
            logger.info(f"  - 현재 상태 - 실패: {failed_count}개, 건너뜀: {skipped_count}개")

            # 상태별 메시지 구성
            status_parts = []
            if failed_count > 0:
                status_parts.append(f"실패 {failed_count}개")
            if skipped_count > 0:
                status_parts.append(f"건너뜀 {skipped_count}개")

            if status_parts:
                self.gui.add_log(f"[세션 복구] {total_urls}개 URL 복구 완료 ({', '.join(status_parts)} 상태 유지)")
            else:
                self.gui.add_log(f"[세션 복구] {total_urls}개 URL 복구 완료")

            # Log session restore
            try:
                from caller.rest import log_user_action
                log_user_action("세션 복구", f"{total_urls}개 URL이 포함된 이전 세션을 복구했습니다.")
            except Exception:
                pass

            return True

        except Exception as e:
            ui_controller.write_error_log(e)
            logger.exception(f"[세션] 복구 실패: {e}")
            return False

    def clear_session(self) -> bool:
        """저장된 세션 파일 삭제"""
        try:
            if os.path.exists(self.session_file):
                os.remove(self.session_file)
                logger.debug("[세션] 세션 파일 삭제 완료")

            if os.path.exists(self.backup_file):
                os.remove(self.backup_file)
                logger.debug("[세션] 백업 파일 삭제 완료")

            return True

        except Exception as e:
            ui_controller.write_error_log(e)
            logger.error(f"[세션] 파일 삭제 실패: {e}")
            return False

    def _get_session_stats(self) -> Dict[str, int]:
        """현재 세션의 통계 정보 계산"""
        stats = {
            'waiting': 0,
            'processing': 0,
            'completed': 0,
            'failed': 0,
            'skipped': 0
        }

        for status in self.gui.url_status.values():
            # None 상태를 waiting으로 간주
            if status is None:
                stats['waiting'] += 1
            elif status in stats:
                stats[status] += 1

        return stats

    def should_auto_save(self) -> bool:
        """자동 저장이 필요한지 판단"""
        # 큐가 비어있으면 저장 불필요
        if not self.gui.url_queue:
            return False

        # 배치 처리 중이면 저장 필요
        if self.gui.batch_processing or self.gui.dynamic_processing:
            return True

        # 대기 중인 URL이 있으면 저장 (None 상태도 waiting으로 간주)
        waiting_count = sum(
            1 for status in self.gui.url_status.values()
            if status == 'waiting' or status is None
        )

        return waiting_count > 0

    def _is_ui_ready(self) -> bool:
        """UI가 세션 복구를 할 준비가 되었는지 확인"""
        # 실제로 init_ui() 완료 후 존재하는 속성만 체크
        required_attrs = [
            'voice_vars',           # 음성 선택 변수 (존재만 확인, 비어있어도 OK)
            'url_input_panel',      # URL 입력 패널
            'queue_manager',        # 큐 매니저 (update_url_listbox 위임)
        ]

        for attr in required_attrs:
            if not hasattr(self.gui, attr):
                logger.debug(f"[세션] UI 미준비: {attr} 없음")
                return False

        # voice_vars는 비어있어도 URL/상태 복구는 진행
        if not self.gui.voice_vars:
            logger.debug("[세션] 경고: voice_vars 비어있음 - 음성 프로필은 복구 생략")

        return True

    def get_restore_confirmation_message(self, session_data: Dict[str, Any]) -> str:
        """복구 확인 메시지 생성"""
        saved_at = session_data.get('saved_at', '알 수 없음')
        stats = session_data.get('stats', {})

        waiting = stats.get('waiting', 0)
        completed = stats.get('completed', 0)
        failed = stats.get('failed', 0)
        skipped = stats.get('skipped', 0)

        total_urls = len(session_data.get('url_queue', []))

        message = f"""이전 작업 세션이 발견되었습니다.

📅 저장 시각: {saved_at}
📊 작업 현황:
  • 대기 중: {waiting}개
  • 완료: {completed}개
  • 실패: {failed}개
  • 건너뜀: {skipped}개

⚡ 복구 시 동작:
  • 총 {total_urls}개 URL이 대기열에 복구됩니다
  • 실패/건너뜀 상태가 그대로 유지됩니다
  • 작업 시작 시 대기 중인 URL만 처리됩니다

이전 작업을 이어서 진행하시겠습니까?"""

        return message
