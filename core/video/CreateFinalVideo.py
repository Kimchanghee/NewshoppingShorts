from ui.components.custom_dialog import show_error

import logging

import math

import os

import re

from datetime import datetime, timedelta

import secrets

import tempfile

import shutil

import traceback


# moviepy 2.x compatible imports

from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    concatenate_videoclips,
    CompositeVideoClip,
    TextClip,
    ColorClip,
    ImageClip,
    vfx,
)


from core.api import ApiKeyManager

from utils import DriverConfig, Tool, util

from core.video import VideoTool

from core.api import ApiController

from core.download import DouyinExtract, TicktokExtract

from core.video import VideoExtract

from core.video.batch.utils import _extract_product_name

from caller import ui_controller


from pydub import AudioSegment

import config

from prompts import get_subtitle_split_prompt

from core.video.video_validator import VideoValidationManager, needs_regeneration


# Initialize logger for this module

logger = logging.getLogger(__name__)


def create_final_video_thread(app):
    try:
        # 鍮꾨뵒???앹꽦 ?④퀎 ?쒖옉

        app.update_progress_state(
            "video", "processing", 0, "영상을 최종 인코딩 하고 있습니다."
        )

        app.update_overall_progress("video", "processing", 0)

        app.update_status("理쒖쥌 鍮꾨뵒???앹꽦 以?..")

        selected_voice = app.fixed_tts_voice

        logger.debug("\n[理쒖쥌 鍮꾨뵒???앹꽦] ?쒖옉")

        logger.debug("?먮낯 鍮꾨뵒?? %s", app.source_video)

        logger.debug("TTS ?뚯씪 ?? %s", len(app._per_line_tts))

        logger.debug("?좏깮??TTS ?뚯꽦: %s", selected_voice)

        logger.debug("醫뚯슦 諛섏쟾 ?곸슜: %s", app.mirror_video.get())

        logger.debug("?먮쭑 ?앹꽦: %s", app.add_subtitles.get())

        app.update_progress_state("video", "processing", 10)

        # 鍮꾨뵒??濡쒕뱶

        video = VideoFileClip(app.source_video)

        app.cached_video_width = getattr(video, "w", None)

        app.cached_video_height = getattr(video, "h", None)

        logger.debug(
            "[Video] Resolution: %dx%d", app.cached_video_width, app.cached_video_height
        )

        original_duration = video.duration

        video_duration = original_duration

        original_fps = video.fps

        logger.debug("[Video] Duration %.2fs, FPS %s", original_duration, original_fps)

        app.update_progress_state("video", "processing", 20)

        # 醫뚯슦 諛섏쟾 泥섎━

        if app.mirror_video.get():
            logger.debug("[鍮꾨뵒??泥섎━] 醫뚯슦 諛섏쟾 ?곸슜")

            video = video.fx(vfx.mirror_x)

        else:
            logger.debug("[鍮꾨뵒??泥섎━] 醫뚯슦 諛섏쟾 誘몄쟻??(?먮낯 ?좎?)")

        # 以묎뎅???먮쭑 ?쒓굅 泥섎━try:

        try:
            video = app.apply_chinese_subtitle_removal(video)

            logger.debug("[DEBUG] 중국어 자막 제거 완료")

        except Exception as e:
            logger.warning("[DEBUG] 중국어 자막 제거 실패: %s", e)

            ui_controller.write_error_log(e)

        app.update_progress_state("video", "processing", 30)

        # 紐⑤뱺 TTS ?뚯씪???먮낯 鍮꾨뵒??湲몄씠??留욎떠 ?⑹튂湲?

        combined_audio_path = combine_tts_files(app, target_duration=None)

        if not combined_audio_path:
            raise Exception("TTS ?뚯씪 寃고빀 ?ㅽ뙣")

        app.update_progress_state("video", "processing", 40)

        # 鍮꾨뵒?ㅼ뿉 ???ㅻ뵒???곸슜

        new_audio = AudioFileClip(combined_audio_path)

        audio_duration = new_audio.duration

        target_video_duration = audio_duration + 3.0  # CTA 완전 표시 + 여유 (3초)

        logger.debug("[AudioSync] TTS duration: %.2fs", audio_duration)

        logger.debug(
            "[AudioSync] Target video duration: %.2fs (TTS + 3.0s 안전)",
            target_video_duration,
        )

        logger.debug("[AudioSync] Original video duration: %.2fs", original_duration)

        app.update_progress_state("video", "processing", 50)

        if original_duration > target_video_duration:
            logger.debug(
                "[Timing] Video longer by %.1fs - trimming video to %.2fs",
                original_duration - target_video_duration,
                target_video_duration,
            )

            video = video.subclip(0, target_video_duration)

            logger.debug(
                "[AudioSync] Video trimmed to %.2fs to match TTS + 3.0s",
                target_video_duration,
            )

        elif original_duration < target_video_duration:
            logger.debug(
                "[Timing] Video shorter by %.1fs - extending video to %.2fs",
                target_video_duration - original_duration,
                target_video_duration,
            )

            # concatenate_videoclips already imported at top level

            extension_duration = target_video_duration - original_duration

            last_frame = video.to_ImageClip(
                t=video.duration - 0.01, duration=extension_duration
            )

            video = concatenate_videoclips([video, last_frame])

            logger.debug(
                "[AudioSync] Video extended to %.2fs with freeze frame",
                target_video_duration,
            )

        else:
            logger.debug("[Timing] Video duration already matches TTS + 3.0s")

        # Gemini Audio Understanding의 타임스탬프를 그대로 사용 (추가 조정 없음)

        # ???ㅻ뵒???곸슜

        final_video = video.set_audio(new_audio)

        app.update_progress_state("video", "processing", 60)

        # ?먮쭑 異붽? 諛??곸긽 ?먮Ⅴ湲?

        last_subtitle_end = 0.0

        subtitle_applied = False

        if app.add_subtitles.get():
            logger.debug("[鍮꾨뵒??泥섎━] ?먮쭑 ?앹꽦 ?쒕룄 以?..")

            try:
                # Gemini 타임스탬프 기반 자막 생성 (싱크 보존)

                # _extend_last_subtitle_to_video_end 호출 제거: Gemini가 계산한 정확한 종료 시점을 존중

                # 이전 코드는 마지막 자막을 영상 끝까지 강제 연장해서 오디오-자막 싱크가 깨졌음

                subtitle_clips = create_subtitle_clips(app, final_video.duration)

                if subtitle_clips:
                    for idx_preview, clip in enumerate(
                        subtitle_clips[: min(5, len(subtitle_clips))], start=1
                    ):
                        start_ts = getattr(clip, "start", 0.0)

                        duration = getattr(clip, "duration", 0.0)

                        logger.debug(
                            "[Subtitles] Clip %d: %.2f-%.2fs",
                            idx_preview,
                            start_ts,
                            start_ts + duration,
                        )

                    logger.info(
                        "[Subtitles] Applied %d subtitle clips", len(subtitle_clips)
                    )

                    # 留덉?留??먮쭑 ???쒓컙 李얘린

                    for clip in subtitle_clips:
                        clip_end = clip.start + clip.duration

                        if clip_end > last_subtitle_end:
                            last_subtitle_end = clip_end

                    logger.debug(
                        "[Subtitles] Last subtitle end: %.2fs", last_subtitle_end
                    )

                    # ?먮쭑 ?곸슜

                    final_video = CompositeVideoClip([final_video] + subtitle_clips)

                    final_video.fps = original_fps

                    subtitle_applied = True

                else:
                    logger.debug("[鍮꾨뵒??泥섎━] ?앹꽦???먮쭑???놁쓬")

            except Exception as e:
                ui_controller.write_error_log(e)

        else:
            logger.debug("[鍮꾨뵒??泥섎━] ?먮쭑 ?앹꽦 嫄대꼫?")

        # 워터마크 적용

        watermark_enabled = getattr(app, "watermark_enabled", False)

        watermark_channel_name = getattr(app, "watermark_channel_name", "")

        watermark_position = getattr(app, "watermark_position", "bottom_right")

        if watermark_enabled and watermark_channel_name:
            # 영상 크기 확인 (None 방어)

            video_w = getattr(app, "cached_video_width", None) or 1080

            video_h = getattr(app, "cached_video_height", None) or 1920

            logger.info(
                "[워터마크] 적용 중: '%s' at %s (%dx%d)",
                watermark_channel_name,
                watermark_position,
                video_w,
                video_h,
            )

            try:
                watermark_clip = VideoTool._create_watermark_clip(
                    app,
                    watermark_channel_name,
                    watermark_position,
                    video_w,
                    video_h,
                    final_video.duration,
                )

                if watermark_clip:
                    final_video = CompositeVideoClip([final_video, watermark_clip])

                    final_video.fps = original_fps

                    logger.info("[워터마크] 적용 완료")

                else:
                    logger.warning("[워터마크] 클립 생성 실패")

            except Exception as e:
                logger.error("[워터마크] 적용 중 오류: %s", e)

                ui_controller.write_error_log(e)

        else:
            if watermark_enabled and not watermark_channel_name:
                logger.warning("[워터마크] 채널 이름이 비어있어 건너뜀")

        if subtitle_applied and last_subtitle_end > 0:
            # ?먮쭑 湲곗??쇰줈 ?먮Ⅴ湲?(CTA 완전 표시 + 2초 여유)

            if final_video.duration > last_subtitle_end + 2.0:
                cut_point = last_subtitle_end + 2.0

                logger.debug(
                    "[Trim] Using subtitle end: %.1fs -> %.1fs",
                    final_video.duration,
                    cut_point,
                )

                final_video = final_video.subclip(0, cut_point)

                logger.debug(
                    "[Trim] Completed subtitle-based cut: %.1fs", final_video.duration
                )

            else:
                logger.debug(
                    "[Trim] No trim needed - video already ends at %.1fs",
                    final_video.duration,
                )

        else:
            # ?ㅻ뵒??湲곗??쇰줈 ?먮Ⅴ湲?(?먮쭑???녿뒗 寃쎌슦)

            if final_video.duration > audio_duration + 2.5:
                cut_point = audio_duration + 2.5

                logger.debug(
                    "[Trim] Using audio duration: %.1fs -> %.1fs",
                    final_video.duration,
                    cut_point,
                )

                final_video = final_video.subclip(0, cut_point)

                logger.debug(
                    "[Trim] Completed audio-based cut: %.1fs", final_video.duration
                )

        app.update_progress_state("video", "processing", 70)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 상품명 추출 (batch.utils의 함수 사용)

        product_name = _extract_product_name(app)

        # 파일명: 날짜_상품명.mp4

        output_filename = f"{timestamp}_{product_name}.mp4"

        message_highlights = []

        if app.mirror_video.get():
            message_highlights.append("- Mirroring applied")

        if app.add_subtitles.get():
            message_highlights.append("- Korean subtitles burned-in")

        if selected_voice:
            message_highlights.append(f"- TTS voice: {selected_voice}")

        temp_dir = tempfile.mkdtemp(prefix="final_video_")

        output_path = os.path.join(temp_dir, output_filename)

        logger.debug("[Output] Temporary export path: %s", output_path)

        app.update_progress_state("video", "processing", 80)

        logger.debug("[?몄퐫?? 理쒖쥌 ?곸긽 ?뚮뜑留??쒖옉")

        # 임시 오디오 파일 경로 (절대 경로 사용)

        temp_audio_path = os.path.join(temp_dir, "temp-audio.m4a")

        # MP4 최대 호환성을 위한 필수 옵션

        safe_ffmpeg_params = [
            "-profile:v",
            "high",  # 4K 지원을 위한 High 프로파일
            "-level",
            "5.1",  # 4K 60fps까지 지원 (최대 호환성)
            "-pix_fmt",
            "yuv420p",  # 대부분의 플레이어 호환
            "-movflags",
            "+faststart",  # 메타데이터를 파일 앞으로 이동
        ]

        final_video.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=temp_audio_path,
            remove_temp=True,
            preset="ultrafast",
            fps=original_fps,
            logger="bar",
            threads=4,
            ffmpeg_params=safe_ffmpeg_params,
        )

        final_duration = final_video.duration

        file_size = (
            os.path.getsize(output_path) / (1024 * 1024)
            if os.path.exists(output_path)
            else 0.0
        )

        app.final_video_path = output_path

        app.final_video_temp_dir = temp_dir

        if hasattr(app, "register_generated_video"):
            app.register_generated_video(
                selected_voice,
                output_path,
                final_duration,
                file_size,
                temp_dir,
                message_highlights,
            )

        logger.info(
            "[Complete] Temp file created: %s (%.1f MB)", output_path, file_size
        )

        logger.info("[Complete] Final duration: %.1fs", final_duration)

        video.close()

        new_audio.close()

        final_video.close()

        # 파일 핸들 해제 대기 (Windows에서 ffmpeg 프로세스 완전 종료 대기)

        import gc

        import time

        import subprocess

        gc.collect()

        time.sleep(0.5)  # Windows에서 파일 핸들 해제에 필요한 대기 시간

        # NTFS 권한 설정: Everyone 읽기 권한 추가 (다른 컴퓨터에서도 열 수 있도록)

        try:
            subprocess.run(
                [
                    "icacls",
                    output_path,
                    "/inheritance:e",
                    "/grant",
                    "*S-1-1-0:(R)",  # Everyone
                    "/grant",
                    "*S-1-5-32-545:(R)",  # Users group
                ],
                check=True,
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=30,  # 30 second timeout to prevent hanging
            )

            logger.debug("  권한 설정: 읽기 권한 추가 완료")

        except subprocess.TimeoutExpired:
            logger.warning("  권한 설정 타임아웃 (무시됨)")

        except subprocess.SubprocessError as e:
            logger.warning("  권한 설정 실패 (무시됨): %s", e)

            ui_controller.write_error_log(e)

        try:
            if os.path.exists(combined_audio_path):
                os.remove(combined_audio_path)

        except OSError as cleanup_err:
            logger.warning("[Cleanup] Failed to remove temp audio: %s", cleanup_err)

        # ═══════════════════════════════════════════════════════════

        # 영상 품질 검증 (Gemini Video Understanding)

        # ═══════════════════════════════════════════════════════════

        validation_enabled = getattr(app, "enable_video_validation", True)

        if validation_enabled and os.path.exists(output_path):
            app.update_status("영상 품질 검증 중...")

            app.update_progress_state(
                "video", "processing", 95, "영상 품질을 검증하고 있습니다."
            )

            try:
                validator = VideoValidationManager(app)

                validation_passed, final_path, validation_result = (
                    validator.validate_and_fix(
                        output_path,
                        auto_fix=getattr(
                            app, "auto_fix_video", False
                        ),  # 자동 수정은 기본 비활성화
                    )
                )

                # 검증 결과 저장

                app.last_validation_result = validation_result

                if validation_passed:
                    logger.info("[영상 검증] 품질 검증 통과")

                else:
                    # 검증 실패해도 영상은 저장 (사용자가 확인 가능하도록)

                    vr = validation_result.get("validation_result", validation_result)

                    score = vr.get("score", 0)

                    logger.warning("[영상 검증] 품질 검증 미통과 (점수: %d/100)", score)

                    logger.warning(
                        "[영상 검증] 영상은 저장되었습니다. 검증 결과를 확인하세요."
                    )

                    # 검증 요약 출력

                    logger.info(validator.get_summary())

                # 최종 경로 업데이트 (수정된 경우)

                if final_path != output_path:
                    app.final_video_path = final_path

            except Exception as val_error:
                # 검증 실패해도 영상 생성은 성공으로 처리

                logger.error("[영상 검증] 검증 중 오류 발생 (무시됨): %s", val_error)

                ui_controller.write_error_log(val_error)

        # ═══════════════════════════════════════════════════════════

        app.update_progress_state("video", "completed", 100)

        app.update_overall_progress("video", "completed", 100)

        app.update_status("전체 작업 완료!")

        app.save_generated_videos_locally()

    except Exception as e:
        ui_controller.write_error_log(e)

        app.update_status("鍮꾨뵒???앹꽦 ?ㅻ쪟")

        app.update_progress_state("video", "error", 0)

        app.update_overall_progress("video", "error", 0)

        error_msg = f"理쒖쥌 鍮꾨뵒???앹꽦 ?ㅽ뙣:\n{str(e)}"

        logger.error("\n[?ㅻ쪟] %s", error_msg)

        # 오류 발생 시에도 파일 핸들 해제 (Windows 파일 잠금 방지)

        try:
            if "video" in dir() and video is not None:
                video.close()

        except Exception as cleanup_err:
            logger.warning("[Cleanup] Failed to close video: %s", cleanup_err)

        try:
            if "new_audio" in dir() and new_audio is not None:
                new_audio.close()

        except Exception as cleanup_err:
            logger.warning("[Cleanup] Failed to close audio: %s", cleanup_err)

        try:
            if "final_video" in dir() and final_video is not None:
                final_video.close()

        except Exception as cleanup_err:
            logger.warning("[Cleanup] Failed to close final_video: %s", cleanup_err)

        show_error(app.root, "???ㅻ쪟", error_msg)


def combine_tts_files(app, target_duration=None):
    """?⑥씪 TTS ?뚯씪???곸긽 湲몄씠??留욎떠 議곗젙 - ?덉쟾??諛곗냽 泥섎━"""

    try:
        if not app._per_line_tts or not app._per_line_tts[0]["path"]:
            return None

        tts_path = app._per_line_tts[0]["path"]

        if not os.path.exists(tts_path):
            logger.debug("[TTS ?뚯씪] 議댁옱?섏? ?딆쓬: %s", tts_path)

            return None

        # Gemini Audio Understanding이 이미 정확한 타임스탬프 제공 - 추가 조정 불필요

        logger.debug("[TTS 파일] Gemini 타임스탬프 사용 - 메타데이터 조정 없음")

        # ???대? 議곗젙???뚯씪?몄? ?뺤씤 ??

        filename = os.path.basename(tts_path)

        if "length_adjusted" in filename:
            logger.debug("[TTS 議곗젙] 寃쎄퀬: ?대? 議곗젙???뚯씪?낅땲?? %s", tts_path)

            # ?먮낯 TTS瑜?李얠븘???ъ슜?섍굅???먮윭 諛쒖깮

            for tts_data in app._per_line_tts:
                if tts_data["path"] and "full_script_tts" in tts_data["path"]:
                    tts_path = tts_data["path"]

                    logger.debug("[TTS 議곗젙] ?먮낯 ?뚯씪 ?ъ슜: %s", tts_path)

                    _update_tts_metadata_path(app, tts_path)

                    break

            else:
                # ?먮낯??李얠쓣 ???놁쑝硫?洹몃?濡?吏꾪뻾 (?꾪뿕)

                logger.debug(
                    "[TTS 議곗젙] 二쇱쓽: ?먮낯??李얠쓣 ???놁뼱 議곗젙???뚯씪 ?ъ슜"
                )

        # ?먮낯 鍮꾨뵒??湲몄씠 ?뺤씤

        if target_duration is None:
            target_duration = app.get_video_duration_helper()

        # TTS ?뚯씪 湲몄씠 ?뺤씤

        audio = AudioSegment.from_wav(tts_path)

        audio_duration = len(audio) / 1000.0

        logger.debug(
            "[TTS Adjust] Original length: %.1fs, target: %.1fs",
            audio_duration,
            target_duration,
        )

        # 湲몄씠 李⑥씠媛 1珥??대궡硫?洹몃?濡??ъ슜

        if abs(audio_duration - target_duration) <= 1.0:
            logger.debug(
                "[TTS 議곗젙] 湲몄씠媛 ?곸젅??(李⑥씠 %s珥?, 洹몃?濡??ъ슜",
                abs(audio_duration - target_duration),
            )

            return tts_path

        # ??怨좎쑀??議곗젙 ?뚯씪紐??앹꽦 (??꾩뒪?ы봽 + ?쒕뜡) ??

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        random_suffix = secrets.token_hex(4)

        adjusted_filename = f"length_adjusted_tts_{timestamp}_{random_suffix}.wav"

        adjusted_path = os.path.join(app.tts_output_dir, adjusted_filename)

        if audio_duration > target_duration:
            # TTS媛 ??湲?寃쎌슦 諛곗냽 ?곸슜

            target_duration_with_margin = target_duration - 1.0  # 1珥???吏㏐쾶

            if target_duration_with_margin <= 0:
                target_duration_with_margin = target_duration * 0.95

            speed_ratio = audio_duration / target_duration_with_margin

            logger.debug(
                "[TTS Adjust] Speed needed: %.2fx to %.1f sec",
                speed_ratio,
                target_duration_with_margin,
            )

            # ???덉쟾??諛곗냽 泥섎━ ??

            if speed_ratio <= 1.5:
                # 1.5諛곗냽 ?댄븯: ?덉쭏 ?곗꽑 諛⑹떇

                logger.debug("[TTS 議곗젙] 諛⑸쾿: 怨좏뭹吏?諛곗냽 (pydub effects)")

                # pydub??effects.speedup ?ъ슜

                from pydub.effects import speedup

                adjusted_audio = speedup(
                    audio, playback_speed=speed_ratio, chunk_size=50, crossfade=10
                )

            elif speed_ratio <= 2.0:
                # 1.5~2諛곗냽: 以묎컙 ?덉쭏

                logger.debug(
                    "[TTS 議곗젙] 諛⑸쾿: 以묎컙 ?덉쭏 諛곗냽 (frame rate 議곗젙)"
                )

                adjusted_audio = audio._spawn(
                    audio.raw_data,
                    overrides={"frame_rate": int(audio.frame_rate * speed_ratio)},
                ).set_frame_rate(audio.frame_rate)

            else:
                # 2諛곗냽 珥덇낵: 寃쎄퀬 ??理쒕? 2諛곗냽?쇰줈 ?쒗븳

                logger.debug(
                    "[TTS 議곗젙] 寃쎄퀬: %s諛곗냽? ?덈Т 鍮좊쫫, 2諛곗냽?쇰줈 ?쒗븳",
                    speed_ratio,
                )

                speed_ratio = 2.0

                adjusted_audio = audio._spawn(
                    audio.raw_data,
                    overrides={"frame_rate": int(audio.frame_rate * 2.0)},
                ).set_frame_rate(audio.frame_rate)

            # ??議곗젙???ㅻ뵒??湲몄씠 ?뺤씤 ??

            adjusted_duration = len(adjusted_audio) / 1000.0

            logger.debug(
                "[TTS Adjust] Speed result: %.1fs -> %.1fs",
                audio_duration,
                adjusted_duration,
            )

            adjusted_audio.export(adjusted_path, format="wav")

            # 배속 처리된 오디오에서 앞 무음 오프셋 다시 감지 (자막 싱크 보정)

            new_offset = VideoTool._detect_audio_start_offset(adjusted_path)

            logger.debug("[TTS Adjust] 배속 후 앞 무음 오프셋: %.3fs", new_offset)

            _rescale_tts_metadata_to_duration(
                app, adjusted_duration, new_path=adjusted_path, start_offset=new_offset
            )

            if hasattr(app, "tts_files"):
                app.tts_files = [adjusted_path]

            logger.debug("[TTS 議곗젙] 諛곗냽 ?뚯씪 ?앹꽦: %s", adjusted_filename)

        else:
            # TTS媛 吏㏃? 寃쎌슦 ?앹뿉 臾댁쓬 異붽?

            silence_duration = int((target_duration - audio_duration) * 1000)

            logger.debug("[TTS Adjust] Added silence: %.1fs", silence_duration / 1000)

            silence = AudioSegment.silent(duration=silence_duration)

            adjusted_audio = audio + silence

            adjusted_audio.export(adjusted_path, format="wav")

            # 무음 추가된 오디오에서 앞 무음 오프셋 확인 (원본과 동일해야 함)

            adjusted_duration = len(adjusted_audio) / 1000.0

            current_offset = VideoTool._detect_audio_start_offset(adjusted_path)

            logger.debug("[TTS Adjust] 무음 추가 후 앞 오프셋: %.3fs", current_offset)

            _rescale_tts_metadata_to_duration(
                app,
                adjusted_duration,
                new_path=adjusted_path,
                start_offset=current_offset,
            )

            if hasattr(app, "tts_files"):
                app.tts_files = [adjusted_path]

            logger.debug("[TTS 議곗젙] 臾댁쓬 異붽? ?뚯씪 ?앹꽦: %s", adjusted_filename)

        # ??理쒖쥌 ?뺤씤 ??

        if os.path.exists(adjusted_path):
            final_audio = AudioSegment.from_wav(adjusted_path)

            final_duration = len(final_audio) / 1000.0

            logger.debug(
                "[TTS Adjust] Final verify: %.1f sec (target: %.1f sec)",
                final_duration,
                target_duration,
            )

        return adjusted_path

    except Exception as e:
        logger.error("[TTS Adjustment Error] %s", e, exc_info=True)

        ui_controller.write_error_log(e)

        return tts_path if "tts_path" in locals() else None


def _update_tts_metadata_path(app, new_path):
    """Update stored TTS metadata to reference the latest audio path."""

    if not new_path:
        return

    per_line = getattr(app, "_per_line_tts", None)

    if not per_line:
        return

    updated = []

    for entry in per_line:
        if isinstance(entry, dict):
            new_entry = dict(entry)

            new_entry["path"] = new_path

            updated.append(new_entry)

        else:
            updated.append(entry)

    app._per_line_tts = updated

    logger.debug("[Subtitles] Updated TTS metadata audio path")


def _rescale_tts_metadata_to_duration(
    app, total_duration, new_path=None, tolerance=0.001, start_offset=None
):
    """Rescale per-line TTS metadata to match a new audio duration."""

    if not app or total_duration is None or total_duration < 0:
        return

    per_line = getattr(app, "_per_line_tts", None)

    if not per_line:
        return

    numeric_starts = []

    numeric_ends = []

    for entry in per_line:
        if not isinstance(entry, dict):
            continue

        start_val = entry.get("start")

        end_val = entry.get("end")

        if isinstance(start_val, (int, float)):
            numeric_starts.append(float(start_val))

        if isinstance(end_val, (int, float)):
            numeric_ends.append(float(end_val))

    if not numeric_ends:
        if new_path:
            _update_tts_metadata_path(app, new_path)

        return

    current_min_start = min(numeric_starts) if numeric_starts else 0.0

    current_max_end = max(numeric_ends)

    if current_max_end < current_min_start:
        current_max_end = current_min_start

    current_span = max(current_max_end - current_min_start, 0.0)

    target_offset = start_offset if start_offset is not None else current_min_start

    if target_offset < 0:
        target_offset = 0.0

    target_total = max(total_duration, target_offset)

    target_span = max(target_total - target_offset, 0.0)

    need_scale = current_span > 0 and abs(target_span - current_span) > tolerance

    need_offset = abs(target_offset - current_min_start) > tolerance

    need_path = bool(new_path)

    if not (need_scale or need_offset or need_path):
        return

    scale = target_span / current_span if current_span > 0 else 1.0

    updated = []

    for entry in per_line:
        if not isinstance(entry, dict):
            updated.append(entry)

            continue

        new_entry = dict(entry)

        start_val = entry.get("start")

        end_val = entry.get("end")

        if isinstance(start_val, (int, float)):
            rel_start = float(start_val) - current_min_start

            if current_span > 0:
                new_start = target_offset + rel_start * scale

            else:
                new_start = target_offset + max(rel_start, 0.0)

            if new_start < 0:
                new_start = 0.0

            new_entry["start"] = new_start

        if isinstance(end_val, (int, float)):
            rel_end = float(end_val) - current_min_start

            if current_span > 0:
                new_end = target_offset + rel_end * scale

            else:
                new_end = target_offset + max(rel_end, 0.0)

            if isinstance(new_entry.get("start"), (int, float)):
                new_end = max(new_end, new_entry["start"])

            new_entry["end"] = new_end

        if need_path:
            new_entry["path"] = new_path

        updated.append(new_entry)

    # 마지막 자막의 end 시간 강제 변경 제거 - 오디오와 싱크 보존

    # 각 자막의 타이밍을 비례적으로만 조정하여 원래 타이밍 유지

    # (기존 코드는 마지막 자막을 영상 끝까지 늘려서 싱크가 틀어짐)

    app._per_line_tts = updated

    if need_scale or need_offset:
        logger.debug(
            "[Subtitles] Rescaled metadata span %.3fs -> %.3fs (offset %.3fs -> %.3fs)",
            current_span,
            target_span,
            current_min_start,
            target_offset,
        )
    elif need_path:
        logger.debug("[Subtitles] Updated TTS metadata audio path")


def _extend_last_subtitle_to_video_end(app, video_duration):
    """

    [DEPRECATED] 이 함수는 더 이상 사용하지 않습니다.



    문제점:

    - Gemini 타임스탬프가 계산한 정확한 종료 시점을 덮어씀

    - 자막이 오디오 끝난 뒤에도 계속 표시됨

    - 자막 기반 트리밍 로직이 작동하지 않음 (last_subtitle_end = video_duration)



    대안:

    - Gemini 타임스탬프를 그대로 존중

    - CTA 표시가 필요하면 별도의 CTA 자막 클립으로 처리



    기존 동작 (참고용):

    Extend the last subtitle to the end of the video for complete CTA display.

    This ensures CTA subtitles are visible until the video ends.

    """

    # DEPRECATED: 이 함수는 호출되지 않음

    logger.warning(
        "[WARNING] _extend_last_subtitle_to_video_end is deprecated and should not be called"
    )

    if not app or video_duration is None or video_duration <= 0:
        return

    per_line = getattr(app, "_per_line_tts", None)

    if not per_line:
        return

    # Find the last subtitle entry with valid timing

    last_entry = None

    for entry in reversed(per_line):
        if isinstance(entry, dict) and isinstance(entry.get("end"), (int, float)):
            last_entry = entry

            break

    if not last_entry:
        return

    original_start = last_entry.get("start", 0.0)

    original_end = last_entry.get("end")

    # ALWAYS set last subtitle end to video end for complete CTA display

    # If start is beyond video end, adjust start to ensure minimum display duration

    if original_start >= video_duration:
        # Start is beyond video - move it back to show subtitle

        min_duration = 1.0  # Minimum 1 second display

        last_entry["start"] = max(0.0, video_duration - min_duration)

        logger.debug(
            "[Subtitles] Adjusted last subtitle start from %.2fs to %.2fs (was beyond video end)",
            original_start,
            last_entry["start"],
        )

    last_entry["end"] = video_duration

    logger.debug(
        "[Subtitles] Set last subtitle end to %.2fs (was %.2fs) - CTA complete display guaranteed",
        video_duration,
        original_end,
    )


def create_subtitle_clips(app, video_duration):
    """Generate subtitle clips using improved helper."""

    # CTA 자막 보호: target_video_duration 사용 (audio_duration + 3.0s)

    # _per_line_tts의 마지막 세그먼트가 video_duration을 초과해도 표시되도록

    return create_subtitle_clips_improved(app, video_duration)


def create_subtitle_clips_improved(app, video_duration):
    """Create one-line Korean subtitles derived from translation text or TTS metadata."""

    subtitle_clips = []

    try:
        timed_segments = _build_timed_subtitle_segments(app, video_duration)

        if timed_segments and _metadata_segments_meaningful(
            timed_segments, video_duration
        ):
            logger.info(
                "[Subtitles] Using %d timed segments for burn-in", len(timed_segments)
            )

            for idx_preview, (start_ts, duration, text) in enumerate(
                timed_segments[: min(5, len(timed_segments))], start=1
            ):
                end_ts = start_ts + duration

                sample = (text or "").strip()

                if len(sample) > 60:
                    sample = sample[:57] + "..."

                logger.debug(
                    "[Subtitles] Seg[%d] %.2f-%.2fs :: %s",
                    idx_preview,
                    start_ts,
                    end_ts,
                    sample,
                )

            video_width, video_height = _resolve_video_dimensions(app)

            for start_ts, duration, text in timed_segments:
                clip = VideoTool._create_single_line_subtitle(
                    app,
                    text,
                    duration,
                    start_ts,
                    video_width,
                    video_height,
                )

                if clip:
                    subtitle_clips.append(clip)

            if subtitle_clips:
                logger.info(
                    "[Subtitles] Applied %d subtitle clips", len(subtitle_clips)
                )

            return subtitle_clips

        elif timed_segments:
            logger.warning(
                "[Subtitles] Timed metadata insufficient (%d segment), falling back to translation text",
                len(timed_segments),
            )

        max_chars = 10

        fallback_segments = _extract_translation_segments(
            app, desired_count=None, max_chars=max_chars
        )

        logger.debug(
            "[Subtitles] Translation fallback segments: %d", len(fallback_segments)
        )

        if not fallback_segments:
            logger.warning(
                "[Subtitles] Translation text missing, skipping subtitle generation."
            )

            return []

        video_width, video_height = _resolve_video_dimensions(app)

        for idx_preview, text in enumerate(
            fallback_segments[: min(5, len(fallback_segments))], start=1
        ):
            sample = text.strip()

            if len(sample) > 60:
                sample = sample[:57] + "..."

            logger.debug("[Subtitles] Line %d: %s", idx_preview, sample)

        if not fallback_segments:
            logger.warning("[Subtitles] Could not derive any caption segments.")

            return []

        segment_duration = max(0.5, video_duration / len(fallback_segments))

        current_time = 0.0

        for text in fallback_segments:
            if current_time >= video_duration:
                break

            duration = min(segment_duration, max(0.5, video_duration - current_time))

            text = text.replace("\n", " ").strip()

            subtitle_clip = VideoTool._create_single_line_subtitle(
                app,
                text,
                duration,
                current_time,
                video_width,
                video_height,
            )

            if subtitle_clip:
                subtitle_clips.append(subtitle_clip)

            current_time += duration

        if subtitle_clips:
            logger.info("[Subtitles] Applied %d subtitle clips", len(subtitle_clips))

        return subtitle_clips

    except Exception as exc:
        logger.error("[Subtitles] Error during caption generation: %s", exc)

        ui_controller.write_error_log(exc)

        return []


def _metadata_segments_meaningful(segments, video_duration):
    """Return True if timed segments cover the video with more than one meaningful chunk."""

    if not segments:
        return False

    if len(segments) < 2:
        start, duration, text = segments[0]

        if duration >= video_duration * 0.9:
            return False

        if len((text or "").strip()) <= 5:
            return False

    total_covered = sum(min(duration, video_duration) for _, duration, _ in segments)

    if total_covered < max(2.0, video_duration * 0.3):
        return False

    return True


def _resolve_video_dimensions(app):
    """Return cached video dimensions, loading once if necessary."""

    width = getattr(app, "cached_video_width", None)

    height = getattr(app, "cached_video_height", None)

    if width and height:
        logger.debug("[Subtitles] Using cached dimensions %dx%d", width, height)

        return int(width), int(height)

    if app.video_source.get() == "local":
        source_video = app.local_file_path

    else:
        source_video = app._temp_downloaded_file

    video_width = 1080

    video_height = 1920

    if source_video and os.path.exists(source_video):
        temp_video = None

        try:
            temp_video = VideoFileClip(source_video)

            video_width = temp_video.w

            video_height = temp_video.h

            logger.debug(
                "[Subtitles] Measured dimensions %dx%d from source",
                video_width,
                video_height,
            )

        except Exception as exc:
            ui_controller.write_error_log(exc)

            logger.warning("[Subtitles] Failed to measure video dimensions: %s", exc)

        finally:
            if temp_video is not None:
                try:
                    temp_video.close()

                except Exception:
                    pass  # Cleanup error, ignore

    setattr(app, "cached_video_width", video_width)

    setattr(app, "cached_video_height", video_height)

    logger.debug(
        "[Subtitles] Cached dimensions set to %dx%d", video_width, video_height
    )

    return int(video_width), int(video_height)


def _build_timed_subtitle_segments(app, video_duration):
    """Build subtitle segments from metadata or analysis timestamps."""

    per_line = getattr(app, "_per_line_tts", None)

    # ========== [SYNC DEBUG] 자막 생성 시작 - 입력 데이터 상세 출력 ==========

    logger.debug("=" * 70)

    logger.debug("[SYNC DEBUG] _build_timed_subtitle_segments 시작")

    logger.debug("=" * 70)

    logger.debug("  영상 길이: %.3f초", video_duration)

    logger.debug("  _per_line_tts 개수: %d", len(per_line) if per_line else 0)

    # tts_sync_info 출력

    sync_info = getattr(app, "tts_sync_info", {}) or {}

    logger.debug("  tts_sync_info:")

    logger.debug(
        "    - timestamps_source: %s", sync_info.get("timestamps_source", "unknown")
    )

    logger.debug("    - speeded_duration: %s", sync_info.get("speeded_duration", "N/A"))

    logger.debug(
        "    - audio_start_offset: %s", sync_info.get("audio_start_offset", "N/A")
    )

    if per_line:
        logger.debug("  [입력 _per_line_tts 전체]")

        for i, entry in enumerate(per_line):
            if isinstance(entry, dict):
                text_preview = (
                    entry.get("text", "")[:15] if entry.get("text") else f"seg{i}"
                )

                start = entry.get("start", "N/A")

                end = entry.get("end", "N/A")

                if isinstance(start, (int, float)) and isinstance(end, (int, float)):
                    duration = end - start

                    logger.debug(
                        "    #%d: %.3fs - %.3fs (%.3fs) '%s'",
                        i + 1,
                        start,
                        end,
                        duration,
                        text_preview,
                    )

                else:
                    logger.debug(
                        "    #%d: start=%s, end=%s '%s'",
                        i + 1,
                        start,
                        end,
                        text_preview,
                    )

            else:
                logger.debug("    #%d: [not a dict] %s", i + 1, type(entry))

    logger.debug("=" * 70)

    segments = []

    skipped = 0

    seen_segments = set()  # 중복 체크용: (start_ts, text) 저장

    duplicates = 0

    if per_line:
        for idx, item in enumerate(per_line, start=1):
            # Skip 조건 1: dict가 아닌 경우

            if not isinstance(item, dict):
                skipped += 1

                logger.debug(
                    "[Subtitles Skip] Seg #%d: Not a dict (type=%s)",
                    idx,
                    type(item).__name__,
                )

                continue

            text = (item.get("text") or "").strip()

            start = item.get("start")

            end = item.get("end")

            # Skip 조건 2: 필수 필드 누락

            if (
                not text
                or not isinstance(start, (int, float))
                or not isinstance(end, (int, float))
            ):
                skipped += 1

                missing_fields = []

                if not text:
                    missing_fields.append("text")

                if not isinstance(start, (int, float)):
                    missing_fields.append(f"start({type(start).__name__})")

                if not isinstance(end, (int, float)):
                    missing_fields.append(f"end({type(end).__name__})")

                logger.debug(
                    "[Subtitles Skip] Seg #%d: Missing/invalid fields: %s",
                    idx,
                    ", ".join(missing_fields),
                )

                continue

            # Skip 조건 3: 잘못된 타임스탬프 (end <= start)

            if end <= start:
                if idx == len(per_line):
                    # 마지막 세그먼트가 0초 길이로 눌려 CTA가 사라지는 경우 복구

                    min_tail = 0.6  # CTA 노출을 위한 최소 노출 시간

                    safe_start = (
                        float(start) if isinstance(start, (int, float)) else 0.0
                    )

                    if safe_start >= video_duration:
                        safe_start = max(0.0, video_duration - min_tail)

                    safe_end = min(video_duration, safe_start + min_tail)

                    if safe_end <= safe_start:
                        safe_end = safe_start + 0.25  # 그래도 0이면 짧게라도 노출

                    logger.debug(
                        "[Subtitles Adjust] Last segment had non-positive duration -> %.2f-%.2fs",
                        safe_start,
                        safe_end,
                    )

                    start = safe_start

                    end = safe_end

                else:
                    skipped += 1

                    logger.debug(
                        "[Subtitles Skip] Seg #%d: Invalid timing (start=%.2fs >= end=%.2fs) - '%s'",
                        idx,
                        start,
                        end,
                        text[:20],
                    )

                    continue

            start_ts = max(0.0, float(start))

            end_ts = max(0.0, float(end))

            # Skip 조건 4: 너무 늦게 시작하는 자막

            # CTA 보호: 자막이 영상 길이를 초과해도 표시 (target_video_duration 범위 내)

            # video_duration 대신 더 넉넉한 범위 사용

            if start_ts >= video_duration + 5.0:  # 5초 이상 초과만 skip (CTA 완전 보호)
                skipped += 1

                logger.debug(
                    "[Subtitles Skip] Seg #%d: Starts too late (%.2fs > video_duration %.2fs + 5.0s) - '%s'",
                    idx,
                    start_ts,
                    video_duration,
                    text[:20],
                )

                continue

            # Gemini 타임스탬프를 그대로 사용 (싱크 보존)

            actual_duration = end_ts - start_ts

            # 디버깅: 첫 3개와 마지막 3개 세그먼트 로그

            if len(segments) < 3 or len(segments) >= len(per_line) - 3:
                logger.debug(
                    "[Subtitle Timing] Seg #%d: %.2fs-%.2fs (%.2fs) '%s'",
                    len(segments) + 1,
                    start_ts,
                    end_ts,
                    actual_duration,
                    text[:20],
                )

            # 자막 클립이 비디오 끝을 초과하면 moviepy 오류 발생

            # start_ts + duration이 video_duration을 초과하지 않도록 조정

            if start_ts + actual_duration > video_duration:
                duration = max(0.2, video_duration - start_ts)

                logger.debug(
                    "[Subtitle Trim] Seg #%d trimmed: %.2fs -> %.2fs (video ends at %.2fs)",
                    len(segments) + 1,
                    actual_duration,
                    duration,
                    video_duration,
                )

            else:
                duration = max(0.2, actual_duration)

            # Skip 조건 5: 너무 짧은 자막 (0.05초 미만) - 조건 완화!

            if duration < 0.05:  # 0.1에서 0.05로 완화
                skipped += 1

                logger.debug(
                    "[Subtitles Skip] Seg #%d: Too short (%.2fs < 0.05s) - '%s'",
                    idx,
                    duration,
                    text[:20],
                )

                continue

            # Skip 조건 6: 중복 자막 제거

            # 같은 시작 시간(0.1초 이내)과 같은 텍스트를 가진 세그먼트는 중복으로 간주

            segment_key = (
                round(start_ts * 10),
                text,
            )  # 0.1초 단위로 반올림하여 키 생성

            if segment_key in seen_segments:
                duplicates += 1

                logger.debug(
                    "[Subtitles Skip] Seg #%d: Duplicate (start=%.2fs, text='%s')",
                    idx,
                    start_ts,
                    text[:20],
                )

                continue

            seen_segments.add(segment_key)

            # ★ 핵심 수정: 자막 이중 분할 제거 ★

            # TTS 생성 시 Gemini가 분석한 타임스탬프를 그대로 사용

            # 이중 분할 후 균등 분배하면 실제 발화 타이밍과 맞지 않음!

            # _per_line_tts의 세그먼트는 이미 적절히 분할되어 있음 (max_chars=9)

            segments.append((start_ts, duration, text))

        segments.sort(key=lambda x: x[0])

        # ========== [SYNC DEBUG] 최종 자막 segments 상세 출력 ==========

        if segments:
            logger.debug("=" * 70)

            logger.debug("[SYNC DEBUG] 최종 자막 segments - %d개", len(segments))

            logger.debug("=" * 70)

            for i, (start, dur, text) in enumerate(segments):
                end = start + dur

                text_preview = text[:15] if text else f"seg{i}"

                logger.debug(
                    "    #%d: %.3fs - %.3fs (%.3fs) '%s'",
                    i + 1,
                    start,
                    end,
                    dur,
                    text_preview,
                )

            logger.debug("=" * 70)

            summary = f"[Subtitles] Built {len(segments)} timed segments"

            if skipped > 0 or duplicates > 0:
                details = []

                if skipped > 0:
                    details.append(f"skipped {skipped}")

                if duplicates > 0:
                    details.append(f"duplicates {duplicates}")

                summary += f" ({', '.join(details)})"

            logger.info(summary)

        else:
            logger.warning(
                "[Subtitles] No valid timed segments extracted (skipped %d, duplicates %d)",
                skipped,
                duplicates,
            )

    if segments and _metadata_segments_meaningful(segments, video_duration):
        return segments

    analysis_segments = _build_analysis_based_segments(app, video_duration)

    if analysis_segments:
        return analysis_segments

    return segments


def _build_analysis_based_segments(app, video_duration):
    """Construct subtitle segments using analysis timestamps and translated sentences."""

    analysis = getattr(app, "analysis_result", None)

    if not isinstance(analysis, dict):
        return []

    script_entries = analysis.get("script") or []

    if not isinstance(script_entries, list) or not script_entries:
        return []

    timeline = []

    for entry in script_entries:
        if not isinstance(entry, dict):
            continue

        timestamp = str(entry.get("timestamp", "")).strip()

        start_ts = _parse_timestamp_to_seconds(timestamp)

        if start_ts is None:
            continue

        if start_ts >= video_duration:
            continue

        timeline.append((float(start_ts), entry))

    if not timeline:
        return []

    timeline.sort(key=lambda item: item[0])

    translation_segments = _extract_translation_segments(
        app, desired_count=len(timeline), max_chars=10
    )

    if not translation_segments:
        return []

    segments = []

    total = len(timeline)

    for idx, (start_ts, entry) in enumerate(timeline):
        next_start = timeline[idx + 1][0] if idx + 1 < total else video_duration

        # Leave a short guard so adjacent captions do not overlap

        next_start = max(
            start_ts + 0.6, next_start - 0.1 if idx + 1 < total else video_duration
        )

        end_ts = min(video_duration, next_start)

        duration = max(0.6, end_ts - start_ts)

        if start_ts + duration > video_duration:
            duration = max(0.5, video_duration - start_ts)

        if duration <= 0.4:
            continue

        text = (
            translation_segments[idx]
            if idx < len(translation_segments)
            else translation_segments[-1]
        )

        text = (text or "").strip()

        if not text:
            continue

        segments.append((start_ts, duration, text))

    if segments:
        logger.info(
            "[Subtitles] Built %d segments from analysis timestamps", len(segments)
        )

    return segments


def _extract_translation_segments(app, desired_count=None, max_chars=10):
    """Split translated script into ordered segments suitable for subtitles."""

    # TTS 생성 시 사용된 세그먼트를 그대로 사용 (오디오-자막 싱크 보존)

    if (
        hasattr(app, "_per_line_tts")
        and app._per_line_tts
        and isinstance(app._per_line_tts, list)
    ):
        # TTS 세그먼트의 텍스트를 개별로 추출 (합치지 않음!)

        tts_segments = []

        for item in app._per_line_tts:
            if isinstance(item, dict) and "text" in item:
                text = item.get("text", "").strip()

                if text:
                    tts_segments.append(text)

        if tts_segments:
            # TTS 분할을 그대로 사용 - 오디오와 완벽한 싱크!

            logger.debug(
                "[Subtitles] Using TTS segmentation: %d segments (sync preserved)",
                len(tts_segments),
            )

            if desired_count:
                return _map_segments_to_count(tts_segments, desired_count)

            else:
                return tts_segments

    # Fallback: TTS 메타데이터가 없으면 원본 번역 결과 사용

    raw = (getattr(app, "translation_result", None) or "").strip()

    logger.debug("[Subtitles] Fallback to translation text: %d chars", len(raw))

    if not raw:
        return []

    lines = []

    for original_line in raw.splitlines():
        cleaned = original_line.strip()

        if not cleaned:
            continue

        if re.match(r"^[#*=\-]{3,}$", cleaned):
            continue

        lines.append(cleaned)

    if not lines:
        lines = [raw]

    segments = []

    for line in lines:
        segments.extend(_smart_sentence_split(line, max_chars=max_chars))

    segments = [seg.strip() for seg in segments if seg.strip()]

    if not segments:
        return []

    if desired_count:
        segments = _map_segments_to_count(segments, desired_count)

    return segments


def _map_segments_to_count(segments, target):
    """Map an arbitrary list of segments to a target length while keeping order."""

    if not segments or not target:
        return segments

    total = len(segments)

    if total == target:
        return segments

    mapped = []

    for idx in range(target):
        start_idx = math.floor(idx * total / target)

        end_idx = math.floor((idx + 1) * total / target)

        if end_idx <= start_idx:
            end_idx = min(start_idx + 1, total)

        chunk = (
            " ".join(segments[start_idx:end_idx]).strip()
            if end_idx > start_idx
            else segments[min(start_idx, total - 1)]
        )

        if not chunk:
            chunk = segments[min(start_idx, total - 1)]

        mapped.append(chunk)

    return mapped


def _smart_sentence_split(text, max_chars=10):
    """Split Korean text into readable chunks respecting punctuation and length."""

    normalized = re.sub(r"\s+", " ", text or "").strip()

    if not normalized:
        return []

    boundary_pattern = re.compile(r"(?<=[\.?!…！？。])\s+")

    candidates = []

    for part in boundary_pattern.split(normalized):
        sub_parts = re.split(r"\s*(?:\\n|\n)\s*", part)

        for sub in sub_parts:
            candidate = sub.strip()

            if candidate:
                candidates.append(candidate)

    segments = []

    for candidate in candidates:
        working = candidate

        while len(working) > max_chars:
            split_idx = working.rfind(" ", 0, max_chars)

            if split_idx <= 0:
                split_idx = working.find(" ", max_chars)

            if split_idx <= 0:
                split_idx = max_chars

            segments.append(working[:split_idx].strip())

            working = working[split_idx:].strip()

        if working:
            segments.append(working)

    return segments or [normalized]


def _parse_timestamp_to_seconds(timestamp):
    """Convert HH:MM:SS or MM:SS timestamp strings to seconds."""

    if not timestamp:
        return None

    cleaned = str(timestamp).strip()

    if not cleaned:
        return None

    cleaned = cleaned.replace(",", ":")

    parts = cleaned.split(":")

    try:
        numeric_parts = [float(part) for part in parts]

    except ValueError:
        matches = re.findall(r"\d+(?:\.\d+)?", cleaned)

        if not matches:
            return None

        numeric_parts = [float(value) for value in matches]

    if len(numeric_parts) == 3:
        hours, minutes, seconds = numeric_parts

    elif len(numeric_parts) == 2:
        hours = 0.0

        minutes, seconds = numeric_parts

    elif len(numeric_parts) == 1:
        hours = 0.0

        minutes = 0.0

        seconds = numeric_parts[0]

    else:
        return None

    return max(0.0, hours * 3600 + minutes * 60 + seconds)


def _split_subtitle_with_gemini(app, text: str, max_chars: int = 10) -> list:
    """

    Gemini를 사용해 긴 자막을 자연스러운 단위로 분할



    Args:

        app: 앱 인스턴스 (Gemini 클라이언트 접근용)

        text: 분할할 텍스트

        max_chars: 세그먼트당 최대 글자수 (권장)



    Returns:

        분할된 세그먼트 리스트

    """

    try:
        client = getattr(app, "genai_client", None)

        if not client:
            logger.debug("[Subtitle Split] Gemini 클라이언트 없음, 단순 분할 사용")

            return _fallback_split(text, max_chars)

        prompt = get_subtitle_split_prompt(text)

        response = client.models.generate_content(
            model="gemini-2.0-flash", contents=[prompt]
        )

        result_text = ""

        if hasattr(response, "candidates") and response.candidates:
            for candidate in response.candidates:
                if hasattr(candidate, "content") and candidate.content:
                    for part in candidate.content.parts:
                        if hasattr(part, "text") and part.text:
                            result_text += part.text

        if not result_text:
            result_text = getattr(response, "text", "")

        # 결과 파싱

        segments = []

        for line in result_text.strip().split("\n"):
            line = line.strip()

            # 번호나 마커 제거 (예: "1.", "-", "•")

            line = re.sub(r"^[\d\.\-\•\*]+\s*", "", line).strip()

            if line and len(line) >= 2:
                segments.append(line)

        if segments:
            logger.debug(
                "[Subtitle Split] Gemini 분할: '%s...' -> %d개",
                text[:20],
                len(segments),
            )

            return segments

        else:
            return _fallback_split(text, max_chars)

    except Exception as e:
        logger.warning("[Subtitle Split] Gemini 오류: %s, 단순 분할 사용", e)

        ui_controller.write_error_log(e)

        return _fallback_split(text, max_chars)


def _fallback_split(text: str, max_chars: int = 10) -> list:
    """Gemini 실패 시 사용하는 단순 분할"""

    if len(text) <= max_chars:
        return [text]

    # 공백 기준 분할

    words = text.split(" ")

    if len(words) <= 1:
        # 공백 없으면 중간에서 자르기

        mid = len(text) // 2

        return [text[:mid], text[mid:]]

    segments = []

    current = ""

    for word in words:
        test = f"{current} {word}".strip() if current else word

        if len(test) <= max_chars:
            current = test

        else:
            if current:
                segments.append(current)

            current = word

    if current:
        segments.append(current)

    return segments if segments else [text]
