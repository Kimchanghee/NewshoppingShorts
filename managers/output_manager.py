"""
OutputManager - Manages output file and folder operations.

This module handles:
- Output folder selection and management
- Video registration and tracking
- Local file saving and organization
- Folder naming based on URL and timestamps
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

from tkinter import filedialog
from ui.components.custom_dialog import show_info, show_success
from caller import ui_controller
from managers.settings_manager import get_settings_manager
from utils.logging_config import get_logger

logger = get_logger(__name__)


class OutputManager:
    """
    Manager class for handling output file operations.

    This class manages output directories, video file registration,
    and local file saving with organized folder structures.
    """

    def __init__(self, gui):
        """
        Initialize the OutputManager.

        Args:
            gui: Reference to the VideoAnalyzerGUI instance
        """
        self.gui = gui

    def select_output_folder(self):
        """Select local output folder."""
        old_folder = self.gui.output_folder_path
        selected = filedialog.askdirectory(
            parent=self.gui.root, title="Select Output Folder"
        )
        if not selected:
            return
        selected = os.path.abspath(selected)
        os.makedirs(selected, exist_ok=True)

        # 폴더가 실제로 변경되었는지 확인
        folder_changed = old_folder != selected

        self.gui.output_folder_path = selected
        self.gui.output_folder_var.set(selected)
        if (
            hasattr(self.gui, "output_folder_display")
            and self.gui.output_folder_display
        ):
            self.gui.output_folder_display.config(text=selected)

        # ★ 저장 폴더 경로 영구 저장 ★
        try:
            settings = get_settings_manager()
            settings.set_output_folder(selected)
            logger.info("[설정 저장] 저장 폴더 경로: %s", selected)
        except Exception as e:
            logger.error("[설정 저장 실패] %s", e)

        # ★ 폴더 변경 시 다운로드 파일 참조 초기화 (재다운로드 유도) ★
        if folder_changed:
            self.gui._temp_downloaded_file = None
            self.gui.add_log("[저장 폴더 변경] 다음 작업부터 새 폴더에 저장됩니다.")
            self.gui.add_log("[저장 폴더 변경] 영상이 재다운로드됩니다.")

    def get_output_directory(self) -> str:
        """
        Get the output directory path.

        Returns:
            str: Absolute path to the output directory
        """
        path = getattr(
            self.gui, "output_folder_path", os.path.join(os.getcwd(), "outputs")
        )
        os.makedirs(path, exist_ok=True)
        return path

    def refresh_output_folder_display(self):
        """Refresh the output folder display in the UI."""
        if (
            hasattr(self.gui, "output_folder_display")
            and self.gui.output_folder_display
        ):
            self.gui.output_folder_display.config(text=self.gui.output_folder_var.get())

    def _ensure_read_permissions(self, path: str) -> None:
        """
        Best-effort permission fix on Windows so exported files are readable.

        Uses SID values instead of localized group names to avoid locale issues.
        """
        if os.name != "nt":
            return

        try:
            cmd = [
                "icacls",
                path,
                "/inheritance:e",
                "/grant",
                "*S-1-1-0:(R)",  # Everyone
                "/grant",
                "*S-1-5-32-545:(R)",  # Users group
            ]
            if os.path.isdir(path):
                cmd.append("/T")
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception as exc:
            ui_controller.write_error_log(exc)
            # 권한 설정 실패 시 로깅만 하고 기능은 계속 진행
            logger.warning("[OutputManager] 권한 설정 실패 (%s): %s", path, exc)

    def register_generated_video(
        self,
        voice: str,
        path: str,
        duration: float,
        size_mb: float,
        temp_dir: Optional[str] = None,
        features: Optional[List[str]] = None,
    ) -> None:
        """
        Register a generated video and immediately save to output folder.

        Args:
            voice: Voice name used for TTS
            path: Path to the generated video file
            duration: Duration of the video in seconds
            size_mb: Size of the video file in MB
            temp_dir: Optional temporary directory used during generation
            features: Optional list of features applied to the video
        """
        if (
            not hasattr(self.gui, "generated_videos")
            or self.gui.generated_videos is None
        ):
            self.gui.generated_videos = []

        # Capture URL and timestamp for per-URL folder organization
        url = getattr(self.gui, "_current_processing_url", None)
        timestamp = getattr(self.gui, "_processing_start_time", None)

        # ★★★ 즉시 저장: 영상이 생성되는 대로 바로 출력 폴더로 이동 ★★★
        saved_path = self._save_video_immediately(
            path, url, timestamp, temp_dir, voice, duration, size_mb
        )

        record = {
            "voice": voice,
            "path": saved_path if saved_path else path,  # 저장된 경로 사용
            "duration": duration,
            "size_mb": size_mb,
            "temp_dir": None,  # 이미 정리됨
            "features": list(features) if features else [],
            "url": url,
            "timestamp": timestamp,
            "saved": True if saved_path else False,  # 저장 여부 표시
        }
        self.gui.generated_videos.append(record)

        if saved_path:
            self.gui.add_log(
                f"[OUTPUT] ✓ {voice} 즉시 저장됨 - {duration:.1f}s - {size_mb:.1f}MB"
            )
            self.gui.add_log(f"[OUTPUT]   → {saved_path}")
        else:
            self.gui.add_log(
                f"[OUTPUT] Voice {voice} - {duration:.1f}s - {size_mb:.1f}MB -> {path}"
            )

        # 구독 상태 새로고침은 processor.py에서 useWork 호출 후 처리됨
        # 여기서는 중복 호출 방지를 위해 호출하지 않음

    def _save_video_immediately(
        self,
        path: str,
        url: Optional[str],
        timestamp: Optional[Any],
        temp_dir: Optional[str],
        voice: Optional[str] = None,
        duration: Optional[float] = None,
        size_mb: Optional[float] = None,
    ) -> Optional[str]:
        """
        영상을 즉시 출력 폴더로 저장 + 영상별 로그 파일 생성.

        Args:
            path: 원본 영상 경로
            url: 소스 URL
            timestamp: 타임스탬프
            temp_dir: 임시 디렉토리
            voice: 음성 이름
            duration: 영상 길이 (초)
            size_mb: 파일 크기 (MB)

        Returns:
            저장된 경로 또는 None (실패 시)
        """
        if not path or not os.path.exists(path):
            return None

        try:
            base_output_dir = self.get_output_directory()
            os.makedirs(base_output_dir, exist_ok=True)

            # URL별 폴더 생성
            if url:
                # url_timestamps에서 일관된 타임스탬프 사용
                if (
                    hasattr(self.gui, "url_timestamps")
                    and url in self.gui.url_timestamps
                ):
                    timestamp = self.gui.url_timestamps[url]

                folder_name = self._generate_folder_name_for_url(url, timestamp)
                output_dir = os.path.join(base_output_dir, folder_name)
            else:
                output_dir = base_output_dir

            os.makedirs(output_dir, exist_ok=True)
            self._ensure_read_permissions(output_dir)

            # 파일 이동
            filename = os.path.basename(path)
            target = os.path.join(output_dir, filename)

            if os.path.abspath(path) != os.path.abspath(target):
                shutil.move(path, target)

            self._ensure_read_permissions(target)

            # ★★★ 영상별 로그 파일 생성 ★★★
            self._save_video_log(output_dir, filename, voice, duration, size_mb, url)

            # 임시 디렉토리 정리
            if temp_dir and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

            logger.info("=" * 60)
            logger.info("[즉시 저장] 영상이 저장되었습니다!")
            logger.info("=" * 60)
            logger.info("  파일: %s", filename)
            logger.info("  경로: %s", output_dir)
            logger.info("=" * 60)

            return target

        except Exception as exc:
            ui_controller.write_error_log(exc)
            logger.error("[즉시 저장 실패] %s: %s", path, exc)
            return None

    def _save_video_log(
        self,
        output_dir: str,
        video_filename: str,
        voice: Optional[str],
        duration: Optional[float],
        size_mb: Optional[float],
        url: Optional[str],
    ) -> None:
        """
        개별 영상에 대한 로그 파일 생성.

        Args:
            output_dir: 저장 폴더 경로
            video_filename: 영상 파일명 (예: 20251208_123456_상품명.mp4)
            voice: 음성 이름
            duration: 영상 길이 (초)
            size_mb: 파일 크기 (MB)
            url: 원본 URL
        """
        try:
            # 로그 파일명: 영상파일명에서 .mp4를 _log.txt로 변경
            log_filename = video_filename.replace(".mp4", "_log.txt")
            log_path = os.path.join(output_dir, log_filename)

            # 로그 버퍼에서 현재 로그 가져오기
            log_content = ""
            if hasattr(self.gui, "_url_log_buffer") and self.gui._url_log_buffer:
                log_content = "".join(self.gui._url_log_buffer)

            # 로그 파일 작성
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"{'=' * 70}\n")
                f.write(f"영상 생성 로그\n")
                f.write(f"{'=' * 70}\n\n")

                # 기본 정보
                f.write(f"[기본 정보]\n")
                f.write(
                    f"  생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                f.write(f"  영상 파일: {video_filename}\n")
                if voice:
                    f.write(f"  사용 음성: {voice}\n")
                if duration:
                    f.write(f"  영상 길이: {duration:.1f}초\n")
                if size_mb:
                    f.write(f"  파일 크기: {size_mb:.1f}MB\n")
                if url:
                    f.write(f"  원본 URL: {url}\n")
                f.write("\n")

                # 상세 로그
                if log_content:
                    f.write(f"{'=' * 70}\n")
                    f.write(f"[상세 처리 로그]\n")
                    f.write(f"{'=' * 70}\n\n")
                    f.write(log_content)

            logger.info("[로그 저장] %s", log_filename)

        except Exception as e:
            ui_controller.write_error_log(e)
            logger.error("[로그 저장 실패] %s", e)

    def verify_video_log(self, url: str) -> str:
        """
        영상 생성 후 로그 파일을 분석하여 싱크/오류 문제 확인.

        Args:
            url: 검증할 영상의 원본 URL

        Returns:
            str: "통과" (문제 없음) 또는 "로그 확인 필요" (이슈 발견)
        """
        try:
            # 출력 폴더 찾기
            base_output_dir = self.get_output_directory()

            # URL에 해당하는 폴더 찾기
            if hasattr(self.gui, "url_timestamps") and url in self.gui.url_timestamps:
                timestamp = self.gui.url_timestamps[url]
                folder_name = self._generate_folder_name_for_url(url, timestamp)
                output_dir = os.path.join(base_output_dir, folder_name)
            else:
                # 타임스탬프가 없으면 검증 스킵
                logger.debug("[로그 검증] 타임스탬프 없음 - 스킵")
                return "통과"

            if not os.path.exists(output_dir):
                logger.debug("[로그 검증] 폴더 없음: %s", output_dir)
                return "통과"

            # 로그 파일 찾기 (*_log.txt)
            log_files = [f for f in os.listdir(output_dir) if f.endswith("_log.txt")]
            if not log_files:
                logger.debug("[로그 검증] 로그 파일 없음")
                return "통과"

            issues_found = []

            for log_file in log_files:
                log_path = os.path.join(output_dir, log_file)
                try:
                    with open(log_path, "r", encoding="utf-8") as f:
                        log_content = f.read()
                except Exception as read_err:
                    logger.warning("[로그 검증] 읽기 실패: %s", read_err)
                    continue

                # ★ 싱크 문제 패턴 검사 ★
                sync_issues = self._check_sync_issues(log_content)
                if sync_issues:
                    issues_found.extend(sync_issues)

            if issues_found:
                # 이슈 요약 (최대 2개)
                summary = ", ".join(issues_found[:2])
                if len(issues_found) > 2:
                    summary += f" 외 {len(issues_found) - 2}건"
                logger.warning("[로그 검증] 이슈 발견: %s", summary)
                return f"로그 확인 ({summary})"
            else:
                logger.debug("[로그 검증] 통과")
                return "통과"

        except Exception as e:
            ui_controller.write_error_log(e)
            logger.error("[로그 검증] 오류: %s", e)
            return "통과"  # 검증 실패 시 기본값

    def _check_sync_issues(self, log_content: str) -> List[str]:
        """
        로그 내용에서 싱크 문제 패턴 검사.

        Args:
            log_content: 로그 파일 내용

        Returns:
            List[str]: 발견된 이슈 목록
        """
        issues = []

        # 1. start > end 역행 문제
        if re.search(
            r"start\s*>\s*end|역행|start.*보다.*end.*작", log_content, re.IGNORECASE
        ):
            issues.append("타이밍 역행")

        # 2. 오버랩/겹침 문제
        if re.search(r"overlap|겹침|오버랩", log_content, re.IGNORECASE):
            issues.append("구간 겹침")

        # 3. duration 0 또는 음수
        if re.search(
            r"duration\s*[=:]\s*-?\d*\.?\d*\s*(<=|<)\s*0|duration.*0초|길이.*0",
            log_content,
            re.IGNORECASE,
        ):
            issues.append("길이 0")

        # 4. 명시적 에러 키워드
        error_patterns = [
            (r"\[ERROR\]", "ERROR"),
            (r"치명적\s*오류", "치명적 오류"),
            (r"싱크.*실패|sync.*fail", "싱크 실패"),
            (r"자막.*표시.*안.*됨|자막.*누락", "자막 누락"),
        ]
        for pattern, label in error_patterns:
            if re.search(pattern, log_content, re.IGNORECASE):
                if label not in issues:
                    issues.append(label)

        # 5. Whisper 분석 실패 + 폴백 사용
        if re.search(r"Whisper.*실패.*폴백|char_proportional_fallback", log_content):
            # 폴백은 경고 수준이므로 추가하지 않음 (정상 동작)
            pass

        # 6. TTS 생성 실패
        if re.search(r"TTS.*생성.*실패|TTS.*오류", log_content, re.IGNORECASE):
            issues.append("TTS 오류")

        return issues

    def _generate_folder_name_for_url(self, url: str, timestamp: Optional[Any]) -> str:
        """
        Generate folder name in format: YYYYMMDD_HHMMSS_itemname

        Args:
            url: URL of the video source
            timestamp: Optional timestamp for folder naming

        Returns:
            str: Generated folder name
        """
        # Format timestamp
        if timestamp and isinstance(timestamp, datetime):
            date_time = timestamp.strftime("%Y%m%d_%H%M%S")
        else:
            date_time = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Get item name using derive_product_keyword
        item_name = self.gui.derive_product_keyword(max_words=3, max_length=20)
        if not item_name or item_name == "untitled":
            # Extract from URL if keyword extraction fails
            try:
                # Try to extract meaningful part from URL
                url_parts = url.rstrip("/").split("/")
                if len(url_parts) > 0:
                    last_part = url_parts[-1]
                    # Clean the URL part for folder name
                    item_name = re.sub(r"[^\w\s가-힣-]", "", last_part)[:20]
                if not item_name:
                    item_name = "video"
            except Exception as e:
                logger.debug("[폴더명 생성] URL 파싱 실패: %s", e)
                item_name = "video"

        # Combine into folder name
        folder_name = f"{date_time}_{item_name}"
        # Remove any invalid characters for folder names
        folder_name = re.sub(r'[<>:"/\\|?*]', "", folder_name)
        return folder_name

    def _cleanup_log_buffer(self) -> None:
        """
        로그 캡처 종료 및 버퍼 초기화.
        영상별 로그는 _save_video_log에서 이미 저장되므로 여기서는 정리만 수행.
        """
        try:
            # 로그 캡처 종료
            from core.video.batch.processor import _stop_log_capture

            _stop_log_capture(self.gui)
            # 버퍼 초기화
            if hasattr(self.gui, "_url_log_buffer"):
                self.gui._url_log_buffer = []
        except Exception as e:
            ui_controller.write_error_log(e)
            logger.error("[로그 정리 실패] %s", e)

    def save_generated_videos_locally(self, show_popup: bool = True) -> None:
        """
        Save all registered videos to local output folder.

        Organizes videos into folders based on URL and timestamp.
        Cleans up temporary directories after moving files.

        Args:
            show_popup: Whether to show a popup message after saving
        """
        records = list(getattr(self.gui, "generated_videos", []) or [])
        if not records:
            return

        base_output_dir = self.get_output_directory()
        os.makedirs(base_output_dir, exist_ok=True)

        # 저장 경로 명확히 표시
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        is_desktop = os.path.abspath(base_output_dir) == os.path.abspath(desktop_path)
        logger.info("=" * 70)
        logger.info("[파일 저장] 저장 위치 확인")
        logger.info("=" * 70)
        logger.info("저장 경로: %s", base_output_dir)
        logger.info("바탕화면 여부: %s", "바탕화면" if is_desktop else "다른 위치")
        logger.info("저장할 영상 개수: %d개", len(records))
        logger.info("=" * 70)

        saved_paths = []
        # Group records by URL to organize into folders
        url_groups = {}
        for record in records:
            if not isinstance(record, dict):
                continue
            url = record.get("url")
            if url not in url_groups:
                url_groups[url] = []
            url_groups[url].append(record)

        for url, url_records in url_groups.items():
            # Get timestamp from url_timestamps dictionary (for session consistency)
            # This ensures same folder is used even after session restore
            try:
                if (
                    hasattr(self.gui, "url_timestamps")
                    and url in self.gui.url_timestamps
                ):
                    timestamp = self.gui.url_timestamps[url]
                    from datetime import datetime

                    ts_str = (
                        timestamp.strftime("%Y%m%d_%H%M%S")
                        if isinstance(timestamp, datetime)
                        else str(timestamp)
                    )
                    logger.debug("[폴더 일관성] URL별 타임스탬프 사용: %s", ts_str)
                else:
                    # Fallback: try to get from first record
                    first_record = url_records[0]
                    timestamp = first_record.get("timestamp")
                    logger.debug("[폴더 일관성] 레코드 타임스탬프 사용")
            except Exception as e:
                ui_controller.write_error_log(e)
                logger.warning("[폴더 일관성] 타임스탬프 가져오기 실패: %s", e)
                # Fallback to first record
                first_record = url_records[0]
                timestamp = first_record.get("timestamp")

            # Generate folder name for this URL
            if url:
                try:
                    folder_name = self._generate_folder_name_for_url(url, timestamp)
                    output_dir = os.path.join(base_output_dir, folder_name)
                    logger.debug("[폴더 일관성] 저장 경로: %s", output_dir)
                except Exception as e:
                    ui_controller.write_error_log(e)
                    logger.error("[폴더 일관성] 폴더명 생성 실패: %s", e, exc_info=True)
                    # Fallback to base directory
                    output_dir = base_output_dir
            else:
                # Fallback to base directory if no URL
                output_dir = base_output_dir

            os.makedirs(output_dir, exist_ok=True)
            self._ensure_read_permissions(output_dir)

            # Move all videos for this URL to the folder
            for record in url_records:
                path = record.get("path")
                if not path or not os.path.exists(path):
                    continue
                filename = os.path.basename(path)
                target = os.path.join(output_dir, filename)
                try:
                    if os.path.abspath(path) != os.path.abspath(target):
                        shutil.move(path, target)
                    self._ensure_read_permissions(target)
                    saved_paths.append(target)
                    temp_dir = record.get("temp_dir")
                    if temp_dir and os.path.isdir(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as exc:
                    ui_controller.write_error_log(exc)
                    logger.error("[LocalSave] Failed to store %s: %s", path, exc)

            # ★ 로그는 이제 영상별로 저장됨 (_save_video_immediately에서 처리)
            # 로그 버퍼만 정리
            self._cleanup_log_buffer()

        self.gui.generated_videos = []
        # Show popup only when show_popup=True
        if saved_paths and show_popup:
            message = "저장된 파일:\n" + "\n".join(saved_paths)
            show_success(self.gui.root, "저장 완료", message)
        self.refresh_output_folder_display()
