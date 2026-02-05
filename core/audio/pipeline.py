"""
Audio Pipeline Module
=====================
TTS 생성, 배속 적용, 길이 체크를 위한 통합 파이프라인입니다.

이 모듈은 기존에 분산되어 있던 TTS 관련 로직을 통합합니다:
- processors/tts_processor.py의 길이 체크, 스크립트 축소, 재시도 로직
- core/video/batch/tts_generator.py의 배치 TTS 생성 로직
- core/video/batch/tts_speed.py의 배속 처리 로직

주요 기능:
- TTS 생성 전 길이 예측 및 스크립트 사전 축소
- 영상 길이에 맞는 TTS 생성 (재시도 로직 포함)
- 1.2배속 적용 (ffmpeg atempo 또는 pydub)
- Whisper 분석을 통한 자막 타이밍 추출
"""

import os
import re
import time
import secrets
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from utils.logging_config import get_logger
from utils.korean_text_processor import process_korean_script
from caller import ui_controller

logger = get_logger(__name__)

# ============================================================
# 선택적 의존성 임포트 (런타임에 없을 수 있음)
# ============================================================
try:
    from google.genai import types

    GENAI_TYPES_AVAILABLE = True
except ImportError:
    types = None
    GENAI_TYPES_AVAILABLE = False

try:
    from pydub import AudioSegment

    PYDUB_AVAILABLE = True
except ImportError:
    AudioSegment = None
    PYDUB_AVAILABLE = False


@dataclass
class AudioConfig:
    """
    오디오 파이프라인 설정 클래스

    Attributes:
        speed_ratio: 배속 비율 (기본 1.2배속)
        max_attempts: TTS 생성 최대 재시도 횟수
        chars_per_second: 초당 예상 글자 수 (TTS 길이 추정용)
        min_video_duration: TTS 생성 가능한 최소 영상 길이 (초)
        max_chars_per_segment: 자막 세그먼트당 최대 글자 수
        sample_rate: 오디오 샘플레이트
        channels: 오디오 채널 수
    """

    speed_ratio: float = 1.2
    max_attempts: int = 5
    chars_per_second: float = 7.0
    min_video_duration: float = 4.0
    max_chars_per_segment: int = 13
    sample_rate: int = 44100
    channels: int = 2

    # 배속 후 영상 대비 TTS 최대 비율 (85% = 영상보다 짧게)
    max_duration_ratio: float = 0.85


@dataclass
class TTSResult:
    """
    TTS 생성 결과를 담는 데이터 클래스

    Attributes:
        audio_path: 생성된 오디오 파일 경로
        original_duration: 원본 TTS 길이 (초)
        speeded_duration: 배속 후 TTS 길이 (초)
        metadata: 자막 동기화를 위한 메타데이터 리스트
        timestamps_source: 타임스탬프 추출 방식 (whisper_analysis)
    """

    audio_path: str
    original_duration: float
    speeded_duration: float
    metadata: List[Dict[str, Any]] = field(default_factory=list)
    timestamps_source: str = "unknown"
    speed_ratio: float = 1.2
    voice_start: float = 0.0
    voice_end: float = 0.0


class AudioPipeline:
    """
    TTS 생성 및 오디오 처리 통합 파이프라인

    이 클래스는 다음 기능을 통합 제공합니다:
    1. TTS 길이 사전 예측 및 스크립트 축소
    2. Gemini TTS API를 통한 음성 생성
    3. 영상 길이에 맞는 재시도 로직
    4. 1.2배속 적용
    5. Whisper 분석을 통한 자막 타이밍 추출

    사용 예시:
        pipeline = AudioPipeline(app, config=AudioConfig(speed_ratio=1.2))
        result = pipeline.generate_tts(script, voice="Charon", video_duration=30.0)
    """

    def __init__(self, app, config: Optional[AudioConfig] = None):
        """
        AudioPipeline 초기화

        Args:
            app: 앱 인스턴스 (genai_client, tts_output_dir 등 포함)
            config: 오디오 처리 설정 (기본값 사용 시 None)
        """
        self.app = app
        self.config = config or AudioConfig()

    # ============================================================
    # 공개 API 메서드
    # ============================================================

    def generate_tts(
        self,
        script: str,
        voice: str,
        video_duration: float,
        subtitle_segments: Optional[List[str]] = None,
        cta_lines: Optional[List[str]] = None,
    ) -> TTSResult:
        """
        영상 길이에 맞는 TTS 생성 (통합 메서드)

        전체 워크플로우:
        1. 스크립트 길이 사전 체크 및 축소
        2. TTS 생성 (재시도 포함)
        3. 1.2배속 적용
        4. Whisper 분석으로 자막 타이밍 추출

        Args:
            script: 읽을 스크립트 텍스트
            voice: Gemini TTS 음성 ID (예: "Charon", "Callirrhoe")
            video_duration: 영상 길이 (초)
            subtitle_segments: 자막 세그먼트 리스트 (없으면 자동 분할)
            cta_lines: CTA 문구 리스트 (없으면 앱에서 가져옴)

        Returns:
            TTSResult: 생성된 TTS 정보

        Raises:
            RuntimeError: TTS 생성 실패 시
        """
        # 최소 영상 길이 체크
        if video_duration < self.config.min_video_duration:
            raise RuntimeError(
                f"영상 길이({video_duration:.1f}초)가 너무 짧습니다. "
                f"최소 {self.config.min_video_duration}초 이상의 영상이 필요합니다."
            )

        # 배속 후 허용 최대 TTS 길이 계산
        max_duration_after_speed = video_duration * self.config.max_duration_ratio
        max_duration_original = max_duration_after_speed * self.config.speed_ratio

        logger.info("=" * 60)
        logger.info("[AudioPipeline] TTS 생성 시작")
        logger.info("=" * 60)
        logger.info(f"  영상 길이: {video_duration:.1f}초")
        logger.info(f"  TTS 허용 (1.2배속 후): {max_duration_after_speed:.1f}초")
        logger.info(f"  TTS 허용 (원본): {max_duration_original:.1f}초")

        # CTA 처리
        if cta_lines is None:
            cta_lines = self._get_cta_lines()

        # 스크립트 사전 축소 (너무 긴 경우)
        adjusted_script, cta_text = self._prepare_script_for_duration(
            script, max_duration_original, cta_lines
        )

        # 자막 세그먼트 분할
        if subtitle_segments is None:
            subtitle_segments = self._split_text_naturally(adjusted_script)

        logger.info(f"[AudioPipeline] {len(subtitle_segments)}개 자막 세그먼트")

        # TTS 생성 (재시도 포함)
        result = self._generate_with_retry(
            script=adjusted_script,
            voice=voice,
            max_duration_after_speed=max_duration_after_speed,
            subtitle_segments=subtitle_segments,
            cta_text=cta_text,
        )

        return result

    def estimate_duration(self, script: str) -> float:
        """
        스크립트의 TTS 예상 길이 계산 (배속 후)

        Args:
            script: 스크립트 텍스트

        Returns:
            예상 TTS 길이 (초, 배속 후)
        """
        char_count = len(script.replace(" ", "").replace("\n", ""))
        original_duration = char_count / self.config.chars_per_second
        return original_duration / self.config.speed_ratio

    def trim_script_to_duration(
        self,
        script: str,
        target_duration: float,
        preserve_cta: Optional[str] = None,
    ) -> str:
        """
        목표 TTS 길이에 맞게 스크립트 축소

        Args:
            script: 원본 스크립트
            target_duration: 목표 TTS 길이 (초, 배속 후)
            preserve_cta: 보존할 CTA 텍스트

        Returns:
            축소된 스크립트
        """
        original_duration = target_duration * self.config.speed_ratio
        target_chars = int(original_duration * self.config.chars_per_second)

        return self._trim_script_by_chars(script, target_chars, preserve_cta)

    # ============================================================
    # 내부 헬퍼 메서드
    # ============================================================

    def _get_cta_lines(self) -> List[str]:
        """앱에서 CTA 문구 가져오기"""
        try:
            from ui.panels.cta_panel import get_selected_cta_lines

            return get_selected_cta_lines(self.app)
        except ImportError:
            logger.warning("[AudioPipeline] CTA 패널 임포트 실패")
            return []

    def _prepare_script_for_duration(
        self,
        script: str,
        max_duration_original: float,
        cta_lines: List[str],
    ) -> Tuple[str, str]:
        """
        영상 길이에 맞게 스크립트 사전 조정

        Returns:
            (조정된 스크립트, CTA 텍스트)
        """
        max_chars = int(max_duration_original * self.config.chars_per_second)

        # CTA 텍스트 준비
        cta_text = ""
        is_product = self._is_product_video()
        if cta_lines and is_product:
            cta_text = " ".join(cta_lines)
            if cta_text not in script:
                script = script.strip() + " " + cta_text
                logger.info(f"[AudioPipeline] CTA 추가: {cta_text[:30]}...")

        # 본문과 CTA 분리
        main_script = script
        if cta_text and cta_text in script:
            main_script = script.replace(cta_text, "").strip()

        # 길이 체크 및 축소
        if len(script) > max_chars:
            logger.info(
                f"[AudioPipeline] 스크립트 축소: {len(script)}자 -> {max_chars}자"
            )
            main_script = self._trim_script_by_chars(
                main_script, max_chars - len(cta_text) - 1
            )
            script = main_script + (" " + cta_text if cta_text else "")
            logger.info(f"  조정 후: {len(script)}자")

        return script, cta_text

    def _is_product_video(self) -> bool:
        """상품 영상인지 확인"""
        translation = getattr(self.app, "translation_result", "") or ""
        product_keywords = [
            "상품",
            "제품",
            "구매",
            "링크",
            "product",
            "purchase",
            "buy",
            "shop",
        ]
        return any(kw in translation.lower() for kw in product_keywords)

    def _trim_script_by_chars(
        self,
        script: str,
        target_chars: int,
        preserve_text: Optional[str] = None,
    ) -> str:
        """
        글자 수 기준으로 스크립트 축소 (문장 단위 유지)

        Args:
            script: 원본 스크립트
            target_chars: 목표 글자 수
            preserve_text: 보존할 텍스트 (CTA 등)
        """
        if len(script) <= target_chars:
            return script

        # 보존할 텍스트 제거 후 본문만 처리
        main_script = script
        if preserve_text and preserve_text in script:
            main_script = script.replace(preserve_text, "").strip()
            target_chars = target_chars - len(preserve_text) - 1

        if target_chars <= 0:
            return preserve_text or ""

        # 문장 단위로 분리
        sentence_pattern = re.compile(r"[.!?。！？]\s*")
        sentences = sentence_pattern.split(main_script)
        sentence_ends = sentence_pattern.findall(main_script)

        # 목표 글자 수까지 문장 추가
        reduced = ""
        for i, sent in enumerate(sentences):
            sent = sent.strip()
            if not sent:
                continue
            end_char = sentence_ends[i] if i < len(sentence_ends) else ""
            candidate = reduced + (" " if reduced else "") + sent + end_char.strip()

            if len(candidate) <= target_chars:
                reduced = candidate
            else:
                if reduced:
                    break
                reduced = sent[:target_chars]
                break

        result = reduced.strip()
        if preserve_text:
            result = result + " " + preserve_text

        return result

    def _trim_script_for_retry(self, script: str, reduction_rate: float) -> str:
        """
        재시도를 위한 스크립트 축소

        Args:
            script: 원본 스크립트
            reduction_rate: 축소 비율 (0.0~1.0)
        """
        target_chars = int(len(script) * reduction_rate)
        return self._trim_script_by_chars(script, target_chars)

    def _generate_with_retry(
        self,
        script: str,
        voice: str,
        max_duration_after_speed: float,
        subtitle_segments: List[str],
        cta_text: str,
    ) -> TTSResult:
        """
        재시도 로직을 포함한 TTS 생성
        """
        last_result: Optional[TTSResult] = None
        last_duration = 0.0
        main_script = script.replace(cta_text, "").strip() if cta_text else script

        for attempt in range(self.config.max_attempts):
            try:
                # 재시도 시 스크립트 축소
                if attempt > 0:
                    if last_duration > 0:
                        overshoot_ratio = last_duration / max_duration_after_speed
                        reduction_rate = max(
                            0.3, min(0.9, (1.0 / overshoot_ratio) * 0.85)
                        )
                    else:
                        reduction_rate = 0.7 if attempt == 1 else 0.5

                    logger.info(
                        f"[AudioPipeline] 재시도 {attempt + 1}: {reduction_rate * 100:.0f}% 축소"
                    )
                    reduced_main = self._trim_script_for_retry(
                        main_script, reduction_rate
                    )
                    current_script = reduced_main + (" " + cta_text if cta_text else "")
                    current_segments = self._split_text_naturally(current_script)
                else:
                    current_script = script
                    current_segments = subtitle_segments

                logger.info(
                    f"[AudioPipeline] 시도 {attempt + 1}/{self.config.max_attempts}: {len(current_script)}자"
                )

                # TTS 생성
                result = self._generate_tts_internal(
                    script=current_script,
                    voice=voice,
                    subtitle_segments=current_segments,
                )

                last_result = result
                last_duration = result.speeded_duration

                # 길이 체크
                if result.speeded_duration <= max_duration_after_speed:
                    logger.info(
                        f"[AudioPipeline] 성공: {result.speeded_duration:.1f}초 <= {max_duration_after_speed:.1f}초"
                    )
                    return result

                excess = result.speeded_duration - max_duration_after_speed
                logger.warning(f"[AudioPipeline] 길이 초과: {excess:.1f}초")

            except Exception as exc:
                ui_controller.write_error_log(exc)
                logger.error(f"[AudioPipeline] 시도 {attempt + 1} 실패: {exc}")

                # API 할당량 초과 시 키 전환
                error_str = str(exc)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    self._handle_rate_limit()

                if attempt >= self.config.max_attempts - 1:
                    raise RuntimeError(f"TTS 생성 실패 (최대 재시도 횟수 초과): {exc}")

        # 모든 시도 실패 시 마지막 결과 반환 (길이 초과 허용)
        if last_result:
            logger.warning(
                f"[AudioPipeline] 목표 길이 미달성, 마지막 결과 사용: {last_duration:.1f}초"
            )
            return last_result

        raise RuntimeError("TTS 생성 실패")

    def _generate_tts_internal(
        self,
        script: str,
        voice: str,
        subtitle_segments: List[str],
    ) -> TTSResult:
        """
        실제 TTS 생성 로직
        """
        import wave

        # TTS용 텍스트 변환 (숫자 -> 한글, 영어 -> 한글 발음)
        tts_text = process_korean_script(script)

        logger.info(f"[TTS 생성] {len(script)}자 -> API 호출")
        logger.debug(f"  원본: {script[:50]}...")
        logger.debug(f"  TTS용: {tts_text[:50]}...")

        # Gemini TTS API 호출
        response = self.app.genai_client.models.generate_content(
            model=self.app.config.GEMINI_TTS_MODEL,
            contents=[tts_text],
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice
                        )
                    )
                ),
            ),
        )

        # 응답 검증
        if not response or not response.candidates:
            raise RuntimeError("TTS API 응답 없음")

        candidate = response.candidates[0]
        if not candidate.content or not candidate.content.parts:
            raise RuntimeError("TTS API 응답에 오디오 데이터 없음")

        audio_data = candidate.content.parts[0].inline_data.data
        if not audio_data:
            raise RuntimeError("TTS 오디오 데이터가 비어있음")

        # 원본 TTS 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:21]
        random_suffix = secrets.token_hex(4)
        original_filename = f"tts_full_{voice}_{timestamp}_{random_suffix}.wav"
        original_path = os.path.join(self.app.tts_output_dir, original_filename)

        # WAV 파일 저장
        if audio_data[:4] == b"RIFF":
            with open(original_path, "wb") as f:
                f.write(audio_data)
        else:
            with wave.open(original_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(audio_data)

        # pydub로 로드 및 정규화
        from core.video.batch.audio_utils import (
            _prepare_segment,
            _ensure_pydub_converter,
        )

        raw_audio = AudioSegment.from_file(original_path, format="wav")
        prepared_audio = _prepare_segment(raw_audio)

        # 정규화된 버전 저장
        ffmpeg_path = _ensure_pydub_converter()
        try:
            if ffmpeg_path:
                prepared_audio.export(
                    original_path,
                    format="wav",
                    parameters=[
                        "-ar",
                        str(self.config.sample_rate),
                        "-ac",
                        str(self.config.channels),
                    ],
                )
            else:
                from core.video.batch.audio_utils import _write_wave_fallback

                _write_wave_fallback(
                    prepared_audio, original_path, sample_rate=self.config.sample_rate
                )
        except Exception as export_err:
            logger.warning(f"[TTS] export 폴백: {export_err}")
            from core.video.batch.audio_utils import _write_wave_fallback

            _write_wave_fallback(
                prepared_audio, original_path, sample_rate=self.config.sample_rate
            )

        original_duration = len(prepared_audio) / 1000.0
        logger.info(f"[TTS 생성] 원본 길이: {original_duration:.2f}초")

        # 1.2배속 적용
        speeded_path, speeded_duration = self._apply_speed(
            original_path, prepared_audio, voice, timestamp, random_suffix
        )

        # Whisper 분석으로 자막 타이밍 추출
        metadata, timestamps_source, voice_start, voice_end = (
            self._analyze_with_whisper(
                speeded_path, script, subtitle_segments, speeded_duration
            )
        )

        return TTSResult(
            audio_path=speeded_path,
            original_duration=original_duration,
            speeded_duration=speeded_duration,
            metadata=metadata,
            timestamps_source=timestamps_source,
            speed_ratio=self.config.speed_ratio,
            voice_start=voice_start,
            voice_end=voice_end,
        )

    def _apply_speed(
        self,
        original_path: str,
        audio: "AudioSegment",
        voice: str,
        timestamp: str,
        random_suffix: str,
    ) -> Tuple[str, float]:
        """
        오디오에 배속 적용

        Returns:
            (배속된 파일 경로, 배속 후 길이)
        """
        from core.video.batch.audio_utils import (
            _ensure_pydub_converter,
            _write_wave_fallback,
        )

        speeded_filename = f"tts_speeded_{voice}_{timestamp}_{random_suffix}.wav"
        speeded_path = os.path.join(self.app.tts_output_dir, speeded_filename)

        ffmpeg_path = _ensure_pydub_converter()
        speed_ratio = self.config.speed_ratio

        # ffmpeg atempo 사용 (더 좋은 품질)
        if ffmpeg_path:
            cmd = [
                ffmpeg_path,
                "-y",
                "-i",
                original_path,
                "-filter:a",
                f"atempo={speed_ratio}",
                "-ar",
                str(self.config.sample_rate),
                "-ac",
                str(self.config.channels),
                speeded_path,
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=60)

            if result.returncode == 0 and os.path.exists(speeded_path):
                logger.info(f"[배속] ffmpeg atempo {speed_ratio}x 성공")
            else:
                # ffmpeg 실패 시 pydub 폴백
                speeded_audio = audio.speedup(
                    playback_speed=speed_ratio, chunk_size=150, crossfade=25
                )
                speeded_audio.export(speeded_path, format="wav")
                logger.info(f"[배속] pydub {speed_ratio}x 폴백")
        else:
            # ffmpeg 없으면 pydub 사용
            speeded_audio = audio.speedup(
                playback_speed=speed_ratio, chunk_size=150, crossfade=25
            )
            speeded_audio.export(speeded_path, format="wav")
            logger.info(f"[배속] pydub {speed_ratio}x (ffmpeg 없음)")

        # 배속 후 길이 측정
        speeded_audio = AudioSegment.from_file(speeded_path)
        speeded_duration = len(speeded_audio) / 1000.0

        logger.info(f"[배속] {speed_ratio}x 후 길이: {speeded_duration:.2f}초")

        return speeded_path, speeded_duration

    def _analyze_with_whisper(
        self,
        audio_path: str,
        script: str,
        subtitle_segments: List[str],
        total_duration: float,
    ) -> Tuple[List[Dict[str, Any]], str, float, float]:
        """
        Whisper로 자막 타이밍 분석

        Returns:
            (메타데이터 리스트, 타임스탬프 소스, 음성 시작, 음성 끝)
        """
        from core.video.batch.whisper_analyzer import analyze_tts_with_whisper

        logger.info("[Whisper] 자막 타이밍 분석 시작...")

        whisper_result = analyze_tts_with_whisper(
            self.app, audio_path, script, subtitle_segments
        )

        if not whisper_result or "segments" not in whisper_result:
            raise RuntimeError("Whisper 분석 결과가 없습니다 - 자막 싱크 불가")

        whisper_segments = whisper_result["segments"]
        voice_start = whisper_result.get("voice_start", 0)
        voice_end = whisper_result.get("voice_end", total_duration)

        metadata = []
        for seg in whisper_segments:
            idx = seg.get("index", 1) - 1
            metadata.append(
                {
                    "idx": idx,
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": seg["text"],
                    "path": audio_path,
                    "speaker": None,  # 나중에 설정
                    "is_narr": False,
                }
            )

        logger.info(f"[Whisper] {len(metadata)}개 세그먼트 분석 완료")
        return metadata, "whisper_analysis", voice_start, voice_end

    def _split_text_naturally(self, text: str) -> List[str]:
        """
        텍스트를 자연스럽게 분할 (자막용)

        기존 utils._split_text_naturally 호출
        """
        try:
            from core.video.batch.utils import _split_text_naturally

            return _split_text_naturally(
                self.app, text, self.config.max_chars_per_segment
            )
        except ImportError:
            # 폴백: 단순 분할
            return self._simple_split(text)

    def _simple_split(self, text: str, max_chars: int = 13) -> List[str]:
        """단순 텍스트 분할 (폴백)"""
        segments = []
        words = text.split()
        current = ""

        for word in words:
            if current and len(current) + 1 + len(word) > max_chars:
                segments.append(current)
                current = word
            else:
                current = f"{current} {word}".strip() if current else word

        if current:
            segments.append(current)

        return segments

    def _handle_rate_limit(self):
        """API 할당량 초과 시 키 전환"""
        try:
            api_mgr = getattr(self.app, "api_key_manager", None)
            if api_mgr:
                api_mgr.block_current_key(duration_minutes=5)
                logger.info("[AudioPipeline] API 키 전환 중...")
                if hasattr(self.app, "init_client") and self.app.init_client():
                    logger.info("[AudioPipeline] API 키 전환 완료")
                else:
                    time.sleep(60)
        except Exception as e:
            logger.warning(f"[AudioPipeline] API 키 전환 오류: {e}")
            time.sleep(60)
