# -*- coding: utf-8 -*-
"""
Auto Updater Module
자동 업데이트 모듈

사용자가 프로그램 실행 시 서버에서 최신 버전을 확인하고,
업데이트가 있으면 알림 후 다운로드합니다.
"""

import os
import sys
import json
import time
import shutil
import hashlib
import tempfile
import threading
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Callable, Tuple

import requests
from utils.logging_config import get_logger

logger = get_logger(__name__)

# 현재 앱 버전 (빌드 시 이 값을 업데이트)
CURRENT_VERSION = "1.3.10"

# 버전 확인 API 엔드포인트
UPDATE_CHECK_URL = os.getenv(
    "UPDATE_CHECK_URL",
    "https://ssmaker-auth-api-1049571775048.us-central1.run.app/app/version"
)


def get_current_version() -> str:
    """
    현재 앱 버전 반환.
    
    Returns:
        현재 버전 문자열
    """
    # 버전 파일이 있으면 읽음
    version_file = get_version_file_path()
    if version_file and version_file.exists():
        try:
            with open(version_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("version", CURRENT_VERSION)
        except Exception:
            pass
    
    return CURRENT_VERSION


def get_version_file_path() -> Optional[Path]:
    """
    버전 파일 경로 반환.

    PyInstaller --onefile 모드에서는:
    1. EXE 옆 version.json 우선 (업데이트 시 교체 가능)
    2. _MEIPASS 번들 내 version.json 폴백 (초기 설치 시)

    Returns:
        버전 파일 경로 또는 None
    """
    if getattr(sys, 'frozen', False):
        # 1순위: EXE 옆 (업데이트 시 새 버전 파일이 여기에 놓임)
        exe_dir = Path(sys.executable).parent
        exe_version = exe_dir / "version.json"
        if exe_version.exists():
            return exe_version

        # 2순위: _MEIPASS 번들 내 (--onefile 초기 실행 시)
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            bundled_version = Path(meipass) / "version.json"
            if bundled_version.exists():
                return bundled_version

        return exe_version  # 없어도 경로는 반환 (get_current_version에서 fallback)
    else:
        # 개발 환경
        base_path = Path(__file__).parent.parent
        return base_path / "version.json"


def parse_version(version_str: str) -> Tuple[int, int, int]:
    """
    버전 문자열을 튜플로 파싱.
    
    Args:
        version_str: 버전 문자열 (예: "1.0.0")
    
    Returns:
        (major, minor, patch) 튜플
    """
    try:
        parts = version_str.strip().split('.')
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except (ValueError, IndexError):
        logger.warning(f"Failed to parse version: {version_str}")
        return (0, 0, 0)


def compare_versions(current: str, latest: str) -> int:
    """
    두 버전을 비교.
    
    Args:
        current: 현재 버전
        latest: 최신 버전
    
    Returns:
        -1: current < latest (업데이트 필요)
         0: current == latest (동일)
         1: current > latest (현재가 더 최신)
    """
    current_tuple = parse_version(current)
    latest_tuple = parse_version(latest)
    
    if current_tuple < latest_tuple:
        return -1
    elif current_tuple > latest_tuple:
        return 1
    else:
        return 0


class UpdateChecker:
    """
    자동 업데이트 확인 및 다운로드 클래스.
    """
    
    def __init__(
        self,
        check_url: str = UPDATE_CHECK_URL,
        timeout: int = 10
    ):
        """
        초기화.
        
        Args:
            check_url: 버전 확인 API URL
            timeout: 요청 타임아웃 (초)
        """
        self.check_url = check_url
        self.timeout = timeout
        self.current_version = get_current_version()
        self._update_info: Optional[Dict[str, Any]] = None
        
    def check_for_updates(self) -> Dict[str, Any]:
        """
        서버에서 업데이트 확인.
        
        Returns:
            업데이트 정보 딕셔너리:
            {
                "update_available": bool,
                "current_version": str,
                "latest_version": str,
                "download_url": str (optional),
                "release_notes": str (optional),
                "is_mandatory": bool,
                "error": str (optional)
            }
        """
        result = {
            "update_available": False,
            "current_version": self.current_version,
            "latest_version": self.current_version,
            "download_url": None,
            "release_notes": None,
            "is_mandatory": False,
            "error": None
        }
        
        try:
            logger.info(f"Checking for updates at: {self.check_url}")
            
            response = requests.get(
                self.check_url,
                timeout=self.timeout,
                headers={"User-Agent": f"SSMaker/{self.current_version}"}
            )
            
            if response.status_code == 200:
                data = response.json()
                
                latest_version = data.get("version", self.current_version)
                result["latest_version"] = latest_version
                result["download_url"] = data.get("download_url")
                result["release_notes"] = data.get("release_notes", "")
                result["is_mandatory"] = data.get("is_mandatory", False)
                
                # 버전 비교
                comparison = compare_versions(self.current_version, latest_version)
                if comparison < 0:
                    result["update_available"] = True
                    logger.info(f"Update available: {self.current_version} -> {latest_version}")
                else:
                    logger.info(f"No update needed. Current: {self.current_version}, Latest: {latest_version}")
            else:
                result["error"] = f"HTTP {response.status_code}"
                logger.warning(f"Update check failed: HTTP {response.status_code}")
                
        except requests.exceptions.Timeout:
            result["error"] = "요청 시간이 초과되었습니다."
            logger.warning("Update check timeout")
        except requests.exceptions.ConnectionError:
            result["error"] = "서버에 연결할 수 없습니다."
            logger.warning("Update check connection error")
        except json.JSONDecodeError:
            result["error"] = "서버 응답을 파싱할 수 없습니다."
            logger.warning("Update check JSON parse error")
        except Exception as e:
            result["error"] = f"알 수 없는 오류: {str(e)[:50]}"
            logger.exception(f"Update check error: {e}")
        
        self._update_info = result
        return result
    
    def download_update(
        self,
        download_url: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Optional[Path]:
        """
        업데이트 파일 다운로드.
        
        Args:
            download_url: 다운로드 URL
            progress_callback: 진행률 콜백 (downloaded_bytes, total_bytes)
        
        Returns:
            다운로드된 파일 경로 또는 None
        """
        if not download_url:
            logger.error("Download URL is empty")
            return None
        
        try:
            logger.info(f"Downloading update from: {download_url}")
            
            # 임시 디렉토리에 다운로드
            temp_dir = Path(tempfile.gettempdir()) / "ssmaker_update"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # 파일명 추출
            filename = download_url.split("/")[-1].split("?")[0]
            if not filename.endswith((".exe", ".zip", ".msi")):
                filename = "ssmaker_update.exe"
            
            download_path = temp_dir / filename
            
            # 스트리밍 다운로드
            response = requests.get(
                download_url,
                stream=True,
                timeout=60,
                headers={"User-Agent": f"SSMaker/{self.current_version}"}
            )
            response.raise_for_status()
            
            total_size = int(response.headers.get("content-length", 0))
            downloaded_size = 0
            
            with open(download_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if progress_callback and total_size > 0:
                            progress_callback(downloaded_size, total_size)
            
            logger.info(f"Download complete: {download_path}")
            return download_path
            
        except Exception as e:
            logger.exception(f"Download failed: {e}")
            return None
    
    def install_update(self, installer_path: Path) -> bool:
        """
        다운로드된 업데이트 설치.
        
        Args:
            installer_path: 설치 파일 경로
        
        Returns:
            성공 여부
        """
        if not installer_path or not installer_path.exists():
            logger.error("Installer file not found")
            return False
        
        try:
            logger.info(f"Installing update: {installer_path}")
            
            # Windows: 설치 프로그램 실행
            if sys.platform == "win32":
                # 현재 프로그램 종료 후 설치 프로그램 실행
                subprocess.Popen(
                    [str(installer_path)],
                    shell=True,
                    creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP
                )
                return True
            else:
                logger.warning("Auto-install not supported on this platform")
                return False
                
        except Exception as e:
            logger.exception(f"Install failed: {e}")
            return False


class UpdateCheckerAsync:
    """
    비동기 업데이트 확인 클래스.
    백그라운드에서 업데이트를 확인합니다.
    """
    
    def __init__(self):
        self._checker = UpdateChecker()
        self._result: Optional[Dict[str, Any]] = None
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[Dict[str, Any]], None]] = None
    
    def check_async(
        self,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> None:
        """
        비동기로 업데이트 확인.
        
        Args:
            callback: 완료 후 호출될 콜백 함수
        """
        self._callback = callback
        self._thread = threading.Thread(target=self._check_worker, daemon=True)
        self._thread.start()
    
    def _check_worker(self):
        """백그라운드 워커."""
        self._result = self._checker.check_for_updates()
        if self._callback:
            self._callback(self._result)
    
    def get_result(self) -> Optional[Dict[str, Any]]:
        """결과 반환."""
        return self._result
    
    def is_checking(self) -> bool:
        """확인 중 여부."""
        return self._thread is not None and self._thread.is_alive()


# 싱글톤 인스턴스
_update_checker: Optional[UpdateCheckerAsync] = None


def get_update_checker() -> UpdateCheckerAsync:
    """
    전역 업데이트 체커 인스턴스 반환.
    
    Returns:
        UpdateCheckerAsync 인스턴스
    """
    global _update_checker
    if _update_checker is None:
        _update_checker = UpdateCheckerAsync()
    return _update_checker


def check_for_updates_on_startup(
    callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> None:
    """
    시작 시 업데이트 확인 (비동기).
    
    Args:
        callback: 업데이트 확인 완료 후 콜백
    """
    checker = get_update_checker()
    checker.check_async(callback)
