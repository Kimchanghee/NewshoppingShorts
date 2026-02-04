"""
Video Analysis Module for Batch Processing

Contains video analysis and translation functions for batch processing.
"""

import os
import re
import time
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
    """배치??비디??분석 - OCR ?�막 감�? ?�함"""
    try:
        # ?�택??CTA ?�인 가?�오�?        from ui.panels.cta_panel import get_selected_cta_lines
        cta_lines = get_selected_cta_lines(app)

        selected_voice = getattr(app, "fixed_tts_voice", None) or getattr(app, "last_voice_used", None)
        if not selected_voice:
            voice_candidates = getattr(app, "available_tts_voices", None) or getattr(app, "multi_voice_presets", None)
            if voice_candidates:
                selected_voice = voice_candidates[0]
        if not selected_voice:
            selected_voice = "미�???

        voice_label = _get_voice_display_name(selected_voice) if selected_voice != "미�??? else "미�???
        app.add_log("[분석] ?�상 분석???�작?�니??..")
        logger.info("[배치 분석] ?�작")
        logger.info(f"?�용 모델: {config.GEMINI_VIDEO_MODEL}")
        logger.info(f"?�택??TTS ?�성: {voice_label}")

        prompt = get_video_analysis_prompt(cta_lines)

        # 5�??�?�아?�으�?분석 ?�행 (최�? 5???�시??
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
        ANALYSIS_TIMEOUT = 300  # 5�?        MAX_RETRIES = 5

        # 진행 ?�황 ?�시 ?�레??관??변??        analysis_done = threading.Event()
        elapsed_time = [0]  # mutable object for thread

        def progress_indicator():
            while not analysis_done.is_set():
                analysis_done.wait(10)  # 10초마??체크
                if not analysis_done.is_set():
                    elapsed_time[0] += 10
                    app.add_log(f"[분석] AI 분석 진행 �?.. ({elapsed_time[0]}�?경과)")
                    logger.info(f"[배치 분석] 분석 진행 �?.. ({elapsed_time[0]}�?경과)")
                    sys.stdout.flush()

        progress_thread = threading.Thread(target=progress_indicator, daemon=True)
        progress_thread.start()

        def is_gemini_server_error(error_str: str) -> bool:
            """Gemini ?�버 ?�류?��? ?�인 (API ???�류 ?�외)"""
            server_error_keywords = [
                '500', '502', '503', '504',  # HTTP ?�버 ?�류
                'INTERNAL', 'UNAVAILABLE', 'RESOURCE_EXHAUSTED',  # gRPC ?�류
                'ServerError', 'ServiceUnavailable',
                'overloaded', 'capacity', 'temporarily',
                'InternalServerError', 'BadGateway', 'GatewayTimeout',
                'internal error', 'server error',
            ]
            error_lower = error_str.lower()
            # API ??관???�류???�외
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
                logger.debug(f"[배치 분석] 커스텀 다이얼로그 표시 실패, 기본 다이얼로그 사용: {e}")

        def show_server_error_popup():
            """Gemini 서버 오류 팝업 표시"""
            try:
                # UI 스레드에서 팝업 표시 (PyQt6)
                QTimer.singleShot(0, lambda: _show_gemini_server_error_dialog(app))
            except Exception as popup_err:
                logger.warning(f"[배치 분석] 팝업 표시 실패: {popup_err}")

        # ?�재 ?�용 중인 API ??로깅 (api_key_manager�??�선 ?�용)
        api_mgr = getattr(app, "api_key_manager", None) or getattr(app, "api_manager", None)
        current_api_key = getattr(api_mgr, "current_key", "unknown") if api_mgr else "unknown"
        logger.debug(f"[?�상 분석 API] ?�용 중인 API ?? {current_api_key}")

        response = None
        last_error = None
        is_server_error = False
        video_file = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if attempt > 1:
                    app.add_log(f"[분석] API ?�시??{attempt}/{MAX_RETRIES}...")
                logger.info(f"[배치 분석] API ?�출 ?�도 {attempt}/{MAX_RETRIES} (?�?�아?? {ANALYSIS_TIMEOUT}�?")

                # API ?��? 바뀌었거나 �??�도?�면 ?�일 ?�로???�행
                if video_file is None:
                    # ?�일 ?�로??(Gemini가 ?�동?�로 최적 ?�상???�택)
                    app.add_log(f"[분석] ?�상 ?�일 ?�로??�?.. ({os.path.basename(app._temp_downloaded_file)})")
                    logger.info(f"[배치 분석] ?�상 ?�일 ?�로??�?.. ({os.path.basename(app._temp_downloaded_file)})")
                    video_file = app.genai_client.files.upload(file=app._temp_downloaded_file)
                    app.add_log("[분석] ?�로???�료, Gemini ?�버?�서 처리 ?��?�?..")
                    logger.info("[배치 분석] ?�로???�료, ?�일 처리 ?��?�?..")

                    wait_count = 0
                    max_wait_time = 600  # 최�? 10�??��?                    while video_file.state == types.FileState.PROCESSING:
                        time.sleep(2)
                        wait_count += 2
                        if wait_count >= max_wait_time:
                            raise TimeoutError(f"?�일 처리 ?�간 초과 ({max_wait_time}�?")
                        if wait_count % 10 == 0:
                            app.add_log(f"[분석] ?�버 처리 �?.. ({wait_count}�?경과)")
                        video_file = app.genai_client.files.get(name=video_file.name)

                    if video_file.state == types.FileState.FAILED:
                        error_message = getattr(getattr(video_file, "error", None), "message", "")
                        raise RuntimeError(f"?�일 처리 ?�패: {error_message}")
                    
                    app.add_log(f"[분석] ?�버 처리 ?�료 ({wait_count}�??�요)")
                    logger.info(f"[배치 분석] ?�일 처리 ?�료 ({wait_count}�??�요)")

                # 비디???�트 ?�성 (??�� ?�재 video_file 기�?)
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
                        app.add_log("[분석] AI 분석 ?�답 ?�신 ?�료!")
                        logger.info(f"[배치 분석] API ?�출 ?�공 (?�도 {attempt})")
                        break  # ?�공?�면 루프 종료
                    except FuturesTimeoutError:
                        logger.warning(f"[배치 분석] ?�?�아?? {ANALYSIS_TIMEOUT}�?초과 (?�도 {attempt}/{MAX_RETRIES})")
                        last_error = f"분석 ?�?�아??({ANALYSIS_TIMEOUT}�?초과)"
                        is_server_error = True
                        if attempt < MAX_RETRIES:
                            import random
                            wait_time = min(60, 10 * (2 ** (attempt - 1))) + random.uniform(0, 5)
                            time.sleep(wait_time)
                        continue

            except Exception as e:
                last_error = str(e)
                logger.error(f"[배치 분석] API ?�출 ?�패 (?�도 {attempt}): {e}")

                # 429 Quota Exceeded ?�는 403 Permission Denied 처리 (??교체)
                is_quota_error = "429" in str(e) and ("RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower())
                is_permission_error = "403" in str(e) or "PERMISSION_DENIED" in str(e) or "permission denied" in str(e).lower()

                if is_quota_error or is_permission_error:
                    if is_quota_error:
                        logger.warning("[배치 분석] API ???�당??초과(429) 감�?. ??교체�??�도?�니??")
                    else:
                        logger.warning("[배치 분석] API ??권한 ?�류(403) 감�?. ??교체 �??�일 ?�업로드�??�도?�니??")
                    
                    if api_mgr:
                        api_mgr.block_current_key(duration_minutes=60 if is_permission_error else 5)
                        if app.init_client():
                            new_key = getattr(api_mgr, 'current_key', 'unknown')
                            logger.info(f"[배치 분석] API ??교체 ?�료 -> {new_key}. 즉시 ?�시?�합?�다.")
                            video_file = None  # ???�로 ?�업로드 ?�요?��?�?초기??                            continue
                        else:
                            logger.error("[배치 분석] 교체??API ?��? ???�상 ?�습?�다.")
                    else:
                        logger.warning("[배치 분석] API Key Manager가 ?�어 ??교체�??�행?????�습?�다.")

                # Gemini ?�버 ?�류?��? ?�인
                if is_gemini_server_error(last_error):
                    is_server_error = True
                    logger.warning("[배치 분석] Gemini ?�버 ?�류 감�?!")

                if attempt < MAX_RETRIES:
                    wait_time = min(90, 5 * (2 ** (attempt - 1))) if is_server_error else 3
                    import random
                    time.sleep(wait_time + random.uniform(0, 5))
                continue

        # 진행 ?�시 ?�레??종료
        analysis_done.set()
        progress_thread.join(timeout=0.5)

        if response is None:
            # Gemini ?�버 ?�류�??�업 ?�시
            if is_server_error:
                show_server_error_popup()
            raise RuntimeError(f"?�상 분석 ?�패 ({MAX_RETRIES}???�도): {last_error}")

        logger.info(f"[배치 분석] Gemini 분석 ?�료 (�?{elapsed_time[0] + 10}�??�요)")

        # 비용 계산 �?로깅
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            cost_info = app.token_calculator.calculate_cost(
                model=config.GEMINI_VIDEO_MODEL,
                usage_metadata=response.usage_metadata,
                media_type="video"
            )
            app.token_calculator.log_cost("비디??분석", config.GEMINI_VIDEO_MODEL, cost_info)

        result_text = _extract_text_from_response(response)

        # ?�품 ?�명 모드?��? ?�인 (?�국???�명???�성?�었?��?)
        is_product_description = "=== ?�품 ?�명" in result_text or ("?�성???? in result_text and "?�국?? in result_text)

        if is_product_description:
            # ?�품 ?�명 모드: ?�국???�명??직접 ?�용
            logger.info("[배치 분석] ?�품 ?�명 모드 감�? - ?�성 ?��??�음")

            # ?�품 ?�명 추출
            desc_match = re.search(r'===\s*?�품 ?�명[^=]*===\s*(.+)', result_text, re.DOTALL)
            if desc_match:
                product_desc = desc_match.group(1).strip()
            else:
                # ?�체 ?�스?��? ?�품 ?�명?�로 ?�용
                product_desc = result_text.strip()

            # ?�품 ?�명 모드?�서??OCR�??�막 ?�치 감�?
            logger.info("[배치 분석] ?�품 ?�명 모드?�서??OCR ?�막 감�? ?�작...")
            app.update_progress_state('ocr_analysis', 'processing', 10, "중국???�막??찾고 ?�습?�다.")
            subtitle_positions = app.detect_subtitles_with_opencv()
            app.update_progress_state('ocr_analysis', 'completed', 100, "OCR 분석 ?�료!")
            logger.info(f"[배치 분석] OCR ?�막 감�? ?�료: {len(subtitle_positions) if subtitle_positions else 0}�??�역")

            # ?�국???�명??video_analysis_result?� translation_result???�??            app.video_analysis_result = product_desc
            app.translation_result = product_desc
            app.analysis_result = {
                'script': [],  # ?��??�음
                'subtitle_positions': subtitle_positions,
                'raw_subtitle_positions': subtitle_positions  # ?�터�????�본 ?�??            }
            logger.info(f"[배치 분석] ?�품 ?�명 ?�성 ?�료 - {len(product_desc)}??)
            logger.debug(f"[미리보기] {product_desc[:100]}...")
        else:
            # 중국???��?모드: 기존 로직
            script_data = parse_script_from_text(app, result_text)

            # OCR�??�막 ?�치 감�? (추�?)
            logger.info("[배치 분석] OCR ?�막 감�? ?�작 (10-30�??�요)...")
            app.update_progress_state('ocr_analysis', 'processing', 10, "중국???�막??찾고 ?�습?�다.")
            subtitle_positions = app.detect_subtitles_with_opencv()
            app.update_progress_state('ocr_analysis', 'completed', 100, "OCR 분석 ?�료!")
            logger.info(f"[배치 분석] OCR ?�막 감�? ?�료: {len(subtitle_positions) if subtitle_positions else 0}�??�역")

            app.analysis_result = {
                'script': script_data,
                'subtitle_positions': subtitle_positions,
                'raw_subtitle_positions': subtitle_positions  # ?�터�????�본 ?�??            }

            # ???��??�싱 ?�패 ???�본 ?�스?��? fallback?�로 ?�????            if not script_data:
                logger.warning("[배치 분석] ?��??�싱 ?�패 - ?�본 ?�스?��? fallback?�로 ?�용")
                # ?�본 분석 결과?�서 ?�국??중국???�스??추출
                fallback_text = result_text.strip()
                if fallback_text:
                    app.video_analysis_result = fallback_text
                    app.translation_result = fallback_text  # 번역 결과로도 ?�??                    logger.info(f"[배치 분석] Fallback ?�스???�?? {len(fallback_text)}??)
                else:
                    app.video_analysis_result = None
            else:
                app.video_analysis_result = None  # ?��?모드?�서???�용 ?�함

            logger.info(f"[배치 분석] ?�료 - ?��?{len(script_data)}�?)
            if subtitle_positions:
                logger.info(f"[배치 분석] OCR 중국???�막: {len(subtitle_positions)}�??�역")
            else:
                logger.info("[배치 분석] OCR 중국???�막 ?�음")

    except Exception as e:
        ui_controller.write_error_log(e)
        error_text = str(e)
        translated_error = _translate_error_message(error_text)
        logger.error(f"[배치 분석 ?�류] {translated_error}")
        # traceback 출력 ?�거 - ?��? 메시지�??�시
        if "PERMISSION_DENIED" in error_text or "403" in error_text or "권한" in translated_error:
            logger.error("[배치 분석] API ?��? ?�당 Gemini 모델 ?�는 ?�일 ?�로??기능???�용??권한???�는지 ?�인?�세??")
        raise


def _translate_script_for_batch(app):
    """배치??번역 - 기존 translate_script 로직 ?�용"""
    try:
        # ???��? translation_result가 ?�정?�어 ?�으�?(?�품 ?�명 모드 ?�는 fallback) ?�킵 ??        if app.translation_result:
            logger.info(f"[배치 번역] ?��? 번역 결과 ?�음 - ?�킵 ({len(app.translation_result)}??")
            return

        if not app.analysis_result.get('script'):
            logger.info("[배치 번역] ?�본이 ?�어 번역 ?�킵")
            return

        selected_voice = getattr(app, "fixed_tts_voice", None) or getattr(app, "last_voice_used", None)
        if not selected_voice:
            voice_candidates = getattr(app, "available_tts_voices", None) or getattr(app, "multi_voice_presets", None)
            if voice_candidates:
                selected_voice = voice_candidates[0]
        if not selected_voice:
            selected_voice = "미�???

        voice_label = _get_voice_display_name(selected_voice) if selected_voice != "미�??? else "미�???
        app.add_log("[번역] ?��?번역 �?각색???�작?�니??..")
        logger.info("[배치 번역] ?�작")
        logger.info(f"?�용 모델: {config.GEMINI_TEXT_MODEL}")
        logger.info(f"?�택??TTS ?�성: {voice_label}")

        video_duration = app.get_video_duration_helper()
        target_duration = video_duration * config.DAESA_GILI
        target_chars = int(target_duration * 4.2)

        script_lines = []
        original_total_chars = 0

        for line in app.analysis_result['script']:
            timestamp = line.get('timestamp', '00:00')
            speaker = line.get('speaker', '?????�음')
            text = line.get('text', '')
            original_total_chars += len(text)
            script_lines.append(f"[{timestamp}] [{speaker}] {text}")

        script_text = "\n".join(script_lines)

        expansion_ratio = target_chars / original_total_chars if original_total_chars > 0 else 1.0

        # ?�택??CTA ?�인 가?�오�?        from ui.panels.cta_panel import get_selected_cta_lines
        cta_lines = get_selected_cta_lines(app)

        if expansion_ratio >= 0.8:
            length_instruction = "?�본보다 20% ?�상 길게 ?�연?�럽�??��????�현?�로 번역"
        elif expansion_ratio >= 0.6:
            length_instruction = "?�본보다 10-20% 짧게 ?�심 ?�용 ?��??�며 번역"
        else:
            length_instruction = "?�본보다 20% ?�상 짧게 ?�심�?추려??번역"

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
                    app.add_log(f"[번역] API ?�시??{attempt}/{MAX_RETRIES}...")
                
                # ?�재 ?�용 중인 API ??로깅
                api_mgr = getattr(app, 'api_key_manager', None) or getattr(app, 'api_manager', None)
                current_api_key = getattr(api_mgr, 'current_key', 'unknown') if api_mgr else 'unknown'
                logger.debug(f"[번역 API] ?�용 중인 API ??(?�도 {attempt}): {current_api_key}")

                response = app.genai_client.models.generate_content(
                    model=config.GEMINI_TEXT_MODEL,
                    contents=[prompt],
                )
                break # ?�공 ??루프 ?�출
                
            except Exception as e:
                logger.error(f"[배치 번역] API ?�출 ?�패 (?�도 {attempt}): {e}")
                
                # 429 Quota Exceeded 처리 (??교체)
                if "429" in str(e) and ("RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower()):
                    logger.warning("[배치 번역] API ???�당??초과(429) 감�?. ??교체�??�도?�니??")
                    if api_mgr:
                        api_mgr.block_current_key(duration_minutes=60)
                        # ?�라?�언???�초기화 (????로드)
                        if app.init_client():
                            new_key = getattr(api_mgr, 'current_key', 'unknown')
                            logger.info(f"[배치 번역] API ??교체 ?�료 -> {new_key}. 즉시 ?�시?�합?�다.")
                            continue
                        else:
                            logger.error("[배치 번역] 교체??API ?��? ???�상 ?�습?�다.")
                    else:
                        logger.warning("[배치 번역] API Key Manager가 ?�어 ??교체�??�행?????�습?�다.")
                
                if attempt < MAX_RETRIES:
                    time.sleep(2 * attempt)
                else:
                    raise e

        # 비용 계산 �?로깅
        if response and hasattr(response, 'usage_metadata') and response.usage_metadata:
            cost_info = app.token_calculator.calculate_cost(
                model=config.GEMINI_TEXT_MODEL,
                usage_metadata=response.usage_metadata,
                media_type="text"
            )
            app.token_calculator.log_cost("?��?번역 �?각색", config.GEMINI_TEXT_MODEL, cost_info)

        # ?�전?�게 ?�스??추출 (thought_signature 경고 방�?)
        translated_text = _extract_text_from_response(response) if response else ""

        if not translated_text:
            translated_text = script_text
            logger.warning("[배치 번역] 결과가 ?�어 ?�본 ?�크립트�??�용?�니??")

        app.translation_result = translated_text
        app.add_log(f"[번역] 번역 ?�료 - {len(app.translation_result)}??)
        logger.info(f"[배치 번역] ?�료 - {len(app.translation_result)}??)
    except Exception as e:
        ui_controller.write_error_log(e)
        translated_error = _translate_error_message(str(e))
        logger.error(f"[배치 번역 ?�류] {translated_error}")
        # traceback 출력 ?�거 - ?��? 메시지�??�시
        raise

