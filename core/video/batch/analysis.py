"""
Video Analysis Module for Batch Processing

Contains video analysis and translation functions for batch processing.
"""

import os
import re
import time
import threading
import sys

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
        logger.info(f"사용 모델: {config.GEMINI_VIDEO_MODEL}")
        logger.info(f"선택된 TTS 음성: {voice_label}")

        prompt = get_video_analysis_prompt(cta_lines)

        # 파일 업로드 (Gemini가 자동으로 최적 해상도 선택)
        app.add_log(f"[분석] 영상 파일 업로드 중... ({os.path.basename(app._temp_downloaded_file)})")
        logger.info(f"[배치 분석] 영상 파일 업로드 중... ({os.path.basename(app._temp_downloaded_file)})")
        video_file = app.genai_client.files.upload(file=app._temp_downloaded_file)
        app.add_log("[분석] 업로드 완료, Gemini 서버에서 처리 대기 중...")
        logger.info("[배치 분석] 업로드 완료, 파일 처리 대기 중...")

        wait_count = 0
        max_wait_time = 600  # 최대 10분 대기 (타임아웃)
        while video_file.state == types.FileState.PROCESSING:
            time.sleep(2)
            wait_count += 2
            if wait_count >= max_wait_time:
                raise TimeoutError(f"파일 처리 시간 초과 ({max_wait_time}초). 네트워크 상태를 확인하세요.")
            if wait_count % 10 == 0:  # 10초마다 로그 출력
                app.add_log(f"[분석] 서버 처리 중... ({wait_count}초 경과)")
                logger.info(f"[배치 분석] 파일 처리 중... ({wait_count}초 경과)")
            video_file = app.genai_client.files.get(name=video_file.name)

        app.add_log(f"[분석] 서버 처리 완료 ({wait_count}초 소요)")
        logger.info(f"[배치 분석] 파일 처리 완료 ({wait_count}초 소요)")

        if video_file.state == types.FileState.FAILED:
            error_message = getattr(getattr(video_file, "error", None), "message", "")
            raise RuntimeError(f"파일 처리 실패: {error_message}")

        if not video_file.uri or not video_file.mime_type:
            raise RuntimeError("업로드된 비디오 정보에 URI 또는 MIME 타입이 없습니다.")

        # 비디오 파트 생성
        video_part = types.Part.from_uri(
            file_uri=video_file.uri,
            mime_type=video_file.mime_type
        )

        # API 호출 전 로그
        app.add_log("[분석] Gemini AI로 영상 분석 요청 중...")
        app.add_log(f"[분석] 영상 길이: {app.get_video_duration_helper():.1f}초")
        app.add_log("[분석] AI 분석에는 30초~2분 정도 소요됩니다...")
        logger.info("[배치 분석] Gemini API로 영상 분석 요청 중...")
        logger.info(f"[배치 분석] 영상 길이: {app.get_video_duration_helper():.1f}초")
        logger.info("[배치 분석] 분석에는 30초~2분 정도 소요될 수 있습니다. 잠시만 기다려주세요...")

        # 진행 상황 표시 스레드
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

        # 현재 사용 중인 API 키 로깅 (api_key_manager를 우선 사용)
        api_mgr = getattr(app, "api_key_manager", None) or getattr(app, "api_manager", None)
        current_api_key = getattr(api_mgr, "current_key", "unknown") if api_mgr else "unknown"
        logger.debug(f"[영상 분석 API] 사용 중인 API 키: {current_api_key}")

        # 5분 타임아웃으로 분석 실행 (최대 5회 재시도)
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
        ANALYSIS_TIMEOUT = 300  # 5분
        MAX_RETRIES = 5

        def call_gemini_api():
            # Gemini 3 모델: thinking_level 사용 (LOW = 빠름, HIGH = 느림)
            # Gemini 2.5 모델: thinking_budget 사용 (0 = 끔, 24576 = 최대)
            is_gemini_3 = "gemini-3" in config.GEMINI_VIDEO_MODEL.lower()

            if is_gemini_3:
                thinking_level = (
                    types.ThinkingLevel.LOW
                    if config.GEMINI_THINKING_LEVEL == "low"
                    else types.ThinkingLevel.HIGH
                )
                generation_config = types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(
                        thinking_level=thinking_level
                    ),
                    temperature=config.GEMINI_TEMPERATURE,
                )
            else:
                # Gemini 2.5 이하 모델
                thinking_budget = 0 if config.GEMINI_THINKING_LEVEL == "low" else 24576
                generation_config = types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=thinking_budget
                    ),
                    temperature=config.GEMINI_TEMPERATURE,
                )

            return app.genai_client.models.generate_content(
                model=config.GEMINI_VIDEO_MODEL,
                contents=[
                    video_part,
                    prompt,
                ],
                config=generation_config,
            )

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

        def show_server_error_popup():
            """Gemini 서버 오류 팝업 표시"""
            try:
                # UI 스레드에서 팝업 표시
                if hasattr(app, 'root') and app.root:
                    app.root.after(0, lambda: _show_gemini_server_error_dialog(app))
                else:
                    logger.warning("[배치 분석] Gemini 서버 오류 - 잠시 후 다시 시도해주세요")
            except Exception as popup_err:
                logger.warning(f"[배치 분석] 팝업 표시 실패: {popup_err}")

        def _show_gemini_server_error_dialog(app):
            """Gemini 서버 오류 다이얼로그"""
            try:
                from ui.components.custom_dialog import show_warning
                show_warning(
                    app.root,
                    "Gemini 서버 오류",
                    "Gemini AI 서버에 일시적인 문제가 발생했습니다.\n\n"
                    "잠시 후 다시 시도해주세요.\n"
                    "(보통 1-2분 내에 복구됩니다)"
                )
            except Exception as e:
                logger.debug(f"[배치 분석] 커스텀 다이얼로그 표시 실패, 기본 다이얼로그 사용: {e}")
                import tkinter.messagebox as msgbox
                msgbox.showwarning(
                    "Gemini 서버 오류",
                    "Gemini AI 서버에 일시적인 문제가 발생했습니다.\n\n"
                    "잠시 후 다시 시도해주세요."
                )

        response = None
        last_error = None
        is_server_error = False

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if attempt > 1:
                    app.add_log(f"[분석] API 재시도 {attempt}/{MAX_RETRIES}...")
                logger.info(f"[배치 분석] API 호출 시도 {attempt}/{MAX_RETRIES} (타임아웃: {ANALYSIS_TIMEOUT}초)")

                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(call_gemini_api)
                    try:
                        response = future.result(timeout=ANALYSIS_TIMEOUT)
                        app.add_log("[분석] AI 분석 응답 수신 완료!")
                        logger.info(f"[배치 분석] API 호출 성공 (시도 {attempt})")
                        break  # 성공하면 루프 종료
                    except FuturesTimeoutError:
                        logger.warning(f"[배치 분석] 타임아웃! {ANALYSIS_TIMEOUT}초 초과 (시도 {attempt}/{MAX_RETRIES})")
                        last_error = f"분석 타임아웃 ({ANALYSIS_TIMEOUT}초 초과)"
                        is_server_error = True  # 타임아웃도 서버 문제로 간주
                        if attempt < MAX_RETRIES:
                            # 타임아웃도 지수 백오프 적용
                            import random
                            wait_time = min(60, 10 * (2 ** (attempt - 1))) + random.uniform(0, 5)
                            logger.info(f"[배치 분석] {int(wait_time)}초 후 재시도합니다...")
                            time.sleep(wait_time)
                            elapsed_time[0] = 0
                        continue

            except Exception as e:
                last_error = str(e)
                logger.error(f"[배치 분석] API 호출 실패 (시도 {attempt}): {e}")

                # Gemini 서버 오류인지 확인
                if is_gemini_server_error(last_error):
                    is_server_error = True
                    logger.warning("[배치 분석] Gemini 서버 오류 감지!")

                if attempt < MAX_RETRIES:
                    # 지수 백오프: 서버 오류일 때 점점 더 오래 대기 (5, 15, 30, 60, 90초)
                    if is_server_error:
                        base_wait = 5
                        wait_time = min(90, base_wait * (2 ** (attempt - 1)))  # 지수 증가, 최대 90초
                        # 약간의 랜덤 지터 추가 (0~5초)
                        import random
                        jitter = random.uniform(0, 5)
                        wait_time = int(wait_time + jitter)
                    else:
                        wait_time = 3
                    logger.info(f"[배치 분석] {wait_time}초 후 재시도합니다... (시도 {attempt + 1}/{MAX_RETRIES})")
                    time.sleep(wait_time)
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
        ui_controller.write_error_log(e)
        error_text = str(e)
        translated_error = _translate_error_message(error_text)
        logger.error(f"[배치 분석 오류] {translated_error}")
        # traceback 출력 제거 - 한글 메시지만 표시
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
        logger.info(f"사용 모델: {config.GEMINI_TEXT_MODEL}")
        logger.info(f"선택된 TTS 음성: {voice_label}")

        video_duration = app.get_video_duration_helper()
        target_duration = video_duration * config.DAESA_GILI
        target_chars = int(target_duration * 4.2)

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

        # 현재 사용 중인 API 키 로깅
        api_mgr = getattr(app, 'api_key_manager', None) or getattr(app, 'api_manager', None)
        current_api_key = getattr(api_mgr, 'current_key', 'unknown') if api_mgr else 'unknown'
        logger.debug(f"[번역 API] 사용 중인 API 키: {current_api_key}")

        response = app.genai_client.models.generate_content(
            model=config.GEMINI_TEXT_MODEL,
            contents=[prompt],
        )

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
        logger.info(f"[배치 번역] 완료 - {len(app.translation_result)}자")
    except Exception as e:
        ui_controller.write_error_log(e)
        translated_error = _translate_error_message(str(e))
        logger.error(f"[배치 번역 오류] {translated_error}")
        # traceback 출력 제거 - 한글 메시지만 표시
        raise
