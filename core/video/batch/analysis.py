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
    """ë°°ì¹˜??ë¹„ë””??ë¶„ì„ - OCR ?ë§‰ ê°ì? ?¬í•¨"""
    try:
        # ? íƒ??CTA ?¼ì¸ ê°€?¸ì˜¤ê¸?        from ui.panels.cta_panel import get_selected_cta_lines
        cta_lines = get_selected_cta_lines(app)

        selected_voice = getattr(app, "fixed_tts_voice", None) or getattr(app, "last_voice_used", None)
        if not selected_voice:
            voice_candidates = getattr(app, "available_tts_voices", None) or getattr(app, "multi_voice_presets", None)
            if voice_candidates:
                selected_voice = voice_candidates[0]
        if not selected_voice:
            selected_voice = "ë¯¸ì???

        voice_label = _get_voice_display_name(selected_voice) if selected_voice != "ë¯¸ì??? else "ë¯¸ì???
        app.add_log("[ë¶„ì„] ?ìƒ ë¶„ì„???œì‘?©ë‹ˆ??..")
        logger.info("[ë°°ì¹˜ ë¶„ì„] ?œì‘")
        logger.info(f"?¬ìš© ëª¨ë¸: {config.GEMINI_VIDEO_MODEL}")
        logger.info(f"? íƒ??TTS ?Œì„±: {voice_label}")

        prompt = get_video_analysis_prompt(cta_lines)

        # 5ë¶??€?„ì•„?ƒìœ¼ë¡?ë¶„ì„ ?¤í–‰ (ìµœë? 5???¬ì‹œ??
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
        ANALYSIS_TIMEOUT = 300  # 5ë¶?        MAX_RETRIES = 5

        # ì§„í–‰ ?í™© ?œì‹œ ?¤ë ˆ??ê´€??ë³€??        analysis_done = threading.Event()
        elapsed_time = [0]  # mutable object for thread

        def progress_indicator():
            while not analysis_done.is_set():
                analysis_done.wait(10)  # 10ì´ˆë§ˆ??ì²´í¬
                if not analysis_done.is_set():
                    elapsed_time[0] += 10
                    app.add_log(f"[ë¶„ì„] AI ë¶„ì„ ì§„í–‰ ì¤?.. ({elapsed_time[0]}ì´?ê²½ê³¼)")
                    logger.info(f"[ë°°ì¹˜ ë¶„ì„] ë¶„ì„ ì§„í–‰ ì¤?.. ({elapsed_time[0]}ì´?ê²½ê³¼)")
                    sys.stdout.flush()

        progress_thread = threading.Thread(target=progress_indicator, daemon=True)
        progress_thread.start()

        def is_gemini_server_error(error_str: str) -> bool:
            """Gemini ?œë²„ ?¤ë¥˜?¸ì? ?•ì¸ (API ???¤ë¥˜ ?œì™¸)"""
            server_error_keywords = [
                '500', '502', '503', '504',  # HTTP ?œë²„ ?¤ë¥˜
                'INTERNAL', 'UNAVAILABLE', 'RESOURCE_EXHAUSTED',  # gRPC ?¤ë¥˜
                'ServerError', 'ServiceUnavailable',
                'overloaded', 'capacity', 'temporarily',
                'InternalServerError', 'BadGateway', 'GatewayTimeout',
                'internal error', 'server error',
            ]
            error_lower = error_str.lower()
            # API ??ê´€???¤ë¥˜???œì™¸
            api_key_keywords = ['api_key', 'apikey', 'invalid key', 'permission_denied', '401', '403', 'quota']
            if any(kw in error_lower for kw in api_key_keywords):
                return False
            return any(kw.lower() in error_lower for kw in server_error_keywords)

        def _show_gemini_server_error_dialog(app):
            """Gemini ?œë²„ ?¤ë¥˜ ?¤ì´?¼ë¡œê·?""
            try:
                from ui.components.custom_dialog import show_warning
                show_warning(
                    app.root,
                    "Gemini ?œë²„ ?¤ë¥˜",
                    "Gemini AI ?œë²„???¼ì‹œ?ì¸ ë¬¸ì œê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤.\n\n"
                    "? ì‹œ ???¤ì‹œ ?œë„?´ì£¼?¸ìš”.\n"
                    "(ë³´í†µ 1-2ë¶??´ì— ë³µêµ¬?©ë‹ˆ??"
                )
            except Exception as e:
                logger.debug(f"[ë°°ì¹˜ ë¶„ì„] ì»¤ìŠ¤?€ ?¤ì´?¼ë¡œê·??œì‹œ ?¤íŒ¨, ê¸°ë³¸ ?¤ì´?¼ë¡œê·??¬ìš©: {e}")
                
        def show_server_error_popup():
            """Gemini ?œë²„ ?¤ë¥˜ ?ì—… ?œì‹œ"""
            try:
                # UI ?¤ë ˆ?œì—???ì—… ?œì‹œ
                if hasattr(app, 'root') and app.root:
                    app.root.after(0, lambda: _show_gemini_server_error_dialog(app))
                else:
                    logger.warning("[ë°°ì¹˜ ë¶„ì„] Gemini ?œë²„ ?¤ë¥˜ - ? ì‹œ ???¤ì‹œ ?œë„?´ì£¼?¸ìš”")
            except Exception as popup_err:
                logger.warning(f"[ë°°ì¹˜ ë¶„ì„] ?ì—… ?œì‹œ ?¤íŒ¨: {popup_err}")

        # ?„ì¬ ?¬ìš© ì¤‘ì¸ API ??ë¡œê¹… (api_key_managerë¥??°ì„  ?¬ìš©)
        api_mgr = getattr(app, "api_key_manager", None) or getattr(app, "api_manager", None)
        current_api_key = getattr(api_mgr, "current_key", "unknown") if api_mgr else "unknown"
        logger.debug(f"[?ìƒ ë¶„ì„ API] ?¬ìš© ì¤‘ì¸ API ?? {current_api_key}")

        response = None
        last_error = None
        is_server_error = False
        video_file = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if attempt > 1:
                    app.add_log(f"[ë¶„ì„] API ?¬ì‹œ??{attempt}/{MAX_RETRIES}...")
                logger.info(f"[ë°°ì¹˜ ë¶„ì„] API ?¸ì¶œ ?œë„ {attempt}/{MAX_RETRIES} (?€?„ì•„?? {ANALYSIS_TIMEOUT}ì´?")

                # API ?¤ê? ë°”ë€Œì—ˆê±°ë‚˜ ì²??œë„?¼ë©´ ?Œì¼ ?…ë¡œ???˜í–‰
                if video_file is None:
                    # ?Œì¼ ?…ë¡œ??(Geminiê°€ ?ë™?¼ë¡œ ìµœì  ?´ìƒ??? íƒ)
                    app.add_log(f"[ë¶„ì„] ?ìƒ ?Œì¼ ?…ë¡œ??ì¤?.. ({os.path.basename(app._temp_downloaded_file)})")
                    logger.info(f"[ë°°ì¹˜ ë¶„ì„] ?ìƒ ?Œì¼ ?…ë¡œ??ì¤?.. ({os.path.basename(app._temp_downloaded_file)})")
                    video_file = app.genai_client.files.upload(file=app._temp_downloaded_file)
                    app.add_log("[ë¶„ì„] ?…ë¡œ???„ë£Œ, Gemini ?œë²„?ì„œ ì²˜ë¦¬ ?€ê¸?ì¤?..")
                    logger.info("[ë°°ì¹˜ ë¶„ì„] ?…ë¡œ???„ë£Œ, ?Œì¼ ì²˜ë¦¬ ?€ê¸?ì¤?..")

                    wait_count = 0
                    max_wait_time = 600  # ìµœë? 10ë¶??€ê¸?                    while video_file.state == types.FileState.PROCESSING:
                        time.sleep(2)
                        wait_count += 2
                        if wait_count >= max_wait_time:
                            raise TimeoutError(f"?Œì¼ ì²˜ë¦¬ ?œê°„ ì´ˆê³¼ ({max_wait_time}ì´?")
                        if wait_count % 10 == 0:
                            app.add_log(f"[ë¶„ì„] ?œë²„ ì²˜ë¦¬ ì¤?.. ({wait_count}ì´?ê²½ê³¼)")
                        video_file = app.genai_client.files.get(name=video_file.name)

                    if video_file.state == types.FileState.FAILED:
                        error_message = getattr(getattr(video_file, "error", None), "message", "")
                        raise RuntimeError(f"?Œì¼ ì²˜ë¦¬ ?¤íŒ¨: {error_message}")
                    
                    app.add_log(f"[ë¶„ì„] ?œë²„ ì²˜ë¦¬ ?„ë£Œ ({wait_count}ì´??Œìš”)")
                    logger.info(f"[ë°°ì¹˜ ë¶„ì„] ?Œì¼ ì²˜ë¦¬ ?„ë£Œ ({wait_count}ì´??Œìš”)")

                # ë¹„ë””???ŒíŠ¸ ?ì„± (??ƒ ?„ì¬ video_file ê¸°ì?)
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
                        app.add_log("[ë¶„ì„] AI ë¶„ì„ ?‘ë‹µ ?˜ì‹  ?„ë£Œ!")
                        logger.info(f"[ë°°ì¹˜ ë¶„ì„] API ?¸ì¶œ ?±ê³µ (?œë„ {attempt})")
                        break  # ?±ê³µ?˜ë©´ ë£¨í”„ ì¢…ë£Œ
                    except FuturesTimeoutError:
                        logger.warning(f"[ë°°ì¹˜ ë¶„ì„] ?€?„ì•„?? {ANALYSIS_TIMEOUT}ì´?ì´ˆê³¼ (?œë„ {attempt}/{MAX_RETRIES})")
                        last_error = f"ë¶„ì„ ?€?„ì•„??({ANALYSIS_TIMEOUT}ì´?ì´ˆê³¼)"
                        is_server_error = True
                        if attempt < MAX_RETRIES:
                            import random
                            wait_time = min(60, 10 * (2 ** (attempt - 1))) + random.uniform(0, 5)
                            time.sleep(wait_time)
                        continue

            except Exception as e:
                last_error = str(e)
                logger.error(f"[ë°°ì¹˜ ë¶„ì„] API ?¸ì¶œ ?¤íŒ¨ (?œë„ {attempt}): {e}")

                # 429 Quota Exceeded ?ëŠ” 403 Permission Denied ì²˜ë¦¬ (??êµì²´)
                is_quota_error = "429" in str(e) and ("RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower())
                is_permission_error = "403" in str(e) or "PERMISSION_DENIED" in str(e) or "permission denied" in str(e).lower()

                if is_quota_error or is_permission_error:
                    if is_quota_error:
                        logger.warning("[ë°°ì¹˜ ë¶„ì„] API ??? ë‹¹??ì´ˆê³¼(429) ê°ì?. ??êµì²´ë¥??œë„?©ë‹ˆ??")
                    else:
                        logger.warning("[ë°°ì¹˜ ë¶„ì„] API ??ê¶Œí•œ ?¤ë¥˜(403) ê°ì?. ??êµì²´ ë°??Œì¼ ?¬ì—…ë¡œë“œë¥??œë„?©ë‹ˆ??")
                    
                    if api_mgr:
                        api_mgr.block_current_key(duration_minutes=60 if is_permission_error else 5)
                        if app.init_client():
                            new_key = getattr(api_mgr, 'current_key', 'unknown')
                            logger.info(f"[ë°°ì¹˜ ë¶„ì„] API ??êµì²´ ?„ë£Œ -> {new_key}. ì¦‰ì‹œ ?¬ì‹œ?„í•©?ˆë‹¤.")
                            video_file = None  # ???¤ë¡œ ?¬ì—…ë¡œë“œ ?„ìš”?˜ë?ë¡?ì´ˆê¸°??                            continue
                        else:
                            logger.error("[ë°°ì¹˜ ë¶„ì„] êµì²´??API ?¤ê? ???´ìƒ ?†ìŠµ?ˆë‹¤.")
                    else:
                        logger.warning("[ë°°ì¹˜ ë¶„ì„] API Key Managerê°€ ?†ì–´ ??êµì²´ë¥??˜í–‰?????†ìŠµ?ˆë‹¤.")

                # Gemini ?œë²„ ?¤ë¥˜?¸ì? ?•ì¸
                if is_gemini_server_error(last_error):
                    is_server_error = True
                    logger.warning("[ë°°ì¹˜ ë¶„ì„] Gemini ?œë²„ ?¤ë¥˜ ê°ì?!")

                if attempt < MAX_RETRIES:
                    wait_time = min(90, 5 * (2 ** (attempt - 1))) if is_server_error else 3
                    import random
                    time.sleep(wait_time + random.uniform(0, 5))
                continue

        # ì§„í–‰ ?œì‹œ ?¤ë ˆ??ì¢…ë£Œ
        analysis_done.set()
        progress_thread.join(timeout=0.5)

        if response is None:
            # Gemini ?œë²„ ?¤ë¥˜ë©??ì—… ?œì‹œ
            if is_server_error:
                show_server_error_popup()
            raise RuntimeError(f"?ìƒ ë¶„ì„ ?¤íŒ¨ ({MAX_RETRIES}???œë„): {last_error}")

        logger.info(f"[ë°°ì¹˜ ë¶„ì„] Gemini ë¶„ì„ ?„ë£Œ (ì´?{elapsed_time[0] + 10}ì´??Œìš”)")

        # ë¹„ìš© ê³„ì‚° ë°?ë¡œê¹…
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            cost_info = app.token_calculator.calculate_cost(
                model=config.GEMINI_VIDEO_MODEL,
                usage_metadata=response.usage_metadata,
                media_type="video"
            )
            app.token_calculator.log_cost("ë¹„ë””??ë¶„ì„", config.GEMINI_VIDEO_MODEL, cost_info)

        result_text = _extract_text_from_response(response)

        # ?í’ˆ ?¤ëª… ëª¨ë“œ?¸ì? ?•ì¸ (?œêµ­???¤ëª…???ì„±?˜ì—ˆ?”ì?)
        is_product_description = "=== ?í’ˆ ?¤ëª…" in result_text or ("?Œì„±???? in result_text and "?œêµ­?? in result_text)

        if is_product_description:
            # ?í’ˆ ?¤ëª… ëª¨ë“œ: ?œêµ­???¤ëª…??ì§ì ‘ ?¬ìš©
            logger.info("[ë°°ì¹˜ ë¶„ì„] ?í’ˆ ?¤ëª… ëª¨ë“œ ê°ì? - ?Œì„± ?€ë³??†ìŒ")

            # ?í’ˆ ?¤ëª… ì¶”ì¶œ
            desc_match = re.search(r'===\s*?í’ˆ ?¤ëª…[^=]*===\s*(.+)', result_text, re.DOTALL)
            if desc_match:
                product_desc = desc_match.group(1).strip()
            else:
                # ?„ì²´ ?ìŠ¤?¸ë? ?í’ˆ ?¤ëª…?¼ë¡œ ?¬ìš©
                product_desc = result_text.strip()

            # ?í’ˆ ?¤ëª… ëª¨ë“œ?ì„œ??OCRë¡??ë§‰ ?„ì¹˜ ê°ì?
            logger.info("[ë°°ì¹˜ ë¶„ì„] ?í’ˆ ?¤ëª… ëª¨ë“œ?ì„œ??OCR ?ë§‰ ê°ì? ?œì‘...")
            app.update_progress_state('ocr_analysis', 'processing', 10, "ì¤‘êµ­???ë§‰??ì°¾ê³  ?ˆìŠµ?ˆë‹¤.")
            subtitle_positions = app.detect_subtitles_with_opencv()
            app.update_progress_state('ocr_analysis', 'completed', 100, "OCR ë¶„ì„ ?„ë£Œ!")
            logger.info(f"[ë°°ì¹˜ ë¶„ì„] OCR ?ë§‰ ê°ì? ?„ë£Œ: {len(subtitle_positions) if subtitle_positions else 0}ê°??ì—­")

            # ?œêµ­???¤ëª…??video_analysis_result?€ translation_result???€??            app.video_analysis_result = product_desc
            app.translation_result = product_desc
            app.analysis_result = {
                'script': [],  # ?€ë³??†ìŒ
                'subtitle_positions': subtitle_positions,
                'raw_subtitle_positions': subtitle_positions  # ?„í„°ë§????ë³¸ ?€??            }
            logger.info(f"[ë°°ì¹˜ ë¶„ì„] ?í’ˆ ?¤ëª… ?ì„± ?„ë£Œ - {len(product_desc)}??)
            logger.debug(f"[ë¯¸ë¦¬ë³´ê¸°] {product_desc[:100]}...")
        else:
            # ì¤‘êµ­???€ë³?ëª¨ë“œ: ê¸°ì¡´ ë¡œì§
            script_data = parse_script_from_text(app, result_text)

            # OCRë¡??ë§‰ ?„ì¹˜ ê°ì? (ì¶”ê?)
            logger.info("[ë°°ì¹˜ ë¶„ì„] OCR ?ë§‰ ê°ì? ?œì‘ (10-30ì´??Œìš”)...")
            app.update_progress_state('ocr_analysis', 'processing', 10, "ì¤‘êµ­???ë§‰??ì°¾ê³  ?ˆìŠµ?ˆë‹¤.")
            subtitle_positions = app.detect_subtitles_with_opencv()
            app.update_progress_state('ocr_analysis', 'completed', 100, "OCR ë¶„ì„ ?„ë£Œ!")
            logger.info(f"[ë°°ì¹˜ ë¶„ì„] OCR ?ë§‰ ê°ì? ?„ë£Œ: {len(subtitle_positions) if subtitle_positions else 0}ê°??ì—­")

            app.analysis_result = {
                'script': script_data,
                'subtitle_positions': subtitle_positions,
                'raw_subtitle_positions': subtitle_positions  # ?„í„°ë§????ë³¸ ?€??            }

            # ???€ë³??Œì‹± ?¤íŒ¨ ???ë³¸ ?ìŠ¤?¸ë? fallback?¼ë¡œ ?€????            if not script_data:
                logger.warning("[ë°°ì¹˜ ë¶„ì„] ?€ë³??Œì‹± ?¤íŒ¨ - ?ë³¸ ?ìŠ¤?¸ë? fallback?¼ë¡œ ?¬ìš©")
                # ?ë³¸ ë¶„ì„ ê²°ê³¼?ì„œ ?œêµ­??ì¤‘êµ­???ìŠ¤??ì¶”ì¶œ
                fallback_text = result_text.strip()
                if fallback_text:
                    app.video_analysis_result = fallback_text
                    app.translation_result = fallback_text  # ë²ˆì—­ ê²°ê³¼ë¡œë„ ?€??                    logger.info(f"[ë°°ì¹˜ ë¶„ì„] Fallback ?ìŠ¤???€?? {len(fallback_text)}??)
                else:
                    app.video_analysis_result = None
            else:
                app.video_analysis_result = None  # ?€ë³?ëª¨ë“œ?ì„œ???¬ìš© ?ˆí•¨

            logger.info(f"[ë°°ì¹˜ ë¶„ì„] ?„ë£Œ - ?€ë³?{len(script_data)}ê°?)
            if subtitle_positions:
                logger.info(f"[ë°°ì¹˜ ë¶„ì„] OCR ì¤‘êµ­???ë§‰: {len(subtitle_positions)}ê°??ì—­")
            else:
                logger.info("[ë°°ì¹˜ ë¶„ì„] OCR ì¤‘êµ­???ë§‰ ?†ìŒ")

    except Exception as e:
        ui_controller.write_error_log(e)
        error_text = str(e)
        translated_error = _translate_error_message(error_text)
        logger.error(f"[ë°°ì¹˜ ë¶„ì„ ?¤ë¥˜] {translated_error}")
        # traceback ì¶œë ¥ ?œê±° - ?œê? ë©”ì‹œì§€ë§??œì‹œ
        if "PERMISSION_DENIED" in error_text or "403" in error_text or "ê¶Œí•œ" in translated_error:
            logger.error("[ë°°ì¹˜ ë¶„ì„] API ?¤ê? ?´ë‹¹ Gemini ëª¨ë¸ ?ëŠ” ?Œì¼ ?…ë¡œ??ê¸°ëŠ¥???¬ìš©??ê¶Œí•œ???ˆëŠ”ì§€ ?•ì¸?˜ì„¸??")
        raise


def _translate_script_for_batch(app):
    """ë°°ì¹˜??ë²ˆì—­ - ê¸°ì¡´ translate_script ë¡œì§ ?œìš©"""
    try:
        # ???´ë? translation_resultê°€ ?¤ì •?˜ì–´ ?ˆìœ¼ë©?(?í’ˆ ?¤ëª… ëª¨ë“œ ?ëŠ” fallback) ?¤í‚µ ??        if app.translation_result:
            logger.info(f"[ë°°ì¹˜ ë²ˆì—­] ?´ë? ë²ˆì—­ ê²°ê³¼ ?ˆìŒ - ?¤í‚µ ({len(app.translation_result)}??")
            return

        if not app.analysis_result.get('script'):
            logger.info("[ë°°ì¹˜ ë²ˆì—­] ?€ë³¸ì´ ?†ì–´ ë²ˆì—­ ?¤í‚µ")
            return

        selected_voice = getattr(app, "fixed_tts_voice", None) or getattr(app, "last_voice_used", None)
        if not selected_voice:
            voice_candidates = getattr(app, "available_tts_voices", None) or getattr(app, "multi_voice_presets", None)
            if voice_candidates:
                selected_voice = voice_candidates[0]
        if not selected_voice:
            selected_voice = "ë¯¸ì???

        voice_label = _get_voice_display_name(selected_voice) if selected_voice != "ë¯¸ì??? else "ë¯¸ì???
        app.add_log("[ë²ˆì—­] ?€ë³?ë²ˆì—­ ë°?ê°ìƒ‰???œì‘?©ë‹ˆ??..")
        logger.info("[ë°°ì¹˜ ë²ˆì—­] ?œì‘")
        logger.info(f"?¬ìš© ëª¨ë¸: {config.GEMINI_TEXT_MODEL}")
        logger.info(f"? íƒ??TTS ?Œì„±: {voice_label}")

        video_duration = app.get_video_duration_helper()
        target_duration = video_duration * config.DAESA_GILI
        target_chars = int(target_duration * 4.2)

        script_lines = []
        original_total_chars = 0

        for line in app.analysis_result['script']:
            timestamp = line.get('timestamp', '00:00')
            speaker = line.get('speaker', '?????†ìŒ')
            text = line.get('text', '')
            original_total_chars += len(text)
            script_lines.append(f"[{timestamp}] [{speaker}] {text}")

        script_text = "\n".join(script_lines)

        expansion_ratio = target_chars / original_total_chars if original_total_chars > 0 else 1.0

        # ? íƒ??CTA ?¼ì¸ ê°€?¸ì˜¤ê¸?        from ui.panels.cta_panel import get_selected_cta_lines
        cta_lines = get_selected_cta_lines(app)

        if expansion_ratio >= 0.8:
            length_instruction = "?ë³¸ë³´ë‹¤ 20% ?´ìƒ ê¸¸ê²Œ ?ì—°?¤ëŸ½ê³??ë????œí˜„?¼ë¡œ ë²ˆì—­"
        elif expansion_ratio >= 0.6:
            length_instruction = "?ë³¸ë³´ë‹¤ 10-20% ì§§ê²Œ ?µì‹¬ ?´ìš© ? ì??˜ë©° ë²ˆì—­"
        else:
            length_instruction = "?ë³¸ë³´ë‹¤ 20% ?´ìƒ ì§§ê²Œ ?µì‹¬ë§?ì¶”ë ¤??ë²ˆì—­"

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
                    app.add_log(f"[ë²ˆì—­] API ?¬ì‹œ??{attempt}/{MAX_RETRIES}...")
                
                # ?„ì¬ ?¬ìš© ì¤‘ì¸ API ??ë¡œê¹…
                api_mgr = getattr(app, 'api_key_manager', None) or getattr(app, 'api_manager', None)
                current_api_key = getattr(api_mgr, 'current_key', 'unknown') if api_mgr else 'unknown'
                logger.debug(f"[ë²ˆì—­ API] ?¬ìš© ì¤‘ì¸ API ??(?œë„ {attempt}): {current_api_key}")

                response = app.genai_client.models.generate_content(
                    model=config.GEMINI_TEXT_MODEL,
                    contents=[prompt],
                )
                break # ?±ê³µ ??ë£¨í”„ ?ˆì¶œ
                
            except Exception as e:
                logger.error(f"[ë°°ì¹˜ ë²ˆì—­] API ?¸ì¶œ ?¤íŒ¨ (?œë„ {attempt}): {e}")
                
                # 429 Quota Exceeded ì²˜ë¦¬ (??êµì²´)
                if "429" in str(e) and ("RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower()):
                    logger.warning("[ë°°ì¹˜ ë²ˆì—­] API ??? ë‹¹??ì´ˆê³¼(429) ê°ì?. ??êµì²´ë¥??œë„?©ë‹ˆ??")
                    if api_mgr:
                        api_mgr.block_current_key(duration_minutes=60)
                        # ?´ë¼?´ì–¸???¬ì´ˆê¸°í™” (????ë¡œë“œ)
                        if app.init_client():
                            new_key = getattr(api_mgr, 'current_key', 'unknown')
                            logger.info(f"[ë°°ì¹˜ ë²ˆì—­] API ??êµì²´ ?„ë£Œ -> {new_key}. ì¦‰ì‹œ ?¬ì‹œ?„í•©?ˆë‹¤.")
                            continue
                        else:
                            logger.error("[ë°°ì¹˜ ë²ˆì—­] êµì²´??API ?¤ê? ???´ìƒ ?†ìŠµ?ˆë‹¤.")
                    else:
                        logger.warning("[ë°°ì¹˜ ë²ˆì—­] API Key Managerê°€ ?†ì–´ ??êµì²´ë¥??˜í–‰?????†ìŠµ?ˆë‹¤.")
                
                if attempt < MAX_RETRIES:
                    time.sleep(2 * attempt)
                else:
                    raise e

        # ë¹„ìš© ê³„ì‚° ë°?ë¡œê¹…
        if response and hasattr(response, 'usage_metadata') and response.usage_metadata:
            cost_info = app.token_calculator.calculate_cost(
                model=config.GEMINI_TEXT_MODEL,
                usage_metadata=response.usage_metadata,
                media_type="text"
            )
            app.token_calculator.log_cost("?€ë³?ë²ˆì—­ ë°?ê°ìƒ‰", config.GEMINI_TEXT_MODEL, cost_info)

        # ?ˆì „?˜ê²Œ ?ìŠ¤??ì¶”ì¶œ (thought_signature ê²½ê³  ë°©ì?)
        translated_text = _extract_text_from_response(response) if response else ""

        if not translated_text:
            translated_text = script_text
            logger.warning("[ë°°ì¹˜ ë²ˆì—­] ê²°ê³¼ê°€ ?†ì–´ ?ë³¸ ?¤í¬ë¦½íŠ¸ë¥??¬ìš©?©ë‹ˆ??")

        app.translation_result = translated_text
        app.add_log(f"[ë²ˆì—­] ë²ˆì—­ ?„ë£Œ - {len(app.translation_result)}??)
        logger.info(f"[ë°°ì¹˜ ë²ˆì—­] ?„ë£Œ - {len(app.translation_result)}??)
    except Exception as e:
        ui_controller.write_error_log(e)
        translated_error = _translate_error_message(str(e))
        logger.error(f"[ë°°ì¹˜ ë²ˆì—­ ?¤ë¥˜] {translated_error}")
        # traceback ì¶œë ¥ ?œê±° - ?œê? ë©”ì‹œì§€ë§??œì‹œ
        raise

