import os
import re
import wave
import sys
from pydub import AudioSegment
from caller import ui_controller
from utils.logging_config import get_logger

logger = get_logger(__name__)

# Font cache to avoid repeated loading and log spam per subtitle segment
_font_cache = {}  # key: (font_id, font_size) -> ImageFont object
_font_fallback_warned = set()  # track which font_ids already had fallback warning


def _resource_path(relative_path: str) -> str:
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)

        candidate = os.path.join(exe_dir, relative_path)
        if os.path.exists(candidate):
            return candidate

        base_path = getattr(sys, "_MEIPASS", exe_dir)
        return os.path.join(base_path, relative_path)

    base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(base_path, relative_path)


def _wav_duration_sec(path: str) -> float:
    try:
        audio = AudioSegment.from_file(path)
        return float(len(audio) / 1000.0)
    except Exception:
        try:
            if wave is None:
                return 0.0
            with wave.open(path, "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate() or 1
                return frames / float(rate)
        except Exception:
            return 0.0


def _make_silent_wav(path: str, ms: int = 600) -> str:
    ms = max(200, int(ms))
    AudioSegment.silent(duration=ms).export(path, format="wav")
    return path


def _detect_audio_start_offset(path: str, threshold_ratio: float = 0.01) -> float:
    """
    오디오 파일에서 실제 소리가 시작하는 지점(앞 무음 길이)을 감지합니다.

    Gemini TTS로 생성된 오디오는 앞에 약 0.1~0.2초의 무음이 포함되어 있습니다.
    이 오프셋을 자막 타임스탬프에 적용하면 오디오-자막 싱크가 정확해집니다.

    Args:
        path: 오디오 파일 경로
        threshold_ratio: 무음 판정 임계값 (최대 진폭 대비 비율, 기본 1%)

    Returns:
        앞 무음 길이 (초). 감지 실패 시 0.0 반환
    """
    try:
        import numpy as np

        with wave.open(path, "rb") as wf:
            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            frame_rate = wf.getframerate()
            n_frames = wf.getnframes()

            if n_frames == 0 or frame_rate == 0:
                return 0.0

            # 오디오 데이터 읽기
            frames = wf.readframes(n_frames)

            # numpy 배열로 변환
            if sample_width == 2:
                audio = np.frombuffer(frames, dtype=np.int16)
            elif sample_width == 1:
                audio = np.frombuffer(frames, dtype=np.uint8).astype(np.int16) - 128
            else:
                # 다른 비트 깊이는 지원하지 않음
                return 0.0

            # 스테레오면 모노로 변환
            if n_channels == 2:
                audio = audio[::2]  # 왼쪽 채널만 사용

            # 절대값으로 변환
            audio_abs = np.abs(audio)
            max_amplitude = np.max(audio_abs)

            if max_amplitude == 0:
                return 0.0

            # 임계값 계산 (최대 진폭의 threshold_ratio)
            threshold = max_amplitude * threshold_ratio

            # 임계값을 초과하는 첫 번째 샘플 찾기
            non_silent = np.where(audio_abs > threshold)[0]

            if len(non_silent) == 0:
                return 0.0

            first_sound_sample = non_silent[0]
            offset_seconds = first_sound_sample / frame_rate

            # 최대 0.5초까지만 오프셋으로 인정 (너무 큰 값은 오류)
            if offset_seconds > 0.5:
                logger.warning(
                    f"[Audio Offset] 감지된 오프셋이 너무 큼 ({offset_seconds:.3f}s), 0.0s 사용"
                )
                return 0.0

            logger.info(
                f"[Audio Offset] 앞 무음 감지: {offset_seconds:.3f}초 (임계값: {threshold_ratio * 100:.1f}%)"
            )
            return offset_seconds

    except Exception as e:
        logger.warning(f"[Audio Offset] 감지 실패: {e}")
        return 0.0


def _create_single_line_subtitle(
    app, text, duration, start_time, video_width, video_height
):
    try:
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np

        # moviepy 2.x compatible imports
        from moviepy.editor import CompositeVideoClip, ImageClip

        # 디버깅: 자막 클립 생성 정보
        logger.debug(
            f"[Subtitle Clip] Creating: {start_time:.2f}s-{start_time + duration:.2f}s ({duration:.2f}s) '{text[:30]}'"
        )

        # 9:16 세로 영상 기준 폰트 크기 (해상도 비례 계산)
        # 1080p(1920px) 기준 78px, 다른 해상도는 비례 계산
        base_height = 1920  # 1080p 세로 기준 높이
        base_font_size = 78
        font_size = max(40, int(base_font_size * (video_height / base_height)))

        # 선택된 폰트 가져오기 (기본값: seoul_hangang)
        selected_font_id = getattr(app, "selected_font_id", "seoul_hangang")

        # Use cached font if available
        cache_key = (selected_font_id, font_size)
        if cache_key in _font_cache:
            font = _font_cache[cache_key]
        else:
            # 프로젝트 폰트 폴더 경로
            project_fonts_dir = _resource_path("fonts")
            logger.info(
                f"[SubtitleFont] 폰트 로드 시작: {selected_font_id} ({font_size}px), dir={project_fonts_dir}"
            )

            # 폰트 ID별 경로 매핑
            font_map = {
                "seoul_hangang": [
                    os.path.join(project_fonts_dir, "SeoulHangangB.ttf"),
                    os.path.join(project_fonts_dir, "SeoulHangangEB.ttf"),
                    os.path.join(project_fonts_dir, "SeoulHangangM.ttf"),
                    os.path.join(project_fonts_dir, "SeoulHangangL.ttf"),
                ],
                "unpeople_gothic": [
                    os.path.join(project_fonts_dir, "UnPeople.ttf"),
                ],
                "pretendard": [
                    os.path.join(project_fonts_dir, "Pretendard-ExtraBold.ttf"),
                    os.path.join(project_fonts_dir, "Pretendard-Bold.ttf"),
                    os.path.join(project_fonts_dir, "Pretendard-SemiBold.ttf"),
                ],
                "paperlogy": [
                    os.path.join(project_fonts_dir, "Paperlogy-9Black.ttf"),
                    os.path.join(project_fonts_dir, "Paperlogy-8ExtraBold.ttf"),
                    os.path.join(project_fonts_dir, "Paperlogy-7Bold.ttf"),
                ],
                "gmarketsans": [
                    os.path.join(project_fonts_dir, "GmarketSansTTFBold.ttf"),
                    os.path.join(project_fonts_dir, "GmarketSansTTFMedium.ttf"),
                    os.path.join(project_fonts_dir, "GmarketSansTTFLight.ttf"),
                ],
            }

            korean_fonts = font_map.get(selected_font_id, font_map["seoul_hangang"]).copy()

            font = None
            for font_path in korean_fonts:
                if os.path.exists(font_path):
                    try:
                        font = ImageFont.truetype(font_path, font_size)
                        logger.info(
                            f"[SubtitleFont] 로드 완료: {os.path.basename(font_path)} ({font_size}px)"
                        )
                        break
                    except Exception as e:
                        logger.warning(
                            f"[SubtitleFont] truetype failed: {font_path} -> {e}"
                        )
                        continue

            if font is None:
                # Only warn once per font_id to avoid spam
                if selected_font_id not in _font_fallback_warned:
                    _font_fallback_warned.add(selected_font_id)
                    logger.warning(
                        f"[SubtitleFont] {selected_font_id} 폰트 없음, 시스템 폰트로 폴백"
                    )

                fallback_fonts = []
                if sys.platform == "win32":
                    fallback_fonts = [
                        "C:\\Windows\\Fonts\\malgun.ttf",
                        "C:\\Windows\\Fonts\\batang.ttc",
                        "C:\\Windows\\Fonts\\gulim.ttc",
                    ]
                elif sys.platform == "darwin":
                    fallback_fonts = [
                        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
                        "/System/Library/Fonts/AppleGothic.ttf",
                    ]
                else:
                    fallback_fonts = [
                        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    ]

                for fallback_path in fallback_fonts:
                    if os.path.exists(fallback_path):
                        try:
                            font = ImageFont.truetype(fallback_path, font_size)
                            logger.info(
                                f"[SubtitleFont] 시스템 폴백 사용: {os.path.basename(fallback_path)}"
                            )
                            break
                        except Exception as e:
                            logger.warning(f"[SubtitleFont] 폴백 실패 {fallback_path}: {e}")
                            continue

                if font is None:
                    logger.warning(
                        "[SubtitleFont] 모든 폰트 로드 실패, PIL 기본 폰트 사용"
                    )
                    font = ImageFont.load_default()

            # Cache the loaded font
            _font_cache[cache_key] = font

        text = text.strip()

        # 텍스트 너비 측정 (줄바꿈 없이 한 줄로 표시)
        tmp = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        draw_tmp = ImageDraw.Draw(tmp)

        bbox = draw_tmp.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        # ★ 텍스트가 영상 너비의 85%를 초과하면 폰트 축소
        max_text_width = int(video_width * 0.85)
        min_font_size = max(32, font_size // 2)
        current_font_size = font_size
        while text_w > max_text_width and current_font_size > min_font_size:
            current_font_size -= 2
            try:
                shrunk_font = ImageFont.truetype(font.path, current_font_size)
            except Exception:
                break
            bbox = draw_tmp.textbbox((0, 0), text, font=shrunk_font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            font = shrunk_font
        if current_font_size < font_size:
            logger.info(
                f"[Subtitle] 폰트 축소: {font_size}→{current_font_size}px (텍스트 '{text[:20]}' 너비 초과)"
            )

        # 균일한 여백 계산 (상하좌우 동일한 비율)
        padding = max(
            20, min(50, int(text_w * 0.2))
        )  # 최소 20px, 최대 50px, 텍스트 너비의 20%
        desired_w = min(text_w + padding * 2, int(video_width * 0.9))
        desired_h = text_h + padding * 2
        bg_x, bg_y, bg_w, bg_h = _resolve_korean_subtitle_bbox(
            app, desired_w, desired_h, video_width, video_height
        )

        # 둥근 모서리 반경 (살짝만 - 박스 높이의 15%)
        corner_radius = max(8, int(bg_h * 0.15))

        # 1. 둥근 모서리가 있는 반투명 검정 배경 이미지 생성
        bg_image = Image.new("RGBA", (video_width, video_height), (0, 0, 0, 0))
        bg_draw = ImageDraw.Draw(bg_image)

        # 둥근 사각형 그리기 (65% 불투명 검정)
        bg_draw.rounded_rectangle(
            [(bg_x, bg_y), (bg_x + bg_w, bg_y + bg_h)],
            radius=corner_radius,
            fill=(0, 0, 0, 166),  # 65% opacity (255 * 0.65 ≈ 166)
        )

        # 2. 텍스트를 배경 정중앙에 배치 (균일한 여백)
        center_x = bg_x + bg_w / 2
        center_y = bg_y + bg_h / 2
        try:
            bg_draw.text(
                (center_x, center_y),
                text,
                font=font,
                fill=(255, 255, 255, 255),
                anchor="mm",
            )
        except TypeError:
            # anchor 미지원 시 수동 계산
            text_x = bg_x + (bg_w - text_w) // 2
            text_y = bg_y + (bg_h - text_h) // 2 - bbox[1]
            bg_draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 255))

        # 3. 단일 이미지 클립 생성 (배경 + 텍스트 합친 상태)
        subtitle_np = np.array(bg_image)
        subtitle_clip = ImageClip(subtitle_np, duration=duration).set_start(start_time)

        return subtitle_clip

    except Exception as e:
        ui_controller.write_error_log(e)
        logger.error(f"[Subtitle Clip] Error: {e}")
        return None


def _resolve_korean_subtitle_bbox(app, desired_w, desired_h, video_width, video_height):
    """Determine Korean subtitle background box position and size.

    Uses subtitle settings from app state:
    - subtitle_overlay_on_chinese + korean_subtitle_override: overlay above Chinese subtitle
    - subtitle_position: preset position (top_center, middle_center, bottom_center)
    - subtitle_custom_y_percent: custom Y position (0-100%)
    """
    final_w = max(1, int(desired_w))
    final_h = max(1, int(desired_h))
    final_x = (video_width - final_w) // 2  # 가로 중앙 정렬

    # 1. 오버레이 모드: 중국어 자막 위에 배치
    overlay_on = getattr(app, 'subtitle_overlay_on_chinese', False)
    override = getattr(app, 'korean_subtitle_override', None)
    if overlay_on and isinstance(override, dict) and 'y' in override:
        # korean_subtitle_override의 y는 % 단위 (0-100)
        cn_y_pct = override['y']
        cn_h_pct = override.get('height', 10)
        # 중국어 자막 영역 바로 위에 배치 (간격 8px)
        cn_top_px = int(video_height * cn_y_pct / 100)
        final_y = cn_top_px - final_h - 8
        # 화면 밖으로 나가지 않도록 클램프
        final_y = max(0, final_y)
        return final_x, final_y, final_w, final_h

    # 2. 사용자 설정 위치 사용
    position = getattr(app, 'subtitle_position', 'bottom_center')
    preset_y = {
        'top_center': 15.0,
        'middle_center': 45.0,
        'bottom_center': 80.0,
    }

    if position == 'custom':
        y_pct = getattr(app, 'subtitle_custom_y_percent', 80.0)
    else:
        y_pct = preset_y.get(position, 80.0)

    # y_pct는 자막 중심의 화면 Y% (0=상단, 100=하단)
    center_y = int(video_height * y_pct / 100)
    final_y = center_y - final_h // 2

    # 화면 범위 클램프
    final_y = max(0, min(video_height - final_h, final_y))

    return final_x, final_y, final_w, final_h


def _sanitize_channel_name(name: str) -> str:
    """
    워터마크용 채널 이름에서 문제가 될 수 있는 문자 제거

    Args:
        name: 원본 채널 이름

    Returns:
        정제된 채널 이름 (최대 50자)
    """
    # 알파벳, 숫자, 한글, 일본어, 중국어, 공백, 일반 구두점만 허용
    sanitized = re.sub(
        r"[^\w\s\u3131-\uD79D\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\.\-\_@#]",
        "",
        name,
        flags=re.UNICODE,
    )
    return sanitized.strip()[:50]


def _create_watermark_clip(
    app, channel_name, position, video_width, video_height, duration,
    font_id=None, size_key=None
):
    """
    워터마크 클립 생성 (회색 50% 불투명도 텍스트)

    Args:
        app: 앱 인스턴스
        channel_name: 채널 이름 문자열
        position: 위치 ('top_left', 'top_right', 'bottom_left', 'bottom_right')
        video_width: 영상 너비
        video_height: 영상 높이
        duration: 영상 전체 길이
        font_id: 폰트 ID (None이면 pretendard 기본값)
        size_key: 크기 키 ('small', 'medium', 'large', None이면 medium 기본값)

    Returns:
        moviepy ImageClip 또는 None (실패 시)
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np
        from moviepy.editor import ImageClip

        if not channel_name or not channel_name.strip():
            return None

        # 채널 이름 정제 (특수문자 제거, 길이 제한)
        channel_name = _sanitize_channel_name(channel_name)
        if not channel_name:
            return None

        # 크기 키 → 비율 매핑
        size_map = {"small": 0.015, "medium": 0.025, "large": 0.035}
        size_ratio = size_map.get(size_key, 0.025)
        font_size = max(20, int(video_height * size_ratio))

        # 프로젝트 폰트 폴더 경로
        project_fonts_dir = _resource_path("fonts")

        # 폰트 ID → 파일 매핑
        font_id_map = {
            "pretendard": [
                os.path.join(project_fonts_dir, "Pretendard-SemiBold.ttf"),
                os.path.join(project_fonts_dir, "Pretendard-Bold.ttf"),
            ],
            "seoul_hangang": [
                os.path.join(project_fonts_dir, "SeoulHangangB.ttf"),
                os.path.join(project_fonts_dir, "SeoulHangangM.ttf"),
            ],
            "gmarketsans": [
                os.path.join(project_fonts_dir, "GmarketSansTTFMedium.ttf"),
                os.path.join(project_fonts_dir, "GmarketSansTTFBold.ttf"),
            ],
            "paperlogy": [
                os.path.join(project_fonts_dir, "Paperlogy-9Black.ttf"),
            ],
            "unpeople_gothic": [
                os.path.join(project_fonts_dir, "UnPeople.ttf"),
            ],
        }

        # 선택된 폰트 후보 + 폴백
        selected_fonts = font_id_map.get(font_id, [])
        fallback_fonts = [
            os.path.join(project_fonts_dir, "Pretendard-SemiBold.ttf"),
            os.path.join(project_fonts_dir, "Pretendard-Bold.ttf"),
            os.path.join(project_fonts_dir, "SeoulHangangM.ttf"),
            os.path.join(project_fonts_dir, "GmarketSansTTFMedium.ttf"),
        ]
        font_candidates = selected_fonts + [f for f in fallback_fonts if f not in selected_fonts]

        # 시스템 폴백 폰트
        if sys.platform == "win32":
            font_candidates.extend(
                [
                    "C:\\Windows\\Fonts\\malgun.ttf",
                    "C:\\Windows\\Fonts\\arial.ttf",
                ]
            )
        elif sys.platform == "darwin":
            font_candidates.extend(
                [
                    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
                ]
            )
        else:
            font_candidates.extend(
                [
                    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                ]
            )

        font = None
        for font_path in font_candidates:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    logger.debug(
                        f"[Watermark] Font loaded: {os.path.basename(font_path)} ({font_size}px)"
                    )
                    break
                except Exception as e:
                    logger.debug(f"[Watermark] Font load failed: {font_path} -> {e}")
                    continue

        if font is None:
            logger.warning("[Watermark] All font loading failed, using default")
            font = ImageFont.load_default()

        # 텍스트 크기 측정
        tmp = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        draw_tmp = ImageDraw.Draw(tmp)
        bbox = draw_tmp.textbbox((0, 0), channel_name, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        # 여백
        margin = int(video_width * 0.03)  # 화면 가장자리에서 3% 여백

        # 위치별 좌표 계산
        if position == "top_left":
            x = margin
            y = margin
        elif position == "top_right":
            x = video_width - text_w - margin
            y = margin
        elif position == "bottom_left":
            x = margin
            y = video_height - text_h - margin
        else:  # bottom_right (기본값)
            x = video_width - text_w - margin
            y = video_height - text_h - margin

        # 전체 크기의 투명 이미지 생성
        watermark_img = Image.new("RGBA", (video_width, video_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(watermark_img)

        # 회색 50% 불투명도 텍스트 그리기
        # RGB(128, 128, 128) = 회색, Alpha 128 = 50% 불투명도
        gray_color = (128, 128, 128, 128)
        draw.text((x, y), channel_name, font=font, fill=gray_color)

        # numpy 배열로 변환 후 ImageClip 생성
        watermark_np = np.array(watermark_img)
        watermark_clip = ImageClip(watermark_np, duration=duration).set_start(0)

        logger.debug(
            f"[Watermark] Created: '{channel_name}' at {position} ({x}, {y}), duration={duration:.1f}s"
        )
        return watermark_clip

    except Exception as e:
        ui_controller.write_error_log(e)
        logger.error(f"[Watermark] Error creating watermark: {e}")
        return None
