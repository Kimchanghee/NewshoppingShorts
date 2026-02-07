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

from .audio_utils import _ensure_pydub_converter
from .utils import _split_text_naturally
from caller import ui_controller
from utils.logging_config import get_logger

logger = get_logger(__name__)


def _should_disable_faster_whisper() -> bool:
    """
    Decide whether to skip faster-whisper entirely.

    In some environments (notably Python 3.14 at the time of writing), native
    dependencies like CTranslate2 can hard-crash the process (no Python traceback).
    When disabled, callers still get usable timestamps via a safe fallback.
    """
    env = (os.environ.get("SSMAKER_DISABLE_FASTER_WHISPER") or "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        return True
    if env in ("0", "false", "no", "off"):
        return False

    # Conservative default until the ecosystem stabilizes.
    return sys.version_info >= (3, 14)


def _char_proportional_timestamps(app, tts_path: str, transcript_text: str, subtitle_segments):
    """Safe fallback: distribute segment durations proportional to character counts."""
    audio = AudioSegment.from_file(tts_path)
    audio_duration = len(audio) / 1000.0

    if subtitle_segments is None:
        subtitle_segments = _split_text_naturally(app, transcript_text)

    # Best-effort lead-in offset detection.
    voice_start = 0.0
    try:
        from core.video.VideoTool import _detect_audio_start_offset

        voice_start = float(_detect_audio_start_offset(tts_path) or 0.0)
    except Exception:
        voice_start = 0.0

    if voice_start < 0:
        voice_start = 0.0
    if voice_start > audio_duration:
        voice_start = 0.0

    def _seg_len(s: str) -> int:
        return max(1, len(re.sub(r"[^0-9A-Za-z가-힣]", "", str(s or ""))))

    segs = list(subtitle_segments or [])
    if not segs:
        return {
            "audio_duration": audio_duration,
            "voice_start": voice_start,
            "voice_end": audio_duration,
            "segments": [],
        }

    lengths = [_seg_len(s) for s in segs]
    total = sum(lengths)
    available = max(0.0, audio_duration - voice_start)
    min_dur = 0.15

    # First pass allocation.
    spans = []
    t = voice_start
    for i, (seg_text, seg_len) in enumerate(zip(segs, lengths), start=1):
        dur = (available * (seg_len / total)) if total > 0 else (available / max(1, len(segs)))
        dur = max(min_dur, float(dur))
        spans.append((i, seg_text, t, t + dur))
        t = t + dur

    # Scale down if we overshoot.
    last_end = spans[-1][3]
    target_end = max(voice_start + min_dur, audio_duration - 0.005)
    if last_end > target_end and last_end > voice_start:
        scale = (target_end - voice_start) / (last_end - voice_start)
        scaled = []
        for i, seg_text, start, end in spans:
            s2 = voice_start + (start - voice_start) * scale
            e2 = voice_start + (end - voice_start) * scale
            if e2 - s2 < min_dur:
                e2 = s2 + min_dur
            scaled.append((i, seg_text, s2, e2))
        spans = scaled

    segments = []
    prev_end = voice_start
    for i, seg_text, start, end in spans:
        if start < prev_end:
            start = prev_end + 0.005
        if end <= start:
            end = start + min_dur
        if end > audio_duration:
            end = audio_duration - 0.005
        if start < 0:
            start = 0.0
        segments.append(
            {
                "index": i,
                "text": seg_text,
                "start": round(start, 3),
                "end": round(end, 3),
            }
        )
        prev_end = end

    voice_end = segments[-1]["end"] if segments else audio_duration
    return {
        "audio_duration": audio_duration,
        "voice_start": round(voice_start, 3),
        "voice_end": round(voice_end, 3),
        "segments": segments,
    }


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


def _find_model_in_dir(model_dir):
    """
    모델 디렉토리에서 model.bin을 찾는다.
    1) 플랫 구조: model_dir/model.bin
    2) HuggingFace 캐시: model_dir/models--*/snapshots/*/model.bin
    """
    if not os.path.isdir(model_dir):
        return None

    # Case 1: 플랫 구조
    if os.path.exists(os.path.join(model_dir, 'model.bin')):
        return model_dir

    # Case 2: HuggingFace 캐시 구조
    for entry in os.listdir(model_dir):
        if not entry.startswith('models--'):
            continue
        snapshots_dir = os.path.join(model_dir, entry, 'snapshots')
        if not os.path.isdir(snapshots_dir):
            continue
        for snapshot in os.listdir(snapshots_dir):
            snapshot_path = os.path.join(snapshots_dir, snapshot)
            if os.path.isdir(snapshot_path) and os.path.exists(os.path.join(snapshot_path, 'model.bin')):
                return snapshot_path

    return None


def _list_available_model_sizes(model_root: str):
    """Return model size directory names that look usable under model_root."""
    sizes = []
    if not model_root or not os.path.isdir(model_root):
        return sizes
    try:
        for entry in os.listdir(model_root):
            full = os.path.join(model_root, entry)
            if not os.path.isdir(full):
                continue
            if _find_model_in_dir(full):
                sizes.append(entry)
    except Exception:
        return []
    # Stable ordering helps debugging; callers still apply their own preference order.
    return sorted(set(sizes))


def _get_model_path(model_size):
    """
    faster-whisper 모델 경로 가져오기
    빌드 환경에서는 번들된 모델 사용, 개발 환경에서는 자동 다운로드

    HuggingFace 캐시 구조 지원:
      faster_whisper_models/<size>/models--Systran--faster-whisper-<size>/
        snapshots/<commit_hash>/model.bin (symlink → blobs/)
    """
    if not getattr(sys, "frozen", False):
        # Dev environment: prefer local bundled models if present, otherwise let faster-whisper download.
        dev_model_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "..",
            "..",
            "faster_whisper_models",
            model_size,
        )
        dev_model_dir = os.path.normpath(dev_model_dir)
        resolved = _find_model_in_dir(dev_model_dir)
        if resolved:
            logger.info(f"[Faster-Whisper] 로컬 모델 사용: {resolved}")
            return resolved
        return model_size

    # Frozen (PyInstaller): offline-only, so the model must exist in the bundle.
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    exe_dir = os.path.dirname(sys.executable)

    roots = []
    env_root = os.environ.get("WHISPER_MODEL_PATH")
    if env_root:
        roots.append(env_root)
    roots.append(os.path.join(base_path, "faster_whisper_models"))
    roots.append(os.path.join(exe_dir, "faster_whisper_models"))

    # De-dupe while preserving order.
    uniq_roots = []
    for r in roots:
        if r and r not in uniq_roots:
            uniq_roots.append(r)

    # Try requested size first, then common fallbacks.
    size_try_order = []
    if model_size:
        size_try_order.append(model_size)
    for s in ("base", "small", "tiny"):
        if s not in size_try_order:
            size_try_order.append(s)

    available_by_root = {}
    for root in uniq_roots:
        if not root or not os.path.isdir(root):
            continue

        available_by_root[root] = _list_available_model_sizes(root)

        # Preferred sizes first.
        for size in size_try_order:
            candidate_dir = os.path.join(root, size)
            resolved = _find_model_in_dir(candidate_dir)
            if resolved:
                if size != model_size:
                    logger.warning(
                        "[Faster-Whisper] Requested model '%s' not found; using '%s' instead.",
                        model_size,
                        size,
                    )
                logger.info(f"[Faster-Whisper] 빌드 포함 모델 사용: {resolved}")
                return resolved

        # As a last resort, use any available model in the bundle.
        for size in available_by_root[root]:
            if size in size_try_order:
                continue
            candidate_dir = os.path.join(root, size)
            resolved = _find_model_in_dir(candidate_dir)
            if resolved:
                logger.warning(
                    "[Faster-Whisper] Requested model '%s' not found; using '%s' instead.",
                    model_size,
                    size,
                )
                logger.info(f"[Faster-Whisper] 빌드 포함 모델 사용: {resolved}")
                return resolved

    searched = []
    for root in uniq_roots:
        for size in size_try_order:
            searched.append(os.path.join(root, size))

    avail_lines = []
    for root, sizes in available_by_root.items():
        avail_lines.append(f"- {root}: {', '.join(sizes) if sizes else '(none)'}")
    avail_text = "\n".join(avail_lines) if avail_lines else "(none)"

    raise RuntimeError(
        "[Faster-Whisper] 오프라인 실행 실패: 빌드에 포함된 모델을 찾을 수 없습니다.\n"
        f"요청 모델: {model_size}\n"
        "검색 경로:\n"
        + "\n".join(searched[:15])
        + ("\n..." if len(searched) > 15 else "")
        + "\n"
        f"사용 가능 모델:\n{avail_text}\n"
        "해결방법: scripts/download_whisper_models.py를 실행하여 모델을 준비한 후 재빌드하세요."
    )


def analyze_tts_with_whisper(app, tts_path, transcript_text, subtitle_segments=None):
    """
    Faster-Whisper STT로 TTS 오디오 분석 (로컬, 무료, 빠름)

    - Faster-Whisper (CTranslate2 기반) 로컬 실행
    - OpenAI Whisper 대비 4~5배 빠름
    - PyTorch 불필요 → 빌드 크기 대폭 감소
    - 단어 단위 정밀 타임스탬프 획득
    """
    try:
        if _should_disable_faster_whisper():
            logger.info(
                "[Faster-Whisper] Disabled (Python %s). Using char-proportional fallback timing.",
                platform.python_version(),
            )
            return _char_proportional_timestamps(app, tts_path, transcript_text, subtitle_segments)

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

        # If CUDA was requested but not actually available, fall back to CPU.
        if str(device).lower() == "cuda":
            try:
                import ctranslate2

                cuda_count = getattr(ctranslate2, "get_cuda_device_count", lambda: 0)()
                if not cuda_count:
                    logger.warning(
                        "[Faster-Whisper] CUDA requested but no CUDA devices detected by CTranslate2; using CPU."
                    )
                    device = "cpu"
                    compute_type = "int8"
            except Exception as cuda_probe_err:
                logger.warning(
                    "[Faster-Whisper] CUDA probe failed (%s); using CPU.",
                    cuda_probe_err,
                )
                device = "cpu"
                compute_type = "int8"

        # 모델 로드 (cache key includes device/compute_type to avoid mixing CPU/CUDA instances).
        model_key = f"_faster_whisper_model_{model_size}_{device}_{compute_type}"
        model = getattr(app, model_key, None)
        if model is None:
            logger.info(f"[Faster-Whisper] 모델 로딩 중 ({model_size}, {device}, {compute_type})...")
            model_path = _get_model_path(model_size)

            try:
                model = WhisperModel(
                    model_path,
                    device=device,
                    compute_type=compute_type,
                    cpu_threads=cpu_threads,
                )
            except Exception as model_err:
                # Common failure mode: CUDA selected on a non-CUDA machine.
                if str(device).lower() == "cuda":
                    logger.warning(
                        "[Faster-Whisper] CUDA model init failed (%s); retrying on CPU.",
                        model_err,
                    )
                    device = "cpu"
                    compute_type = "int8"
                    model_key = f"_faster_whisper_model_{model_size}_{device}_{compute_type}"
                    model = getattr(app, model_key, None)
                    if model is None:
                        model = WhisperModel(
                            model_path,
                            device=device,
                            compute_type=compute_type,
                            cpu_threads=cpu_threads,
                        )
                else:
                    raise

            setattr(app, model_key, model)
            logger.info("[Faster-Whisper] 모델 로드 완료")
        else:
            logger.debug("[Faster-Whisper] 캐시된 모델 사용")

        # 자막 세그먼트 준비
        if subtitle_segments is None:
            subtitle_segments = _split_text_naturally(app, transcript_text)

        logger.info(f"[Faster-Whisper] {len(subtitle_segments)}개 세그먼트 분석 요청")
        for i, seg in enumerate(subtitle_segments):
            logger.debug(f"  {i+1}. {seg}")

        # Faster-Whisper 음성 인식 (단어 타임스탬프 포함)
        logger.info("[Faster-Whisper] 음성 인식 중...")

        try:
            segments, info = model.transcribe(
                tts_path,
                language="ko",
                beam_size=beam_size,
                word_timestamps=True,
                vad_filter=True
            )
        except RuntimeError as vad_err:
            if "onnxruntime" in str(vad_err).lower():
                logger.warning("[Faster-Whisper] VAD 필터에 onnxruntime 필요 - VAD 없이 재시도")
                segments, info = model.transcribe(
                    tts_path,
                    language="ko",
                    beam_size=beam_size,
                    word_timestamps=True,
                    vad_filter=False
                )
            else:
                raise

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
                        'start': round(start_time, 3),
                        'end': round(end_time, 3)
                    })
                    logger.debug(f"  #{seg_idx+1}: {start_time:.3f}s ~ {end_time:.3f}s | '{seg_text[:20]}'")
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
                        'start': round(start_time, 3),
                        'end': round(end_time, 3)
                    })
                    logger.debug(f"  #{seg_idx+1}: {start_time:.3f}s ~ {end_time:.3f}s | '{seg_text[:20]}'")
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
                    'start': round(start_time, 3),
                    'end': round(end_time, 3)
                })

                logger.debug(f"  #{seg_idx+1}: {start_time:.3f}s ~ {end_time:.3f}s | '{seg_text[:20]}'")

        # 타임스탬프 정규화
        logger.debug("[Faster-Whisper] 타임스탬프 정규화...")

        # 1단계: duration이 양수인지 확인 및 수정
        for i, seg in enumerate(mapped_segments):
            duration = seg['end'] - seg['start']
            if duration <= 0:
                seg['end'] = round(seg['start'] + 0.3, 3)
                logger.debug(f"  [수정] #{i+1}: duration {duration:.3f}s → 0.3s")

        # 2단계: 역행(overlap) 수정 - 최소 갭으로 원본 타이밍 보존
        for i in range(1, len(mapped_segments)):
            prev_end = mapped_segments[i-1]['end']
            curr_start = mapped_segments[i]['start']

            if curr_start < prev_end:
                old_start = curr_start
                # 0.005s 갭만 추가 (기존 0.02s → 0.005s로 축소하여 싱크 드리프트 최소화)
                new_start = round(prev_end + 0.005, 3)

                original_duration = mapped_segments[i]['end'] - curr_start
                new_end = round(new_start + original_duration, 3)

                if new_end > audio_duration:
                    new_end = round(audio_duration - 0.005, 3)
                    if new_end <= new_start:
                        seg_text = mapped_segments[i]['text']
                        seg_chars = len(re.sub(r'[\s,.!?~·\-]', '', seg_text))
                        min_duration_by_chars = max(0.2, seg_chars * 0.08)
                        new_end = round(new_start + min_duration_by_chars, 3)

                mapped_segments[i]['start'] = new_start
                mapped_segments[i]['end'] = new_end
                logger.debug(f"  [역행 수정] #{i+1}: {old_start:.3f}s → {new_start:.3f}s")

        # 3단계: 전체 스케일링 - 0.05s 이상 초과할 때만 (미세 오차는 무시)
        last_seg = mapped_segments[-1]
        overshoot = last_seg['end'] - audio_duration
        if overshoot > 0.05:
            current_total = last_seg['end']
            target_total = audio_duration - 0.005
            scale_factor = target_total / current_total if current_total > 0 else 1.0

            logger.debug(f"  [스케일링] 전체 축소: {current_total:.3f}s → {target_total:.3f}s (overshoot={overshoot:.3f}s)")

            for seg in mapped_segments:
                seg['start'] = round(seg['start'] * scale_factor, 3)
                seg['end'] = round(seg['end'] * scale_factor, 3)

                seg_text = seg['text']
                seg_chars = len(re.sub(r'[\s,.!?~·\-]', '', seg_text))
                min_duration = max(0.15, seg_chars * 0.06)

                if seg['end'] - seg['start'] < min_duration:
                    seg['end'] = round(seg['start'] + min_duration, 3)

            # 스케일링 후 재발생한 overlap 수정
            for i in range(1, len(mapped_segments)):
                if mapped_segments[i]['start'] < mapped_segments[i-1]['end']:
                    mapped_segments[i]['start'] = round(mapped_segments[i-1]['end'] + 0.005, 3)
        elif overshoot > 0:
            # 소폭 초과: 마지막 세그먼트 end만 클램프
            last_seg['end'] = round(audio_duration - 0.005, 3)
            logger.debug(f"  [클램프] 마지막 세그먼트 end → {last_seg['end']:.3f}s (overshoot={overshoot:.3f}s)")

        # 4단계: 최종 검증 - 원본 Whisper 타이밍 최대 보존
        for i, seg in enumerate(mapped_segments):
            if seg['start'] < 0:
                seg['start'] = 0.0

            if seg['end'] <= seg['start']:
                seg_text = seg['text']
                seg_chars = len(re.sub(r'[\s,.!?~·\-]', '', seg_text))
                min_duration = max(0.15, seg_chars * 0.06)
                seg['end'] = round(seg['start'] + min_duration, 3)

            if seg['end'] > audio_duration:
                seg['end'] = round(audio_duration - 0.005, 3)
                if seg['end'] <= seg['start']:
                    seg['start'] = max(0.0, seg['end'] - 0.15)

        logger.info("[Faster-Whisper] 최종 세그먼트:")
        for seg in mapped_segments:
            logger.debug(f"  #{seg['index']}: {seg['start']:.3f}s ~ {seg['end']:.3f}s | '{seg['text'][:20]}'")

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
        logger.info(f"  - voice_start: {voice_start:.3f}초")
        logger.info(f"  - voice_end: {voice_end:.3f}초")
        logger.info(f"  - 매핑된 세그먼트: {len(mapped_segments)}개")
        logger.info("=" * 60)

        return timestamps

    except Exception as e:
        ui_controller.write_error_log(e)
        logger.error(f"[Faster-Whisper 오류] {str(e)}", exc_info=True)
        raise RuntimeError(f"Whisper 자막 분석 실패: {e}") from e


def analyze_tts_with_gemini(app, tts_path, transcript_text, subtitle_segments=None):
    """
    Faster-Whisper STT로 대체됨 (무료, 로컬, 빠름)
    기존 Gemini Audio Understanding 대신 Faster-Whisper 사용
    """
    return analyze_tts_with_whisper(app, tts_path, transcript_text, subtitle_segments)
