"""
TTS Generator Module
====================
Google Gemini TTS API를 사용한 음성 생성 모듈입니다.

이 모듈은 core/audio/pipeline.py의 AudioPipeline을 사용하여
TTS 생성, 배속 적용, 자막 싱크를 수행합니다.

주요 기능:
- 전체 스크립트 통으로 TTS 생성 (_generate_tts_full_script)
- 세그먼트별 개별 TTS 생성 (_generate_tts_for_segment)
- 배치 처리용 TTS 생성 워크플로우 (_generate_tts_for_batch)
- Fallback 메타데이터 생성 (_create_fallback_metadata)

변경 이력:
- AudioPipeline 통합으로 중복 코드 제거 (길이 체크, 스크립트 축소, 재시도 로직)

사용되는 곳:
- processor.py (배치 처리 워크플로우)
- tts_handler.py (호환성 유지용)
"""

import os
import re
import time
import glob
import secrets
import subprocess
from datetime import datetime

from google.genai import types
from pydub import AudioSegment

from .audio_utils import _ensure_pydub_converter, _prepare_segment, _write_wave_fallback
from .whisper_analyzer import analyze_tts_with_whisper
from .utils import (
    _split_text_naturally,
    _get_voice_display_name,
)
from caller import ui_controller
from utils.korean_text_processor import process_korean_script
from utils.logging_config import get_logger
import config

logger = get_logger(__name__)


# ============================================================
# AudioPipeline 통합 - 공통 로직은 pipeline.py에서 가져옴
# ============================================================

def _get_audio_pipeline(app):
    """
    AudioPipeline 인스턴스 가져오기 (지연 임포트로 순환 참조 방지)

    Args:
        app: 앱 인스턴스

    Returns:
        AudioPipeline 인스턴스
    """
    from core.audio import AudioPipeline, AudioConfig

    # 앱에 캐시된 파이프라인이 있으면 재사용
    if hasattr(app, '_audio_pipeline') and app._audio_pipeline is not None:
        return app._audio_pipeline

    # 새 파이프라인 생성 (기본 설정 사용)
    pipeline = AudioPipeline(app, AudioConfig())
    app._audio_pipeline = pipeline
    return pipeline


def _create_fallback_metadata(app, subtitle_segments, total_duration, audio_path, start_offset=None):
    """
    Gemini 분석 실패 시 세그먼트 기반 fallback 메타데이터 생성.
    균등 분배 대신 글자 수 비례 분배로 더 정확한 싱크.

    AudioPipeline._create_fallback_metadata와 동일한 로직이지만
    하위 호환성을 위해 유지합니다.

    Args:
        app: 앱 인스턴스
        subtitle_segments: 자막 세그먼트 리스트
        total_duration: 전체 오디오 길이 (초)
        audio_path: 오디오 파일 경로
        start_offset: 앞무음 오프셋 (자막 시작 시간에 추가)
    """
    if not subtitle_segments or total_duration <= 0:
        return

    if start_offset is None:
        sync_info = getattr(app, 'tts_sync_info', {}) or {}
        start_offset = sync_info.get('audio_start_offset', 0.0)

    num_segments = len(subtitle_segments)
    effective_duration = max(0.1, total_duration - start_offset)

    # 글자 수 비례 분배
    char_counts = []
    for text in subtitle_segments:
        clean_text = text.strip() if isinstance(text, str) else str(text).strip()
        char_counts.append(max(1, len(clean_text)))

    total_chars = sum(char_counts)

    logger.info(f"[Fallback 메타데이터] {num_segments}개 세그먼트, 총 {total_chars}자 (글자 수 비례 분배, offset: {start_offset:.3f}s)")

    updated = []
    current_time = start_offset

    for idx, text in enumerate(subtitle_segments):
        clean_text = text.strip() if isinstance(text, str) else str(text).strip()
        char_ratio = char_counts[idx] / total_chars
        segment_duration = effective_duration * char_ratio

        start = current_time
        end = current_time + segment_duration

        entry = {
            'idx': idx,
            'start': start,
            'end': end,
            'text': clean_text,
            'path': audio_path,
            'speaker': getattr(app, 'fixed_tts_voice', None),
            'is_narr': False,
        }
        updated.append(entry)
        current_time = end

    app._per_line_tts = updated
    logger.info(f"[Fallback 메타데이터] {num_segments}개 세그먼트 메타데이터 생성 완료 (글자 수 비례)")


def _generate_tts_full_script(app, full_script: str, voice: str) -> tuple:
    """
    전체 스크립트를 통으로 TTS 생성

    Args:
        app: 앱 인스턴스
        full_script: 전체 스크립트 텍스트
        voice: 음성 이름

    Returns:
        tuple: (AudioSegment, wav_path) - 생성된 오디오와 저장 경로
    """
    import wave

    # TTS용 텍스트: 숫자 -> 자연스러운 한국어, 영어 -> 한글
    tts_text = process_korean_script(full_script)

    logger.info(f"[TTS 통으로 생성] 전체 스크립트 ({len(full_script)}자)")
    logger.debug(f"  원본: {full_script[:50]}...")
    logger.debug(f"  TTS용: {tts_text[:50]}...")

    try:
        response = app.genai_client.models.generate_content(
            model=config.GEMINI_TTS_MODEL,
            contents=[tts_text],
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice
                        )
                    )
                )
            )
        )
    except Exception as e:
        logger.error(f"[TTS API Error] {e}")
        if "404" in str(e) or "NotFound" in str(e):
            raise RuntimeError(f"TTS 모델을 찾을 수 없습니다: {config.GEMINI_TTS_MODEL}. config.py를 확인하세요.")
        else:
            raise e

    # 비용 계산 (선택적)
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        app.token_calculator.calculate_cost(
            model=config.GEMINI_TTS_MODEL,
            usage_metadata=response.usage_metadata,
            media_type="audio"
        )

    # API 응답 검증
    if not response or not response.candidates:
        raise RuntimeError("TTS API 응답 없음")

    candidate = response.candidates[0]
    if not candidate.content or not candidate.content.parts:
        raise RuntimeError("TTS API 응답에 오디오 데이터 없음")

    audio_data = candidate.content.parts[0].inline_data.data
    if not audio_data:
        raise RuntimeError("TTS 오디오 데이터가 비어있음")

    # 파일 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:21]
    random_suffix = secrets.token_hex(4)
    original_filename = f"tts_full_{voice}_{timestamp}_{random_suffix}.wav"
    original_path = os.path.join(app.tts_output_dir, original_filename)

    # WAV 데이터가 RIFF 헤더로 시작하면 그대로 저장
    if audio_data[:4] == b'RIFF':
        with open(original_path, 'wb') as f:
            f.write(audio_data)
    else:
        # raw PCM 데이터인 경우 wave 모듈로 저장
        with wave.open(original_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(audio_data)

    # pydub로 로드 및 정규화
    raw_audio = AudioSegment.from_file(original_path, format="wav")
    prepared_audio = _prepare_segment(raw_audio)

    # 정규화된 버전 저장
    ffmpeg_path = _ensure_pydub_converter()
    try:
        if ffmpeg_path:
            prepared_audio.export(original_path, format="wav", parameters=["-ar", "44100", "-ac", "2"])
        else:
            _write_wave_fallback(prepared_audio, original_path, sample_rate=44100)
    except Exception as export_err:
        logger.warning(f"[export 폴백] {export_err}")
        _write_wave_fallback(prepared_audio, original_path, sample_rate=44100)

    duration_sec = len(prepared_audio) / 1000.0
    logger.info(f"[TTS 통으로 생성] 완료: {duration_sec:.2f}초, {os.path.basename(original_path)}")

    return prepared_audio, original_path


def _generate_tts_for_segment(app, text: str, voice: str, is_cta: bool = False,
                               segment_position: str = "middle", total_segments: int = 1) -> tuple:
    """
    단일 세그먼트에 대해 TTS 생성 (하위 호환성 유지)

    Args:
        app: 앱 인스턴스
        text: 읽을 텍스트
        voice: 음성 이름
        is_cta: CTA 문구 여부
        segment_position: 세그먼트 위치 ("first", "middle", "last", "only")
        total_segments: 전체 세그먼트 수

    Returns:
        tuple: (AudioSegment, duration_ms) - 트림/정규화된 오디오와 밀리초 단위 길이
    """
    import wave
    import tempfile

    # TTS용 텍스트: 숫자 -> 자연스러운 한국어, 영어 -> 한글
    tts_text = process_korean_script(text)

    try:
        response = app.genai_client.models.generate_content(
            model=config.GEMINI_TTS_MODEL,
            contents=[tts_text],
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice
                        )
                    )
                )
            )
        )
    except Exception as e:
        logger.error(f"[TTS API Error] {e}")
        if "404" in str(e) or "NotFound" in str(e):
            raise RuntimeError(f"TTS 모델을 찾을 수 없습니다: {config.GEMINI_TTS_MODEL}. config.py를 확인하세요.")
        else:
            raise e

    # 비용 계산 (선택적)
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        app.token_calculator.calculate_cost(
            model=config.GEMINI_TTS_MODEL,
            usage_metadata=response.usage_metadata,
            media_type="audio"
        )

    # API 응답 검증
    if not response or not response.candidates:
        raise RuntimeError("TTS API 응답 없음")

    candidate = response.candidates[0]
    if not candidate.content or not candidate.content.parts:
        raise RuntimeError("TTS API 응답에 오디오 데이터 없음")

    audio_data = candidate.content.parts[0].inline_data.data
    if not audio_data:
        raise RuntimeError("TTS 오디오 데이터가 비어있음")

    # 임시 파일에 저장 후 로드 (Windows 호환성)
    temp_file = None
    try:
        temp_fd, temp_path = tempfile.mkstemp(suffix=".wav", prefix="tts_seg_")
        os.close(temp_fd)
        temp_file = temp_path

        # WAV 데이터가 RIFF 헤더로 시작하면 그대로 저장
        if audio_data[:4] == b'RIFF':
            with open(temp_path, 'wb') as f:
                f.write(audio_data)
        else:
            # raw PCM 데이터인 경우 wave 모듈로 저장
            with wave.open(temp_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(audio_data)

        # pydub로 로드
        raw_segment = AudioSegment.from_file(temp_path, format="wav")

        # 레퍼런스 프로그램 방식: 트림 + 정규화
        prepared_segment = _prepare_segment(raw_segment)

        # 트림/정규화 후 실제 길이를 측정
        duration_ms = int(prepared_segment.duration_seconds * 1000)

        return prepared_segment, duration_ms

    finally:
        # 임시 파일 정리
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError as e:
                logger.warning(f"[TTS] 임시 파일 삭제 실패: {temp_file} - {e}")


def _generate_tts_for_batch(app, voice):
    """
    TTS 통으로 생성 + Whisper 분석으로 자막 싱크

    AudioPipeline을 사용하여 다음 워크플로우를 수행합니다:
    1. 영상 길이에 맞는 스크립트 사전 축소
    2. 전체 스크립트를 통으로 TTS 생성 (1회 API 호출)
    3. 1.2배속 적용
    4. Whisper로 오디오 분석하여 자막 세그먼트별 타이밍 추출
    5. 자막 싱크 메타데이터 생성

    장점:
    - API 호출 1회로 효율적
    - 자연스러운 억양 (문장이 끊기지 않음)
    - Whisper 분석으로 정확한 타이밍
    - AudioPipeline 통합으로 중복 코드 제거

    Args:
        app: 앱 인스턴스
        voice: Gemini TTS 음성 ID
    """
    # 영상 길이 확인
    video_duration = app.get_video_duration_helper()

    app.add_log(f"[TTS] 음성 생성 시작 - 영상: {video_duration:.1f}초")
    logger.info("=" * 60)
    logger.info("[TTS] AudioPipeline을 사용한 통합 TTS 생성")
    logger.info("=" * 60)

    # 음성 정보 설정
    selected_voice = voice
    voice_label = _get_voice_display_name(voice)
    app.fixed_tts_voice = voice

    # 스크립트 추출
    original_script = app.extract_clean_script_from_translation()

    if not original_script:
        logger.error("[TTS 오류] 스크립트 추출 실패!")
        logger.error(f"  - translation_result: {len(app.translation_result) if app.translation_result else 'None'}자")
        logger.error(f"  - video_analysis_result: {type(getattr(app, 'video_analysis_result', None))}")
        logger.error(f"  - analysis_result.script: {len(app.analysis_result.get('script', [])) if app.analysis_result else 'None'}개")
        raise RuntimeError("추출된 대본이 없습니다 (분석 결과를 확인하세요)")

    # AudioPipeline 사용하여 TTS 생성
    try:
        pipeline = _get_audio_pipeline(app)

        # CTA 문장 가져오기
        from ui.panels.cta_panel import get_selected_cta_lines
        cta_lines = get_selected_cta_lines(app)

        # TTS 생성 (파이프라인이 길이 체크, 재시도, 배속 모두 처리)
        app.add_log(f"[TTS] 음성 생성 API 호출 중... ({len(original_script)}자)")

        result = pipeline.generate_tts(
            script=original_script,
            voice=selected_voice,
            video_duration=video_duration,
            cta_lines=cta_lines,
        )

        app.add_log(f"[TTS] 음성 생성 완료 - {result.speeded_duration:.1f}초")

        # 메타데이터에 speaker 설정
        for entry in result.metadata:
            entry['speaker'] = selected_voice

        # 결과 저장 (기존 인터페이스 유지)
        app._per_line_tts = result.metadata
        app.tts_files = [result.audio_path]

        app.tts_sync_info = {
            'original_duration': result.original_duration,
            'speeded_duration': result.speeded_duration,
            'speed_ratio': result.speed_ratio,
            'start_silence': 0.0,
            'audio_start_offset': result.voice_start,
            'voice_end': result.voice_end,
            'file_path': result.audio_path,
            'timestamps_source': result.timestamps_source,
            'segment_count': len(result.metadata),
        }

        # 결과 출력
        logger.info("=" * 60)
        logger.info(f"[TTS 완료] {result.timestamps_source}")
        logger.info(f"  원본: {result.original_duration:.2f}초 -> 배속: {result.speeded_duration:.2f}초")
        logger.info(f"  세그먼트: {len(result.metadata)}개")
        logger.info("=" * 60)
        for entry in result.metadata:
            text_preview = entry['text'][:25] + '...' if len(entry['text']) > 25 else entry['text']
            logger.debug(f"  #{entry['idx']+1}: {entry['start']:.2f}s ~ {entry['end']:.2f}s | '{text_preview}'")
        logger.info("=" * 60)

        # 비용 로깅
        app.token_calculator.log_cost(
            f"TTS 음성 생성 ({voice_label}) - AudioPipeline",
            config.GEMINI_TTS_MODEL,
            {'total_cost': 0}
        )

    except Exception as exc:
        ui_controller.write_error_log(exc)
        logger.error(f"[TTS] AudioPipeline 오류: {exc}")
        raise


def _generate_tts_for_batch_legacy(app, voice):
    """
    레거시 TTS 생성 함수 (하위 호환성 유지)

    AudioPipeline 사용에 문제가 있을 경우를 위한 폴백 함수입니다.
    기존 로직을 그대로 유지합니다.

    Args:
        app: 앱 인스턴스
        voice: Gemini TTS 음성 ID
    """
    max_attempts = 3

    # 영상 길이 확인
    video_duration = app.get_video_duration_helper()
    max_audio_duration_after_speed = video_duration * 0.85
    max_audio_duration_original = max_audio_duration_after_speed * 1.2

    app.add_log(f"[TTS] 음성 생성 시작 - 영상: {video_duration:.1f}초")
    logger.info("=" * 60)
    logger.info("[TTS 통으로 생성] Whisper 분석으로 자막 싱크 (레거시)")
    logger.info("=" * 60)
    logger.info(f"  영상 길이: {video_duration:.1f}초")
    logger.info(f"  TTS 허용 (1.2배속 후): {max_audio_duration_after_speed:.1f}초")
    logger.info(f"  TTS 허용 (원본): {max_audio_duration_original:.1f}초")

    selected_voice = voice
    voice_label = _get_voice_display_name(voice)
    app.fixed_tts_voice = voice
    original_script = app.extract_clean_script_from_translation()

    if not original_script:
        logger.error("[TTS 오류] 스크립트 추출 실패!")
        raise RuntimeError("추출된 대본이 없습니다 (분석 결과를 확인하세요)")

    # 상품 정보 확인
    is_product = any(keyword in app.translation_result for keyword in ['상품', '제품', '구매', '링크'])

    # CTA 문장 가져오기
    from ui.panels.cta_panel import get_selected_cta_lines
    actual_cta_lines = get_selected_cta_lines(app)

    # 영상 길이 기반 최대 글자 수 계산
    chars_per_second = 7.0
    max_chars = int(max_audio_duration_original * chars_per_second)

    # CTA 텍스트 준비
    cta_text = ""
    if actual_cta_lines and is_product:
        cta_text = " ".join(actual_cta_lines)
        if cta_text not in original_script:
            original_script = original_script.strip() + " " + cta_text

    # 본문 분리
    main_script = original_script
    if cta_text and cta_text in original_script:
        main_script = original_script.replace(cta_text, "").strip()

    # 스크립트 축소 (AudioPipeline._trim_script_by_chars와 동일 로직)
    if len(original_script) > max_chars:
        logger.info(f"[스크립트 길이 조정] 원본 {len(original_script)}자 -> 최대 {max_chars}자")

        main_target_chars = max_chars - len(cta_text) - 1 if cta_text else max_chars

        if main_target_chars > 20:
            sentence_pattern = re.compile(r'[.!?。！？]\s*')
            sentences = sentence_pattern.split(main_script)
            sentence_ends = sentence_pattern.findall(main_script)

            reduced_main = ""
            for i, sent in enumerate(sentences):
                sent = sent.strip()
                if not sent:
                    continue
                end_char = sentence_ends[i] if i < len(sentence_ends) else ""
                candidate = reduced_main + (" " if reduced_main else "") + sent + end_char.strip()

                if len(candidate) <= main_target_chars:
                    reduced_main = candidate
                else:
                    if reduced_main:
                        break
                    reduced_main = sent + end_char.strip()
                    break

            reduced_main = reduced_main.strip()
            if reduced_main:
                main_script = reduced_main
                original_script = main_script + (" " + cta_text if cta_text else "")

    last_duration = None

    for attempt in range(max_attempts):
        try:
            # 텍스트 준비 (재시도 시 축소)
            if attempt == 0:
                full_script = original_script
            else:
                if last_duration and max_audio_duration_after_speed > 0:
                    overshoot_ratio = last_duration / max_audio_duration_after_speed
                    reduction_rate = max(0.3, min(0.9, (1.0 / overshoot_ratio) * 0.85))
                else:
                    reduction_rate = 0.7 if attempt == 1 else 0.5
                target_len = int(len(main_script) * reduction_rate)

                sentence_pattern = re.compile(r'[.!?。！？]\s*')
                sentences = sentence_pattern.split(main_script)
                sentence_ends = sentence_pattern.findall(main_script)

                reduced_main = ""
                for i, sent in enumerate(sentences):
                    sent = sent.strip()
                    if not sent:
                        continue
                    end_char = sentence_ends[i] if i < len(sentence_ends) else ""
                    candidate = reduced_main + (" " if reduced_main else "") + sent + end_char.strip()

                    if len(candidate) <= target_len:
                        reduced_main = candidate
                    else:
                        if reduced_main:
                            break
                        reduced_main = sent + end_char.strip()
                        break

                reduced_main = reduced_main.strip()
                if not reduced_main:
                    reduced_main = main_script[:target_len].rsplit(' ', 1)[0].strip()

                full_script = reduced_main + (" " + cta_text if cta_text else "")

            logger.info(f"[TTS 시도 {attempt+1}/{max_attempts}] {len(full_script)}자")

            # 자막 세그먼트 분할
            subtitle_segments = _split_text_naturally(app, full_script)
            logger.info(f"[TTS] {len(subtitle_segments)}개 세그먼트로 분할")

            # TTS 생성
            app.add_log(f"[TTS] 음성 생성 API 호출 중... ({len(full_script)}자)")

            tts_success = False
            tts_retry = 0
            max_tts_retry = 3
            combined_audio = None
            original_path = None

            while not tts_success and tts_retry < max_tts_retry:
                try:
                    combined_audio, original_path = _generate_tts_full_script(
                        app, full_script, selected_voice
                    )
                    tts_success = True
                except Exception as tts_err:
                    tts_retry += 1
                    error_str = str(tts_err)
                    logger.warning(f"[TTS 오류] ({tts_retry}/{max_tts_retry}): {error_str[:60]}")

                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                        try:
                            if hasattr(app, 'api_key_manager') and app.api_key_manager:
                                app.api_key_manager.block_current_key(duration_minutes=5)
                                if hasattr(app, 'init_client') and app.init_client():
                                    logger.info("[API 키 전환] 완료")
                                else:
                                    time.sleep(60)
                        except Exception as key_err:
                            logger.warning(f"[API 키 전환 오류] {key_err}")
                            time.sleep(60)
                    else:
                        time.sleep(2)

            if not tts_success:
                raise RuntimeError(f"TTS 생성 실패: {full_script[:50]}...")

            original_duration_sec = len(combined_audio) / 1000.0
            app.add_log(f"[TTS] 음성 생성 완료 - {original_duration_sec:.1f}초")

            # 1.2배속 적용
            speed_ratio = 1.2
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:21]
            random_suffix = secrets.token_hex(4)
            speeded_filename = f"tts_speeded_{selected_voice}_{timestamp}_{random_suffix}.wav"
            speeded_path = os.path.join(app.tts_output_dir, speeded_filename)

            ffmpeg_path = _ensure_pydub_converter()

            if ffmpeg_path:
                cmd = [
                    ffmpeg_path, "-y", "-i", original_path,
                    "-filter:a", f"atempo={speed_ratio}",
                    "-ar", "44100", "-ac", "2",
                    speeded_path
                ]
                result = subprocess.run(cmd, capture_output=True, timeout=60)
                if result.returncode == 0 and os.path.exists(speeded_path):
                    logger.info("[TTS] ffmpeg atempo 1.2배속 성공")
                else:
                    speeded_audio = combined_audio.speedup(playback_speed=speed_ratio, chunk_size=150, crossfade=25)
                    speeded_audio.export(speeded_path, format="wav")
                    logger.info("[TTS] pydub 1.2배속 폴백")
            else:
                speeded_audio = combined_audio.speedup(playback_speed=speed_ratio, chunk_size=150, crossfade=25)
                speeded_audio.export(speeded_path, format="wav")
                logger.info("[TTS] pydub 1.2배속 (ffmpeg 없음)")

            # 배속 후 길이 측정
            speeded_audio = AudioSegment.from_file(speeded_path)
            speeded_duration_sec = len(speeded_audio) / 1000.0
            logger.info(f"[TTS] 1.2배속 후 길이: {speeded_duration_sec:.2f}초")

            last_duration = speeded_duration_sec

            # 길이 체크
            if speeded_duration_sec > max_audio_duration_after_speed:
                excess = speeded_duration_sec - max_audio_duration_after_speed
                logger.warning(f"[TTS] {excess:.1f}초 초과")
                if attempt < max_attempts - 1:
                    continue
                else:
                    logger.info("[TTS] 최종 시도 - 현재 결과 사용")

            # Whisper 분석
            app.add_log("[자막] Whisper로 자막 타이밍 분석 중...")

            whisper_result = analyze_tts_with_whisper(
                app, speeded_path, full_script, subtitle_segments
            )
            app.add_log("[자막] Whisper 분석 완료")

            # 결과 처리
            if whisper_result and 'segments' in whisper_result:
                whisper_segments = whisper_result['segments']
                voice_start = whisper_result.get('voice_start', 0)
                voice_end = whisper_result.get('voice_end', speeded_duration_sec)

                subtitle_entries = []
                for seg in whisper_segments:
                    idx = seg.get('index', 1) - 1
                    subtitle_entries.append({
                        'idx': idx,
                        'start': seg['start'],
                        'end': seg['end'],
                        'text': seg['text'],
                        'path': speeded_path,
                        'speaker': selected_voice,
                        'is_narr': False,
                    })

                timestamps_source = 'whisper_analysis'
            else:
                # 글자 수 비례 폴백
                logger.warning("[Whisper] 분석 실패 -> 글자 수 비례 폴백")
                char_counts = [max(1, len(re.sub(r'[\s,.!?~\-]', '', seg))) for seg in subtitle_segments]
                total_chars = sum(char_counts)

                subtitle_entries = []
                current_time = 0.0

                for idx, seg_text in enumerate(subtitle_segments):
                    char_ratio = char_counts[idx] / total_chars
                    segment_duration = speeded_duration_sec * char_ratio

                    subtitle_entries.append({
                        'idx': idx,
                        'start': round(current_time, 3),
                        'end': round(current_time + segment_duration, 3),
                        'text': seg_text,
                        'path': speeded_path,
                        'speaker': selected_voice,
                        'is_narr': False,
                    })
                    current_time += segment_duration

                voice_start = 0
                voice_end = speeded_duration_sec
                timestamps_source = 'char_proportional_fallback'

            # 결과 저장
            app._per_line_tts = subtitle_entries
            app.tts_files = [speeded_path]

            app.tts_sync_info = {
                'original_duration': original_duration_sec,
                'speeded_duration': speeded_duration_sec,
                'speed_ratio': speed_ratio,
                'start_silence': 0.0,
                'audio_start_offset': voice_start,
                'voice_end': voice_end,
                'file_path': speeded_path,
                'original_tts_path': original_path,
                'timestamps_source': timestamps_source,
                'segment_count': len(subtitle_segments),
            }

            logger.info(f"[TTS 완료] {timestamps_source}")
            return

        except Exception as exc:
            ui_controller.write_error_log(exc)
            error_str = str(exc)
            logger.error(f"[TTS] 시도 {attempt+1} 실패: {exc}")

            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                try:
                    api_mgr = getattr(app, 'api_key_manager', None)
                    if api_mgr:
                        api_mgr.block_current_key(duration_minutes=5)
                        if hasattr(app, 'init_client') and app.init_client():
                            logger.info("[API 키 전환] 완료")
                except Exception as key_err:
                    logger.warning(f"[API 키 전환 오류] {key_err}")

            if attempt >= max_attempts - 1:
                raise


def _cleanup_previous_attempts(app, keep_file, attempt_count):
    """이전 시도 파일들 정리"""
    try:
        for i in range(1, attempt_count + 1):
            pattern = f"*_try{i}.wav"
            for file in glob.glob(os.path.join(app.tts_output_dir, pattern)):
                if file != keep_file:
                    try:
                        os.remove(file)
                        logger.debug(f"[정리] 이전 시도 파일 삭제: {os.path.basename(file)}")
                    except Exception as e:
                        logger.debug(f"[정리] 파일 삭제 실패: {e}")
    except Exception as e:
        logger.debug(f"[정리] 정리 작업 실패: {e}")
