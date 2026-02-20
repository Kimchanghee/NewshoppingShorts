# -*- coding: utf-8 -*-
"""
Auto Updater Module
?먮룞 ?낅뜲?댄듃 紐⑤뱢

?ъ슜?먭? ?꾨줈洹몃옩 ?ㅽ뻾 ???쒕쾭?먯꽌 理쒖떊 踰꾩쟾???뺤씤?섍퀬,
?낅뜲?댄듃媛 ?덉쑝硫??뚮┝ ???ㅼ슫濡쒕뱶?⑸땲??
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

from urllib.parse import urlparse

import requests
from utils.logging_config import get_logger

logger = get_logger(__name__)

# ?꾩옱 ??踰꾩쟾 (鍮뚮뱶 ????媛믪쓣 ?낅뜲?댄듃)
CURRENT_VERSION = "1.4.13"

# 踰꾩쟾 ?뺤씤 API ?붾뱶?ъ씤??
UPDATE_CHECK_URL = os.getenv(
    "UPDATE_CHECK_URL",
    "https://ssmaker-auth-api-1049571775048.us-central1.run.app/app/version"
)

# Allowed domains for update downloads (security: prevent redirect to malicious hosts)
_ALLOWED_DOWNLOAD_DOMAINS: frozenset[str] = frozenset({
    "github.com",
    "objects.githubusercontent.com",
    "storage.googleapis.com",
    "ssmaker-auth-api-1049571775048.us-central1.run.app",
})


def get_current_version() -> str:
    """
    ?꾩옱 ??踰꾩쟾 諛섑솚.
    
    Returns:
        ?꾩옱 踰꾩쟾 臾몄옄??    """
    # 踰꾩쟾 ?뚯씪???덉쑝硫??쎌쓬
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
    踰꾩쟾 ?뚯씪 寃쎈줈 諛섑솚.

    PyInstaller --onefile 紐⑤뱶?먯꽌??
    1. EXE ??version.json ?곗꽑 (?낅뜲?댄듃 ??援먯껜 媛??
    2. _MEIPASS 踰덈뱾 ??version.json ?대갚 (珥덇린 ?ㅼ튂 ??

    Returns:
        踰꾩쟾 ?뚯씪 寃쎈줈 ?먮뒗 None
    """
    if getattr(sys, 'frozen', False):
        # 1?쒖쐞: EXE ??(?낅뜲?댄듃 ????踰꾩쟾 ?뚯씪???ш린???볦엫)
        exe_dir = Path(sys.executable).parent
        exe_version = exe_dir / "version.json"
        if exe_version.exists():
            return exe_version

        # 2?쒖쐞: _MEIPASS 踰덈뱾 ??(--onefile 珥덇린 ?ㅽ뻾 ??
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            bundled_version = Path(meipass) / "version.json"
            if bundled_version.exists():
                return bundled_version

        return exe_version  # ?놁뼱??寃쎈줈??諛섑솚 (get_current_version?먯꽌 fallback)
    else:
        # 媛쒕컻 ?섍꼍
        base_path = Path(__file__).parent.parent
        return base_path / "version.json"


def parse_version(version_str: str) -> Tuple[int, int, int]:
    """
    踰꾩쟾 臾몄옄?댁쓣 ?쒗뵆濡??뚯떛.
    
    Args:
        version_str: 踰꾩쟾 臾몄옄??(?? "1.0.0")
    
    Returns:
        (major, minor, patch) ?쒗뵆
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
    ??踰꾩쟾??鍮꾧탳.
    
    Args:
        current: ?꾩옱 踰꾩쟾
        latest: 理쒖떊 踰꾩쟾
    
    Returns:
        -1: current < latest (?낅뜲?댄듃 ?꾩슂)
         0: current == latest (?숈씪)
         1: current > latest (?꾩옱媛 ??理쒖떊)
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
    ?먮룞 ?낅뜲?댄듃 ?뺤씤 諛??ㅼ슫濡쒕뱶 ?대옒??
    """
    
    def __init__(
        self,
        check_url: str = UPDATE_CHECK_URL,
        timeout: int = 10
    ):
        """
        珥덇린??
        
        Args:
            check_url: 踰꾩쟾 ?뺤씤 API URL
            timeout: ?붿껌 ??꾩븘??(珥?
        """
        self.check_url = check_url
        self.timeout = timeout
        self.current_version = get_current_version()
        self._update_info: Optional[Dict[str, Any]] = None
        
    def check_for_updates(self) -> Dict[str, Any]:
        """
        ?쒕쾭?먯꽌 ?낅뜲?댄듃 ?뺤씤.
        
        Returns:
            ?낅뜲?댄듃 ?뺣낫 ?뺤뀛?덈━:
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
                result["file_hash"] = data.get("file_hash")  # SHA256 hash for integrity verification
                
                # 踰꾩쟾 鍮꾧탳
                comparison = compare_versions(self.current_version, latest_version)
                if comparison < 0:
                    if not result["download_url"]:
                        result["error"] = "Missing download_url in update metadata"
                        logger.error("Update metadata missing download_url")
                    elif not result["file_hash"]:
                        result["error"] = "Missing file_hash in update metadata"
                        logger.error("Update metadata missing file_hash; refusing unsafe update")
                    else:
                        # Validate download URL domain before accepting update
                        dl_parsed = urlparse(result["download_url"])
                        if dl_parsed.scheme != "https" or dl_parsed.hostname not in _ALLOWED_DOWNLOAD_DOMAINS:
                            result["error"] = f"Untrusted download domain: {dl_parsed.hostname}"
                            logger.error(f"[Security] Rejecting update from untrusted domain: {dl_parsed.hostname}")
                        else:
                            result["update_available"] = True
                            logger.info(f"Update available: {self.current_version} -> {latest_version}")
                else:
                    logger.info(f"No update needed. Current: {self.current_version}, Latest: {latest_version}")
            elif response.status_code == 404:
                # Some backend deployments do not include update API routes.
                # This is not a connectivity failure; just skip update flow.
                logger.info("Update endpoint not available (404). Skipping update check.")
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
            result["error"] = "서버 응답을 해석할 수 없습니다."
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
        ?낅뜲?댄듃 ?뚯씪 ?ㅼ슫濡쒕뱶.
        
        Args:
            download_url: ?ㅼ슫濡쒕뱶 URL
            progress_callback: 吏꾪뻾瑜?肄쒕갚 (downloaded_bytes, total_bytes)
        
        Returns:
            ?ㅼ슫濡쒕뱶???뚯씪 寃쎈줈 ?먮뒗 None
        """
        if not download_url:
            logger.error("Download URL is empty")
            return None

        # Security: validate download URL domain against allowlist
        parsed_url = urlparse(download_url)
        if parsed_url.scheme != "https":
            logger.error(f"[Security] Rejecting non-HTTPS download URL: {parsed_url.scheme}")
            return None
        if parsed_url.hostname not in _ALLOWED_DOWNLOAD_DOMAINS:
            logger.error(f"[Security] Rejecting download from untrusted domain: {parsed_url.hostname}")
            return None

        try:
            logger.info(f"Downloading update from: {download_url}")
            
            # Download to a temporary directory.
            temp_dir = Path(tempfile.gettempdir()) / "ssmaker_update"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Determine target filename.
            filename = download_url.split("/")[-1].split("?")[0]
            if not filename.endswith((".exe", ".zip", ".msi")):
                filename = "ssmaker_update.exe"
            
            download_path = temp_dir / filename
            
            # Stream download for stable memory usage.
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

            # Verify file integrity with SHA256 hash
            expected_hash = self._update_info.get("file_hash") if self._update_info else None
            if expected_hash:
                sha256 = hashlib.sha256()
                with open(download_path, "rb") as f:
                    for block in iter(lambda: f.read(8192), b""):
                        sha256.update(block)
                actual_hash = sha256.hexdigest()
                if actual_hash.lower() != expected_hash.lower():
                    logger.error(f"Hash mismatch! Expected: {expected_hash[:16]}..., Got: {actual_hash[:16]}...")
                    download_path.unlink(missing_ok=True)
                    return None
                logger.info("File integrity verified (SHA256)")
            else:
                logger.error("No file_hash provided by server - refusing to install update")
                download_path.unlink(missing_ok=True)
                return None

            return download_path
            
        except Exception as e:
            logger.exception(f"Download failed: {e}")
            return None
    
    def install_update(self, installer_path: Path) -> bool:
        """
        다운로드된 Inno Setup 인스톨러를 사일런트 모드로 실행하여 업데이트 설치.

        이 메서드가 True를 반환하면, 호출자는 반드시 앱을 종료해야 합니다.
        인스톨러가 파일 교체 후 앱을 자동으로 재시작합니다.

        Args:
            installer_path: 인스톨러 파일 경로

        Returns:
            성공 여부
        """
        if not installer_path or not installer_path.exists():
            logger.error("Installer file not found")
            return False

        try:
            logger.info(f"Installing update (silent): {installer_path}")

            if sys.platform == "win32":
                # Inno Setup 사일런트 설치:
                # /VERYSILENT  - UI 없이 설치
                # /SUPPRESSMSGBOXES - 메시지 박스 숨김
                # /CLOSEAPPLICATIONS - 실행 중인 앱 자동 종료
                # /SP- - 설치 확인 프롬프트 건너뛰기
                subprocess.Popen(
                    [
                        str(installer_path),
                        "/VERYSILENT",
                        "/SUPPRESSMSGBOXES",
                        "/CLOSEAPPLICATIONS",
                        "/SP-",
                    ],
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
                logger.info("Installer launched. App should exit now for update to proceed.")
                return True
            else:
                logger.warning("Auto-install not supported on this platform")
                return False

        except Exception as e:
            logger.exception(f"Install failed: {e}")
            return False


class UpdateCheckerAsync:
    """
    鍮꾨룞湲??낅뜲?댄듃 ?뺤씤 ?대옒??
    諛깃렇?쇱슫?쒖뿉???낅뜲?댄듃瑜??뺤씤?⑸땲??
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
        鍮꾨룞湲곕줈 ?낅뜲?댄듃 ?뺤씤.
        
        Args:
            callback: ?꾨즺 ???몄텧??肄쒕갚 ?⑥닔
        """
        self._callback = callback
        self._thread = threading.Thread(target=self._check_worker, daemon=True)
        self._thread.start()
    
    def _check_worker(self):
        """諛깃렇?쇱슫???뚯빱."""
        self._result = self._checker.check_for_updates()
        if self._callback:
            self._callback(self._result)
    
    def get_result(self) -> Optional[Dict[str, Any]]:
        """寃곌낵 諛섑솚."""
        return self._result
    
    def is_checking(self) -> bool:
        """?뺤씤 以??щ?."""
        return self._thread is not None and self._thread.is_alive()


# ?깃????몄뒪?댁뒪
_update_checker: Optional[UpdateCheckerAsync] = None


def get_update_checker() -> UpdateCheckerAsync:
    """
    ?꾩뿭 ?낅뜲?댄듃 泥댁빱 ?몄뒪?댁뒪 諛섑솚.
    
    Returns:
        UpdateCheckerAsync ?몄뒪?댁뒪
    """
    global _update_checker
    if _update_checker is None:
        _update_checker = UpdateCheckerAsync()
    return _update_checker


def check_for_updates_on_startup(
    callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> None:
    """
    ?쒖옉 ???낅뜲?댄듃 ?뺤씤 (鍮꾨룞湲?.
    
    Args:
        callback: ?낅뜲?댄듃 ?뺤씤 ?꾨즺 ??肄쒕갚
    """
    checker = get_update_checker()
    checker.check_async(callback)
