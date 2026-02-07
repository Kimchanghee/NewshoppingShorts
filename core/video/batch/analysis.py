"""
Video Analysis Module for Batch Processing

Contains video analysis and translation functions for batch processing.
"""

import os
import re
import time
import traceback
import threading
import sys

from PyQt6.QtCore import QTimer
from google.genai import types

from .utils import (
    _get_voice_display_name,
    _extract_text_from_response,
    _translate_error_message,
    parse_script_from_text
)
from caller import ui_controller
from utils.logging_config import get_logger
import config
from prompts import get_video_analysis_prompt, get_translation_prompt

logger = get_logger(__name__)


def _analyze_video_for_batch(app):
    """배치용 비디오 분석 - OCR 자막 감지 포함"""
    try:
        # 선택된 CTA 라인 가져오기
        from ui.panels.cta_panel import get_selected_cta_lines
        cta_lines = get_selected_cta_lines(app)

        selected_voice = getattr(app, "fixed_tts_voice", None) or getattr(app, "last_voice_used", None)
        if not selected_voice:
            voice_candidates = getattr(app, "available_tts_voices", None) or getattr(app, "multi_voice_presets", None)
            if voice_candidates:
                selected_voice = voice_candidates[0]
        if not selected_voice:
            selected_voice = "미지정"

        voice_label = _get_voice_display_name(selected_voice) if selected_voice != "미지정" else "미지정"
        app.add_log("[분석] 영상 분석을 시작합니다...")
        logger.info("[배치 분석] 시작")
        logger.info("  사용 모델: %s", config.GEMINI_VIDEO_MODEL)
        logger.info("  선택된 TTS 음성: %s", voice_label)
        logger.info("  영상 파일: %s", os.path.basename(getattr(app, '_temp_downloaded_file', '') or ''))
        logger.info("  Thinking 레벨: %s", config.GEMINI_THINKING_LEVEL)
        logger.info("  Temperature: %s", config.GEMINI_TEMPERATURE)

        prompt = get_video_analysis_prompt(cta_lines)

        # 5분 타임아웃으로 분석 실행 (최대 5회 재시도)
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
        ANALYSIS_TIMEOUT = 300  # 5분
        MAX_RETRIES = 5

        # 진행 상황 표시 스레드 관련 변수
        analysis_done = threading.Event()
        elapsed_time = [0]  # mutable object for thread

        def progress_indicator():
            while not analysis_done.is_set():
                analysis_done.wait(10)  # 10초마다 체크
                if not analysis_done.is_set():
                    elapsed_time[0] += 10
                    app.add_log(f"[분석] AI 분석 진행 중... ({elapsed_time[0]}초 경과)")
                    logger.info(f"[배치 분석] 분석 진행 중... ({elapsed_time[0]}초 경과)")
                    sys.stdout.flush()

        progress_thread = threading.Thread(target=progress_indicator, daemon=True)
        progress_thread.start()

        def is_gemini_server_error(error_str: str) -> bool:
            """Gemini 서버 오류인지 확인 (API 키 오류 제외)"""
            server_error_keywords = [
                '500', '502', '503', '504',  # HTTP 서버 오류
                'INTERNAL', 'UNAVAILABLE', 'RESOURCE_EXHAUSTED',  # gRPC 오류
                'ServerError', 'ServiceUnavailable',
                'overloaded', 'capacity', 'temporarily',
                'InternalServerError', 'BadGateway', 'GatewayTimeout',
                'internal error', 'server error',
            ]
            error_lower = error_str.lower()
            # API 키 관련 오류는 제외
            api_key_keywords = ['api_key', 'apikey', 'invalid key', 'permission_denied', '401', '403', 'quota']
            if any(kw in error_lower for kw in api_key_keywords):
                return False
            return any(kw.lower() in error_lower for kw in server_error_keywords)

        def _show_gemini_server_error_dialog(app):
            """Gemini 서버 오류 다이얼로그"""
            try:
                from ui.components.custom_dialog import show_warning
                show_warning(
                    app,
                    "Gemini 서버 오류",
                    "Gemini AI 서버에 일시적인 문제가 발생했습니다.\n\n"
                    "잠시 후 다시 시도해주세요.\n"
                    "(보통 1-2분 내에 복구됩니다)"
                )
            except Exception as e:
                logger.debug(f"[배치 분석] 커스텀 다이얼로그 표시 실패: {e}")

        def show_server_error_popup():
            """Gemini 서버 오류 팝업 표시"""
            try:
                # UI 스레드에서 팝업 표시 (PyQt6)
                QTimer.singleShot(0, lambda: _show_gemini_server_error_dialog(app))
            except Exception as popup_err:
                logger.warning(f"[배치 분석] 팝업 표시 실패: {popup_err}")

        # 현재 사용 중인 API 키 로깅 (api_key_manager를 우선 사용)
        api_mgr = getattr(app, "api_key_manager", None) or getattr(app, "api_manager", None)
        current_api_key = getattr(api_mgr, "current_key", "unknown") if api_mgr else "unknown"
        logger.info(f"[영상 분석 API] 사용 중인 API 키: {current_api_key}")
        if api_mgr and hasattr(api_mgr, "get_status"):
            status_text = api_mgr.get_status()
            if status_text:
                for status_line in status_text.split("\n"):
                    logger.info(f"  {status_line}")

        response = None
        last_error = None
        is_server_error = False
        video_file = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if attempt > 1:
                    app.add_log(f"[분석] API 재시도 {attempt}/{MAX_RETRIES}...")
                logger.info(f"[배치 분석] API 호출 시도 {attempt}/{MAX_RETRIES} (타임아웃: {ANALYSIS_TIMEOUT}초)")

                # API 키가 바뀌었거나 첫 시도라면 파일 업로드 수행
                if video_file is None:
                    # 파일 업로드 (Gemini가 자동으로 최적 해상도 선택)
                    app.add_log(f"[분석] 영상 파일 업로드 중... ({os.path.basename(app._temp_downloaded_file)})")
                    logger.info(f"[배치 분석] 영상 파일 업로드 중... ({os.path.basename(app._temp_downloaded_file)})")
                    video_file = app.genai_client.files.upload(file=app._temp_downloaded_file)
                    app.add_log("[분석] 업로드 완료, Gemini 서버에서 처리 대기 중...")
                    logger.info("[배치 분석] 업로드 완료, 파일 처리 대기 중...")

                    wait_count = 0
                    max_wait_time = 600  # 최대 10분 대기
                    while video_file.state == types.FileState.PROCESSING:
                        time.sleep(2)
                        wait_count += 2
                        if wait_count >= max_wait_time:
                            raise TimeoutError(f"파일 처리 시간 초과 ({max_wait_time}초)")
                        if wait_count % 10 == 0:
                            app.add_log(f"[분석] 서버 처리 중... ({wait_count}초 경과)")
                        video_file = app.genai_client.files.get(name=video_file.name)

                    if video_file.state == types.FileState.FAILED:
                        error_message = getattr(getattr(video_file, "error", None), "message", "")
                        raise RuntimeError(f"파일 처리 실패: {error_message}")
                    
                    app.add_log(f"[분석] 서버 처리 완료 ({wait_count}초 소요)")
                    logger.info(f"[배치 분석] 파일 처리 완료 ({wait_count}초 소요)")

                # 비디오 파트 생성 (항상 현재 video_file 기준)
                video_part = types.Part.from_uri(
                    file_uri=video_file.uri,
                    mime_type=video_file.mime_type
                )

                def call_gemini_api_internal():
                    is_gemini_3 = "gemini-3" in config.GEMINI_VIDEO_MODEL.lower()
                    if is_gemini_3:
                        thinking_level = (
                            types.ThinkingLevel.LOW
                            if config.GEMINI_THINKING_LEVEL == "low"
                            else types.ThinkingLevel.HIGH
                        )
                        generation_config = types.GenerateContentConfig(
                            thinking_config=types.ThinkingConfig(thinking_level=thinking_level),
                            temperature=config.GEMINI_TEMPERATURE,
                        )
                    else:
                        thinking_budget = 0 if config.GEMINI_THINKING_LEVEL == "low" else 24576
                        generation_config = types.GenerateContentConfig(
                            thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
                            temperature=config.GEMINI_TEMPERATURE,
                        )

                    return app.genai_client.models.generate_content(
                        model=config.GEMINI_VIDEO_MODEL,
                        contents=[video_part, prompt],
                        config=generation_config,
                    )

                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(call_gemini_api_internal)
                    try:
                        response = future.result(timeout=ANALYSIS_TIMEOUT)
                        app.add_log("[분석] AI 분석 응답 수신 완료!")
                        logger.info(f"[배치 분석] API 호출 성공 (시도 {attempt})")
                        break  # 성공하면 루프 종료
                    except FuturesTimeoutError:
                        logger.warning(f"[배치 분석] 타임아웃! {ANALYSIS_TIMEOUT}초 초과 (시도 {attempt}/{MAX_RETRIES})")
                        last_error = f"분석 타임아웃 ({ANALYSIS_TIMEOUT}초 초과)"
                        is_server_error = True
                        if attempt < MAX_RETRIES:
                            import random
                            wait_time = min(60, 10 * (2 ** (attempt - 1))) + random.uniform(0, 5)
                            time.sleep(wait_time)
                        continue

            except Exception as e:
                last_error = str(e)
                logger.error(f"[배치 분석] API 호출 실패 (시도 {attempt}): {e}")

                # 429 Quota Exceeded 또는 403 Permission Denied 처리 (키 교체)
                is_quota_error = "429" in str(e) and ("RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower())
                is_permission_error = "403" in str(e) or "PERMISSION_DENIED" in str(e) or "permission denied" in str(e).lower()

                if is_quota_error or is_permission_error:
                    blocked_key = getattr(api_mgr, 'current_key', 'unknown') if api_mgr else 'unknown'
                    short_err = str(e)[:80]
                    if is_quota_error:
                        logger.warning(f"[배치 분석] API 키 할당량 초과(429) 감지. 현재 키: {blocked_key}")
                        app.add_log(f"[분석] API 429 할당량 초과 (키: {blocked_key}) - {short_err}")
                    else:
                        logger.warning(f"[배치 분석] API 키 권한 오류(403) 감지. 현재 키: {blocked_key}")
                        app.add_log(f"[분석] API 403 권한 오류 (키: {blocked_key}) - {short_err}")

                    if api_mgr:
                        try:
                            api_mgr.block_current_key(duration_minutes=30)
                        except Exception as block_err:
                            logger.error(f"[배치 분석] 키 차단 실패: {block_err}")
                        try:
                            new_key_value = api_mgr.get_available_key()
                            new_key_name = getattr(api_mgr, 'current_key', 'unknown')
                            if app.init_client(use_specific_key=new_key_value):
                                logger.info(f"[배치 분석] API 키 교체 완료: {blocked_key} -> {new_key_name}")
                                app.add_log(f"[분석] API 키 교체: {blocked_key} -> {new_key_name}")
                                video_file = None  # 새 키로 재업로드 필요하므로 초기화
                                continue
                            else:
                                logger.error(f"[배치 분석] 새 키 {new_key_name} 초기화 실패")
                        except Exception as key_err:
                            logger.error(f"[배치 분석] 교체할 API 키가 없습니다: {key_err}")
                            app.add_log(f"[분석] 사용 가능한 API 키 없음 - {key_err}")
                    else:
                        logger.warning("[배치 분석] API Key Manager가 없어 키 교체를 수행할 수 없습니다.")

                # Gemini 서버 오류인지 확인
                if is_gemini_server_error(last_error):
                    is_server_error = True
                    logger.warning("[배치 분석] Gemini 서버 오류 감지!")

                if attempt < MAX_RETRIES:
                    wait_time = min(90, 5 * (2 ** (attempt - 1))) if is_server_error else 3
                    import random
                    time.sleep(wait_time + random.uniform(0, 5))
                continue

        # 진행 표시 스레드 종료
        analysis_done.set()
        progress_thread.join(timeout=0.5)

        if response is None:
            # Gemini 서버 오류면 팝업 표시
            if is_server_error:
                show_server_error_popup()
            raise RuntimeError(f"영상 분석 실패 ({MAX_RETRIES}회 시도): {last_error}")

        logger.info(f"[배치 분석] Gemini 분석 완료 (총 {elapsed_time[0] + 10}초 소요)")

        # 비용 계산 및 로깅
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            cost_info = app.token_calculator.calculate_cost(
                model=config.GEMINI_VIDEO_MODEL,
                usage_metadata=response.usage_metadata,
                media_type="video"
            )
            app.token_calculator.log_cost("비디오 분석", config.GEMINI_VIDEO_MODEL, cost_info)

        result_text = _extract_text_from_response(response)

        # 상품 설명 모드인지 확인 (한국어 설명이 생성되었는지)
        is_product_description = "=== 상품 설명" in result_text or ("음성이 없" in result_text and "한국어" in result_text)

        if is_product_description:
            # 상품 설명 모드: 한국어 설명을 직접 사용
            logger.info("[배치 분석] 상품 설명 모드 감지 - 음성 대본 없음")

            # 상품 설명 추출
            desc_match = re.search(r'===\s*상품 설명[^=]*===\s*(.+)', result_text, re.DOTALL)
            if desc_match:
                product_desc = desc_match.group(1).strip()
            else:
                # 전체 텍스트를 상품 설명으로 사용
                product_desc = result_text.strip()

            # 상품 설명 모드에서도 OCR로 자막 위치 감지
            logger.info("[배치 분석] 상품 설명 모드에서도 OCR 자막 감지 시작...")
            app.update_progress_state('ocr_analysis', 'processing', 10, "중국어 자막을 찾고 있습니다.")
            subtitle_positions = app.detect_subtitles_with_opencv()
            app.update_progress_state('ocr_analysis', 'completed', 100, "OCR 분석 완료!")
            logger.info(f"[배치 분석] OCR 자막 감지 완료: {len(subtitle_positions) if subtitle_positions else 0}개 영역")

            # 한국어 설명을 video_analysis_result와 translation_result에 저장
            app.video_analysis_result = product_desc
            app.translation_result = product_desc
            app.analysis_result = {
                'script': [],  # 대본 없음
                'subtitle_positions': subtitle_positions,
                'raw_subtitle_positions': subtitle_positions  # 필터링 전 원본 저장
            }
            logger.info(f"[배치 분석] 상품 설명 생성 완료 - {len(product_desc)}자")
            logger.debug(f"[미리보기] {product_desc[:100]}...")
        else:
            # 중국어 대본 모드: 기존 로직
            script_data = parse_script_from_text(app, result_text)

            # OCR로 자막 위치 감지 (추가)
            logger.info("[배치 분석] OCR 자막 감지 시작 (10-30초 소요)...")
            app.update_progress_state('ocr_analysis', 'processing', 10, "중국어 자막을 찾고 있습니다.")
            subtitle_positions = app.detect_subtitles_with_opencv()
            app.update_progress_state('ocr_analysis', 'completed', 100, "OCR 분석 완료!")
            logger.info(f"[배치 분석] OCR 자막 감지 완료: {len(subtitle_positions) if subtitle_positions else 0}개 영역")

            app.analysis_result = {
                'script': script_data,
                'subtitle_positions': subtitle_positions,
                'raw_subtitle_positions': subtitle_positions  # 필터링 전 원본 저장
            }

            # ★ 대본 파싱 실패 시 원본 텍스트를 fallback으로 저장 ★
            if not script_data:
                logger.warning("[배치 분석] 대본 파싱 실패 - 원본 텍스트를 fallback으로 사용")
                # 원본 분석 결과에서 한국어/중국어 텍스트 추출
                fallback_text = result_text.strip()
                if fallback_text:
                    app.video_analysis_result = fallback_text
                    app.translation_result = fallback_text  # 번역 결과로도 저장
                    logger.info(f"[배치 분석] Fallback 텍스트 저장: {len(fallback_text)}자")
                else:
                    app.video_analysis_result = None
            else:
                app.video_analysis_result = None  # 대본 모드에서는 사용 안함

            logger.info(f"[배치 분석] 완료 - 대본 {len(script_data)}개")
            if subtitle_positions:
                logger.info(f"[배치 분석] OCR 중국어 자막: {len(subtitle_positions)}개 영역")
            else:
                logger.info("[배치 분석] OCR 중국어 자막 없음")

    except Exception as e:
        logger.error("[배치 분석 오류 스택트레이스]")
        traceback.print_exc()
        ui_controller.write_error_log(e)
        error_text = str(e)
        translated_error = _translate_error_message(error_text)
        logger.error(f"[배치 분석 오류] {translated_error}")
        if "PERMISSION_DENIED" in error_text or "403" in error_text or "권한" in translated_error:
            logger.error("[배치 분석] API 키가 해당 Gemini 모델 또는 파일 업로드 기능을 사용할 권한이 있는지 확인하세요.")
        raise


def _translate_script_for_batch(app):
    """배치용 번역 - 기존 translate_script 로직 활용"""
    try:
        # ★ 이미 translation_result가 설정되어 있으면 (상품 설명 모드 또는 fallback) 스킵 ★
        if app.translation_result:
            logger.info(f"[배치 번역] 이미 번역 결과 있음 - 스킵 ({len(app.translation_result)}자)")
            return

        if not app.analysis_result.get('script'):
            logger.info("[배치 번역] 대본이 없어 번역 스킵")
            return

        selected_voice = getattr(app, "fixed_tts_voice", None) or getattr(app, "last_voice_used", None)
        if not selected_voice:
            voice_candidates = getattr(app, "available_tts_voices", None) or getattr(app, "multi_voice_presets", None)
            if voice_candidates:
                selected_voice = voice_candidates[0]
        if not selected_voice:
            selected_voice = "미지정"

        voice_label = _get_voice_display_name(selected_voice) if selected_voice != "미지정" else "미지정"
        app.add_log("[번역] 대본 번역 및 각색을 시작합니다...")
        logger.info("[배치 번역] 시작")
        logger.info("  사용 모델: %s", config.GEMINI_TEXT_MODEL)
        logger.info("  선택된 TTS 음성: %s", voice_label)

        video_duration = app.get_video_duration_helper()
        target_duration = video_duration * config.DAESA_GILI
        target_chars = int(target_duration * 4.2)
        logger.info("  영상 길이: %.1f초, 대사 목표: %.1f초 (%d자)", video_duration, target_duration, target_chars)

        script_lines = []
        original_total_chars = 0

        for line in app.analysis_result['script']:
            timestamp = line.get('timestamp', '00:00')
            speaker = line.get('speaker', '알 수 없음')
            text = line.get('text', '')
            original_total_chars += len(text)
            script_lines.append(f"[{timestamp}] [{speaker}] {text}")

        script_text = "\n".join(script_lines)

        expansion_ratio = target_chars / original_total_chars if original_total_chars > 0 else 1.0

        # 선택된 CTA 라인 가져오기
        from ui.panels.cta_panel import get_selected_cta_lines
        cta_lines = get_selected_cta_lines(app)

        if expansion_ratio >= 0.8:
            length_instruction = "원본보다 20% 이상 길게 자연스럽고 풍부한 표현으로 번역"
        elif expansion_ratio >= 0.6:
            length_instruction = "원본보다 10-20% 짧게 핵심 내용 유지하며 번역"
        else:
            length_instruction = "원본보다 20% 이상 짧게 핵심만 추려서 번역"

        prompt = get_translation_prompt(
            script_text=script_text,
            video_duration=video_duration,
            target_duration=target_duration,
            target_chars=target_chars,
            length_instruction=length_instruction,
            cta_lines=cta_lines
        )

        MAX_RETRIES = 3
        response = None
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if attempt > 1:
                    app.add_log(f"[번역] API 재시도 {attempt}/{MAX_RETRIES}...")
                
                # 현재 사용 중인 API 키 로깅
                api_mgr = getattr(app, 'api_key_manager', None) or getattr(app, 'api_manager', None)
                current_api_key = getattr(api_mgr, 'current_key', 'unknown') if api_mgr else 'unknown'
                logger.debug(f"[번역 API] 사용 중인 API 키 (시도 {attempt}): {current_api_key}")

                response = app.genai_client.models.generate_content(
                    model=config.GEMINI_TEXT_MODEL,
                    contents=[prompt],
                )
                break # 성공 시 루프 탈출
                
            except Exception as e:
                logger.error(f"[배치 번역] API 호출 실패 (시도 {attempt}): {e}")
                
                # 429 Quota Exceeded 처리 (키 교체)
                if "429" in str(e) and ("RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower()):
                    blocked_key = getattr(api_mgr, 'current_key', 'unknown') if api_mgr else 'unknown'
                    logger.warning(f"[배치 번역] API 키 할당량 초과(429) 감지. 현재 키: {blocked_key}")
                    if api_mgr:
                        api_mgr.block_current_key(duration_minutes=30)
                        try:
                            new_key_value = api_mgr.get_available_key()
                            new_key_name = getattr(api_mgr, 'current_key', 'unknown')
                            if app.init_client(use_specific_key=new_key_value):
                                logger.info(f"[배치 번역] API 키 교체 완료: {blocked_key} -> {new_key_name}")
                                app.add_log(f"[번역] API 키 교체: {blocked_key} -> {new_key_name}")
                                continue
                            else:
                                logger.error(f"[배치 번역] 새 키 {new_key_name} 초기화 실패")
                        except Exception as key_err:
                            logger.error(f"[배치 번역] 교체할 API 키가 없습니다: {key_err}")
                    else:
                        logger.warning("[배치 번역] API Key Manager가 없어 키 교체를 수행할 수 없습니다.")
                
                if attempt < MAX_RETRIES:
                    time.sleep(2 * attempt)
                else:
                    raise e

        # 비용 계산 및 로깅
        if response and hasattr(response, 'usage_metadata') and response.usage_metadata:
            cost_info = app.token_calculator.calculate_cost(
                model=config.GEMINI_TEXT_MODEL,
                usage_metadata=response.usage_metadata,
                media_type="text"
            )
            app.token_calculator.log_cost("대본 번역 및 각색", config.GEMINI_TEXT_MODEL, cost_info)

        # 안전하게 텍스트 추출 (thought_signature 경고 방지)
        translated_text = _extract_text_from_response(response) if response else ""

        if not translated_text:
            translated_text = script_text
            logger.warning("[배치 번역] 결과가 없어 원본 스크립트를 사용합니다.")

        app.translation_result = translated_text
        app.add_log(f"[번역] 번역 완료 - {len(app.translation_result)}자")
        logger.info("[배치 번역] 완료 - %d자", len(app.translation_result))
        if translated_text:
            preview = translated_text[:120].replace('\n', ' ')
            logger.info("  번역 미리보기: %s...", preview)
    except Exception as e:
        ui_controller.write_error_log(e)
        translated_error = _translate_error_message(str(e))
        logger.error(f"[배치 번역 오류] {translated_error}")
        # traceback 출력 제거 - 한글 메시지만 표시
        raise
