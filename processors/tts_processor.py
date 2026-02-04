"""
TTS Processing Module

This module handles text-to-speech generation and metadata building.
"""

import os
import re
from datetime import datetime
from typing import Any, Dict, List, Iterable

from utils.logging_config import get_logger
from utils.korean_text_processor import process_korean_script

logger = get_logger(__name__)

try:
    from google import genai
    from google.genai import types

    GENAI_SDK_AVAILABLE = True
    GENAI_TYPES_AVAILABLE = True
except Exception as e:
    logger.warning("Gemini SDK not available: %s", e)
    genai = None
    types = None
    GENAI_SDK_AVAILABLE = False
    GENAI_TYPES_AVAILABLE = False

try:
    # moviepy 1.x compatible imports
    from moviepy.editor import VideoFileClip

    MOVIEPY_AVAILABLE = True
except Exception as e:
    logger.warning("moviepy not available: %s", e)
    VideoFileClip = None
    MOVIEPY_AVAILABLE = False
from caller import ui_controller


class TTSProcessor:
    """
    Handles text-to-speech generation and metadata processing.

    This processor generates Korean TTS audio from translated scripts using
    Gemini's TTS API and builds timing metadata for subtitle synchronization.
    """

    def __init__(self, gui):
        """
        Initialize the TTSProcessor.

        Args:
            gui: Main GUI instance containing translation results and TTS settings
        """
        self.gui = gui

    def generate_tts_for_voice(self, voice: str):
        """
        Generate TTS audio for a specific voice with automatic length adjustment.

        Attempts to generate TTS that fits video duration (max 110% of video length).
        If TTS is too long, automatically reduces script and retries up to 3 times.

        Args:
            voice: Voice name/ID to use for TTS generation

        Returns:
            Tuple of (metadata list, duration, output_path)

        Raises:
            RuntimeError: If Gemini SDK unavailable or no translated script available
        """
        vm = getattr(self.gui, "voice_manager", None)
        voice_name = voice
        voice_label = voice
        if vm:
            profile = vm.get_voice_profile(voice)
            if profile:
                voice_name = profile.get("voice_name") or voice
                voice_label = profile.get("label", voice)

        if not (GENAI_SDK_AVAILABLE and GENAI_TYPES_AVAILABLE):
            raise RuntimeError(
                "Gemini SDK가 없거나 사용할 수 없어 TTS를 생성할 수 없습니다."
            )

        script = self.extract_clean_script_from_translation(max_len=2000)
        if not script:
            raise RuntimeError("No translated script available for TTS generation.")

        base_segments = self._split_script_for_tts(script, max_chars=9)
        base_script = "\n".join(base_segments) if base_segments else script

        video_duration = self.get_video_duration_helper()

        # 20초 이상 영상: TTS는 최대 20초까지 생성 (배속 후에도 충분)
        # 20초 미만 영상: TTS는 영상 길이에 맞춤
        if video_duration > 20.0:
            max_allowed = 20.0  # 1.2배속 후에도 20초 이하
            logger.info(
                "[TTS 제한] 영상 %.1f초 > 20초이므로 TTS 최대 20초까지 생성 (배속 후에도 충분)",
                video_duration,
            )
        else:
            max_allowed = video_duration - 0.5  # 짧은 영상: 영상 길이 기준
            logger.info(
                "[TTS 제한] 영상 %.1f초 <= 20초이므로 TTS는 영상에 맞춤", video_duration
            )

        attempts = 5  # 3에서 5회로 증가 (재시도 더 많이 허용)
        last_metadata = None
        last_duration = 0.0
        last_duration_after_speed = 0.0
        last_path = None
        # 제품 영상 감지 (영문 + 한국어 키워드)
        translation_text = (self.gui.translation_result or "").lower()
        is_product = any(
            keyword in translation_text
            for keyword in [
                "product",
                "purchase",
                "buy",
                "shop",
                "link",
                "제품",
                "상품",
                "구매",
                "링크",
                "확인해",
            ]
        )

        script_len_for_estimate = len(base_script.replace("\n", " "))
        estimated_tts_duration = script_len_for_estimate * 0.15
        estimated_after_speed = estimated_tts_duration / 1.2

        logger.info("[TTS 사전 확인] 허용 TTS(1.2배속): %.1f초 이하", max_allowed)
        logger.info(
            "[TTS 사전 확인] %d자는 약 %.1f초 예상",
            script_len_for_estimate,
            estimated_after_speed,
        )

        if max_allowed < 3.0:
            raise RuntimeError(
                f"영상 길이({video_duration:.1f}초)가 너무 짧아 TTS를 생성할 수 없습니다. "
                f"최소 4초 이상의 영상이 필요합니다."
            )

        if estimated_after_speed > max_allowed * 1.5:
            pre_reduction = max_allowed / estimated_after_speed
            base_script = self._trim_script_for_attempt(base_script, pre_reduction)
            base_segments = self._split_script_for_tts(base_script, max_chars=9)
            script_len_for_estimate = len(base_script.replace("\n", " "))
            logger.info(
                "[TTS 사전 축소] 예상 길이가 초과하여 스크립트를 %d%% 축소 (%d자)",
                int(pre_reduction * 100),
                len(base_script),
            )

        for attempt in range(attempts):
            if attempt == 0:
                segments_for_attempt = base_segments
                full_script = base_script
            else:
                if last_duration_after_speed > 0:
                    overshoot_ratio = last_duration_after_speed / max_allowed
                    reduction_rate = (1.0 / overshoot_ratio) * 0.95
                    reduction_rate = max(0.30, min(0.95, reduction_rate))
                    logger.info(
                        "[TTS 재시도 %d] 이전 생성 %.1f초가 목표 %.1f초 초과",
                        attempt + 1,
                        last_duration_after_speed,
                        max_allowed,
                    )
                    logger.info(
                        "  스크립트 %.1f%% 축소 (%d자)",
                        reduction_rate * 100,
                        int(len(base_script) * reduction_rate),
                    )
                else:
                    reduction_rate = 0.85**attempt

                trimmed = self._trim_script_for_attempt(base_script, reduction_rate)
                segments_for_attempt = self._split_script_for_tts(trimmed, max_chars=9)
                full_script = (
                    "\n".join(segments_for_attempt) if segments_for_attempt else trimmed
                )

            # CTA 추가 (모든 시도에서 적용 - 통합 후 2분할)
            # 선택된 CTA 라인 가져오기
            from ui.panels.cta_panel import get_selected_cta_lines

            cta_segments = get_selected_cta_lines(self.gui)
            cta_first_line = cta_segments[0] if cta_segments else "제품이 마음에"

            if is_product and cta_first_line not in full_script:
                # CTA 3줄을 한줄로 통합
                cta_text = " ".join(cta_segments)
                full_script += " " + cta_text

                # CTA 통합 후 2분할 (너무 길면 균등 분할)
                cta_combined = " ".join(cta_segments)
                cta_max_chars = 15  # 한 세그먼트 최대 글자수

                if len(cta_combined) <= cta_max_chars:
                    # 짧으면 한줄로
                    cta_final_segments = [cta_combined]
                else:
                    # 길면 2분할 (중간 지점에서 공백 기준 분할)
                    mid = len(cta_combined) // 2
                    # 중간 근처 공백 찾기
                    split_idx = cta_combined.rfind(" ", 0, mid + 5)
                    if split_idx <= 0:
                        split_idx = cta_combined.find(" ", mid)
                    if split_idx <= 0:
                        split_idx = mid

                    part1 = cta_combined[:split_idx].strip()
                    part2 = cta_combined[split_idx:].strip()
                    cta_final_segments = (
                        [part1, part2] if part1 and part2 else [cta_combined]
                    )

                segments_for_attempt = segments_for_attempt + cta_final_segments
                logger.info(
                    "[TTS CTA] 제품 영상 감지, CTA 통합 후 %d분할: %s",
                    len(cta_final_segments),
                    cta_final_segments,
                )

            if not segments_for_attempt:
                normalized_full = full_script.strip()
                segments_for_attempt = [normalized_full] if normalized_full else []

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:21]
            output_filename = (
                f"full_script_tts_{voice_name}_{timestamp}_try{attempt + 1}.wav"
            )
            output_path = os.path.join(self.gui.tts_output_dir, output_filename)
            self.gui.add_log(
                f"[TTS] Voice {voice_label} | attempt {attempt + 1} | {len(full_script)} chars"
            )

            # ★★★ TTS용 텍스트: 숫자→자연스러운 한국어, 영어→한글 ★★★
            # 자막에는 "7개"로 표시되지만, TTS는 "일곱 개"로 읽음
            tts_script = process_korean_script(full_script)

            try:
                response = self.gui.genai_client.models.generate_content(
                    model=self.gui.config.GEMINI_TTS_MODEL,
                    contents=[tts_script],
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=voice_name
                                )
                            )
                        ),
                    ),
                )
            except Exception as e:
                logger.error(f"[TTS API Error] {e}")
                if "404" in str(e) or "NotFound" in str(e):
                    raise RuntimeError(f"TTS 모델을 찾을 수 없습니다: {self.gui.config.GEMINI_TTS_MODEL}. config.py를 확인하세요.")
                elif "400" in str(e) or "InvalidArgument" in str(e):
                    raise RuntimeError(f"TTS 요청 파라미터가 잘못되었습니다: {e}")
                else:
                    raise e

            # Response 구조 검증 및 audio_data 추출
            try:
                audio_data = response.candidates[0].content.parts[0].inline_data.data
            except (IndexError, AttributeError) as e:
                logger.error("[TTS 오류] Gemini 응답 구조 오류: %s", e)
                logger.error("[TTS 오류] Response type: %s", type(response))
                if hasattr(response, "candidates"):
                    logger.error(
                        "[TTS 오류] Candidates count: %d",
                        len(response.candidates) if response.candidates else 0,
                    )
                raise RuntimeError(
                    f"Gemini TTS API 응답 구조가 예상과 다릅니다. "
                    f"오류: {str(e)}. API 키와 모델 설정을 확인해주세요."
                )

            from core.video.DynamicBatch import save_wave_file
            from core.video import VideoTool

            save_wave_file(self.gui, output_path, audio_data)

            tts_duration = VideoTool._wav_duration_sec(output_path)
            after_speed = tts_duration / 1.2

            # 오디오 앞 무음 감지 (자막 싱크용)
            audio_start_offset = VideoTool._detect_audio_start_offset(output_path)

            metadata = self.build_tts_metadata(
                full_script,
                tts_duration,
                output_path,
                voice_name,
                segments=segments_for_attempt,
                audio_start_offset=audio_start_offset,
            )
            if not metadata:
                metadata = [
                    {
                        "idx": 0,
                        "start": 0.0,
                        "end": tts_duration,
                        "path": output_path,
                        "speaker": voice_label,
                        "text": full_script[:200],
                        "is_narr": False,
                    }
                ]

            last_metadata = metadata
            last_duration = tts_duration
            last_duration_after_speed = after_speed
            last_path = output_path
            self.gui.add_log(
                f"[TTS] Result length {tts_duration:.2f}s (1.2x => {after_speed:.2f}s)"
            )

            if after_speed <= max_allowed:
                logger.info(
                    "[TTS 성공] %.1f초 <= %.1f초 (시도 %d/%d)",
                    after_speed,
                    max_allowed,
                    attempt + 1,
                    attempts,
                )
                return metadata, tts_duration, output_path

            shortage = after_speed - max_allowed
            logger.warning(
                "[TTS 길이 초과] %.1f초 > %.1f초 (초과: %.1f초)",
                after_speed,
                max_allowed,
                shortage,
            )
            self.gui.add_log(
                f"[TTS] Exceeds target length by {shortage:.1f}s, reducing script and retrying"
            )

        logger.warning("[TTS 실패] %d회 시도했으나 목표 길이에 맞추지 못함", attempts)
        logger.warning(
            "  최종 길이: %.1f초 (목표: %.1f초)", last_duration_after_speed, max_allowed
        )
        logger.warning("  초과: %.1f초", last_duration_after_speed - max_allowed)

        if last_duration_after_speed > max_allowed * 1.3:
            raise RuntimeError(
                f"TTS 길이({last_duration_after_speed:.1f}초)가 영상 길이({video_duration:.1f}초)를 너무 많이 초과합니다. "
                f"더 짧은 TTS를 생성할 수 없어 영상 제작을 중단합니다"
            )

        logger.warning("  하지만 강제로 진행합니다 (주의: 마지막 TTS가 잘릴 수 있음)")
        self.gui.add_log(
            f"[TTS Warning] Failed to meet target length after {attempts} attempts, using shortest version"
        )
        return last_metadata, last_duration, last_path

    def build_tts_metadata(
        self,
        script: str,
        total_duration: float,
        tts_path: str,
        speaker: str,
        max_chars: int = 12,
        segments: List[str] = None,
        audio_start_offset: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Build TTS metadata with timing information for subtitle synchronization.

        Uses Gemini's audio understanding API to analyze the generated TTS audio
        and extract accurate word-level timestamps for perfect audio-subtitle sync.

        Args:
            script: Full Korean script text
            total_duration: Total TTS audio duration in seconds
            tts_path: Path to generated TTS audio file
            speaker: Voice/speaker name used
            max_chars: Maximum characters per subtitle segment
            segments: Preferred subtitle segments to align with

        Returns:
            List of metadata dictionaries with timing and text for each segment
        """
        if not tts_path or total_duration <= 0:
            return []

        # Try to use Gemini Audio Understanding API for accurate timing
        logger.info(
            "[Audio Analysis] Gemini 오디오 이해 API로 정확한 타이밍 추출 중..."
        )
        audio_metadata = self._analyze_audio_with_gemini(
            tts_path, script, max_chars, subtitle_segments=segments
        )

        if audio_metadata:
            if segments:
                audio_metadata = self._align_metadata_to_segments(
                    audio_metadata, segments
                )
            logger.info(
                "[Audio Analysis] Gemini 분석 완료 - %d개 세그먼트 (정확한 싱크)",
                len(audio_metadata),
            )
            # Add common fields
            for idx, item in enumerate(audio_metadata):
                item["idx"] = idx
                item["path"] = tts_path
                item["speaker"] = speaker
                item["is_narr"] = False

            # 오디오 앞 무음 오프셋 적용 (자막-오디오 싱크 보정)
            first_start = audio_metadata[0]["start"]
            last_end = audio_metadata[-1]["end"]
            logger.debug(
                "[Audio Timing] Gemini 타임스탬프: %.2fs ~ %.2fs (총 %.2fs)",
                first_start,
                last_end,
                last_end - first_start,
            )
            logger.debug("[Audio Timing] 실제 오디오 길이: %.2fs", total_duration)
            logger.debug(
                "[Audio Timing] 오디오 앞 무음 오프셋: %.3fs", audio_start_offset
            )

            # Gemini 타임스탬프가 오디오 앞 무음을 고려하지 않았다면 오프셋 적용
            # Gemini가 0초부터 시작한다면 실제 음성은 audio_start_offset 후에 시작함
            # 따라서 자막 타임스탬프를 오프셋만큼 뒤로 밀어야 함
            if audio_start_offset > 0.05 and first_start < audio_start_offset:
                offset_to_apply = audio_start_offset - first_start
                logger.debug(
                    "[Audio Sync] 자막 타임스탬프 보정: +%.3fs (Gemini 시작: %.3fs, 실제 음성: %.3fs)",
                    offset_to_apply,
                    first_start,
                    audio_start_offset,
                )
                for item in audio_metadata:
                    item["start"] = item["start"] + offset_to_apply
                    item["end"] = item["end"] + offset_to_apply
                # 보정 후 확인
                first_start = audio_metadata[0]["start"]
                last_end = audio_metadata[-1]["end"]
                logger.debug(
                    "[Audio Sync] 보정 후 타임스탬프: %.2fs ~ %.2fs",
                    first_start,
                    last_end,
                )

            # 디버깅: 첫 3개와 마지막 3개 세그먼트 타임스탬프
            logger.debug("[Gemini Segments] 첫 3개:")
            for i, item in enumerate(audio_metadata[:3]):
                logger.debug(
                    "  %d. %.2f-%.2fs: '%s'",
                    i + 1,
                    item["start"],
                    item["end"],
                    item["text"][:30],
                )
            if len(audio_metadata) > 3:
                logger.debug("[Gemini Segments] 마지막 3개:")
                for i, item in enumerate(
                    audio_metadata[-3:], start=len(audio_metadata) - 2
                ):
                    logger.debug(
                        "  %d. %.2f-%.2fs: '%s'",
                        i,
                        item["start"],
                        item["end"],
                        item["text"][:30],
                    )
            # Merge short segments for better subtitle readability
            audio_metadata = self._merge_short_segments(audio_metadata, min_chars=6)
            return audio_metadata

        # Gemini Audio Understanding 실패 시 fallback 메타데이터 생성
        logger.warning("[Audio Analysis] Gemini 분석 실패 - fallback 메타데이터 생성")
        logger.warning("[Audio Analysis] 경고: 자막 싱크가 정확하지 않을 수 있습니다")
        logger.debug("[Audio Timing] 오디오 앞 무음 오프셋: %.3fs", audio_start_offset)

        # Fallback: 글자 수 기반 타이밍 계산 (오디오 오프셋 적용)
        fallback_metadata = []

        # 오프셋이 있으면 오디오 실제 재생 구간만 사용
        effective_start = audio_start_offset if audio_start_offset > 0.05 else 0.0
        effective_duration = total_duration - effective_start

        if segments and len(segments) > 0:
            # segments가 있으면 균등 분배 (오프셋 이후부터)
            segment_count = len(segments)
            time_per_segment = effective_duration / segment_count

            for idx, seg_text in enumerate(segments):
                start_time = effective_start + idx * time_per_segment
                end_time = effective_start + (idx + 1) * time_per_segment
                fallback_metadata.append(
                    {
                        "idx": idx,
                        "start": start_time,
                        "end": end_time,
                        "text": str(seg_text).strip(),
                        "path": tts_path,
                        "speaker": speaker,
                        "is_narr": False,
                    }
                )
            logger.info(
                "[Fallback] %d개 세그먼트 균등 분배 (각 %.2f초, 시작: %.2fs)",
                len(fallback_metadata),
                time_per_segment,
                effective_start,
            )
        else:
            # segments가 없으면 전체 스크립트를 하나로 (오프셋 적용)
            fallback_metadata.append(
                {
                    "idx": 0,
                    "start": effective_start,
                    "end": total_duration,
                    "text": script[:200],  # 최대 200자
                    "path": tts_path,
                    "speaker": speaker,
                    "is_narr": False,
                }
            )
            logger.info(
                "[Fallback] 단일 세그먼트 생성 (%.2fs-%.2fs)",
                effective_start,
                total_duration,
            )

        return fallback_metadata

    def _analyze_audio_with_gemini(
        self,
        audio_path: str,
        expected_script: str,
        max_chars: int = 12,
        subtitle_segments: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Analyze audio using Gemini's Audio Understanding API to extract accurate timestamps.

        Args:
            audio_path: Path to the audio file
            expected_script: Expected transcript text for validation
            max_chars: Maximum characters per subtitle segment
            subtitle_segments: Preferred subtitle splits to align with

        Returns:
            List of metadata dictionaries with accurate timing, or empty list on failure
        """
        try:
            if not (GENAI_SDK_AVAILABLE and GENAI_TYPES_AVAILABLE):
                return []

            if not os.path.exists(audio_path):
                logger.warning("[Audio Analysis] 오디오 파일 없음: %s", audio_path)
                return []

            # 1. Upload audio file to Gemini Files API
            logger.info(
                "[Audio Analysis] 오디오 파일 업로드 중... (%s)",
                os.path.basename(audio_path),
            )
            uploaded_file = self.gui.genai_client.files.upload(file=audio_path)
            logger.info("[Audio Analysis] 업로드 완료: %s", uploaded_file.name)

            # 2. Request detailed transcript with timestamps
            # Gemini can provide timestamps in format MM:SS or with word-level timing
            if subtitle_segments:
                segment_list = "\n".join(
                    f"{idx + 1}. {str(seg).strip()}"
                    for idx, seg in enumerate(subtitle_segments)
                    if str(seg).strip()
                )
                prompt = (
                    "Align this Korean audio to the provided subtitle segments exactly. "
                    "Keep the same order and text; do not merge, split, or add segments. "
                    "Return start and end time in seconds for each item using the format '0.0-1.2: [text]'.\n"
                    f"Segments:\n{segment_list}\n"
                    "Only provide the aligned list with precise timings."
                )
            else:
                prompt = (
                    "Please provide a detailed transcript of this Korean audio with precise timestamps. "
                    "For each sentence or phrase, indicate the start and end time in seconds (e.g., '0.0-2.5: 안녕하세요'). "
                    "Split the transcript into natural speaking segments of about 8-10 characters each. "
                    "Use this format:\n"
                    "0.0-2.5: [text]\n"
                    "2.5-5.0: [text]\n"
                    "Keep timestamps accurate to the actual speech timing."
                )

            logger.info("[Audio Analysis] Gemini로 타임스탬프 분석 중...")

            # 최대 5회 재시도 (503 서버 오류 대응)
            MAX_AUDIO_RETRIES = 5
            response = None
            last_error = None

            for attempt in range(1, MAX_AUDIO_RETRIES + 1):
                try:
                    logger.info(
                        "[Audio Analysis] API 호출 시도 %d/%d",
                        attempt,
                        MAX_AUDIO_RETRIES,
                    )
                    response = self.gui.genai_client.models.generate_content(
                        model=self.gui.config.GEMINI_TEXT_MODEL,
                        contents=[prompt, uploaded_file],
                    )
                    if response and response.text:
                        break  # 성공
                except Exception as api_err:
                    last_error = str(api_err)
                    is_server_error = (
                        "503" in last_error
                        or "UNAVAILABLE" in last_error
                        or "overloaded" in last_error.lower()
                    )
                    logger.warning(
                        "[Audio Analysis] API 오류 (시도 %d/%d): %s",
                        attempt,
                        MAX_AUDIO_RETRIES,
                        last_error[:100],
                    )

                    if attempt < MAX_AUDIO_RETRIES:
                        import time

                        wait_time = 5 if is_server_error else 3
                        logger.info("[Audio Analysis] %d초 후 재시도...", wait_time)
                        time.sleep(wait_time)
                    else:
                        logger.error("[Audio Analysis] 최대 재시도 횟수 초과")
                        raise

            if not response or not response.text:
                logger.warning("[Audio Analysis] Gemini 응답 없음")
                return []

            transcript = response.text.strip()
            logger.debug("[Audio Analysis] Gemini 응답:\n%s...", transcript[:500])

            metadata = self._parse_timestamped_transcript(transcript, max_chars)

            if metadata and len(metadata) > 0:
                logger.info("[Audio Analysis] %d개 세그먼트로 파싱 완료", len(metadata))
                return metadata
            else:
                logger.warning("[Audio Analysis] 타임스탬프 파싱 실패")
                return []

        except Exception as e:
            ui_controller.write_error_log(e)
            logger.error(
                "[Audio Analysis] Gemini 분석 중 오류 발생: %s", str(e), exc_info=True
            )
            return []

    def _parse_timestamped_transcript(
        self, transcript: str, max_chars: int
    ) -> List[Dict[str, Any]]:
        """
        Parse Gemini's timestamped transcript into metadata entries.

        Supports multiple formats:
        - "0.0-2.5: text"
        - "00:00-00:02: text"
        - "[0.0s] text"

        Args:
            transcript: Timestamped transcript from Gemini
            max_chars: Maximum characters per segment

        Returns:
            List of metadata dictionaries with start/end/text
        """
        metadata = []

        # Pattern 1: "0.0-2.5: text" or "0.0 - 2.5: text"
        pattern1 = re.compile(
            r"(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\s*:\s*(.+?)(?=\n|$)", re.MULTILINE
        )
        matches1 = pattern1.findall(transcript)

        # Pattern 2: "00:00-00:02: text" (MM:SS format)
        pattern2 = re.compile(
            r"(\d+):(\d+)\s*-\s*(\d+):(\d+)\s*:\s*(.+?)(?=\n|$)", re.MULTILINE
        )
        matches2 = pattern2.findall(transcript)

        # Pattern 3: "[0.0s] text" or "(0.0s) text"
        pattern3 = re.compile(
            r"[\[\(](\d+\.?\d*)s?[\]\)]\s*(.+?)(?=\n|$)", re.MULTILINE
        )
        matches3 = pattern3.findall(transcript)

        if matches1:
            # Format: "0.0-2.5: text"
            for start_str, end_str, text in matches1:
                try:
                    start = float(start_str)
                    end = float(end_str)
                    text = text.strip()
                    if text and end > start:
                        metadata.append(
                            {
                                "start": start,
                                "end": end,
                                "text": text[: max_chars * 3],  # Allow some overflow
                            }
                        )
                except ValueError:
                    continue

        elif matches2:
            # Format: "00:00-00:02: text" (MM:SS)
            for min1, sec1, min2, sec2, text in matches2:
                try:
                    start = int(min1) * 60 + int(sec1)
                    end = int(min2) * 60 + int(sec2)
                    text = text.strip()
                    if text and end > start:
                        metadata.append(
                            {
                                "start": float(start),
                                "end": float(end),
                                "text": text[: max_chars * 3],
                            }
                        )
                except ValueError:
                    continue

        elif matches3:
            # Format: "[0.0s] text" - need to estimate duration
            for time_str, text in matches3:
                try:
                    start = float(time_str)
                    text = text.strip()
                    # Estimate duration: ~0.15s per character for Korean
                    estimated_duration = len(text) * 0.15
                    end = start + estimated_duration
                    if text:
                        metadata.append(
                            {"start": start, "end": end, "text": text[: max_chars * 3]}
                        )
                except ValueError:
                    continue

        # If no patterns matched, try to extract lines and estimate timing
        if not metadata:
            lines = [line.strip() for line in transcript.split("\n") if line.strip()]
            # Check if any line looks like it has timestamps
            has_timestamps = any(re.search(r"\d+[:.]\d+", line) for line in lines)
            if not has_timestamps:
                # No timestamps found, can't use this
                return []

        # Split long segments if needed
        final_metadata = []
        for entry in metadata:
            text = entry["text"]
            start = entry["start"]
            end = entry["end"]
            duration = end - start

            if len(text) <= max_chars:
                final_metadata.append(entry)
            else:
                # Split long text into smaller segments
                words = text.split()
                if not words:
                    final_metadata.append(entry)
                    continue

                # Calculate time per word
                time_per_word = duration / len(words)
                current_text = ""
                current_start = start

                for i, word in enumerate(words):
                    if current_text and len(current_text + " " + word) > max_chars:
                        # Flush current segment
                        word_count = len(current_text.split())
                        seg_duration = word_count * time_per_word
                        final_metadata.append(
                            {
                                "start": current_start,
                                "end": current_start + seg_duration,
                                "text": current_text,
                            }
                        )
                        current_start += seg_duration
                        current_text = word
                    else:
                        current_text = (
                            f"{current_text} {word}".strip() if current_text else word
                        )

                # Add remaining text
                if current_text:
                    final_metadata.append(
                        {"start": current_start, "end": end, "text": current_text}
                    )

        return final_metadata

    def _align_metadata_to_segments(
        self,
        metadata: List[Dict[str, Any]],
        segments: List[str],
    ) -> List[Dict[str, Any]]:
        """Align Gemini timestamps to the preferred subtitle segments."""
        if not metadata or not segments:
            return metadata

        cleaned_segments = [str(seg).strip() for seg in segments if str(seg).strip()]
        if not cleaned_segments:
            return metadata

        sorted_meta = sorted(metadata, key=lambda m: m.get("start", 0.0))

        if len(sorted_meta) == len(cleaned_segments):
            for idx, text in enumerate(cleaned_segments):
                sorted_meta[idx]["text"] = text
                sorted_meta[idx]["idx"] = idx
            return sorted_meta

        start_time = sorted_meta[0].get("start", 0.0)
        end_time = sorted_meta[-1].get("end", start_time)
        total_duration = max(end_time - start_time, 0.3 * len(cleaned_segments))
        total_chars = sum(len(seg) for seg in cleaned_segments) or len(cleaned_segments)

        rebuilt = []
        cursor = start_time
        for idx, text in enumerate(cleaned_segments):
            ratio = (
                len(text) / total_chars if total_chars else 1 / len(cleaned_segments)
            )
            duration = max(0.25, total_duration * ratio)
            rebuilt.append(
                {
                    "idx": idx,
                    "start": cursor,
                    "end": cursor + duration,
                    "text": text,
                }
            )
            cursor += duration

        return rebuilt

    def _merge_short_segments(
        self, metadata: List[Dict[str, Any]], min_chars: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Merge segments with ≤min_chars characters into adjacent segments.

        Short segments (≤6 characters) are merged with the previous segment
        to improve subtitle readability. The merged segment keeps the end
        time of the short segment.

        Example:
            Before: ["꿀템을" (8자), "소개합니다." (6자)]
            After:  ["꿀템을 소개합니다."]

        Args:
            metadata: List of metadata dictionaries with start/end/text
            min_chars: Minimum characters threshold (segments ≤ this are merged)

        Returns:
            List of merged metadata dictionaries
        """
        if not metadata or len(metadata) <= 1:
            return metadata

        merged = []
        i = 0

        while i < len(metadata):
            current = metadata[i].copy()

            # Check if next segment should be merged
            while i + 1 < len(metadata):
                next_seg = metadata[i + 1]
                next_text = next_seg.get("text", "").strip()

                # If next segment is short (≤min_chars), merge it
                if len(next_text) <= min_chars:
                    current["text"] = f"{current['text']} {next_text}".strip()
                    current["end"] = next_seg["end"]
                    i += 1  # Skip the merged segment
                else:
                    break

            merged.append(current)
            i += 1

        # Re-index the merged segments
        for idx, item in enumerate(merged):
            item["idx"] = idx

        logger.info(
            "[Segment Merge] %d개 -> %d개 세그먼트 (짧은 구간 병합 완료)",
            len(metadata),
            len(merged),
        )
        return merged

    def _split_script_for_tts(self, script: str, max_chars: int = 9) -> List[str]:
        """
        Split script into naturally phrased segments for TTS and subtitles.

        Args:
            script: Full script text
            max_chars: Target characters per segment

        Returns:
            List of script segments
        """
        normalized = re.sub(r"\s+", " ", (script or "")).strip()
        if not normalized:
            return []

        target = max_chars or 9
        min_chars = max(3, target - 3)  # 더 작은 세그먼트 허용
        hard_max = target + 2  # 최대 글자수 (9 + 2 = 11)

        # 마침표, 물음표, 느낌표 등으로 문장 분리 (공백 여부 무관)
        boundary_pattern = re.compile(r"(?<=[\.\?!。？！…])\s*")
        candidates: List[str] = []
        for part in boundary_pattern.split(normalized):
            for sub in re.split(r"\s*(?:\\n|\n)\s*", part):
                candidate = sub.strip()
                if candidate:
                    candidates.append(candidate)

        raw_segments = candidates or [normalized]
        segments: List[str] = []

        def flush_segment(seg: str):
            seg = seg.strip(" ,;")
            if seg:
                segments.append(seg)

        for sentence in raw_segments:
            working_tokens = re.split(
                r"(\s*,\s*|ㆍ|·|;|\s+그리고\s+|\s+하지만\s+|\s+그래서\s+|\s+그런데\s+)",
                sentence,
            )
            buffer = ""
            for token in working_tokens:
                token = token.strip()
                if not token:
                    continue
                candidate = f"{buffer} {token}".strip() if buffer else token
                if len(candidate) > hard_max and buffer:
                    flush_segment(buffer)
                    buffer = token
                else:
                    buffer = candidate
            flush_segment(buffer)

        refined: List[str] = []
        for seg in segments:
            working = seg
            while len(working) > hard_max:
                split_idx = working.rfind(" ", 0, target)
                if split_idx <= 0:
                    split_idx = working.find(" ", target)
                if split_idx <= 0:
                    split_idx = hard_max
                refined.append(working[:split_idx].strip())
                working = working[split_idx:].strip()
            if working:
                refined.append(working)

        # 마침표/느낌표/물음표로 끝나는 세그먼트는 병합하지 않음
        merged: List[str] = []
        for seg in refined:
            # 이전 세그먼트가 문장 종결 부호로 끝나면 병합하지 않음
            prev_ends_with_punct = merged and merged[-1][-1] in ".!?。？！…"

            if merged and len(seg) < min_chars and not prev_ends_with_punct:
                # 병합 후에도 hard_max를 넘지 않을 때만 병합
                if len(merged[-1]) + len(seg) + 1 <= hard_max:
                    merged[-1] = f"{merged[-1]} {seg}".strip()
                else:
                    merged.append(seg)
            else:
                merged.append(seg)

        # 마지막 세그먼트가 너무 짧으면 이전과 병합 (단, 이전이 문장 종결이 아닐 때만)
        if len(merged) > 1 and len(merged[-1]) < min_chars:
            if merged[-2][-1] not in ".!?。？！…":
                if len(merged[-2]) + len(merged[-1]) + 1 <= hard_max:
                    merged[-2] = f"{merged[-2]} {merged[-1]}".strip()
                    merged.pop()

        return self._rebalance_subtitle_segments(merged, max_chars)

    def _rebalance_subtitle_segments(
        self, segments: Iterable[str], max_chars: int
    ) -> List[str]:
        """
        Rebalance subtitle segments for better readability.

        Merges short segments and splits long ones to optimize subtitle display.

        Args:
            segments: List of text segments
            max_chars: Maximum characters per segment

        Returns:
            Rebalanced list of segments
        """
        cleaned = [seg.strip() for seg in segments if seg and seg.strip()]
        if not cleaned:
            return []

        changed = True
        while changed:
            changed = False
            i = 0
            while i < len(cleaned):
                segment = cleaned[i]
                if not segment:
                    cleaned.pop(i)
                    changed = True
                    continue

                tokens = segment.split()
                if not tokens:
                    cleaned.pop(i)
                    changed = True
                    continue

                if segment[-1] in ",;:!?" and len(tokens) > 3:
                    prefix = " ".join(tokens[:-2]).strip()
                    suffix = " ".join(tokens[-2:]).strip()
                    if prefix:
                        cleaned[i] = prefix
                        if suffix:
                            cleaned.insert(i + 1, suffix)
                        changed = True
                        continue

                if i < len(cleaned) - 1 and segment[-1] not in ",;:!?":
                    next_segment = cleaned[i + 1]
                    if next_segment:
                        next_segment = next_segment.strip()
                    if next_segment:
                        if len(tokens) > 2:
                            last_token = tokens[-1]
                            if len(last_token) <= 2 and not last_token.endswith(
                                ("는", "요")
                            ):
                                candidate = f"{last_token} {next_segment}".strip()
                                if len(candidate) <= max_chars:
                                    cleaned[i] = " ".join(tokens[:-1]).strip()
                                    cleaned[i + 1] = candidate
                                    if not cleaned[i]:
                                        cleaned.pop(i)
                                    changed = True
                                    continue
                i += 1

        return [seg for seg in cleaned if seg]

    def _trim_script_for_attempt(self, script: str, reduction_rate: float) -> str:
        """
        Trim script to target character count for retry attempts.

        Args:
            script: Original script text
            reduction_rate: Fraction of original length to keep (0.0-1.0)

        Returns:
            Trimmed script text
        """
        sentences = re.split(r"(?:[.!?]\s+)", script)
        target_chars = int(len(script) * reduction_rate)
        if target_chars <= 0:
            return script
        trimmed = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(trimmed) + len(sentence) <= target_chars:
                trimmed += sentence + " "
            else:
                break
        trimmed = trimmed.strip()
        return trimmed if trimmed else script

    def extract_clean_script_from_translation(self, max_len: int = 14) -> str:
        """
        Extract and clean Korean script from translation result.

        Removes metadata, timestamps, speaker tags, and formatting to get
        pure Korean subtitle text.

        Args:
            max_len: Maximum length multiplier (max_len * 200 chars)

        Returns:
            Cleaned Korean script text
        """
        try:
            raw = (self.gui.translation_result or "").strip()
            full_script = ""

            # 번역 결과가 있으면 먼저 처리
            if raw:
                cleaned_lines: List[str] = []
                for original_line in raw.splitlines():
                    line = original_line.strip()
                    if not line:
                        continue

                    # Drop obvious metadata and status lines.
                    if re.match(r"^[#*= -]{3,}$", line):
                        continue

                    # Remove timestamps, speaker tags, numbering and parenthetical notes.
                    line = re.sub(r"\[[^\]]*\]", "", line)
                    line = re.sub(r"\([^)]*\)", "", line)
                    line = re.sub(r"^\d+[\.)]\s*", "", line)
                    line = re.sub(r"^(?:-|\*|\u2022)\s*", "", line)
                    line = re.sub(r"\s+", " ", line).strip()

                    if len(line) < 2:
                        continue
                    cleaned_lines.append(line)

                if not cleaned_lines:
                    logger.warning(
                        "[ScriptExtract] No usable lines found, falling back to raw text"
                    )
                    cleaned_lines = [
                        line.strip() for line in raw.splitlines() if line.strip()
                    ]

                full_script = re.sub(r"\s+", " ", " ".join(cleaned_lines)).strip()

            # 번역 결과가 없거나 비어있으면 영상 분석 결과 사용
            if not full_script:
                logger.warning(
                    "[ScriptExtract] Translation result is empty, trying video analysis result"
                )

                # 1. video_analysis_result 확인 (상품 설명)
                video_analysis = getattr(self.gui, "video_analysis_result", None)
                if video_analysis:
                    if isinstance(video_analysis, str):
                        full_script = video_analysis.strip()
                        logger.info(
                            "[ScriptExtract] Using video_analysis_result as script"
                        )
                    elif isinstance(video_analysis, dict):
                        # 딕셔너리에서 텍스트 추출
                        full_script = video_analysis.get(
                            "description", ""
                        ) or video_analysis.get("script", "")
                        if full_script:
                            logger.info(
                                "[ScriptExtract] Using video_analysis_result (dict) as script"
                            )

                # 2. analysis_result 확인 (기존 fallback)
                if not full_script and isinstance(
                    getattr(self.gui, "analysis_result", None), dict
                ):
                    alt = self.gui.analysis_result.get("script")
                    if isinstance(alt, list):
                        fallback = " ".join(
                            str(entry.get("text", "")).strip()
                            for entry in alt
                            if isinstance(entry, dict) and entry.get("text")
                        )
                        full_script = re.sub(r"\s+", " ", fallback).strip()
                        if full_script:
                            logger.info(
                                "[ScriptExtract] Using analysis_result script as fallback"
                            )

            if max_len and len(full_script) > max_len * 200:
                full_script = full_script[: max_len * 200].rsplit(" ", 1)[0].strip()

            # ★ 자막용 스크립트는 숫자 그대로 유지 (7개, 3명 등)
            # ★ TTS 호출 시에만 한국어로 변환 (일곱 개, 세 명 등)
            return full_script

        except Exception as e:
            ui_controller.write_error_log(e)
            logger.error(
                "[ScriptExtract] Error while cleaning script: %s", e, exc_info=True
            )
            fallback = re.sub(
                r"[^\w\s.,!?\uAC00-\uD7A3]", "", self.gui.translation_result or ""
            ).strip()
            return fallback

    def get_video_duration_helper(self):
        """
        Measure original video duration.

        Returns:
            Video duration in seconds (defaults to 60.0 if unavailable)
        """
        try:
            if not MOVIEPY_AVAILABLE or VideoFileClip is None:
                logger.warning("[영상 길이] moviepy가 없어 기본값 60초를 사용합니다.")
                return 60.0
            if self.gui.video_source.get() == "local":
                source_video = self.gui.local_file_path
            else:
                source_video = self.gui._temp_downloaded_file

            if source_video and os.path.exists(source_video):
                temp_video = VideoFileClip(source_video)
                duration = temp_video.duration
                temp_video.close()
                logger.info("[영상 길이] 측정 완료: %.1f초", duration)
                return duration
            else:
                logger.warning("[영상 길이] 영상 파일을 찾을 수 없음, 기본값 60초 사용")
                return 60.0

        except Exception as e:
            logger.error("[영상 길이] 측정 오류: %s, 기본값 60초 사용", str(e))
            return 60.0
