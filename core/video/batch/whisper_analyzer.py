"""
Faster-Whisper STT Analyzer for TTS Processing

Contains Faster-Whisper-based speech-to-text analysis for accurate subtitle timing.
Uses CTranslate2 for fast inference without PyTorch dependency.
"""

import os
import re
import sys
import platform

from pydub import AudioSegment
from pydub.silence import detect_leading_silence

from .audio_utils import _ensure_pydub_converter
from .utils import _split_text_naturally
from caller import ui_controller
from utils.logging_config import get_logger

logger = get_logger(__name__)


def _get_runtime_base_path():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _get_whisper_model_params(app):
    """시스템 최적화 설정에서 Whisper 파라미터 가져오기"""
    try:
        from utils.system_optimizer import get_system_optimizer
        optimizer = get_system_optimizer(app)
        params = optimizer.get_optimized_whisper_params()
        return params
    except Exception as e:
        # 기본값 반환 (faster-whisper)
        logger.debug(f"Whisper 파라미터 로드 실패, 기본값 사용: {e}")
        return {
            'model_size': 'base',
            'device': 'cpu',
            'compute_type': 'int8',
            'beam_size': 5,
            'cpu_threads': 4
        }


def _get_model_path(model_size):
    """
    faster-whisper 모델 경로 가져오기
    빌드 환경에서는 번들된 모델 사용, 개발 환경에서는 자동 다운로드
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller 빌드인 경우
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        bundled_model_dir = os.path.join(base_path, 'faster_whisper_models', model_size)

        if os.path.isdir(bundled_model_dir):
            model_file = os.path.join(bundled_model_dir, 'model.bin')
            if os.path.exists(model_file):
                logger.info(f"[Faster-Whisper] 빌드 포함 모델 사용: {bundled_model_dir}")
                return bundled_model_dir

        # 번들에 없으면 에러
        raise RuntimeError(
            f"[Faster-Whisper] 오프라인 실행 실패: 모델이 빌드에 포함되지 않았습니다.\n"
            f"경로: {bundled_model_dir}\n"
            f"해결방법: download_whisper_models.py를 실행하여 모델을 다운로드한 후 재빌드하세요."
        )
    else:
        # 개발 환경: 모델 이름만 반환 (자동 다운로드)
        return model_size


def analyze_tts_with_whisper(app, tts_path, transcript_text, subtitle_segments=None):
    """
    Faster-Whisper STT로 TTS 오디오 분석 (로컬, 무료, 빠름)

    - Faster-Whisper (CTranslate2 기반) 로컬 실행
    - OpenAI Whisper 대비 4~5배 빠름
    - PyTorch 불필요 → 빌드 크기 대폭 감소
    - 단어 단위 정밀 타임스탬프 획득
    """
    try:
        logger.info("=" * 60)
        logger.info("[Faster-Whisper STT 분석] 시작...")
        logger.info("=" * 60)
        logger.info(f"  - TTS 파일: {os.path.basename(tts_path)}")
        logger.info(f"  - 파일 크기: {os.path.getsize(tts_path) / 1024:.1f}KB")

        # 각 음성마다 독립적 분석을 위해 이전 결과 초기화
        if hasattr(app, '_last_whisper_path'):
            if app._last_whisper_path != tts_path:
                logger.info("[Faster-Whisper] 새로운 음성 파일 감지 - 이전 캐시 초기화")
        app._last_whisper_path = tts_path

        # ffmpeg 경로 설정
        ffmpeg_path = _ensure_pydub_converter()
        if ffmpeg_path:
            ffmpeg_dir = os.path.dirname(ffmpeg_path)
            current_path = os.environ.get('PATH', '')
            if ffmpeg_dir not in current_path:
                os.environ['PATH'] = ffmpeg_dir + os.pathsep + current_path
                logger.debug(f"[Faster-Whisper] ffmpeg 경로 추가: {ffmpeg_dir}")

        # Python 3.14+ 호환성 체크 - faster-whisper는 Python 3.14를 지원하지 않음
        py_version = sys.version_info
        if py_version >= (3, 14):
            logger.info(
                f"[Faster-Whisper] Python {py_version.major}.{py_version.minor}은 "
                "faster-whisper를 지원하지 않습니다. 글자 수 비례 폴백 사용."
            )
            if subtitle_segments is None:
                subtitle_segments = _split_text_naturally(app, transcript_text)
            try:
                audio = AudioSegment.from_file(tts_path)
                audio_duration = len(audio) / 1000.0
            except Exception as audio_err:
                logger.warning(f"[Faster-Whisper 폴백] 오디오 로드 실패: {audio_err}")
                audio_duration = 0.0
            return _create_char_proportional_timestamps(
                app, tts_path, subtitle_segments, audio_duration
            )

        # Faster-Whisper 모델 로드
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            if getattr(sys, 'frozen', False):
                raise RuntimeError(
                    "[Faster-Whisper] faster-whisper 패키지가 빌드에 포함되지 않았습니다. "
                    "재빌드가 필요합니다."
                )

            logger.info("[Faster-Whisper] faster-whisper 패키지 없음 - 설치 중...")
            import subprocess as sp
            sp.run([sys.executable, "-m", "pip", "install", "faster-whisper"], check=True)
            from faster_whisper import WhisperModel

        # 시스템 최적화 파라미터 가져오기
        whisper_params = _get_whisper_model_params(app)
        model_size = whisper_params.get('model_size', 'base')
        device = whisper_params.get('device', 'cpu')
        compute_type = whisper_params.get('compute_type', 'int8')
        cpu_threads = whisper_params.get('cpu_threads', 4)
        beam_size = whisper_params.get('beam_size', 5)

        # 모델 로드
        model_key = f"_faster_whisper_model_{model_size}"
        if not hasattr(app, model_key) or getattr(app, model_key) is None:
            logger.info(f"[Faster-Whisper] 모델 로딩 중 ({model_size}, {device}, {compute_type})...")

            model_path = _get_model_path(model_size)

            model = WhisperModel(
                model_path,
                device=device,
                compute_type=compute_type,
                cpu_threads=cpu_threads
            )
            setattr(app, model_key, model)
            logger.info("[Faster-Whisper] 모델 로드 완료")
        else:
            logger.debug("[Faster-Whisper] 캐시된 모델 사용")
            model = getattr(app, model_key)

        # 자막 세그먼트 준비
        if subtitle_segments is None:
            subtitle_segments = _split_text_naturally(app, transcript_text)

        logger.info(f"[Faster-Whisper] {len(subtitle_segments)}개 세그먼트 분석 요청")
        for i, seg in enumerate(subtitle_segments):
            logger.debug(f"  {i+1}. {seg}")

        # Faster-Whisper 음성 인식 (단어 타임스탬프 포함)
        logger.info("[Faster-Whisper] 음성 인식 중...")

        segments, info = model.transcribe(
            tts_path,
            language="ko",
            beam_size=beam_size,
            word_timestamps=True,
            vad_filter=True
        )

        # 세그먼트를 리스트로 변환 (generator이므로)
        whisper_segments = list(segments)

        # 전체 오디오 정보
        audio = AudioSegment.from_file(tts_path)
        audio_duration = len(audio) / 1000.0

        # 인식된 텍스트 조합
        recognized_text = ' '.join([seg.text for seg in whisper_segments])

        logger.info("[Faster-Whisper] 인식 완료!")
        logger.info(f"  - 오디오 길이: {audio_duration:.2f}초")
        logger.info(f"  - 언어: {info.language} (확률: {info.language_probability:.2f})")
        logger.debug(f"  - 인식된 텍스트: {recognized_text[:50]}...")

        # 단어 목록 추출
        words = []
        for segment in whisper_segments:
            if segment.words:
                for word_info in segment.words:
                    words.append({
                        'word': word_info.word.strip(),
                        'start': word_info.start,
                        'end': word_info.end
                    })

        logger.info(f"  - 인식된 단어: {len(words)}개")

        if not words:
            logger.info("[Faster-Whisper] 단어 타임스탬프 없음 - 세그먼트 기반 분석")
            if whisper_segments:
                total_whisper_duration = whisper_segments[-1].end - whisper_segments[0].start
                whisper_start = whisper_segments[0].start

                mapped_segments = []
                num_segs = len(subtitle_segments)
                seg_duration = total_whisper_duration / num_segs if num_segs > 0 else 1.0

                for seg_idx, seg_text in enumerate(subtitle_segments):
                    start_time = whisper_start + (seg_idx * seg_duration)
                    end_time = start_time + seg_duration
                    mapped_segments.append({
                        'index': seg_idx + 1,
                        'text': seg_text,
                        'start': round(start_time, 2),
                        'end': round(end_time, 2)
                    })
                    logger.debug(f"  #{seg_idx+1}: {start_time:.2f}s ~ {end_time:.2f}s | '{seg_text[:20]}'")
            else:
                logger.info("[Faster-Whisper] 세그먼트도 없음 - 오디오 전체 균등 분배")
                num_segs = len(subtitle_segments)
                seg_duration = audio_duration / num_segs if num_segs > 0 else 1.0

                mapped_segments = []
                for seg_idx, seg_text in enumerate(subtitle_segments):
                    start_time = seg_idx * seg_duration
                    end_time = (seg_idx + 1) * seg_duration
                    mapped_segments.append({
                        'index': seg_idx + 1,
                        'text': seg_text,
                        'start': round(start_time, 2),
                        'end': round(end_time, 2)
                    })
                    logger.debug(f"  #{seg_idx+1}: {start_time:.2f}s ~ {end_time:.2f}s | '{seg_text[:20]}'")
        else:
            # 단어가 있을 때: 단어를 자막 세그먼트에 매핑
            logger.info("[Faster-Whisper] 단어 → 세그먼트 매핑 중...")

            mapped_segments = []
            word_idx = 0

            for seg_idx, seg_text in enumerate(subtitle_segments):
                seg_chars = re.sub(r'[\s,.!?~·\-]', '', seg_text)

                seg_words = []
                matched_chars = 0

                while word_idx < len(words) and matched_chars < len(seg_chars):
                    word = words[word_idx]
                    word_clean = re.sub(r'[\s,.!?~·\-]', '', word['word'])

                    if word_clean:
                        seg_words.append(word)
                        matched_chars += len(word_clean)

                    word_idx += 1

                if seg_words:
                    start_time = seg_words[0]['start']
                    end_time = seg_words[-1]['end']
                else:
                    total_segs = len(subtitle_segments)
                    start_time = (seg_idx / total_segs) * audio_duration
                    end_time = ((seg_idx + 1) / total_segs) * audio_duration

                mapped_segments.append({
                    'index': seg_idx + 1,
                    'text': seg_text,
                    'start': round(start_time, 2),
                    'end': round(end_time, 2)
                })

                logger.debug(f"  #{seg_idx+1}: {start_time:.2f}s ~ {end_time:.2f}s | '{seg_text[:20]}'")

        # 타임스탬프 정규화
        logger.debug("[Faster-Whisper] 타임스탬프 정규화...")

        # 1단계: duration이 양수인지 확인 및 수정
        for i, seg in enumerate(mapped_segments):
            duration = seg['end'] - seg['start']
            if duration <= 0:
                seg['end'] = round(seg['start'] + 0.3, 2)
                logger.debug(f"  [수정] #{i+1}: duration {duration:.2f}s → 0.3s")

        # 2단계: 역행(overlap) 수정
        for i in range(1, len(mapped_segments)):
            prev_end = mapped_segments[i-1]['end']
            curr_start = mapped_segments[i]['start']

            if curr_start < prev_end:
                overlap = prev_end - curr_start
                old_start = curr_start
                new_start = round(prev_end + 0.02, 2)

                seg_text = mapped_segments[i]['text']
                seg_chars = len(re.sub(r'[\s,.!?~·\-]', '', seg_text))
                min_duration_by_chars = max(0.3, seg_chars * 0.12)

                original_duration = mapped_segments[i]['end'] - curr_start
                actual_duration = max(original_duration, min_duration_by_chars)
                new_end = round(new_start + actual_duration, 2)

                if new_end > audio_duration:
                    new_end = round(audio_duration - 0.02, 2)
                    if new_end <= new_start:
                        new_end = round(new_start + min_duration_by_chars, 2)

                mapped_segments[i]['start'] = new_start
                mapped_segments[i]['end'] = new_end
                logger.debug(f"  [역행 수정] #{i+1}: {old_start:.2f}s → {new_start:.2f}s")

        # 3단계: 전체 스케일링
        last_seg = mapped_segments[-1]
        if last_seg['end'] > audio_duration:
            current_total = last_seg['end']
            target_total = audio_duration - 0.02
            scale_factor = target_total / current_total if current_total > 0 else 1.0

            logger.debug(f"  [스케일링] 전체 축소: {current_total:.2f}s → {target_total:.2f}s")

            for seg in mapped_segments:
                seg['start'] = round(seg['start'] * scale_factor, 2)
                seg['end'] = round(seg['end'] * scale_factor, 2)

                seg_text = seg['text']
                seg_chars = len(re.sub(r'[\s,.!?~·\-]', '', seg_text))
                min_duration = max(0.2, seg_chars * 0.08)

                if seg['end'] - seg['start'] < min_duration:
                    seg['end'] = round(seg['start'] + min_duration, 2)

        # 4단계: 최종 검증
        for i, seg in enumerate(mapped_segments):
            if seg['start'] < 0:
                seg['start'] = 0

            seg_text = seg['text']
            seg_chars = len(re.sub(r'[\s,.!?~·\-]', '', seg_text))
            min_duration = max(0.2, seg_chars * 0.08)

            if seg['end'] <= seg['start']:
                seg['end'] = round(seg['start'] + min_duration, 2)
            elif seg['end'] - seg['start'] < min_duration:
                seg['end'] = round(seg['start'] + min_duration, 2)

            if seg['end'] > audio_duration:
                seg['end'] = round(audio_duration - 0.01, 2)

        logger.info("[Faster-Whisper] 최종 세그먼트:")
        for seg in mapped_segments:
            logger.debug(f"  #{seg['index']}: {seg['start']:.2f}s ~ {seg['end']:.2f}s | '{seg['text'][:20]}'")

        # 결과 구성
        voice_start = mapped_segments[0]['start'] if mapped_segments else 0
        voice_end = mapped_segments[-1]['end'] if mapped_segments else audio_duration

        timestamps = {
            'audio_duration': audio_duration,
            'voice_start': voice_start,
            'voice_end': voice_end,
            'segments': mapped_segments
        }

        logger.info("[Faster-Whisper] 분석 완료!")
        logger.info(f"  - voice_start: {voice_start:.2f}초")
        logger.info(f"  - voice_end: {voice_end:.2f}초")
        logger.info(f"  - 매핑된 세그먼트: {len(mapped_segments)}개")
        logger.info("=" * 60)

        return timestamps

    except Exception as e:
        ui_controller.write_error_log(e)
        logger.error(f"[Faster-Whisper 오류] {str(e)}", exc_info=True)

        try:
            if subtitle_segments is None:
                subtitle_segments = _split_text_naturally(app, transcript_text)

            audio = AudioSegment.from_file(tts_path)
            audio_duration = len(audio) / 1000.0
        except Exception as audio_err:
            logger.warning(f"[Faster-Whisper 폴백] 오디오 로드 실패: {audio_err}")
            audio_duration = 0.0

        logger.info("[Faster-Whisper] 실패 → 글자 수 비례 폴백 사용")

        return _create_char_proportional_timestamps(
            app, tts_path, subtitle_segments, audio_duration
        )


def _create_char_proportional_timestamps(app, tts_path, subtitle_segments, audio_duration):
    """
    글자 수 비례 타임스탬프 생성 (Whisper 실패시 폴백)
    """
    logger.info("[글자 수 비례] 타임스탬프 생성...")

    # 앞/뒤 무음 감지
    try:
        audio = AudioSegment.from_file(tts_path)
        leading_silence_ms = detect_leading_silence(audio, silence_threshold=-40, chunk_size=10)
        voice_start = min(leading_silence_ms / 1000.0, 0.3)
        trailing_silence_ms = detect_leading_silence(audio.reverse(), silence_threshold=-40, chunk_size=10)
        voice_end = max(audio_duration - (trailing_silence_ms / 1000.0), voice_start + 0.5)
    except Exception as e:
        logger.debug(f"[글자 수 비례] 무음 감지 실패, 기본값 사용: {e}")
        voice_start = 0.0
        voice_end = audio_duration

    effective_duration = voice_end - voice_start

    # 글자 수 계산
    char_counts = []
    for seg_text in subtitle_segments:
        clean_text = re.sub(r'[\s,.!?~·\-]', '', seg_text)
        char_counts.append(max(1, len(clean_text)))

    total_chars = sum(char_counts)

    # 세그먼트별 시간 할당
    mapped_segments = []
    current_time = voice_start

    for seg_idx, seg_text in enumerate(subtitle_segments):
        char_ratio = char_counts[seg_idx] / total_chars
        segment_duration = effective_duration * char_ratio

        start_time = current_time
        end_time = current_time + segment_duration

        if seg_idx == len(subtitle_segments) - 1:
            end_time = voice_end

        mapped_segments.append({
            'index': seg_idx + 1,
            'text': seg_text,
            'start': round(start_time, 2),
            'end': round(end_time, 2)
        })

        logger.debug(f"  #{seg_idx+1}: {start_time:.2f}s ~ {end_time:.2f}s | '{seg_text[:15]}...' ({char_counts[seg_idx]}자)")
        current_time = end_time

    # 마지막 자막 끝을 오디오 끝에 맞춤
    if mapped_segments:
        mapped_segments[-1]['end'] = round(audio_duration - 0.02, 2)

    logger.info(f"[글자 수 비례] 완료 ({len(mapped_segments)}개 세그먼트)")

    return {
        'audio_duration': audio_duration,
        'voice_start': voice_start,
        'voice_end': voice_end,
        'segments': mapped_segments,
        'method': 'char_proportional'
    }


def analyze_tts_with_gemini(app, tts_path, transcript_text, subtitle_segments=None):
    """
    Faster-Whisper STT로 대체됨 (무료, 로컬, 빠름)
    기존 Gemini Audio Understanding 대신 Faster-Whisper 사용
    """
    return analyze_tts_with_whisper(app, tts_path, transcript_text, subtitle_segments)
