"""
Main Batch Processor

Contains the main batch processing workflow and video creation logic.
"""

import os
import re
import gc
import time
import shutil
import tempfile
import subprocess
import tkinter as tk
from datetime import datetime
from typing import List

from utils.logging_config import get_logger
from caller import rest

logger = get_logger(__name__)


def _safe_set_url_status(app, url: str, status: str):
    """스레드 안전하게 url_status 설정"""
    lock = getattr(app, "url_status_lock", None)
    if lock:
        with lock:
            app.url_status[url] = status
    else:
        app.url_status[url] = status


def _safe_get_url_status(app, url: str, default=None):
    """스레드 안전하게 url_status 조회"""
    lock = getattr(app, "url_status_lock", None)
    if lock:
        with lock:
            return app.url_status.get(url, default)
    else:
        return app.url_status.get(url, default)


def _set_processing_step(app, url: str, step: str):
    """
    현재 처리 중인 단계를 url_status_message에 저장하고 UI 갱신
    Save current processing step to url_status_message and refresh UI

    Steps:
    - 다운로드 중
    - 분석 중
    - 번역 중
    - TTS 생성 중
    - 자막 생성 중
    - 인코딩 중
    """
    if not hasattr(app, "url_status_message"):
        app.url_status_message = {}
    app.url_status_message[url] = step
    # UI 갱신 (메인 스레드에서 실행)
    if hasattr(app, "root") and app.root:
        app.root.after(0, app.update_url_listbox)


from ui.components.custom_dialog import (
    show_info,
    show_warning,
    show_error,
    show_question,
    show_success,
)

# moviepy 2.x compatible imports
from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    concatenate_videoclips,
    CompositeVideoClip,
    TextClip,
    ColorClip,
    ImageClip,
    vfx,
)


from utils import Tool
from core.video import VideoTool
from core.download import DouyinExtract
from .utils import (
    _extract_product_name,
    _get_voice_display_name,
    _translate_error_message,
    _get_short_error_message,
)
from .encoder import (
    _check_gpu_encoder_available,
    _ensure_even_resolution,
    RealtimeEncodingLogger,
)
from .tts_handler import _generate_tts_for_batch, combine_tts_files_with_speed
from .subtitle_handler import create_subtitle_clips_for_speed
from .analysis import _analyze_video_for_batch, _translate_script_for_batch
from core.video.CreateFinalVideo import (
    _rescale_tts_metadata_to_duration,
    _update_tts_metadata_path,
)
from caller import ui_controller
import sys
import io


# ★★★ 로그 캡처 시스템 ★★★
class LogCapture:
    """
    stdout을 캡처하면서 원래 출력도 유지하는 클래스
    Capture stdout while preserving original output with UTF-8 support
    """

    def __init__(self, app, original_stdout):
        self.app = app
        self.original_stdout = original_stdout
        # UTF-8 인코딩 속성 (logging StreamHandler 호환성)
        # UTF-8 encoding property for logging StreamHandler compatibility
        self.encoding = "utf-8"
        self.errors = "replace"

    def write(self, text):
        # 원래 stdout에도 출력 (즉시 flush로 버퍼링 방지)
        # Write to original stdout with immediate flush to prevent buffering
        if self.original_stdout:
            try:
                self.original_stdout.write(text)
                self.original_stdout.flush()  # 즉시 출력
            except (UnicodeEncodeError, UnicodeDecodeError):
                # 인코딩 오류 시 대체 문자로 출력
                safe_text = text.encode("utf-8", errors="replace").decode("utf-8")
                self.original_stdout.write(safe_text)
                self.original_stdout.flush()
            except Exception:
                pass  # 출력 실패 시 무시
        # 버퍼에도 저장 (빈 줄 제외)
        if hasattr(self.app, "_url_log_buffer") and text.strip():
            self.app._url_log_buffer.append(text)

    def flush(self):
        if self.original_stdout:
            try:
                self.original_stdout.flush()
            except Exception:
                pass

    def isatty(self):
        """터미널 여부 반환 (colorama 호환성)"""
        if self.original_stdout and hasattr(self.original_stdout, "isatty"):
            return self.original_stdout.isatty()
        return False

    def fileno(self):
        """파일 디스크립터 반환 (일부 라이브러리 호환성)"""
        if self.original_stdout and hasattr(self.original_stdout, "fileno"):
            return self.original_stdout.fileno()
        raise io.UnsupportedOperation("fileno")

    @property
    def buffer(self):
        """buffer 속성 반환 (io.TextIOWrapper 호환성)"""
        if self.original_stdout and hasattr(self.original_stdout, "buffer"):
            return self.original_stdout.buffer
        return None


def _start_log_capture(app):
    """로그 캡처 시작"""
    if not hasattr(app, "_original_stdout"):
        app._original_stdout = sys.stdout
    sys.stdout = LogCapture(app, app._original_stdout)


def _stop_log_capture(app):
    """로그 캡처 종료"""
    if hasattr(app, "_original_stdout") and app._original_stdout:
        sys.stdout = app._original_stdout


def _get_captured_log(app) -> str:
    """캡처된 로그를 문자열로 반환"""
    if hasattr(app, "_url_log_buffer") and app._url_log_buffer:
        return "".join(app._url_log_buffer)
    return ""


def dynamic_batch_processing_thread(app):
    """Main batch processing workflow for multiple URLs"""
    successful_count = 0
    failed_count = 0
    processed_urls = set()
    pending_remaining: List[str] = []

    try:
        app.add_log("=" * 60)
        app.add_log("배치 처리를 시작합니다.")
        app.add_log("대기열에 등록된 URL을 순서대로 처리합니다.")
        app.add_log("HTTP 500 계열 오류가 발생하면 최대 3회까지 재시도합니다.")
        app.add_log("=" * 60)

        while app.batch_processing:
            # 대기 중인 URL 찾기
            waiting_urls = []
            for url in app.url_queue:
                if url not in processed_urls and app.url_status.get(url) in [
                    "waiting",
                    None,
                ]:
                    waiting_urls.append(url)

            if not waiting_urls:
                app.add_log("대기 중인 URL이 없어 잠시 대기합니다.")
                found = False
                # 최대 10초 동안 1초 간격으로 재확인
                for _ in range(10):
                    if not app.batch_processing:
                        break
                    time.sleep(1)
                    new_waiting = [
                        url
                        for url in app.url_queue
                        if url not in processed_urls
                        and app.url_status.get(url) in ["waiting", None]
                    ]
                    if new_waiting:
                        app.add_log(
                            f"대기열에서 새 URL {len(new_waiting)}개를 감지했습니다. 이어서 처리합니다."
                        )
                        found = True
                        break

                if not found and app.batch_processing:
                    app.add_log("새 URL이 없어 10초 뒤 다시 확인합니다.")
                    time.sleep(10)

                continue

            # URL 처리
            url = waiting_urls[0]
            processed_urls.add(url)

            # 500 오류 재시도 로직 (API 키 자동 전환)
            max_retries = 5
            retry_count = 0

            while retry_count < max_retries and app.batch_processing:
                try:
                    current_index = app.url_queue.index(url) + 1
                    total_in_queue = len(app.url_queue)

                    if retry_count == 0:
                        app.add_log(
                            f"\n[Batch] ({current_index}/{total_in_queue}) URL 처리 시작: {url[:50]}..."
                        )
                    else:
                        app.add_log(
                            f"[Batch] 재시도 {retry_count}/{max_retries} 진행 중: {url[:50]}..."
                        )

                    # 상태 업데이트 (스레드 안전)
                    _safe_set_url_status(app, url, "processing")
                    app.current_processing_index = app.url_queue.index(url)
                    app.root.after(0, app.update_url_listbox)
                    app.root.after(0, app.update_overall_progress_display)

                    # 이전 결과 초기화
                    clear_all_previous_results(app)

                    # 각 단계 처리 (메인의 메서드 호출)
                    _process_single_video(app, url, current_index, total_in_queue)

                    # 성공 (단, 스킵된 경우는 상태 유지)
                    if _safe_get_url_status(app, url) == "skipped":
                        app.add_log(
                            f"[SKIP] [{current_index}/{total_in_queue}] 건너뜀 - 다음 영상으로 진행"
                        )
                        # 스킵된 경우 세션 저장 후 다음으로 진행
                        try:
                            app._auto_save_session()
                        except Exception as session_err:
                            logger.warning("[세션] 저장 실패: %s", session_err)
                        break  # 다음 URL로

                    # 성공 처리
                    _safe_set_url_status(app, url, "completed")
                    successful_count += 1
                    app.add_log(f"[OK] [{current_index}/{total_in_queue}] 완료!")

                    # 작업 횟수 차감 (Work count decrement)
                    try:
                        user_id = (
                            app.login_data.get("data", {}).get("data", {}).get("id", "")
                            if app.login_data
                            else ""
                        )
                        if user_id:
                            work_result = rest.useWork(user_id)
                            if work_result.get("success"):
                                remaining = work_result.get("remaining", -1)
                                if remaining == -1:
                                    logger.debug("[작업횟수] 무제한")
                                else:
                                    app.add_log(f"[작업횟수] 잔여: {remaining}회")
                                # Update local login_data for header display
                                if app.login_data and "data" in app.login_data:
                                    if "data" in app.login_data["data"]:
                                        app.login_data["data"]["data"]["work_used"] = (
                                            work_result.get("used", 0)
                                        )
                                # Refresh subscription info display
                                if hasattr(app, "_update_subscription_info"):
                                    app.root.after(0, app._update_subscription_info)
                            else:
                                logger.warning(
                                    "[작업횟수] 업데이트 실패: %s",
                                    work_result.get("message", ""),
                                )
                    except Exception as work_err:
                        logger.warning("[작업횟수] 차감 실패 (무시됨): %s", work_err)

                    try:
                        # 개별 작업 완료 시 팝업 없이 저장만 수행
                        logger.info(
                            "[LocalSave] 저장 시작 - generated_videos: %d개",
                            len(getattr(app, "generated_videos", [])),
                        )
                        app.save_generated_videos_locally(show_popup=False)
                        logger.info("[LocalSave] 저장 완료")
                        app.final_video_path = ""
                        app.final_video_temp_dir = None

                        # ★★★ 로그 검증: 싱크/오류 문제 확인 ★★★
                        try:
                            if hasattr(app, "output_manager") and app.output_manager:
                                verification_result = (
                                    app.output_manager.verify_video_log(url)
                                )
                                app.url_remarks[url] = verification_result
                                logger.debug(
                                    "[비고] 로그 검증 결과: %s", verification_result
                                )
                        except Exception as verify_err:
                            logger.warning("[비고] 로그 검증 실패: %s", verify_err)
                            app.url_remarks[url] = "통과"

                    except Exception as e:
                        logger.error(
                            "[LocalSave] Failed to move generated videos: %s",
                            e,
                            exc_info=True,
                        )
                        ui_controller.write_error_log(e)

                    # 세션 저장
                    try:
                        app._auto_save_session()
                    except Exception as session_err:
                        logger.warning("[세션] 저장 실패: %s", session_err)

                    break

                except Exception as e:
                    ui_controller.write_error_log(e)
                    error_msg = str(e)
                    error_lower = error_msg.lower()

                    # ★ 503 서버 과부하 → 5분 대기 후 재시도 (API 키 교체 없음, 무한 재시도)
                    if (
                        "503" in error_msg
                        or "overloaded" in error_lower
                        or "unavailable" in error_lower
                    ):
                        wait_minutes = 5
                        app.add_log(
                            f"[WARN] ⏸️ Gemini 서버 과부하 감지! {wait_minutes}분 후 재시도합니다..."
                        )
                        app.add_log(f"[INFO] 현재 URL에서 일시중지 - 서버 복구 대기 중")

                        # 5분 대기 (1초 단위로 체크)
                        for remaining in range(wait_minutes * 60, 0, -1):
                            if not app.batch_processing:
                                app.add_log("[INFO] 사용자가 중지함")
                                break
                            if remaining % 60 == 0:
                                app.add_log(
                                    f"[INFO] 대기 중... {remaining // 60}분 남음"
                                )
                            time.sleep(1)

                        if app.batch_processing:
                            app.add_log(f"[INFO] ▶️ 재시도 시작: {url[:50]}...")
                            # retry_count 증가 없이 계속 재시도
                            continue
                        else:
                            break

                    # ★ 429 할당량 초과 → API 키 교체 후 재시도
                    elif (
                        "429" in error_msg
                        or "quota" in error_lower
                        or "resource_exhausted" in error_lower
                    ):
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = retry_count * 15  # 15, 30, 45초
                            app.add_log(
                                f"[WARN] API 할당량 초과. {wait_time}초 후 다른 키로 재시도..."
                            )

                            # API 키 교체
                            try:
                                app.api_key_manager.block_current_key(
                                    duration_minutes=5
                                )
                                new_key = app.api_key_manager.get_available_key()
                                app.init_client(use_specific_key=new_key)
                                app.add_log("🔑 API 키 교체 완료")
                            except Exception as api_key_err:
                                logger.warning("API 키 교체 실패: %s", api_key_err)
                                app.add_log("[WARN] API 키 교체 실패")

                            # 대기
                            for _ in range(wait_time):
                                if not app.batch_processing:
                                    break
                                time.sleep(1)
                            continue
                        else:
                            app.add_log(
                                f"❌ {max_retries}번 재시도 실패 (모든 API 키 소진)"
                            )
                            _safe_set_url_status(app, url, "failed")
                            app.url_status_message[url] = _get_short_error_message(e)
                            failed_count += 1

                            try:
                                app._auto_save_session()
                            except Exception as session_err:
                                logger.warning("[세션] 저장 실패: %s", session_err)

                            break

                    # ★ 500 기타 서버 오류 → 1분 대기 후 재시도
                    elif "500" in error_msg:
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = 60  # 1분 대기
                            app.add_log(
                                f"[WARN] 서버 오류 발생. {wait_time}초 후 재시도..."
                            )

                            for _ in range(wait_time):
                                if not app.batch_processing:
                                    break
                                time.sleep(1)
                            continue
                        else:
                            app.add_log(f"❌ {max_retries}번 재시도 실패")
                            _safe_set_url_status(app, url, "failed")
                            app.url_status_message[url] = _get_short_error_message(e)
                            failed_count += 1

                            try:
                                app._auto_save_session()
                            except Exception as session_err:
                                logger.warning("[세션] 저장 실패: %s", session_err)

                            break
                    else:
                        lowered = error_msg.lower()
                        permission_indicators = [
                            "permission denied",
                            "permission_denied",
                            "forbidden",
                            "403",
                            "suspended",
                            "invalid api key",
                            "unauthorized",
                        ]
                        if any(token in lowered for token in permission_indicators):
                            app.add_log(
                                "[WARN] API 권한 오류 감지. 현재 키를 차단하고 다른 키로 교체합니다."
                            )
                            try:
                                # 장기간 차단하여 곧바로 재사용되지 않도록 처리
                                app.api_key_manager.block_current_key(
                                    duration_minutes=60
                                )
                            except Exception as block_exc:
                                app.add_log(f"[WARN] 키 차단 중 오류: {block_exc}")
                            try:
                                new_key = app.api_key_manager.get_available_key()
                                if app.init_client(use_specific_key=new_key):
                                    app.add_log("🔑 API 키 교체 완료 (권한 오류 대응)")
                                    continue
                            except Exception as switch_exc:
                                app.add_log(
                                    f"[WARN] 권한 오류 후 새 API 키 확보 실패: {switch_exc}"
                                )
                        _safe_set_url_status(app, url, "failed")
                        # 비고란에 짧은 오류 메시지 저장
                        app.url_status_message[url] = _get_short_error_message(e)
                        failed_count += 1
                        translated_error_msg = _translate_error_message(error_msg)
                        app.add_log(f"❌ 실패: {translated_error_msg[:100]}")

                        # 세션 저장
                        try:
                            app._auto_save_session()
                        except Exception as session_err:
                            logger.warning("[세션] 저장 실패: %s", session_err)

                        break

            # 정리
            try:
                if Tool is not None:
                    Tool.cleanup_temp_files(getattr(app, "_temp_downloaded_file", None))
            except Exception as cleanup_err:
                logger.debug(
                    "[정리] 임시 파일 정리 실패 (무시됨): %s", str(cleanup_err)[:50]
                )

            app.root.after(0, app.update_url_listbox)
            app.root.after(0, app.update_overall_progress_display)

            # 간격 대기 - 10초 간격으로 다음 URL 처리
            if app.batch_processing:
                pending = [
                    candidate
                    for candidate in app.url_queue
                    if candidate not in processed_urls
                    and app.url_status.get(candidate) in ["waiting", None]
                ]
                gap_seconds = max(0, int(getattr(app, "url_gap_seconds", 10)))
                if pending and gap_seconds > 0:
                    app.add_log(f"⏱ 다음 URL까지 {gap_seconds}초 대기합니다.")
                    for _ in range(gap_seconds):
                        if not app.batch_processing:
                            break
                        time.sleep(1)
                elif pending:
                    time.sleep(0.5)

        # 완료 로그
        pending_remaining = [
            url
            for url in app.url_queue
            if app.url_status.get(url) in ("waiting", "processing")
        ]
        app.add_log("=" * 60)
        app.add_log("배치 처리를 종료합니다.")
        app.add_log(f"성공 {successful_count}건 / 실패 {failed_count}건")
        if pending_remaining:
            app.add_log(
                f"미처리 URL {len(pending_remaining)}건은 대기 상태로 남아 있습니다."
            )
        app.add_log("=" * 60)

    except Exception as e:
        translated_error = _translate_error_message(str(e))
        app.add_log(f"[오류] 배치 처리 오류: {translated_error}")
        ui_controller.write_error_log(e)
        # traceback 출력 제거 - 한글 메시지만 표시

    finally:
        app.batch_processing = False
        app.dynamic_processing = False
        # threads.py에서는 tkinter를 임포트하지 않고 문자열로 상태 지정
        app.root.after(0, lambda: app.start_batch_button.config(state="normal"))
        app.root.after(0, lambda: app.stop_batch_button.config(state="disabled"))
        summary = f"배치 처리 완료: 성공 {successful_count}건, 실패 {failed_count}건"
        if pending_remaining:
            summary += f" (미처리 {len(pending_remaining)}건 대기)"

        all_jobs_finished = not pending_remaining

        # 모든 작업이 완료되었으면 세션 파일 삭제
        if all_jobs_finished:
            try:
                app.session_manager.clear_session()
                app.add_log("[세션] 모든 작업 완료 - 세션 파일 삭제")
            except Exception as session_err:
                logger.warning("[세션] 정리 실패: %s", session_err)
        else:
            # 미처리 작업이 남아있으면 세션 저장
            try:
                app._auto_save_session()
            except Exception as session_err:
                logger.warning("[세션] 저장 실패: %s", session_err)

        if processed_urls and all_jobs_finished:
            app.root.after(0, lambda: show_success(app.root, "배치 완료", summary))
        app.update_status("준비 완료")

        # 비용은 각 URL 완료 시마다 출력되므로 여기서는 출력하지 않음
        # (각 URL 처리 후 이미 reset_session 호출됨)


def _process_single_video(app, url, current_number, total_urls):
    """Process a single video inside the dynamic batch workflow."""

    app.reset_progress_states()
    if hasattr(app, "set_active_job"):
        app.set_active_job(url, current_number, total_urls)

    # ★★★ 로그 캡처 시작 ★★★
    # 이 URL 처리에 대한 모든 로그를 저장
    app._url_log_buffer = []
    _start_log_capture(app)

    # Store URL and timestamp for per-URL folder organization
    app._current_processing_url = url

    # URL별 타임스탬프 관리 (세션 복구 시 폴더명 일관성 유지)
    if not hasattr(app, "url_timestamps"):
        app.url_timestamps = {}

    # 기존 타임스탬프가 있으면 재사용 (같은 폴더에 저장)
    if url in app.url_timestamps:
        app._processing_start_time = app.url_timestamps[url]
        logger.debug(
            "[폴더 관리] 기존 타임스탬프 재사용: %s",
            app._processing_start_time.strftime("%Y%m%d_%H%M%S"),
        )
    else:
        # 새로운 URL이면 새 타임스탬프 생성
        app._processing_start_time = datetime.now()
        app.url_timestamps[url] = app._processing_start_time
        logger.debug(
            "[폴더 관리] 새 타임스탬프 생성: %s",
            app._processing_start_time.strftime("%Y%m%d_%H%M%S"),
        )

    current_step = "download"

    try:
        # 1. Download the source clip.
        _set_processing_step(app, url, "다운로드 중")
        app.update_progress_state(
            "download", "processing", 5, "현재 원본 동영상을 찾고 있습니다."
        )
        app.update_step_progress("download", 20)
        app.add_log(f"📥 [{current_number}/{total_urls}] 영상 다운로드 중...")

        # 저장 폴더 변경 시나 기존 다운로드 파일이 없으면 재다운로드
        need_redownload = (
            not hasattr(app, "_temp_downloaded_file")
            or app._temp_downloaded_file is None
            or not os.path.exists(app._temp_downloaded_file)
        )

        if need_redownload:
            downloaded_path = DouyinExtract.download_tiktok_douyin_video(url)
            app._temp_downloaded_file = downloaded_path
            app.add_log(
                f"[다운로드] 새로 다운로드 완료: {os.path.basename(downloaded_path)}"
            )
        else:
            app.add_log(
                f"[다운로드] 기존 파일 사용: {os.path.basename(app._temp_downloaded_file)}"
            )

        # Measure the original duration so later steps can adjust pacing.
        original_video_duration = app.get_video_duration_helper()
        app.add_log(f"[INFO] 원본 영상 길이: {original_video_duration:.1f}s")
        app.original_video_duration = original_video_duration

        # 영상 길이 제한 체크
        MAX_VIDEO_DURATION = 39
        MIN_VIDEO_DURATION = 10

        # 39초 초과 영상 건너뛰기 (팝업 없이 자동 스킵)
        if original_video_duration > MAX_VIDEO_DURATION:
            skip_message = f"영상 길이 초과 (제한: {MAX_VIDEO_DURATION}초, 실제: {original_video_duration:.1f}초)"
            app.add_log(
                f"⏭️ [{current_number}/{total_urls}] {skip_message} - 다음 영상으로 자동 이동"
            )
            _safe_set_url_status(app, url, "skipped")
            app.url_status_message[url] = f"길이초과{int(original_video_duration)}초"
            app.update_url_listbox()

            # 팝업 제거 - 로그만 남기고 다음 영상으로 진행

            app.cleanup_temp_files()
            app.reset_progress_states()
            try:
                app._auto_save_session()
            except Exception as session_err:
                logger.warning("[세션] 저장 실패: %s", session_err)
            return

        # 10초 미만 영상 건너뛰기 (팝업 없이 자동 스킵)
        if original_video_duration < MIN_VIDEO_DURATION:
            skip_message = f"영상 너무 짧음 (최소: {MIN_VIDEO_DURATION}초, 실제: {original_video_duration:.1f}초)"
            app.add_log(
                f"⏭️ [{current_number}/{total_urls}] {skip_message} - 다음 영상으로 자동 이동"
            )
            _safe_set_url_status(app, url, "skipped")
            app.url_status_message[url] = f"너무짧음{original_video_duration:.0f}초"
            app.update_url_listbox()

            # 팝업 제거 - 로그만 남기고 다음 영상으로 진행

            app.cleanup_temp_files()
            app.reset_progress_states()
            try:
                app._auto_save_session()
            except Exception as session_err:
                logger.warning("[세션] 저장 실패: %s", session_err)
            return

        app.update_progress_state("download", "completed", 100, "원본 영상 확보 완료!")
        app.update_step_progress("download", 100)

        # 2. Analyze the clip with the AI helper.
        current_step = "analysis"
        _set_processing_step(app, url, "분석 중")
        app.update_progress_state(
            "analysis", "processing", 5, "동영상을 분석하고 있습니다."
        )
        app.update_step_progress("analysis", 20)
        app.add_log(
            f"[AI] [{current_number}/{total_urls}] 영상 분석 중... ({original_video_duration:.1f}s)"
        )
        _analyze_video_for_batch(app)
        app.update_progress_state("analysis", "completed", 100, None)
        app.update_step_progress("analysis", 100)

        # 3. Translate / adapt the generated script.
        current_step = "translation"
        _set_processing_step(app, url, "번역 중")
        app.update_progress_state(
            "translation", "processing", 5, "번역과 각색을 하고 있습니다."
        )
        app.update_step_progress("translation", 20)
        app.add_log(f"[SCRIPT] [{current_number}/{total_urls}] 대본 정리 중...")
        _translate_script_for_batch(app)
        app.update_progress_state("translation", "completed", 100, None)
        app.update_step_progress("translation", 100)

        # 4. TTS + 자막 생성 (음성마다 개별 계산)
        # 각 음성마다 Whisper 분석을 통해 독립적인 자막 타이밍 생성
        logger.debug("[자막 준비] 음성별 개별 타이밍 계산")

        # 4. TTS + 5. Final video creation (per voice).
        # 사용자가 실제로 선택한 음성만 사용 (voice_vars에서 체크된 것)
        selected_voices = [vid for vid, state in app.voice_vars.items() if state.get()]
        voice_manager = getattr(app, "voice_manager", None)
        if selected_voices:
            voices = []
            for vid in selected_voices:
                if voice_manager:
                    profile = voice_manager.get_voice_profile(vid)
                    if profile and profile.get("voice_name"):
                        voices.append(profile["voice_name"])
                        continue
                voices.append(vid)
        else:
            # 선택된 음성이 없으면 기본값 사용
            voices = getattr(
                app,
                "multi_voice_presets",
                getattr(app, "available_tts_voices", [app.fixed_tts_voice]),
            )

        voice_labels = [
            _get_voice_display_name(v)
            for v in (voices if isinstance(voices, list) else [voices])
        ]
        if selected_voices:
            logger.info(
                "[음성 선택] 사용자가 선택한 음성 사용: %s", ", ".join(voice_labels)
            )
        else:
            logger.info("[음성 선택] 기본 음성 사용: %s", ", ".join(voice_labels))

        max_voices = getattr(app, "max_voice_selection", None)
        if max_voices and len(voices) > max_voices:
            voices = list(voices)[:max_voices]
        total_voices = len(voices)
        if total_voices == 0:
            voices = [app.fixed_tts_voice]
            total_voices = 1

        for idx_voice, voice in enumerate(voices, 1):
            # ★★★ 핵심 수정: 음성마다 모든 TTS 관련 데이터 완전 초기화 ★★★
            # 이전 음성의 타이밍 데이터가 남아있으면 새 음성에 잘못 적용됨
            app._cached_subtitle_clips = None
            app._per_line_tts = []  # TTS 메타데이터 초기화
            app.tts_sync_info = {}  # 타이밍 정보 초기화
            if hasattr(app, "_last_whisper_path"):
                delattr(app, "_last_whisper_path")  # Whisper 캐시 경로 초기화
            logger.debug(
                "[자막 캐시] 음성 %d/%d - 전체 TTS 데이터 초기화 (새로 계산)",
                idx_voice,
                total_voices,
            )

            app.fixed_tts_voice = voice
            voice_label = _get_voice_display_name(voice)  # 한글 이름으로 변환

            # ★ 현재 처리 중인 음성을 진행현황 패널에 표시
            if hasattr(app, "set_active_voice"):
                app.set_active_voice(voice, idx_voice, total_voices)

            voice_progress = max(5, int(((idx_voice - 1) / total_voices) * 100))
            current_step = "tts"
            # URL 상태에 현재 단계 표시 (TTS 생성)
            _set_processing_step(app, url, f"TTS 생성 중 ({idx_voice}/{total_voices})")
            app.update_progress_state(
                "tts",
                "processing",
                voice_progress,
                f"{voice_label} 음성 합성 중입니다.",
            )
            app.update_step_progress("tts", 20)
            tts_sync_progress = max(5, int(((idx_voice - 1) / total_voices) * 100))
            app.update_progress_state(
                "tts_audio",
                "processing",
                tts_sync_progress,
                f"{voice_label} 음성 생성 준비 중입니다.",
            )
            _generate_tts_for_batch(app, voice)
            after_voice_progress = max(
                voice_progress, int((idx_voice / total_voices) * 100)
            )
            app.update_progress_state(
                "tts",
                "processing",
                after_voice_progress,
                f"{voice_label} 음성 합성이 완료되었습니다.",
            )
            app.update_step_progress("tts", int(20 + 80 * idx_voice / total_voices))
            tts_complete_progress = max(
                tts_sync_progress, int((idx_voice / total_voices) * 100)
            )
            app.update_progress_state(
                "tts_audio",
                "processing",
                tts_complete_progress,
                f"{voice_label} 음성 생성 완료! 싱크 계산을 준비합니다.",
            )
            if idx_voice == total_voices:
                app.update_progress_state(
                    "tts_audio", "completed", 100, "모든 음성 생성이 끝났습니다."
                )

            current_step = "video"
            # URL 상태에 현재 단계 표시 (인코딩)
            _set_processing_step(app, url, f"인코딩 중 ({idx_voice}/{total_voices})")
            video_progress = max(5, int(((idx_voice - 1) / total_voices) * 100))
            app.update_progress_state(
                "video",
                "processing",
                video_progress,
                f"{voice_label} 음성으로 영상을 준비 중입니다.",
            )
            app.update_step_progress("video", 20)
            _create_final_video_for_batch(
                app, voice, idx_voice, total_voices, current_number, total_urls
            )
            after_video_progress = max(
                video_progress, int((idx_voice / total_voices) * 100)
            )
            app.update_progress_state(
                "video",
                "processing",
                after_video_progress,
                f"{voice_label} 음성으로 렌더링 중입니다.",
            )
            app.update_step_progress("video", int(20 + 80 * idx_voice / total_voices))

        app.update_progress_state(
            "tts",
            "completed",
            100,
            f"음성 합성 단계가 완료되었습니다. (작업 {current_number}/{total_urls})",
        )
        app.update_progress_state(
            "video",
            "completed",
            100,
            f"영상 렌더링 단계가 완료되었습니다. (작업 {current_number}/{total_urls})",
        )

        # URL 1개 처리 완료 - 비용 요약 출력
        app.token_calculator.log_session_summary(
            f"영상 완성 [{current_number}/{total_urls}]"
        )
        # 다음 URL을 위해 비용 초기화
        app.token_calculator.reset_session()

    except Exception as exc:
        # traceback 출력 제거 - 한글 메시지만 표시
        ui_controller.write_error_log(exc)
        error_msg = _translate_error_message(str(exc))
        error_lower = str(exc).lower()
        logger.error("[처리 오류] %s", error_msg)

        # ★ API 키 교체 가능한 오류는 'error' 상태로 표시하지 않음 ★
        # 429(할당량), 403(권한), 503(과부하) 등은 키 교체 후 재시도되므로 진행 중 유지
        is_api_recoverable = any(
            token in error_lower
            for token in [
                "429",
                "quota",
                "resource_exhausted",  # 할당량 초과
                "403",
                "permission",
                "forbidden",  # 권한 오류
                "503",
                "overloaded",
                "unavailable",  # 서버 과부하
                "500",  # 서버 오류
            ]
        )

        if not is_api_recoverable:
            # 복구 불가능한 오류만 'error' 상태 표시
            app.update_progress_state(current_step, "error", 0, error_msg)
            if current_step == "tts":
                app.update_progress_state("tts_audio", "error", 0, error_msg)
            elif current_step == "video":
                app.update_progress_state("finalize", "error", 0, error_msg)
        else:
            # API 오류는 진행 중 상태 유지 (키 교체 후 재시도 예정)
            logger.info("[API 오류] 키 교체 후 재시도 예정 - 진행 상태 유지")

        raise


def _create_final_video_for_batch(
    app, voice, voice_index=None, voice_total=None, job_index=None, total_jobs=None
):
    """배치용 최종 비디오 생성 - TTS 실제 길이로 자르기"""
    try:
        # 음성 정보를 진행 상황에 표시
        if hasattr(app, "set_active_voice"):
            app.set_active_voice(voice, voice_index, voice_total)

        # 음성 ID를 한글 이름으로 변환
        voice_label = _get_voice_display_name(voice)

        app.add_log(f"[인코딩] {voice_label} 음성으로 영상 제작 시작...")

        logger.info("=" * 60)
        logger.info(
            "[배치 비디오 생성] %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        logger.info("=" * 60)

        source_video = app._temp_downloaded_file
        if not source_video or not os.path.exists(source_video):
            raise Exception("원본 비디오 파일을 찾을 수 없습니다")

        if voice_total and voice_index:
            ratio_start = max(0.0, (voice_index - 1) / max(voice_total, 1))
            ratio_end = min(1.0, voice_index / max(voice_total, 1))
        else:
            ratio_start = 0.0
            ratio_end = 1.0

        job_suffix = ""
        if job_index and total_jobs:
            job_suffix = f" (작업 {job_index}/{total_jobs})"
        merge_start = max(0, int(ratio_start * 100))
        merge_end = max(merge_start + 1, int(ratio_end * 100))

        # 진행 상황 메시지에 음성 이름 포함
        if voice_index and voice_total:
            progress_msg = f"[{voice_index}/{voice_total}] {voice_label} 음성을 영상에 합치는 중입니다."
        else:
            progress_msg = f"{voice_label} 음성을 영상에 합치는 중입니다."
        app.update_progress_state(
            "audio_merge", "processing", merge_start, progress_msg
        )

        selected_voice = voice
        logger.info("[비디오 정보]")
        logger.info("  원본 파일: %s", os.path.basename(source_video))
        logger.info("  TTS 음성: %s", voice_label)

        # 비디오 로드
        video = VideoFileClip(source_video)
        original_duration = video.duration
        video_duration = original_duration
        original_fps = video.fps

        logger.info("  원본 길이: %.3f초", original_duration)
        logger.info("  원본 크기: %dx%d", video.w, video.h)
        logger.info("  FPS: %s", original_fps)

        # 9:16 비율 강제 적용 (1080x1920)
        target_width = 1080
        target_height = 1920
        target_ratio = target_height / target_width  # 9:16 = 1.777...
        current_ratio = video.h / video.w

        logger.info("[비율 조정] 9:16 세로 영상으로 변환")
        logger.info("  목표 크기: %dx%d (9:16)", target_width, target_height)

        if abs(current_ratio - target_ratio) > 0.01:  # 비율이 다르면 조정
            # 원본이 더 넓으면(가로 영상) 좌우 crop
            if current_ratio < target_ratio:
                # 높이 기준으로 맞추고 좌우 crop
                new_height = video.h
                new_width = int(new_height / target_ratio)
                x_center = video.w / 2
                x1 = int(x_center - new_width / 2)
                video = video.crop(x1=x1, width=new_width)
                logger.debug("  가로 crop: %dx%d", video.w, video.h)
            # 원본이 더 좁으면(이미 세로) 상하 crop
            else:
                # 너비 기준으로 맞추고 상하 crop
                new_width = video.w
                new_height = int(new_width * target_ratio)
                y_center = video.h / 2
                y1 = int(y_center - new_height / 2)
                video = video.crop(y1=y1, height=new_height)
                logger.debug("  세로 crop: %dx%d", video.w, video.h)

        # 최종 크기로 리사이즈 (1080x1920)
        if video.w != target_width or video.h != target_height:
            video = video.resize((target_width, target_height))
            logger.debug("  최종 크기: %dx%d", video.w, video.h)

        # 자막 생성을 위해 변환된 크기를 캐시
        app.cached_video_width = target_width
        app.cached_video_height = target_height
        logger.debug("  자막 생성용 크기 캐시: %dx%d", target_width, target_height)

        # 좌우 반전 (필요시)
        if hasattr(app, "mirror_video") and app.mirror_video and app.mirror_video.get():
            logger.debug("  좌우 반전 적용")
            video = video.fx(vfx.mirror_x)

        # 중국어 자막 블러
        logger.debug("  중국어 자막 블러 처리...")
        cached_last_frame = (
            None  # 마지막 프레임 캐시 (블러 처리된 VideoClip의 파일 참조 문제 방지)
        )
        try:
            video = app.apply_chinese_subtitle_removal(video)
            # ★ 블러 처리 직후 마지막 프레임 캐시 (나중에 연장 시 사용)
            try:
                cached_last_frame = video.get_frame(max(video.duration - 0.01, 0))
                logger.debug("중국어 자막 제거 완료 + 마지막 프레임 캐시됨")
            except Exception as frame_cache_err:
                logger.debug(
                    "중국어 자막 제거 완료 (프레임 캐시 실패): %s", frame_cache_err
                )
        except Exception as e:
            ui_controller.write_error_log(e)
            logger.warning("중국어 자막 제거 실패: %s", e)

        # TTS 1.2배속 처리 (무음 없이)
        logger.info("[TTS 처리]")
        combined_audio_path = combine_tts_files_with_speed(app)

        if not combined_audio_path or not os.path.exists(combined_audio_path):
            app.update_progress_state(
                "audio_merge", "error", merge_start, "TTS 오디오 결합에 실패했습니다."
            )
            raise Exception("TTS 파일 결합 실패")

        app.update_progress_state(
            "audio_merge",
            "processing",
            merge_end,
            "오디오 합본 완료! 싱크 분석으로 넘어갑니다.",
        )

        # 1.2배속된 오디오 로드
        new_audio = AudioFileClip(combined_audio_path)

        eps = 0.02  # 20ms 정도면 충분
        real_audio_dur = new_audio.duration
        audio_source_path = combined_audio_path

        # sync_info 가져오기 (None 방지)
        sync_info = getattr(app, "tts_sync_info", None) or {}

        # Gemini가 분석한 실제 음성 종료 시점 사용 (CTA 보호)
        actual_audio_end = sync_info.get("actual_audio_end")
        if actual_audio_end and actual_audio_end > 0:
            actual_tts_duration = actual_audio_end
            logger.info(
                "[동기화] Gemini 분석 기준 실제 음성 길이 사용: %.2f초",
                actual_tts_duration,
            )
        else:
            # KeyError 방지: speeded_duration이 없으면 real_audio_dur 사용
            actual_tts_duration = sync_info.get("speeded_duration", real_audio_dur)
            logger.info("[동기화] 파일 길이 기준 사용: %.2f초", actual_tts_duration)

        logger.info("[동기화 분석]")
        logger.info("  원본 비디오: %.3f초", original_duration)
        logger.info(
            "  TTS 오디오: %.3f초 (speed_ratio: %sx)",
            actual_tts_duration,
            sync_info.get("speed_ratio", 1.0),
        )

        # Keep last captions visible: audio length + 1.0s margin
        desired_cut = actual_tts_duration + 1.0
        logger.info("  Target sync length: %.3fs (audio + 1.0s buffer)", desired_cut)
        shortage = actual_tts_duration - original_duration
        if (
            shortage > original_duration * 0.5
        ):  # guard against extremely long TTS vs video
            logger.warning(
                "TTS is %.1fs longer than video (%.0f%%)",
                shortage,
                (actual_tts_duration / original_duration * 100),
            )
            logger.warning("  Video length: %.1fs", original_duration)
            logger.warning("  TTS length: %.1fs", actual_tts_duration)
            raise RuntimeError(
                f"TTS length ({actual_tts_duration:.1f}s) exceeds video length ({original_duration:.1f}s) "
                f"by {shortage:.1f}s. Use a shorter script or a longer source video."
            )

        # 1) Audio shorter than target -> add silence at the end
        if real_audio_dur + eps < desired_cut:
            from pydub import AudioSegment

            pad_ms = int((desired_cut - real_audio_dur + eps) * 1000)
            src_seg = AudioSegment.from_file(combined_audio_path)
            padded = src_seg + AudioSegment.silent(duration=pad_ms)
            padded_path = os.path.join(
                app.tts_output_dir, "speeded_tts_padded_tail.wav"
            )
            padded.export(padded_path, format="wav")
            # AudioSegment 메모리 해제
            del src_seg, padded
            new_audio.close()
            new_audio = AudioFileClip(padded_path)
            real_audio_dur = new_audio.duration  # update
            audio_source_path = padded_path
            # ★ 무음 패딩은 오디오 끝에 추가 - 경로만 업데이트, 타이밍 스케일링 X ★
            # _rescale_tts_metadata_to_duration을 호출하면 타이밍이 늘어나서 싱크가 깨짐!
            _update_tts_metadata_path(app, padded_path)
            logger.debug(
                "  [Audio] Added %.2fs silence -> %.3fs (path only, timing preserved)",
                pad_ms / 1000,
                real_audio_dur,
            )

        # 2) Audio longer than target -> trim slightly
        elif real_audio_dur > desired_cut + eps:
            new_audio = new_audio.subclip(0, max(0, desired_cut - eps))
            real_audio_dur = new_audio.duration  # update
            # 오디오 트림 시에도 기존 오프셋 유지 (자막 싱크 보존)
            current_offset = app.tts_sync_info.get("audio_start_offset", 0.0)
            logger.debug(
                "  [Audio] Trimmed to %.3fs (offset: %.3fs maintained)",
                real_audio_dur,
                current_offset,
            )

        # Sync info / metadata refresh
        sync_info = getattr(app, "tts_sync_info", {}) or {}
        sync_info["speeded_duration"] = real_audio_dur
        sync_info["file_path"] = audio_source_path
        app.tts_sync_info = sync_info

        # ★ 마지막 자막 끝 시간 확인 (CTA 등 모든 자막이 보이도록)
        last_subtitle_end = 0.0
        if hasattr(app, "_per_line_tts") and app._per_line_tts:
            for entry in app._per_line_tts:
                if isinstance(entry, dict):
                    end_time = entry.get("end", 0)
                    if (
                        isinstance(end_time, (int, float))
                        and end_time > last_subtitle_end
                    ):
                        last_subtitle_end = float(end_time)

        # Target video duration = max(오디오 끝, 마지막 자막 끝) + 1.0초
        # 오디오와 자막 모두 끝까지 나온 후 1.0초 여유
        content_end = max(real_audio_dur, last_subtitle_end)
        target_video_duration = content_end + 1.0
        timestamps_source = sync_info.get("timestamps_source", "unknown")
        logger.info("  [영상 길이 계산]")
        logger.info("    타임스탬프 소스: %s", timestamps_source)
        logger.info("    오디오 끝: %.3fs", real_audio_dur)
        logger.info("    마지막 자막 끝: %.3fs", last_subtitle_end)
        logger.info(
            "    Target video duration: %.3fs (콘텐츠 + 1.0s)", target_video_duration
        )

        # Match video length to target (extend with freeze frame or trim)
        if video.duration + eps < target_video_duration:
            extend_dur = target_video_duration - video.duration
            # ImageClip already imported at top level

            # 1순위: 캐시된 마지막 프레임 사용 (블러 처리 직후 저장됨)
            if cached_last_frame is not None:
                try:
                    tail_frame = ImageClip(cached_last_frame, duration=extend_dur)
                    tail_frame.fps = original_fps
                    video = concatenate_videoclips([video, tail_frame])
                    logger.debug(
                        "  [Video] Extended (cached frame): %.3fs -> %.3fs",
                        original_duration,
                        video.duration,
                    )
                except Exception as cache_err:
                    logger.debug(
                        "  [Video] 캐시 프레임 사용 실패: %s", str(cache_err)[:30]
                    )
                    cached_last_frame = None  # 실패 시 다음 방법 시도

            # 2순위: 현재 비디오에서 직접 프레임 추출
            if cached_last_frame is None:
                try:
                    frame_time = max(video.duration - 0.01, 0)
                    last_frame_array = video.get_frame(frame_time)
                    tail_frame = ImageClip(last_frame_array, duration=extend_dur)
                    tail_frame.fps = original_fps
                    video = concatenate_videoclips([video, tail_frame])
                    logger.debug(
                        "  [Video] Extended: %.3fs -> %.3fs (freeze frame)",
                        original_duration,
                        video.duration,
                    )
                except Exception as frame_err:
                    # 3순위: 원본 비디오에서 직접 가져오기
                    logger.debug(
                        "  [Video] 프레임 추출 실패, 원본에서 재시도: %s",
                        str(frame_err)[:40],
                    )
                    try:
                        source_video_clip = VideoFileClip(source_video)
                        frame_time = max(
                            min(
                                source_video_clip.duration - 0.01, video.duration - 0.01
                            ),
                            0,
                        )
                        last_frame_array = source_video_clip.get_frame(frame_time)
                        tail_frame = ImageClip(last_frame_array, duration=extend_dur)
                        tail_frame.fps = original_fps
                        video = concatenate_videoclips([video, tail_frame])
                        source_video_clip.close()
                        logger.debug(
                            "  [Video] Extended (from source): %.3fs -> %.3fs",
                            original_duration,
                            video.duration,
                        )
                    except Exception as fallback_err:
                        # 최후의 수단: 비디오 연장 포기
                        logger.debug(
                            "  [Video] 연장 실패, 현재 길이 유지: %.3fs", video.duration
                        )
        elif video.duration > target_video_duration + eps:
            video = video.subclip(0, target_video_duration)
            logger.debug(
                "  [Video] Trimmed: %.3fs -> %.3fs", original_duration, video.duration
            )

        video_duration = video.duration

        # Apply audio to video
        final_video = video.set_audio(new_audio)

        if final_video.duration > target_video_duration + eps:
            final_video = final_video.subclip(0, target_video_duration)

        # Subtitles
        subtitle_applied = False
        analysis_progress_base = min(100, merge_end + 5)
        overlay_progress_base = min(100, analysis_progress_base + 5)

        if app.add_subtitles.get() if hasattr(app, "add_subtitles") else True:
            try:
                if (
                    hasattr(app, "_cached_subtitle_clips")
                    and app._cached_subtitle_clips is not None
                ):
                    logger.debug("[Subtitles] 동일 음성 내 캐시된 자막 재사용")
                    subtitle_clips = app._cached_subtitle_clips
                else:
                    logger.debug("[Subtitles] 현재 음성에 맞춰 자막 타이밍 계산 중...")

                    # ========== [SYNC DEBUG] 자막 생성 전 오디오/영상 정보 ==========
                    logger.debug("=" * 70)
                    logger.debug("[SYNC DEBUG] 자막 생성 전 상태")
                    logger.debug("=" * 70)
                    logger.debug(
                        "  target_video_duration: %.3fs", target_video_duration
                    )
                    logger.debug("  real_audio_dur: %.3fs", real_audio_dur)
                    sync_info = getattr(app, "tts_sync_info", {}) or {}
                    logger.debug("  tts_sync_info:")
                    logger.debug(
                        "    - timestamps_source: %s",
                        sync_info.get("timestamps_source", "unknown"),
                    )
                    logger.debug(
                        "    - speeded_duration: %s",
                        sync_info.get("speeded_duration", "N/A"),
                    )
                    logger.debug(
                        "    - audio_start_offset: %s",
                        sync_info.get("audio_start_offset", "N/A"),
                    )
                    logger.debug(
                        "    - actual_audio_end: %s",
                        sync_info.get("actual_audio_end", "N/A"),
                    )
                    logger.debug("=" * 70)

                    if voice_index and voice_total:
                        analysis_message = f"[{voice_index}/{voice_total}] {voice_label} - computing subtitle timing from 1.2x audio"
                    else:
                        analysis_message = (
                            f"{voice_label} - computing subtitle timing from 1.2x audio"
                        )
                    app.update_progress_state(
                        "audio_analysis",
                        "processing",
                        analysis_progress_base,
                        analysis_message,
                    )
                    # _extend_last_subtitle_to_video_end 호출 제거: Gemini 타임스탬프 존중
                    # 이전 코드는 마지막 자막을 영상 끝까지 강제 연장해서 싱크가 깨졌음
                    subtitle_clips = create_subtitle_clips_for_speed(
                        app, target_video_duration
                    )
                    app._cached_subtitle_clips = subtitle_clips

                subtitle_count = len(subtitle_clips) if subtitle_clips else 0
                if subtitle_count:
                    analysis_message = (
                        f"Subtitles synced: {subtitle_count} timing points"
                    )
                else:
                    analysis_message = "Audio analysis finished; using default timing."
                app.update_progress_state(
                    "audio_analysis",
                    "processing",
                    analysis_progress_base,
                    analysis_message,
                )
                if not voice_total or (
                    voice_index and voice_total and voice_index == voice_total
                ):
                    app.update_progress_state(
                        "audio_analysis", "completed", 100, analysis_message
                    )
                app.update_progress_state(
                    "subtitle_overlay",
                    "processing",
                    overlay_progress_base,
                    "Overlaying subtitles with calculated timings.",
                )

                if subtitle_clips and len(subtitle_clips) > 0:
                    logger.debug("  Generated subtitles: %d", len(subtitle_clips))
                    final_video = CompositeVideoClip([final_video] + subtitle_clips)
                    final_video.fps = original_fps
                    subtitle_applied = True
                    overlay_message = f"Applied {len(subtitle_clips)} subtitles."
                else:
                    overlay_message = (
                        "No subtitles generated; continuing without burn-in."
                    )
                app.update_progress_state(
                    "subtitle_overlay",
                    "processing",
                    overlay_progress_base,
                    overlay_message,
                )
                if not voice_total or (
                    voice_index and voice_total and voice_index == voice_total
                ):
                    app.update_progress_state(
                        "subtitle_overlay", "completed", 100, overlay_message
                    )
            except Exception as e:
                ui_controller.write_error_log(e)
                logger.warning("  Subtitle error: %s", str(e))
                overlay_message = "An error occurred while applying subtitles."
                app.update_progress_state(
                    "subtitle_overlay",
                    "error",
                    overlay_progress_base,
                    "An error occurred while applying subtitles.",
                )
        else:
            analysis_message = (
                "Subtitles disabled; skipping audio analysis for captions."
            )
            overlay_message = "Subtitles disabled; skipping burn-in."
            app.update_progress_state(
                "audio_analysis", "completed", 100, analysis_message
            )
            app.update_progress_state(
                "subtitle_overlay", "completed", 100, overlay_message
            )

        # *** Final trim - align to target duration ***
        logger.info("[Video Trim]")
        logger.info("  1.2x TTS length (after padding): %.3fs", real_audio_dur)
        logger.info("  Current video length: %.3fs", final_video.duration)

        final_cut_point = target_video_duration
        logger.info("  Planned final length: %.3fs (audio + buffer)", final_cut_point)

        if final_video.duration > final_cut_point:
            logger.debug(
                "  Trimming: %.3fs -> %.3fs", final_video.duration, final_cut_point
            )
            final_video = final_video.subclip(0, final_cut_point)
        elif final_video.duration + eps < final_cut_point:
            logger.debug(
                "  Video short; adjusting duration: %.3fs -> %.3fs",
                final_video.duration,
                final_cut_point,
            )
            final_video = final_video.set_duration(final_cut_point)

        logger.info("  Final video length: %.3fs", final_video.duration)

        logger.info("  최종 영상 길이: %.3f초", final_video.duration)

        polish_progress = min(100, overlay_progress_base + 5)
        app.update_progress_state(
            "post_tasks",
            "processing",
            polish_progress,
            "영상 마무리 작업으로 싱크를 한번 더 점검 중입니다.",
        )
        if not voice_total or (
            voice_index and voice_total and voice_index == voice_total
        ):
            app.update_progress_state(
                "post_tasks",
                "completed",
                100,
                "잔여 작업 정리 완료! 마무리 단계로 이동합니다.",
            )

        # 파일 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 상품명 추출 (여러 소스에서 시도)
        product_name = _extract_product_name(app)

        # 파일명: 날짜_상품명.mp4
        output_filename = f"{timestamp}_{product_name}.mp4"
        temp_dir = tempfile.mkdtemp(prefix="batch_video_")
        output_path = os.path.join(temp_dir, output_filename)
        app.final_video_temp_dir = temp_dir

        logger.info("[인코딩]")
        logger.info("  임시 파일: %s", output_filename)
        logger.info("  임시 폴더: %s", temp_dir)
        logger.info("  최종 길이: %.3fs", final_video.duration)

        # GPU 인코더 사용 가능 여부 확인
        use_gpu = _check_gpu_encoder_available()

        finalize_progress = min(100, polish_progress + 5)
        if voice_index and voice_total:
            finalize_message = f"[{voice_index}/{voice_total}] {voice_label} - 피날레 렌더링으로 완성본을 출력 중입니다."
        else:
            finalize_message = (
                f"{voice_label} - 피날레 렌더링으로 완성본을 출력 중입니다."
            )
        app.update_progress_state(
            "finalize", "processing", finalize_progress, finalize_message
        )

        final_video = _ensure_even_resolution(final_video)

        # MP4 최대 호환성을 위한 필수 옵션
        # -movflags +faststart: 메타데이터를 파일 앞으로 이동 (재생 호환성 필수)
        # -pix_fmt yuv420p: 대부분의 플레이어 호환
        common_ffmpeg_params = [
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
        ]

        # CPU 인코더용 파라미터 (baseline 프로파일, level 4.2 - 1080p 지원)
        cpu_ffmpeg_params = [
            "-profile:v",
            "baseline",
            "-level",
            "4.2",  # 1920x1080 30fps 지원 (level 3.1은 720p까지만 지원)
            *common_ffmpeg_params,
        ]

        # GPU NVENC용 파라미터 (high 프로파일, 레벨 자동 감지)
        # NVENC는 baseline 프로파일에서 제한이 있어 high 프로파일 사용
        # 레벨은 해상도에 따라 자동 선택되도록 지정하지 않음
        gpu_ffmpeg_params = [
            "-profile:v",
            "high",
            *common_ffmpeg_params,
        ]

        # 임시 오디오 파일 경로 (절대 경로 사용)
        temp_audio_path = os.path.join(temp_dir, "temp-audio.m4a")

        use_gpu = _check_gpu_encoder_available()

        # 실시간 인코딩 진행률 로거 - 'bar' 사용 (안정성)
        # encoding_logger = RealtimeEncodingLogger(app, final_video.duration)
        encoding_logger = None

        encoder_type = "GPU (h264_nvenc)" if use_gpu else "CPU (libx264)"
        app.add_log(f"[인코딩] 영상 렌더링 시작 - {encoder_type}")

        if use_gpu:
            logger.info("  인코더: h264_nvenc (GPU) - high 프로파일, 레벨 자동")
            final_video.write_videofile(
                output_path,
                codec="h264_nvenc",
                audio_codec="aac",
                temp_audiofile=temp_audio_path,
                remove_temp=True,
                fps=int(original_fps) if original_fps else 30,
                threads=4,
                logger=encoding_logger,
                bitrate="8000k",
                ffmpeg_params=[
                    "-preset",
                    "slow",
                    "-cq",
                    "18",
                    "-b:v",
                    "8000k",
                    *gpu_ffmpeg_params,
                ],
            )
        else:
            # CPU 인코더 사용 (fallback)
            logger.info("  인코더: libx264 (CPU) - baseline 프로파일, level 4.2")
            final_video.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                temp_audiofile=temp_audio_path,
                remove_temp=True,
                preset="slow",
                fps=original_fps,
                threads=8,
                logger=encoding_logger,
                bitrate="8000k",
                ffmpeg_params=["-crf", "18", *cpu_ffmpeg_params],
            )

        final_duration = final_video.duration
        file_size = (
            os.path.getsize(output_path) / 1024 / 1024
            if os.path.exists(output_path)
            else 0.0
        )
        app.add_log(f"[인코딩] 렌더링 완료 - {final_duration:.1f}초, {file_size:.1f}MB")
        app.final_video_path = output_path
        if hasattr(app, "register_generated_video"):
            app.register_generated_video(
                voice, output_path, final_duration, file_size, temp_dir
            )
        if voice_index and voice_total:
            render_complete_msg = f"[{voice_index}/{voice_total}] {voice_label} 렌더링 완료! 결과물을 정리하고 있습니다."
        else:
            render_complete_msg = (
                f"{voice_label} 렌더링 완료! 결과물을 정리하고 있습니다."
            )
        app.update_progress_state("finalize", "processing", 100, render_complete_msg)

        if not voice_total or (
            voice_index and voice_total and voice_index == voice_total
        ):
            app.update_progress_state(
                "audio_merge", "completed", 100, "모든 오디오 합본이 마무리되었습니다."
            )
            app.update_progress_state(
                "audio_analysis",
                "completed",
                100,
                analysis_message
                if "analysis_message" in locals()
                else "오디오 분석 완료",
            )
            app.update_progress_state(
                "subtitle_overlay",
                "completed",
                100,
                overlay_message
                if "overlay_message" in locals()
                else "자막 적용 단계를 마쳤습니다.",
            )
            app.update_progress_state(
                "post_tasks",
                "completed",
                100,
                "잔여 작업 정리 완료! 마무리 단계로 이동합니다.",
            )
            app.update_progress_state(
                "finalize",
                "completed",
                100,
                f"{voice_label} 음성 기반 영상이 준비되었습니다{job_suffix}.",
            )

        video.close()
        new_audio.close()
        final_video.close()

        # 파일 핸들 해제 대기 (Windows에서 ffmpeg 프로세스 완전 종료 대기)
        gc.collect()
        time.sleep(0.5)  # Windows에서 파일 핸들 해제에 필요한 대기 시간

        # NTFS 권한 설정: Everyone 읽기 권한 추가 (다른 컴퓨터에서도 열 수 있도록)
        try:
            subprocess.run(
                [
                    "icacls",
                    output_path,
                    "/inheritance:e",
                    "/grant",
                    "*S-1-1-0:(R)",  # Everyone
                    "/grant",
                    "*S-1-5-32-545:(R)",  # Users group
                ],
                check=True,
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=30,
            )
            logger.debug("권한 설정: 읽기 권한 추가 완료")
        except Exception as e:
            ui_controller.write_error_log(e)
            logger.debug("  권한 설정 실패 (무시됨): %s", e)

        # ★ 결합 오디오 파일 보존 (삭제 안함) ★
        # try:
        #     if os.path.exists(combined_audio_path):
        #         os.remove(combined_audio_path)
        # except Exception:
        #     pass
        logger.debug("  오디오 파일 보존: %s", os.path.basename(combined_audio_path))

        logger.info("[완료]")
        if voice_index and voice_total:
            logger.info("  음성: [%d/%d] %s", voice_index, voice_total, voice_label)
        else:
            logger.info("  음성: %s", voice_label)
        logger.info("  임시 파일: %s", output_filename)
        logger.info("  용량: %.1f MB", file_size)
        logger.info("  길이: %.3fs", final_duration)
        original_duration = getattr(app, "original_video_duration", final_duration)
        logger.info("  원본 길이: %.3fs", original_duration)
        logger.info("=" * 60)

    except Exception as e:
        ui_controller.write_error_log(e)
        # 에러 발생 시에도 리소스 정리
        try:
            if "video" in locals() and video is not None:
                video.close()
        except Exception as close_err:
            logger.debug("[정리] video close 실패: %s", str(close_err)[:30])
        try:
            if "new_audio" in locals() and new_audio is not None:
                new_audio.close()
        except Exception as close_err:
            logger.debug("[정리] audio close 실패: %s", str(close_err)[:30])
        try:
            if "final_video" in locals() and final_video is not None:
                final_video.close()
        except Exception as close_err:
            logger.debug("[정리] final_video close 실패: %s", str(close_err)[:30])

        # 임시 디렉토리 정리
        try:
            if "temp_dir" in locals() and temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.debug("[정리] 임시 폴더 삭제: %s", temp_dir)
        except Exception as temp_err:
            logger.debug("[정리] 임시 폴더 삭제 실패: %s", str(temp_err)[:30])

        translated_error = _translate_error_message(str(e))
        logger.error("[오류] 배치 영상 처리 실패: %s", translated_error)
        # traceback 출력 제거 - 한글 메시지만 표시
        raise


def clear_all_previous_results(app):
    """모든 이전 분석 결과 초기화 - 완전한 정리 버전"""
    logger.info("[초기화] 이전 분석 결과를 모두 지웁니다...")

    # 0. 파일 핸들 정리를 위한 가비지 컬렉션
    gc.collect()
    time.sleep(0.1)  # 파일 핸들 해제 대기

    # 1. TTS 파일 보존 (삭제하지 않음)
    # ★ 개별 오디오 파일 유지 - 사용자 요청 ★
    if hasattr(app, "_per_line_tts") and app._per_line_tts:
        kept_count = sum(
            1
            for tts_data in app._per_line_tts
            if isinstance(tts_data, dict)
            and "path" in tts_data
            and tts_data["path"]
            and os.path.exists(tts_data["path"])
        )
        if kept_count > 0:
            logger.debug("[초기화] TTS 파일 %d개 보존됨 (삭제 안함)", kept_count)

    # 2. 세션 디렉토리 유지 (새 세션 디렉토리 생성)
    # 기존 파일은 보존하고 새 세션만 생성
    app.session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:21]
    app.tts_output_dir = os.path.join(app.base_tts_dir, f"session_{app.session_id}")
    os.makedirs(app.tts_output_dir, exist_ok=True)
    logger.info("[초기화] 새 세션 디렉토리 생성: %s", app.tts_output_dir)

    # 3. 오래된 세션 디렉토리 정리 (선택사항)
    try:
        if hasattr(app, "base_tts_dir") and os.path.exists(app.base_tts_dir):
            current_time = datetime.now()
            for session_dir in os.listdir(app.base_tts_dir):
                if session_dir.startswith("session_"):
                    session_path = os.path.join(app.base_tts_dir, session_dir)
                    if session_path != app.tts_output_dir and os.path.isdir(
                        session_path
                    ):
                        dir_time = os.path.getmtime(session_path)
                        if (
                            current_time - datetime.fromtimestamp(dir_time)
                        ).total_seconds() > 3600:
                            try:
                                shutil.rmtree(session_path)
                                logger.debug(
                                    "[초기화] 오래된 세션 삭제: %s", session_dir
                                )
                            except Exception as cleanup_err:
                                logger.debug(
                                    "[초기화] 세션 삭제 실패 (무시됨): %s - %s",
                                    session_dir,
                                    str(cleanup_err)[:50],
                                )
    except Exception as e:
        logger.debug("[초기화] 세션 정리 중 오류 (무시됨): %s", str(e)[:50])

    logger.debug("임시 파일 정리 시작")
    # 4. 임시 파일 정리
    app.cleanup_temp_files()

    # 5. 중요: 임시 다운로드 파일 참조 초기화
    app._temp_downloaded_file = None

    # 6. 분석 결과 데이터 초기화
    app.analysis_result = {}
    app.translation_result = ""
    app.tts_file_path = ""
    app.tts_files = []
    app.final_video_path = ""

    # 7. TTS 관련 변수 완전 초기화
    app.speaker_voice_mapping = {}
    app.last_tts_segments = []
    app._per_line_tts = []
    app.tts_sync_info = {}

    # 7-1. 생성된 영상 기록 초기화
    if hasattr(app, "generated_videos"):
        app.generated_videos = []

    # 8. 진행상황 초기화
    for step in app.progress_states:
        app.progress_states[step] = {
            "status": "waiting",
            "progress": 0,
            "message": None,
        }

    # 9. UI 업데이트는 스레드 안전하게
    if hasattr(app, "root"):
        app.root.after(0, app.update_all_progress_displays)

        # UI 탭들 초기화
        if hasattr(app, "script_text"):
            app.root.after(0, lambda: app.script_text.delete(1.0, tk.END))
            app.root.after(
                0,
                lambda: app.script_text.insert(
                    1.0, "새로운 동영상 분석을 시작합니다..."
                ),
            )

        if hasattr(app, "translation_text"):
            app.root.after(0, lambda: app.translation_text.delete(1.0, tk.END))
            app.root.after(
                0, lambda: app.translation_text.insert(1.0, "한국어 번역 중...")
            )

        if hasattr(app, "tts_result_text"):
            app.root.after(0, lambda: app.tts_result_text.delete(1.0, tk.END))
            app.root.after(
                0, lambda: app.tts_result_text.insert(1.0, "TTS 음성 생성 대기 중...")
            )

        if hasattr(app, "tts_status_label"):
            app.root.after(0, lambda: app.tts_status_label.config(text=""))

    logger.info("[초기화 완료] 새로운 분석을 시작할 준비가 되었습니다.")
