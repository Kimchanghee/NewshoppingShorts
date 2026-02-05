"""
Subtitle Handler for Batch Processing

Contains subtitle generation and synchronization functions.
"""

import os
import json
import re
from typing import List, Dict, Any
from datetime import datetime

from core.video.CreateFinalVideo import create_subtitle_clips_improved
from .utils import _split_text_naturally, _extract_text_from_response, _translate_error_message
from caller import ui_controller
from utils.logging_config import get_logger
import config

logger = get_logger(__name__)


def create_subtitle_clips_for_speed(app, video_duration: float):
    """Generate subtitle clips optimized for speed adjustments."""
    logger.info("[자막 생성] 영상 길이: %.2f초, 자막 세그먼트: %d개",
                video_duration,
                len(app._per_line_tts) if hasattr(app, '_per_line_tts') and app._per_line_tts else 0)

    # Log segment timing details
    if hasattr(app, '_per_line_tts') and app._per_line_tts:
        for i, entry in enumerate(app._per_line_tts):
            if isinstance(entry, dict):
                text_preview = (entry.get('text', '') or '')[:20]
                start = entry.get('start', 0)
                end = entry.get('end', 0)
                logger.info("  자막 #%d: %.2f~%.2fs '%s'", i + 1, start, end, text_preview)

    try:
        _ensure_gemini_timestamps_synced(app)
    except (ValueError, TypeError, KeyError, AttributeError) as sync_exc:
        logger.warning("[자막 생성] Gemini 싱크 스킵: %s", sync_exc)

    # Post-sync validation: log final timing state before clip creation
    sync_info = getattr(app, 'tts_sync_info', {}) or {}
    final_source = sync_info.get('timestamps_source', 'unknown') if isinstance(sync_info, dict) else 'unknown'
    logger.info("[자막 싱크 검증] 타이밍 소스: %s", final_source)
    if hasattr(app, '_per_line_tts') and app._per_line_tts:
        seg_count = len(app._per_line_tts)
        first = app._per_line_tts[0] if app._per_line_tts else {}
        last = app._per_line_tts[-1] if app._per_line_tts else {}
        first_start = first.get('start', 0) if isinstance(first, dict) else 0
        last_end = last.get('end', 0) if isinstance(last, dict) else 0
        coverage = last_end - first_start
        gap = video_duration - last_end if last_end > 0 else video_duration
        logger.info("[자막 싱크 검증] 세그먼트: %d개, 범위: %.3f~%.3fs (커버리지: %.1fs), 영상 끝까지 여백: %.1fs",
                    seg_count, first_start, last_end, coverage, gap)
        # Warn if subtitles end significantly before video ends (possible sync issue)
        if gap > 3.0 and coverage > 0:
            logger.warning("[자막 싱크 경고] 자막이 영상보다 %.1f초 일찍 끝남 - 싱크 확인 필요", gap)
        # Warn if subtitles extend beyond video duration
        if last_end > video_duration + 0.5:
            logger.warning("[자막 싱크 경고] 자막이 영상보다 %.1f초 넘어감", last_end - video_duration)

    clips = create_subtitle_clips_improved(app, video_duration)
    if clips:
        logger.info("[자막 생성] 자막 클립 %d개 생성 완료", len(clips))
    else:
        logger.warning("[자막 생성] 자막 클립 생성 실패 (0개)")
    return clips


def _parse_gemini_timestamps(app, response_text, segments):
    """Gemini 응답에서 타임스탬프 추출 - 순서 보장 및 중복 방지"""
    timestamps = []

    try:
        # JSON 블록 추출
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            data = json.loads(json_match.group())

            # ★★★ 핵심: Gemini가 분석한 실제 음성 시작/종료 시점 추출 ★★★
            audio_duration = data.get('audio_duration', 0)
            voice_start = data.get('voice_start', 0)
            voice_end = data.get('voice_end', 0)

            logger.info(f"[Gemini Audio Understanding] 음성 분석 결과: 오디오 파일 길이={audio_duration:.3f}초, "
                        f"실제 음성 시작={voice_start:.3f}초, 실제 음성 종료={voice_end:.3f}초, "
                        f"실제 음성 길이={voice_end - voice_start:.3f}초")

            # app에 voice_start, voice_end 저장 (나중에 싱크 보정에 사용)
            app._gemini_voice_start = voice_start
            app._gemini_voice_end = voice_end
            app._gemini_audio_duration = audio_duration

            # 타임스탬프 임시 저장 (정렬 및 검증용)
            temp_timestamps = []

            for seg_data in data.get('segments', []):
                idx = seg_data.get('index', 0) - 1
                seg_start = seg_data.get('start')
                seg_end = seg_data.get('end')

                # null 처리 (Gemini가 찾지 못한 구간)
                if seg_start is None or seg_end is None:
                    logger.warning(f"[타임스탬프 파싱] 구간 찾지 못함 (index {idx+1})")
                    continue

                start = float(seg_start)
                end = float(seg_end)

                # 유효성 검증
                if end <= start:
                    logger.warning(f"[타임스탬프 파싱] 잘못된 시간 범위 무시: {start}~{end}초 (index {idx+1})")
                    continue

                duration = end - start
                if duration < 0.05:  # 50ms 미만은 무시
                    logger.warning(f"[타임스탬프 파싱] 너무 짧은 구간 무시: {duration:.3f}초 (index {idx+1})")
                    continue

                # 범위 내 index만 처리
                if 0 <= idx < len(segments):
                    temp_timestamps.append({
                        'idx': idx,
                        'text': segments[idx],
                        'start': start,
                        'end': end,
                        'duration': duration
                    })
                else:
                    logger.warning(f"[타임스탬프 파싱] 범위 초과 index 무시: {idx+1}/{len(segments)}")

            # start 시간 순으로 정렬 (1.2배속 순서 보장)
            temp_timestamps.sort(key=lambda x: x['start'])

            # 중복 제거 (같은 idx는 첫 번째 것만 유지)
            seen_indices = set()
            for ts in temp_timestamps:
                if ts['idx'] not in seen_indices:
                    seen_indices.add(ts['idx'])
                    timestamps.append(ts)
                else:
                    logger.warning(f"[타임스탬프 파싱] 중복 index 무시: {ts['idx']+1}")

            logger.info(f"[타임스탬프 파싱] JSON 파싱 성공 - {len(timestamps)}/{len(segments)}개 추출")

            # ★★★ voice_start/voice_end 검증 및 세그먼트 보정 ★★★
            if timestamps and voice_start > 0:
                first_seg_start = timestamps[0]['start']
                last_seg_end = timestamps[-1]['end']

                logger.debug(f"[Audio Understanding 검증] voice_start: {voice_start:.3f}s vs 첫 세그먼트 start: {first_seg_start:.3f}s, "
                            f"voice_end: {voice_end:.3f}s vs 마지막 세그먼트 end: {last_seg_end:.3f}s")

                # 첫 세그먼트 start와 voice_start 차이 계산
                start_diff = first_seg_start - voice_start
                end_diff = last_seg_end - voice_end

                # 허용 오차: 0.1초
                TOLERANCE = 0.1

                if abs(start_diff) > TOLERANCE:
                    logger.info(f"[Audio Understanding] 시작점 불일치: {start_diff:+.3f}초 차이 -> 모든 세그먼트에 -{start_diff:.3f}초 오프셋 적용")

                    # 모든 세그먼트에 오프셋 적용 (voice_start 기준으로 정렬)
                    for ts in timestamps:
                        ts['start'] = max(0, ts['start'] - start_diff)
                        ts['end'] = max(ts['start'] + 0.1, ts['end'] - start_diff)

                    logger.debug(f"[Audio Understanding] 보정 후 첫 세그먼트 start: {timestamps[0]['start']:.3f}s")
                else:
                    logger.debug(f"[Audio Understanding] 시작점 일치 (오차 {start_diff:+.3f}초)")

                if abs(end_diff) > TOLERANCE:
                    logger.debug(f"[Audio Understanding] 종료점 불일치: {end_diff:+.3f}초 차이 (참고용)")
                else:
                    logger.debug(f"[Audio Understanding] 종료점 일치 (오차 {end_diff:+.3f}초)")

            # 누락된 세그먼트 확인
            if len(timestamps) < len(segments):
                missing_indices = [i for i in range(len(segments)) if i not in seen_indices]
                logger.warning(f"[타임스탬프 파싱] 누락된 세그먼트: {len(missing_indices)}개 (index {[i+1 for i in missing_indices]})")

        else:
            logger.debug(f"[타임스탬프 파싱] JSON 형식 아님, 텍스트 파싱 시도")

    except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
        ui_controller.write_error_log(e)
        logger.exception(f"[타임스탬프 파싱 오류] {str(e)}")

    return timestamps


def _merge_gemini_timestamps_into_metadata(app, subtitle_segments, timestamps):
    """Merge Gemini timestamps into TTS metadata for subtitle synchronization"""
    if not app or not timestamps:
        return

    per_line = list(getattr(app, "_per_line_tts", []) or [])
    subtitle_segments = subtitle_segments or []

    sync_info = getattr(app, "tts_sync_info", {}) or {}
    audio_duration = None
    audio_start_offset = 0.0
    if isinstance(sync_info, dict):
        audio_duration = (
            sync_info.get("speeded_duration")
            or sync_info.get("original_duration")
        )
        # ★ 앞무음 오프셋: Gemini TTS 특성상 앞에 무음이 있음
        # audio_start_offset이 없으면 start_silence 사용 (하위 호환성)
        audio_start_offset = sync_info.get("audio_start_offset", sync_info.get("start_silence", 0.0))

    default_path = None
    default_speaker = None
    default_is_narr = False
    if per_line:
        sample_entry = per_line[0]
        if isinstance(sample_entry, dict):
            default_path = sample_entry.get("path")
            default_speaker = sample_entry.get("speaker")
            default_is_narr = sample_entry.get("is_narr", False)
    else:
        if isinstance(sync_info, dict):
            default_path = sync_info.get("file_path")
        default_speaker = getattr(app, "fixed_tts_voice", None)

    # 타임스탬프를 idx 기준 딕셔너리로 변환 (순서 무관 매칭)
    timestamps_by_idx = {}
    if timestamps:
        for ts in timestamps:
            ts_idx = ts.get('idx')
            if ts_idx is not None:
                timestamps_by_idx[ts_idx] = ts

    total_entries = len(subtitle_segments) if subtitle_segments else max(len(per_line or []), len(timestamps or []))
    if total_entries == 0:
        return

    updated: List[Dict[str, Any]] = []
    # Gemini 타임스탬프는 이미 앞무음을 고려했으므로 0.0에서 시작
    # (Gemini가 원본 파일 분석 시 앞무음을 인식하고 타임스탬프에 반영함)
    # 오프셋은 fallback(글자 수 기반)에서만 적용됨
    last_end = 0.0

    for idx in range(total_entries):
        if per_line and idx < len(per_line) and isinstance(per_line[idx], dict):
            base = dict(per_line[idx])
        elif per_line and isinstance(per_line[-1], dict):
            base = dict(per_line[-1])
        else:
            base = {
                "path": default_path,
                "speaker": default_speaker,
                "is_narr": default_is_narr,
            }

        base["idx"] = idx

        if subtitle_segments and idx < len(subtitle_segments):
            base["text"] = subtitle_segments[idx].strip()
        elif idx in timestamps_by_idx and timestamps_by_idx[idx].get("text"):
            base["text"] = str(timestamps_by_idx[idx]["text"]).strip()
        else:
            base["text"] = (base.get("text") or "").strip()

        if not base.get("path") and default_path:
            base["path"] = default_path
        if not base.get("speaker") and default_speaker:
            base["speaker"] = default_speaker
        base["is_narr"] = base.get("is_narr", default_is_narr)

        # idx 기반 매칭 (순서 보장)
        if idx in timestamps_by_idx:
            ts = timestamps_by_idx[idx]
            # ★★★ 핵심 수정: audio_start_offset 적용 ★★★
            # TTS 앞무음이 있으면 자막 시작도 그만큼 뒤로 밀어야 함
            raw_start = float(ts.get("start", 0.0))
            raw_end = float(ts.get("end", raw_start))
            start = raw_start + audio_start_offset  # 앞무음 오프셋 적용
            end = max(start + 0.05, raw_end + audio_start_offset)  # 앞무음 오프셋 적용
        else:
            # 타임스탬프 누락 시 추정 (이전 세그먼트 끝에서 시작)
            orig_start = base.get("start")
            orig_end = base.get("end")
            # ★★★ fallback에도 audio_start_offset 적용 ★★★
            if isinstance(orig_start, (int, float)):
                start = float(orig_start) + audio_start_offset
            else:
                start = last_end
            if start < last_end:
                start = last_end + 0.05  # 최소 50ms 간격
            if isinstance(orig_start, (int, float)) and isinstance(orig_end, (int, float)):
                duration_hint = max(0.3, float(orig_end) - float(orig_start))
            else:
                text_len = len(base.get("text", ""))
                duration_hint = max(0.5, text_len * 0.08)  # 글자당 80ms
            end = start + duration_hint

        # ★★★ 클램핑 완화: offset 적용된 end가 audio_duration을 약간 초과해도 허용 ★★★
        # audio_duration은 배속 후 파일 길이이고, offset이 있으면 마지막 구간이 잘릴 수 있음
        # 따라서 offset만큼 여유를 두고 클램핑 (최대 0.5초 초과까지 허용)
        max_allowed_end = audio_duration + audio_start_offset + 0.2 if audio_duration else None
        if max_allowed_end is not None and end > max_allowed_end:
            end = max(start + 0.3, max_allowed_end)
            logger.debug(f"[클램핑] end {end:.2f}s -> {max_allowed_end:.2f}s (audio_dur={audio_duration:.2f}s, offset={audio_start_offset:.2f}s)")

        base["start"] = start
        base["end"] = end
        updated.append(base)
        last_end = end

    # Gemini 타임스탬프에서 실제 음성 종료 시점 추출
    actual_audio_end = 0.0
    if timestamps:
        # 마지막 타임스탬프의 end 시간 = 실제 음성이 끝나는 시점
        last_timestamp = timestamps[-1]
        raw_audio_end = float(last_timestamp.get("end", 0.0))
        # ★★★ audio_start_offset 적용 ★★★
        actual_audio_end = raw_audio_end + audio_start_offset
        logger.info(f"[Gemini 오디오 분석] 실제 음성 종료: {actual_audio_end:.2f}초 (offset: {audio_start_offset:.2f}초)")

    # ★ 핵심 수정: 마지막 자막 end 시간 강제 변경 제거 ★
    # Gemini가 분석한 정확한 종료 시점을 존중
    # 기존 코드는 마지막 자막을 오디오 파일 끝까지 늘려서 싱크가 깨졌음
    # audio_duration은 파일 길이(뒷무음 포함)이므로 Gemini 분석 결과보다 길 수 있음
    # 마지막 자막이 start보다 짧으면 최소 0.3초 보장
    if updated:
        last_entry = updated[-1]
        if last_entry["end"] <= last_entry["start"]:
            last_entry["end"] = last_entry["start"] + 0.3
            logger.debug(f"[Subtitles] 마지막 자막 최소 길이 보정: {last_entry['start']:.2f}s-{last_entry['end']:.2f}s")

    app._per_line_tts = updated

    # ========== [SYNC DEBUG] 최종 _per_line_tts 상세 출력 ==========
    audio_dur_str = f"{audio_duration:.3f}초" if audio_duration else "N/A"
    actual_end_str = f"{actual_audio_end:.3f}초" if actual_audio_end > 0 else "N/A"
    last_end = updated[-1].get('end', 0) if updated else 0
    logger.info(f"[SYNC DEBUG] _merge_gemini_timestamps 완료 - {len(updated)}개 세그먼트, "
                f"audio_duration={audio_dur_str}, offset={audio_start_offset:.3f}초, "
                f"actual_audio_end={actual_end_str}, 마지막 자막 end={last_end:.3f}초")
    for i, entry in enumerate(updated):
        text_preview = entry.get('text', '')[:15] if entry.get('text') else f"seg{i}"
        start = entry.get('start', 0)
        end = entry.get('end', 0)
        duration = end - start
        logger.debug(f"  #{i+1}: {start:.3f}s - {end:.3f}s ({duration:.3f}s) '{text_preview}'")

    if isinstance(sync_info, dict):
        sync_info["timestamps_source"] = "gemini"
        sync_info["timestamps_count"] = len(timestamps)
        # 실제 음성 종료 시점 저장 (CTA 보호용)
        if actual_audio_end > 0:
            sync_info["actual_audio_end"] = actual_audio_end
        app.tts_sync_info = sync_info


def _ensure_gemini_timestamps_synced(app):
    """Ensure Gemini timestamps are synchronized with TTS metadata"""
    if not app:
        return

    sync_info = getattr(app, "tts_sync_info", {}) or {}
    if not isinstance(sync_info, dict):
        return

    # 이미 Gemini 분석이 완료되었거나 스케일링 처리된 경우 건너뛰기
    timestamps_source = sync_info.get("timestamps_source", "")
    speed_ratio = sync_info.get("speed_ratio", 1.0)
    speeded_duration = sync_info.get("speeded_duration")

    # ★ no_gemini_analysis + speed_ratio>1 → 강제 스케일링 필요
    # 이전 버전에서 스케일링 없이 저장된 세션 데이터 호환성 처리
    if timestamps_source == "no_gemini_analysis" and speed_ratio > 1.0 and speeded_duration:
        logger.info(f"[Gemini Sync] no_gemini_analysis + speed_ratio={speed_ratio} 감지 - 강제 스케일링 수행")
        from core.video.CreateFinalVideo import _rescale_tts_metadata_to_duration
        _rescale_tts_metadata_to_duration(app, speeded_duration)
        sync_info["timestamps_source"] = "force_scaled_from_no_gemini"
        app.tts_sync_info = sync_info
        logger.info(f"[Gemini Sync] 메타데이터를 {speeded_duration:.3f}초에 맞게 스케일링 완료")
        return

    # scaled_from_existing_speeded: 기존 1.2x 파일 재사용 시 스케일링 완료
    # scaled_no_gemini: Gemini 분석 없이 스케일링 완료
    # force_scaled_from_no_gemini: 이전 버전 호환성 강제 스케일링 완료
    # gemini_scaled: 원본 파일 분석 후 1/1.2 스케일링 완료
    # segment_by_segment: ★ 레퍼런스 방식 - 세그먼트별 생성으로 이미 100% 정확한 타이밍 ★
    # whisper_analysis: ★ Whisper 분석 완료 - 100% 정확한 타이밍 ★
    if timestamps_source in ("gemini", "scaled_fallback", "scaled_speeded",
                              "gemini_speeded", "fallback", "scaled_from_existing_speeded",
                              "scaled_no_gemini", "force_scaled_from_no_gemini", "gemini_scaled",
                              "segment_by_segment", "whisper_analysis"):
        logger.debug(f"[Gemini Sync] 이미 처리됨 (source: {timestamps_source})")
        return

    # no_gemini_analysis이지만 speed_ratio<=1이면 스케일링 불필요
    if timestamps_source == "no_gemini_analysis" and speed_ratio <= 1.0:
        logger.debug(f"[Gemini Sync] 스케일링 불필요 (source: {timestamps_source}, speed_ratio={speed_ratio})")
        return

    # ★★★ Gemini 오디오 분석 제거 - 세그먼트별 TTS에서 이미 정확한 타이밍 확보 ★★★
    # API 호출 절약: 세그먼트별 방식은 각 세그먼트의 실제 길이를 측정하므로
    # Gemini 오디오 분석이 불필요함. 기존 타임스탬프를 그대로 사용.
    logger.info(f"[Gemini Sync] Gemini 오디오 분석 스킵 - 세그먼트별 타이밍 사용")

    # 기존 메타데이터가 있으면 그대로 사용
    if hasattr(app, '_per_line_tts') and app._per_line_tts:
        logger.debug(f"[Gemini Sync] 기존 타이밍 유지: {len(app._per_line_tts)}개 세그먼트")
        sync_info["timestamps_source"] = "segment_timing_preserved"
        app.tts_sync_info = sync_info
    return
