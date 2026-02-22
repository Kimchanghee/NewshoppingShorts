# -*- coding: utf-8 -*-
"""
Auto Updater Module
?癒?짗 ??낅쑓??꾨뱜 筌뤴뫀諭?
????癒? ?袁⑥쨮域밸챶????쎈뻬 ????뺤쒔?癒?퐣 筌ㅼ뮇??甕곌쑴????類ㅼ뵥??랁?
??낅쑓??꾨뱜揶쎛 ??됱몵筌????뵝 ????쇱뒲嚥≪뮆諭??몃빍??
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

# ?袁⑹삺 ??甕곌쑴??(??슢諭?????揶쏅?????낅쑓??꾨뱜)
CURRENT_VERSION = "1.4.19"

# 甕곌쑴???類ㅼ뵥 API ?遺얜굡?????
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


def _verify_authenticode_signature(file_path: str, thumbprints_env: str) -> tuple[bool, str]:
    """Verify Windows Authenticode signature status and optional thumbprint allowlist."""
    if sys.platform != "win32":
        return True, "signature check skipped on non-windows"
    if not file_path or not os.path.exists(file_path):
        return False, "file not found"

    allowlist = {
        t.strip().upper().replace(" ", "")
        for t in str(thumbprints_env or "").split(",")
        if t.strip()
    }

    ps_script = (
        "$ErrorActionPreference='Stop'; "
        f"$sig=Get-AuthenticodeSignature -FilePath '{file_path}'; "
        "$thumb=''; if ($sig.SignerCertificate) { $thumb=$sig.SignerCertificate.Thumbprint }; "
        "[PSCustomObject]@{Status=[string]$sig.Status; Thumbprint=[string]$thumb} | ConvertTo-Json -Compress"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        return False, f"signature check failed: {err[:180]}"

    try:
        info = json.loads(proc.stdout.strip() or "{}")
    except Exception:
        return False, "invalid signature verification output"

    status = str(info.get("Status") or "").strip()
    thumbprint = str(info.get("Thumbprint") or "").strip().upper().replace(" ", "")
    if status != "Valid":
        return False, f"invalid signature status: {status or 'unknown'}"
    if allowlist and thumbprint not in allowlist:
        return False, "signer certificate is not allowlisted"
    return True, "ok"


def get_current_version() -> str:
    """
    ?袁⑹삺 ??甕곌쑴??獄쏆꼹??
    
    Returns:
        ?袁⑹삺 甕곌쑴???얜챷???    """
    # 甕곌쑴?????뵬????됱몵筌???뚯벉
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
    甕곌쑴?????뵬 野껋럥以?獄쏆꼹??

    PyInstaller --onefile 筌뤴뫀諭?癒?퐣??
    1. EXE ??version.json ?怨쀪퐨 (??낅쑓??꾨뱜 ???대Ŋ猿?揶쎛??
    2. _MEIPASS 甕곕뜄諭???version.json ??媛?(?λ뜃由???쇳뒄 ??

    Returns:
        甕곌쑴?????뵬 野껋럥以??癒?뮉 None
    """
    if getattr(sys, 'frozen', False):
        # 1??뽰맄: EXE ??(??낅쑓??꾨뱜 ????甕곌쑴?????뵬????由???蹂?뿫)
        exe_dir = Path(sys.executable).parent
        exe_version = exe_dir / "version.json"
        if exe_version.exists():
            return exe_version

        # 2??뽰맄: _MEIPASS 甕곕뜄諭???(--onefile ?λ뜃由???쎈뻬 ??
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            bundled_version = Path(meipass) / "version.json"
            if bundled_version.exists():
                return bundled_version

        return exe_version  # ??곷선??野껋럥以??獄쏆꼹??(get_current_version?癒?퐣 fallback)
    else:
        # 揶쏆뮆而???띻펾
        base_path = Path(__file__).parent.parent
        return base_path / "version.json"


def parse_version(version_str: str) -> Tuple[int, int, int]:
    """
    甕곌쑴???얜챷???곸뱽 ??쀫탣嚥????뼓.
    
    Args:
        version_str: 甕곌쑴???얜챷???(?? "1.0.0")
    
    Returns:
        (major, minor, patch) ??쀫탣
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
    ??甕곌쑴?????쑨??
    
    Args:
        current: ?袁⑹삺 甕곌쑴??        latest: 筌ㅼ뮇??甕곌쑴??    
    Returns:
        -1: current < latest (??낅쑓??꾨뱜 ?袁⑹뒄)
         0: current == latest (??덉뵬)
         1: current > latest (?袁⑹삺揶쎛 ??筌ㅼ뮇??
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
    ?癒?짗 ??낅쑓??꾨뱜 ?類ㅼ뵥 獄???쇱뒲嚥≪뮆諭??????
    """
    
    def __init__(
        self,
        check_url: str = UPDATE_CHECK_URL,
        timeout: int = 10
    ):
        """
        ?λ뜃由??
        
        Args:
            check_url: 甕곌쑴???類ㅼ뵥 API URL
            timeout: ?遺욧퍕 ???袁⑸툡??(??
        """
        self.check_url = check_url
        self.timeout = timeout
        self.current_version = get_current_version()
        self._update_info: Optional[Dict[str, Any]] = None
        
    def check_for_updates(self) -> Dict[str, Any]:
        """
        ??뺤쒔?癒?퐣 ??낅쑓??꾨뱜 ?類ㅼ뵥.
        
        Returns:
            ??낅쑓??꾨뱜 ?類ｋ궖 ?類ㅻ??댿봺:
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
                
                # 甕곌쑴????쑨??                comparison = compare_versions(self.current_version, latest_version)
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
            result["error"] = "?붿껌 ?쒓컙??珥덇낵?섏뿀?듬땲??"
            logger.warning("Update check timeout")
        except requests.exceptions.ConnectionError:
            result["error"] = "?쒕쾭???곌껐?????놁뒿?덈떎."
            logger.warning("Update check connection error")
        except json.JSONDecodeError:
            result["error"] = "?쒕쾭 ?묐떟???댁꽍?????놁뒿?덈떎."
            logger.warning("Update check JSON parse error")
        except Exception as e:
            result["error"] = f"?????녿뒗 ?ㅻ쪟: {str(e)[:50]}"
            logger.exception(f"Update check error: {e}")
        
        self._update_info = result
        return result
    
    def download_update(
        self,
        download_url: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Optional[Path]:
        """
        ??낅쑓??꾨뱜 ???뵬 ??쇱뒲嚥≪뮆諭?
        
        Args:
            download_url: ??쇱뒲嚥≪뮆諭?URL
            progress_callback: 筌욊쑵六양몴??꾩뮆媛?(downloaded_bytes, total_bytes)
        
        Returns:
            ??쇱뒲嚥≪뮆諭?????뵬 野껋럥以??癒?뮉 None
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

            if sys.platform == "win32":
                ok, reason = _verify_authenticode_signature(
                    str(download_path),
                    os.getenv("UPDATE_SIGNER_THUMBPRINTS", ""),
                )
                if not ok:
                    logger.error("Installer signature verification failed: %s", reason)
                    download_path.unlink(missing_ok=True)
                    return None
                logger.info("Installer Authenticode signature verified")

            return download_path
            
        except Exception as e:
            logger.exception(f"Download failed: {e}")
            return None
    
    def install_update(self, installer_path: Path) -> bool:
        """
        ?ㅼ슫濡쒕뱶??Inno Setup ?몄뒪?⑤윭瑜??ъ씪?고듃 紐⑤뱶濡??ㅽ뻾?섏뿬 ?낅뜲?댄듃 ?ㅼ튂.

        ??硫붿꽌?쒓? True瑜?諛섑솚?섎㈃, ?몄텧?먮뒗 諛섎뱶???깆쓣 醫낅즺?댁빞 ?⑸땲??
        ?몄뒪?⑤윭媛 ?뚯씪 援먯껜 ???깆쓣 ?먮룞?쇰줈 ?ъ떆?묓빀?덈떎.

        Args:
            installer_path: ?몄뒪?⑤윭 ?뚯씪 寃쎈줈

        Returns:
            ?깃났 ?щ?
        """
        if not installer_path or not installer_path.exists():
            logger.error("Installer file not found")
            return False

        try:
            logger.info(f"Installing update (silent): {installer_path}")

            if sys.platform == "win32":
                # Inno Setup ?ъ씪?고듃 ?ㅼ튂:
                # /VERYSILENT  - UI ?놁씠 ?ㅼ튂
                # /SUPPRESSMSGBOXES - 硫붿떆吏 諛뺤뒪 ?④?
                # /CLOSEAPPLICATIONS - ?ㅽ뻾 以묒씤 ???먮룞 醫낅즺
                # /SP- - ?ㅼ튂 ?뺤씤 ?꾨＼?꾪듃 嫄대꼫?곌린
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
    ??쑬猷욄묾???낅쑓??꾨뱜 ?類ㅼ뵥 ?????
    獄쏄퉫???깆뒲??뽯퓠????낅쑓??꾨뱜???類ㅼ뵥??몃빍??
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
        ??쑬猷욄묾怨뺤쨮 ??낅쑓??꾨뱜 ?類ㅼ뵥.
        
        Args:
            callback: ?袁⑥┷ ???紐꾪뀱???꾩뮆媛???λ땾
        """
        self._callback = callback
        self._thread = threading.Thread(target=self._check_worker, daemon=True)
        self._thread.start()
    
    def _check_worker(self):
        """獄쏄퉫???깆뒲?????묽."""
        self._result = self._checker.check_for_updates()
        if self._callback:
            self._callback(self._result)
    
    def get_result(self) -> Optional[Dict[str, Any]]:
        """野껉퀗??獄쏆꼹??"""
        return self._result
    
    def is_checking(self) -> bool:
        """?類ㅼ뵥 餓????."""
        return self._thread is not None and self._thread.is_alive()


# ?源????紐꾨뮞??곷뮞
_update_checker: Optional[UpdateCheckerAsync] = None


def get_update_checker() -> UpdateCheckerAsync:
    """
    ?袁⑸열 ??낅쑓??꾨뱜 筌ｋ똻鍮??紐꾨뮞??곷뮞 獄쏆꼹??
    
    Returns:
        UpdateCheckerAsync ?紐꾨뮞??곷뮞
    """
    global _update_checker
    if _update_checker is None:
        _update_checker = UpdateCheckerAsync()
    return _update_checker


def check_for_updates_on_startup(
    callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> None:
    """
    ??뽰삂 ????낅쑓??꾨뱜 ?類ㅼ뵥 (??쑬猷욄묾?.
    
    Args:
        callback: ??낅쑓??꾨뱜 ?類ㅼ뵥 ?袁⑥┷ ???꾩뮆媛?    """
    checker = get_update_checker()
    checker.check_async(callback)


