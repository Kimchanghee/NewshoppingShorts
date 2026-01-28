"""
GPU Encoding Functions for Batch Processing

Contains utilities for GPU-accelerated video encoding and resolution handling.
"""

import os
import sys
import time
import shutil
import ctypes
import subprocess
import traceback

from caller import ui_controller
from utils.logging_config import get_logger

logger = get_logger(__name__)


# GPU 인코더 사용 가능 여부 캐싱
_GPU_ENCODER_AVAILABLE = None


class RealtimeEncodingLogger:
    """실시간 인코딩 진행률을 UI에 표시하는 커스텀 로거"""

    def __init__(self, app, total_duration):
        """
        Args:
            app: VideoAnalyzerGUI 인스턴스
            total_duration: 비디오 총 길이 (초)
        """
        self.app = app
        self.total_duration = total_duration
        self.last_update_time = 0

    def __call__(self, message):
        """moviepy의 logger 콜백"""
        try:
            # moviepy 메시지 파싱: "t:   5.23s [done, now generating...] done"
            if 't:' in message:
                # "t:   5.23s" 형식에서 시간 추출
                import re
                match = re.search(r't:\s*(\d+\.?\d*)s', message)
                if match:
                    current_time = float(match.group(1))
                    progress_pct = min(99, int((current_time / self.total_duration) * 100))

                    # UI 업데이트 빈도 제한 (0.5초마다)
                    current_timestamp = time.time()
                    if current_timestamp - self.last_update_time >= 0.5:
                        self.app.update_progress_state(
                            'finalize',
                            'processing',
                            progress_pct,
                            f"영상 인코딩 중... {progress_pct}%"
                        )
                        self.last_update_time = current_timestamp
        except Exception as e:
            # 로거 오류는 무시 (인코딩에 영향 없도록)
            ui_controller.write_error_log(e)
            pass

    def iter_bar(self, chunk=None, **kwargs):
        """moviepy logger 인터페이스 호환성을 위한 iter_bar 메서드"""
        # moviepy가 't' 키워드 인자로 전달하는 경우 처리
        if chunk is None and 't' in kwargs:
            chunk = kwargs['t']
        # chunk가 iterable이면 그대로 반환, 아니면 빈 리스트
        if chunk is not None:
            return iter(chunk) if hasattr(chunk, '__iter__') else iter([])
        return iter([])


def _nvenc_runtime_healthy(ffmpeg_cmd: str) -> bool:
    """
    NVENC가 실제로 동작하는지 1초짜리 더미 인코딩으로 검증.
    Windows에선 nvcuda.dll 존재도 같이 확인.
    """
    try:
        # 1) nvcuda.dll 체크 (64bit 기준 System32)
        if sys.platform == "win32":
            cuda_dll_paths = [
                r"C:\Windows\System32\nvcuda.dll",
                r"C:\Windows\SysWOW64\nvcuda.dll",
            ]
            has_nvcuda = any(os.path.exists(p) for p in cuda_dll_paths)
            if not has_nvcuda:
                return False
            # 로드 시도(권장)
            try:
                ctypes.WinDLL("nvcuda.dll")
            except Exception as e:
                logger.debug(f"[GPU 인코딩] nvcuda.dll 로드 실패: {e}")
                return False

        # 2) 실제 ffmpeg로 1초 더미를 NVENC로 인코딩해보기
        #    (출력은 NUL로 버려서 빠르게)
        null_out = "NUL" if sys.platform == "win32" else "/dev/null"
        test_cmd = [
            ffmpeg_cmd, "-hide_banner",
            "-f", "lavfi", "-i", "testsrc2=size=128x128:rate=30",
            "-t", "1",
            "-c:v", "h264_nvenc",
            "-f", "null", null_out
        ]
        res = subprocess.run(
            test_cmd,
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        return res.returncode == 0
    except Exception as e:
        logger.debug(f"[GPU 인코딩] NVENC 런타임 확인 실패: {e}", exc_info=True)
        return False


def _check_gpu_encoder_available():
    """NVIDIA NVENC 실제 사용 가능 여부 확인(캐시)"""
    global _GPU_ENCODER_AVAILABLE
    if _GPU_ENCODER_AVAILABLE is not None:
        return _GPU_ENCODER_AVAILABLE

    try:
        # 1) ffmpeg 찾기
        ffmpeg_cmd = None
        try:
            import imageio_ffmpeg
            ffmpeg_cmd = imageio_ffmpeg.get_ffmpeg_exe()
            if ffmpeg_cmd and os.path.exists(ffmpeg_cmd):
                logger.info(f"[GPU 인코딩] imageio-ffmpeg FFmpeg 사용: {ffmpeg_cmd}")
        except Exception as e:
            logger.warning(f"[GPU 인코딩] imageio-ffmpeg 로드 실패: {e}")
            ui_controller.write_error_log(e)

        if not ffmpeg_cmd:
            ffmpeg_cmd = shutil.which("ffmpeg")
        if not ffmpeg_cmd:
            logger.info("[GPU 인코딩] FFmpeg을 찾을 수 없습니다, CPU 인코딩 사용")
            _GPU_ENCODER_AVAILABLE = False
            return False

        # 2) 목록에 h264_nvenc 존재?
        res = subprocess.run(
            [ffmpeg_cmd, "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        if "h264_nvenc" not in res.stdout:
            logger.info("[GPU 인코딩] NVENC 미지원 빌드, CPU 인코딩 사용")
            _GPU_ENCODER_AVAILABLE = False
            return False

        # 3) 실제 런타임 건강검진
        if _nvenc_runtime_healthy(ffmpeg_cmd):
            logger.info("[GPU 인코딩] NVIDIA NVENC 하드웨어 인코더 실제 동작 확인")
            _GPU_ENCODER_AVAILABLE = True
            return True
        else:
            logger.info("[GPU 인코딩] NVENC 런타임 비정상(nvcuda.dll/드라이버 문제). CPU 인코딩 사용")
            _GPU_ENCODER_AVAILABLE = False
            return False

    except subprocess.TimeoutExpired:
        logger.warning("[GPU 인코딩] FFmpeg 응답 시간 초과, CPU 인코딩 사용")
    except Exception as e:
        logger.warning(f"[GPU 인코딩] 확인 실패: {e}, CPU 인코딩 사용", exc_info=True)
        ui_controller.write_error_log(e)

    _GPU_ENCODER_AVAILABLE = False
    return False


def _ensure_even_resolution(clip):
    """Ensure video resolution has even width and height (required for h264 encoding)"""
    w, h = clip.w, clip.h
    new_w = (w // 2) * 2
    new_h = (h // 2) * 2
    return clip if (w == new_w and h == new_h) else clip.resize((new_w, new_h))
