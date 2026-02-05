"""
TTS Speed Processing Module
============================
TTS 오디오의 배속 처리를 담당하는 모듈입니다.

주요 기능:
- TTS 오디오 1.2배속 적용 (ffmpeg atempo 또는 pydub)
- 세그먼트별 TTS 배속 처리
- 메타데이터 타임스탬프 스케일링
- 앞무음 오프셋 감지 및 보정

사용되는 곳:
- processor.py (배치 처리 워크플로우)
- CreateFinalVideo.py (최종 영상 생성)
"""

import os
import secrets
import subprocess
import traceback
from datetime import datetime

from pydub import AudioSegment

from core.video import VideoTool
from core.video.CreateFinalVideo import _rescale_tts_metadata_to_duration
from .audio_utils import _ensure_pydub_converter, _write_wave_fallback
from .whisper_analyzer import analyze_tts_with_whisper
from caller import ui_controller
from utils.logging_config import get_logger

logger = get_logger(__name__)


def _apply_speed_to_segment_tts(app, tts_path):
    """
    세그먼트별 TTS 처리
    - _generate_tts_for_batch에서 이미 1.2배속 적용됨
    - 여기서는 기존 tts_sync_info 유지하고 검증만 수행
    """
    try:
        logger.info(f"[세그먼트 TTS] 입력 파일: {os.path.basename(tts_path)}")

        if not tts_path or not os.path.exists(tts_path):
            logger.error(f"[세그먼트 TTS] 오류: 파일 없음")
            return None

        # 오디오 길이 측정
        audio = AudioSegment.from_wav(tts_path)
        actual_duration = len(audio) / 1000.0

        logger.debug(f"[세그먼트 TTS] 파일 길이: {actual_duration:.3f}초")

        # 기존 tts_sync_info 유지 (이미 1.2배속 적용됨)
        existing_sync_info = getattr(app, 'tts_sync_info', {}) or {}
        existing_speed_ratio = existing_sync_info.get('speed_ratio', 1.0)

        if existing_speed_ratio == 1.2:
            logger.info(f"[세그먼트 TTS] 1.2배속 이미 적용됨 (기존 설정 유지) - "
                       f"원본: {existing_sync_info.get('original_duration', 0):.3f}초, "
                       f"배속: {existing_sync_info.get('speeded_duration', 0):.3f}초")
        else:
            app.tts_sync_info = {
                'original_duration': actual_duration,
                'speeded_duration': actual_duration,
                'speed_ratio': 1.0,
                'start_silence': 0.0,
                'audio_start_offset': 0.0,
                'file_path': tts_path,
                'timestamps_source': 'segment_by_segment',
            }

        # 타이밍 확인
        if hasattr(app, '_per_line_tts') and app._per_line_tts:
            logger.debug(f"[세그먼트 TTS] 자막 타이밍 (1.2배속 적용됨)")
            for entry in app._per_line_tts:
                if isinstance(entry, dict):
                    start = entry.get('start', 0)
                    end = entry.get('end', 0)
                    text_preview = entry.get('text', '')[:20]
                    logger.debug(f"  #{entry.get('idx', 0)+1}: {start:.3f}s ~ {end:.3f}s | '{text_preview}'")

        logger.info(f"[세그먼트 TTS] 완료 - 1.2배속 + 레퍼런스 방식, "
                   f"오디오 길이: {actual_duration:.3f}초, 배속 비율: {existing_sync_info.get('speed_ratio', 1.0)}x")

        return tts_path

    except (OSError, IOError, ValueError) as e:
        ui_controller.write_error_log(e)
        logger.exception(f"[세그먼트 TTS 오류] {str(e)}")
        return tts_path if 'tts_path' in locals() else None


def combine_tts_files_with_speed(app, target_duration=None):
    """
    TTS 파일에 1.2배속 적용 - 무음 추가 없이

    이미 처리된 TTS 소스 타입별 처리:
    - segment_by_segment: Gemini 분석 불필요, 타이밍만 스케일링
    - segment_by_segment_measured: 이미 완료됨
    - gemini_audio_analysis: 재처리 불필요
    - whisper_analysis: 재처리 불필요
    - (char_proportional_fallback 제거됨 - Whisper 필수)
    """
    try:
        logger.info(f"[TTS 배속 처리] 시작 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if not hasattr(app, '_per_line_tts') or not app._per_line_tts:
            logger.error("[TTS 배속] 오류: _per_line_tts가 없습니다")
            return None

        sync_info = getattr(app, 'tts_sync_info', {}) or {}
        timestamps_source = sync_info.get('timestamps_source', '')

        # ★★★ 핵심 수정: 파일이 다르면 무조건 새로 분석 (더 엄격한 체크) ★★★
        current_tts_path = app._per_line_tts[0].get('path', '') if app._per_line_tts else ''
        saved_file_path = sync_info.get('file_path', '')

        # 파일 경로가 완전히 같지 않으면 무조건 재분석
        force_reanalyze = False
        if current_tts_path and saved_file_path:
            # 파일명만 비교 (경로가 다를 수 있음)
            current_filename = os.path.basename(current_tts_path)
            saved_filename = os.path.basename(saved_file_path)
            if current_filename != saved_filename:
                force_reanalyze = True
                logger.info(f"[TTS 배속] 파일 불일치 - 새 음성이므로 Whisper 재분석 필요: "
                           f"저장된={saved_filename}, 현재={current_filename}")

        # tts_sync_info가 비어있거나 timestamps_source가 없으면 재분석
        if not sync_info or not timestamps_source:
            force_reanalyze = True
            logger.debug(f"[TTS 배속] tts_sync_info 비어있음 - Whisper 재분석 필요")

        # ★★★ 핵심: force_reanalyze이면 모든 캐시 무시하고 새로 분석 ★★★
        if force_reanalyze:
            timestamps_source = ''
            sync_info = {}
            app.tts_sync_info = {}  # 이전 음성의 sync_info 완전 초기화
            logger.debug(f"[TTS 배속] tts_sync_info 초기화 완료 - 새 음성 분석 시작")

        if timestamps_source == 'segment_by_segment':
            logger.info("[TTS 배속] 세그먼트별 생성 방식 - 100% 정확한 타이밍")
            tts_path = app._per_line_tts[0]['path']
            return _apply_speed_to_segment_tts(app, tts_path)

        if timestamps_source == 'segment_by_segment_measured':
            tts_path = sync_info.get('file_path') or app._per_line_tts[0]['path']
            logger.info(f"[TTS 배속] 세그먼트별 실측 방식 - 이미 완료됨 (재처리 스킵), "
                       f"파일={os.path.basename(tts_path)}, 배속 후 길이={sync_info.get('speeded_duration', 0):.3f}초, "
                       f"세그먼트 수={sync_info.get('segment_count', 'N/A')}개")
            return tts_path

        if timestamps_source == 'gemini_audio_analysis':
            tts_path = sync_info.get('file_path') or app._per_line_tts[0]['path']
            logger.info(f"[TTS 배속] Gemini 오디오 분석 완료됨 - 재처리 스킵, "
                       f"파일={os.path.basename(tts_path)}, 배속 후 길이={sync_info.get('speeded_duration', 0):.3f}초")
            return tts_path

        if timestamps_source == 'whisper_analysis':
            tts_path = sync_info.get('file_path') or app._per_line_tts[0]['path']
            logger.info(f"[TTS 배속] Whisper 분석 완료됨 - 재처리 스킵, "
                       f"파일={os.path.basename(tts_path)}, 배속 후 길이={sync_info.get('speeded_duration', 0):.3f}초, "
                       f"세그먼트 수={sync_info.get('segment_count', 'N/A')}개 (100% 정확)")
            return tts_path

        tts_path = app._per_line_tts[0]['path']
        logger.debug(f"[TTS 배속] 입력 파일: {os.path.basename(tts_path)}")

        if not tts_path or not os.path.exists(tts_path):
            logger.error(f"[TTS 배속] 오류: 파일이 존재하지 않음")
            return None

        # 이미 배속된 파일인지 확인
        basename = os.path.basename(tts_path)
        if "speeded_tts_1.2x" in basename or "tts_speeded_" in basename:
            logger.info(f"[TTS 배속] 이미 배속된 파일 발견 - 메타데이터 스케일링 수행")

            speeded_audio = AudioSegment.from_wav(tts_path)
            actual_duration = len(speeded_audio) / 1000.0
            speed_ratio = 1.2

            existing_audio_offset = VideoTool._detect_audio_start_offset(tts_path)
            logger.debug(f"[앞무음 보정] 기존 배속 파일 앞 무음: {existing_audio_offset:.3f}초")

            _rescale_tts_metadata_to_duration(app, actual_duration, new_path=tts_path, start_offset=existing_audio_offset)

            app.tts_sync_info = {
                'original_duration': actual_duration * speed_ratio,
                'speeded_duration': actual_duration,
                'speed_ratio': speed_ratio,
                'start_silence': 0.0,
                'audio_start_offset': existing_audio_offset,
                'file_path': tts_path,
                'timestamps_source': 'scaled_from_existing_speeded',
            }

            logger.info(f"  배속 파일 길이: {actual_duration:.3f}초, 메타데이터 스케일링 완료 (offset: {existing_audio_offset:.3f}s)")
            return tts_path

        # 원본 오디오 로드
        audio = AudioSegment.from_wav(tts_path)
        original_duration = len(audio) / 1000.0

        logger.info(f"[원본 TTS 정보] 길이: {original_duration:.3f}초, 샘플레이트: {audio.frame_rate}Hz")

        # 1.2배속 적용
        speed_ratio = 1.2
        target_speed_duration = original_duration / speed_ratio

        logger.debug(f"[배속 계산] 배속 비율: {speed_ratio}x, 목표 길이: {target_speed_duration:.3f}초")

        ffmpeg_path = _ensure_pydub_converter()

        # 배속 적용
        try:
            new_frame_rate = int(audio.frame_rate * speed_ratio)
            speeded_audio = audio._spawn(
                audio.raw_data,
                overrides={"frame_rate": new_frame_rate}
            )
            speeded_audio = speeded_audio.set_frame_rate(44100)
        except (ValueError, TypeError, AttributeError) as speed_err:
            logger.warning(f"[TTS 배속] frame_rate 방식 실패, speedup 사용: {speed_err}")
            from pydub.effects import speedup
            speeded_audio = speedup(audio, playback_speed=speed_ratio)

        start_silence_ms = 0  # 무음 제거

        actual_duration = len(speeded_audio) / 1000.0

        logger.info(f"[배속 결과] 실제 길이: {actual_duration:.3f}초, 배속 비율: {original_duration/actual_duration:.3f}x")

        # 파일명 생성 및 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:21]
        random_suffix = secrets.token_hex(4)
        speeded_filename = f"speeded_tts_1.2x_{timestamp}_{random_suffix}.wav"
        speeded_path = os.path.join(app.tts_output_dir, speeded_filename)

        try:
            if ffmpeg_path:
                speeded_audio.export(speeded_path, format="wav", parameters=["-ar", "44100", "-ac", "2"])
            else:
                logger.warning("[export 대체] ffmpeg 경로를 찾지 못해 wave 모듈로 저장합니다.")
                _write_wave_fallback(speeded_audio, speeded_path, sample_rate=44100)
        except (OSError, IOError, subprocess.SubprocessError) as e:
            ui_controller.write_error_log(e)
            logger.warning(f"[export 폴백] ffmpeg export 실패, wave 모듈로 저장 시도: {e}")
            _write_wave_fallback(speeded_audio, speeded_path, sample_rate=44100)

        audio_start_offset = VideoTool._detect_audio_start_offset(speeded_path)
        logger.debug(f"[앞무음 보정] 배속 파일 앞 무음: {audio_start_offset:.3f}초")

        if hasattr(app, '_per_line_tts') and app._per_line_tts:
            for entry in app._per_line_tts:
                if isinstance(entry, dict):
                    entry['path'] = speeded_path

        app.tts_sync_info = {
            'original_duration': original_duration,
            'speeded_duration': actual_duration,
            'speed_ratio': speed_ratio,
            'start_silence': start_silence_ms / 1000.0,
            'audio_start_offset': audio_start_offset,
            'file_path': speeded_path,
            'original_tts_path': tts_path,
        }

        logger.info(f"[저장 완료] 파일명: {speeded_filename}, 최종 TTS 길이: {actual_duration:.3f}초")

        logger.debug("[TTS 배속] Gemini 오디오 분석 없이 메타데이터 스케일링")
        _rescale_tts_metadata_to_duration(app, actual_duration, new_path=speeded_path, start_offset=audio_start_offset)
        app.tts_sync_info['timestamps_source'] = 'scaled_no_gemini'
        logger.info(f"  메타데이터를 {actual_duration:.3f}초에 맞게 스케일링 완료 (offset: {audio_start_offset:.3f}s)")

        return speeded_path

    except (OSError, IOError, ValueError, TypeError) as e:
        ui_controller.write_error_log(e)
        logger.exception(f"[TTS 배속 치명적 오류] {str(e)}")
        if 'tts_path' in locals():
            return tts_path
        return None
