# -*- coding: utf-8 -*-
"""
업로드 중복 차단 레지스트리 — '3연속 똑같은 영상' 근본 방지.

영구 저장(json)에 이미 업로드/처리한 항목의 키를 기록하고, 새 업로드 전에
(1) 상품/소스 키 중복, (2) 영상 프레임 지각해시(aHash) 유사 여부로 차단한다.

- 상품 키: 정규화한 상품명 + source_url/productId
- 영상 해시: 1초 지점 프레임 8x8 average-hash (cv2 있으면), Hamming <= 6 이면 중복

기존 큐 스크립트의 버그(‘completed’ 상태만 집계 → 재시도가 재업로드)와 무관하게,
업로드 직전 실제 게시 이력 기준으로 판정하므로 재실행/재시도에도 안전하다.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
import uuid
from typing import Dict, List, Optional

from filelock import FileLock, Timeout as FileLockTimeout

from utils.logging_config import get_logger

logger = get_logger(__name__)


class RegistryIntegrityError(RuntimeError):
    """Raised when duplicate-protection state cannot be trusted."""

try:
    import cv2  # type: ignore
    _CV = True
except Exception:
    _CV = False


def _registry_path() -> str:
    return os.path.join(os.path.expanduser("~"), ".ssmaker", "uploaded_registry.json")


def normalize_product_key(*parts: str) -> str:
    """상품/소스 식별 키 정규화(공백·특수문자 제거, 소문자)."""
    joined = " ".join(str(p or "") for p in parts)
    joined = re.sub(r"https?://\S+", lambda m: m.group(0).split("?")[0], joined)  # strip query
    joined = re.sub(r"[^0-9a-zA-Z가-힣]+", "", joined).lower()
    return joined[:200]


def normalize_source_id(url: str) -> str:
    """소스 영상 URL → 안정 식별자(쿼리 제거·소문자). 같은 영상 재사용 차단용."""
    u = str(url or "").strip().split("?")[0].split("#")[0].rstrip("/").lower()
    return u[:300]


def frame_ahash(video_path: str) -> Optional[int]:
    """영상 1초 지점 프레임의 8x8 average-hash. cv2 없거나 실패 시 None."""
    if not _CV or not video_path or not os.path.exists(video_path):
        return None
    try:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(fps * 1.0))
        ok, frame = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
        cap.release()
        if not ok:
            return None
        g = cv2.cvtColor(cv2.resize(frame, (8, 8)), cv2.COLOR_BGR2GRAY)
        bits = (g >= g.mean()).flatten()
        h = 0
        for b in bits:
            h = (h << 1) | int(b)
        return h
    except Exception:
        return None


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


class UploadedRegistry:
    """영구 업로드 이력 + 중복 판정."""

    HASH_DISTANCE_THRESHOLD = 6
    LOCK_TIMEOUT_SECONDS = 10

    def __init__(self, path: Optional[str] = None):
        self._path = path or _registry_path()
        self._backup_path = f"{self._path}.bak"
        self._file_lock = FileLock(f"{self._path}.lock", timeout=self.LOCK_TIMEOUT_SECONDS)
        self._lock = threading.RLock()
        self._product_keys: Dict[str, dict] = {}
        self._hashes: List[dict] = []  # [{"hash": int, "key": str, "at": ts}]
        self._sources: Dict[str, dict] = {}  # 소스 영상 URL/ID → 사용 기록
        self._reservations: Dict[str, dict] = {}
        self._load()

    @staticmethod
    def _validate_data(data: object) -> dict:
        if not isinstance(data, dict):
            raise RegistryIntegrityError("중복 업로드 기록의 형식이 올바르지 않습니다.")
        products = data.get("product_keys", {})
        hashes = data.get("hashes", [])
        sources = data.get("sources", {})
        reservations = data.get("reservations", {})
        if (
            not isinstance(products, dict)
            or not isinstance(hashes, list)
            or not isinstance(sources, dict)
            or not isinstance(reservations, dict)
        ):
            raise RegistryIntegrityError("중복 업로드 기록의 필수 항목이 손상되었습니다.")
        return {
            "product_keys": products,
            "hashes": hashes,
            "sources": sources,
            "reservations": reservations,
        }

    @classmethod
    def _read_file(cls, path: str) -> dict:
        with open(path, "r", encoding="utf-8") as handle:
            return cls._validate_data(json.load(handle))

    def _assign(self, data: dict) -> None:
        self._product_keys = dict(data["product_keys"])
        self._hashes = list(data["hashes"])
        self._sources = dict(data["sources"])
        self._reservations = dict(data["reservations"])

    @staticmethod
    def _merge_hashes(*collections: List[dict]) -> List[dict]:
        merged: List[dict] = []
        seen = set()
        for collection in collections:
            for record in collection:
                if not isinstance(record, dict):
                    continue
                marker = (
                    record.get("hash"), record.get("key"),
                    record.get("platform"), record.get("at"),
                )
                if marker not in seen:
                    seen.add(marker)
                    merged.append(record)
        return merged

    @staticmethod
    def _atomic_write(path: str, data: dict) -> None:
        directory = os.path.dirname(path) or "."
        os.makedirs(directory, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix=".uploaded_registry-", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
            if hasattr(os, "O_DIRECTORY"):
                try:
                    directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
                except OSError:
                    # Windows and some filesystems do not permit directory fsync.
                    pass
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def _load(self) -> None:
        if not os.path.exists(self._path) and not os.path.exists(self._backup_path):
            return
        try:
            self._assign(self._read_file(self._path))
            return
        except Exception as primary_error:
            logger.error("[Registry] primary state is invalid: %s", primary_error)

        try:
            backup = self._read_file(self._backup_path)
            self._assign(backup)
            self._atomic_write(self._path, backup)
            logger.warning("[Registry] restored duplicate-protection state from backup")
        except Exception as backup_error:
            raise RegistryIntegrityError(
                "중복 업로드 기록과 백업이 모두 손상되었습니다. 자동 업로드를 중단합니다."
            ) from backup_error

    def _save(self) -> None:
        try:
            with self._file_lock:
                disk = {
                    "product_keys": {},
                    "hashes": [],
                    "sources": {},
                    "reservations": {},
                }
                if os.path.exists(self._path):
                    disk = self._read_file(self._path)
                merged = {
                    "product_keys": {**disk["product_keys"], **self._product_keys},
                    "hashes": self._merge_hashes(disk["hashes"], self._hashes),
                    "sources": {**disk["sources"], **self._sources},
                    # Reservations are mutated only by the atomic
                    # reserve/finalize/release methods. Never merge a stale
                    # instance snapshot back over another process's finalize.
                    "reservations": dict(disk["reservations"]),
                }
                self._atomic_write(self._path, merged)
                self._atomic_write(self._backup_path, merged)
                self._assign(merged)
        except FileLockTimeout as exc:
            raise RegistryIntegrityError(
                "중복 업로드 기록이 다른 프로세스에서 사용 중입니다. 잠시 후 다시 시도해 주세요."
            ) from exc
        except RegistryIntegrityError:
            raise
        except Exception as exc:
            logger.error("[Registry] durable save failed: %s", exc, exc_info=True)
            raise RegistryIntegrityError("중복 업로드 기록을 안전하게 저장하지 못했습니다.") from exc

    # ── 소스 영상(3플랫폼 등) 재사용 차단 ──
    def is_source_used(self, source_url: str) -> bool:
        sid = normalize_source_id(source_url)
        if not sid:
            return False
        with self._lock:
            return sid in self._sources

    def record_source(self, source_url: str, meta: Optional[dict] = None) -> None:
        sid = normalize_source_id(source_url)
        if not sid:
            return
        with self._lock:
            self._sources[sid] = {"at": time.time(), **(meta or {})}
            self._save()

    def used_source_ids(self) -> set:
        with self._lock:
            return set(self._sources.keys())

    def is_duplicate(
        self,
        product_key: str = "",
        video_path: str = "",
        platform: str = "youtube",
    ) -> tuple[bool, str]:
        """중복이면 (True, 사유). 상품키 또는 영상 유사 둘 중 하나라도 걸리면 중복."""
        with self._lock:
            key = (product_key or "").strip()
            if key and key in self._product_keys:
                return True, f"동일 상품/소스 이미 업로드됨 ({platform})"
            for reservation in self._reservations.values():
                if key and reservation.get("key") == key:
                    return True, "동일 상품/소스가 다른 업로드에서 예약됨"
            vh = frame_ahash(video_path)
            if vh is not None:
                for rec in self._hashes:
                    try:
                        if _hamming(int(rec["hash"]), vh) <= self.HASH_DISTANCE_THRESHOLD:
                            return True, "유사 영상 이미 업로드됨(프레임 해시)"
                    except Exception:
                        continue
                for reservation in self._reservations.values():
                    try:
                        reserved_hash = reservation.get("hash")
                        if reserved_hash is not None and _hamming(int(reserved_hash), vh) <= self.HASH_DISTANCE_THRESHOLD:
                            return True, "유사 영상이 다른 업로드에서 예약됨"
                    except Exception:
                        continue
            return False, ""

    def reserve(
        self,
        product_key: str = "",
        video_path: str = "",
        platform: str = "youtube",
    ) -> tuple[Optional[str], str]:
        """Atomically reserve a duplicate key before a remote upload starts."""
        key = (product_key or "").strip()
        video_hash = frame_ahash(video_path)
        with self._lock:
            try:
                with self._file_lock:
                    disk = {
                        "product_keys": {},
                        "hashes": [],
                        "sources": {},
                        "reservations": {},
                    }
                    if os.path.exists(self._path):
                        disk = self._read_file(self._path)

                    if key and key in disk["product_keys"]:
                        return None, f"동일 상품/소스 이미 업로드됨 ({platform})"
                    for reservation in disk["reservations"].values():
                        if key and reservation.get("key") == key:
                            return None, "동일 상품/소스가 다른 업로드에서 예약됨"
                    if video_hash is not None:
                        for record in disk["hashes"]:
                            try:
                                if _hamming(int(record["hash"]), video_hash) <= self.HASH_DISTANCE_THRESHOLD:
                                    return None, "유사 영상 이미 업로드됨(프레임 해시)"
                            except Exception:
                                continue
                        for reservation in disk["reservations"].values():
                            try:
                                reserved_hash = reservation.get("hash")
                                if reserved_hash is not None and _hamming(int(reserved_hash), video_hash) <= self.HASH_DISTANCE_THRESHOLD:
                                    return None, "유사 영상이 다른 업로드에서 예약됨"
                            except Exception:
                                continue

                    reservation_id = str(uuid.uuid4())
                    disk["reservations"][reservation_id] = {
                        "key": key,
                        "hash": video_hash,
                        "platform": platform,
                        "at": time.time(),
                        "state": "reserved",
                    }
                    self._atomic_write(self._path, disk)
                    self._atomic_write(self._backup_path, disk)
                    self._assign(disk)
                    return reservation_id, ""
            except FileLockTimeout as exc:
                raise RegistryIntegrityError(
                    "다른 업로드가 중복 보호 기록을 사용 중입니다."
                ) from exc
            except RegistryIntegrityError:
                raise
            except Exception as exc:
                raise RegistryIntegrityError(
                    "업로드 전 중복 방지 예약을 저장하지 못했습니다."
                ) from exc

    def finalize_reservation(self, reservation_id: str, video_id: str = "") -> None:
        """Convert a durable pre-upload reservation into upload history."""
        with self._lock:
            try:
                with self._file_lock:
                    disk = self._read_file(self._path)
                    reservation = disk["reservations"].get(str(reservation_id))
                    if not reservation:
                        raise RegistryIntegrityError(
                            "업로드 예약을 찾을 수 없어 자동 복구가 필요합니다."
                        )
                    key = str(reservation.get("key") or "")
                    if key:
                        disk["product_keys"][key] = {
                            "platform": reservation.get("platform") or "youtube",
                            "video_id": str(video_id or ""),
                            "at": time.time(),
                        }
                    if reservation.get("hash") is not None:
                        disk["hashes"].append(
                            {
                                "hash": reservation["hash"],
                                "key": key,
                                "platform": reservation.get("platform") or "youtube",
                                "at": time.time(),
                            }
                        )
                    disk["reservations"].pop(str(reservation_id), None)
                    self._atomic_write(self._path, disk)
                    self._atomic_write(self._backup_path, disk)
                    self._assign(disk)
            except FileLockTimeout as exc:
                raise RegistryIntegrityError("업로드 예약 확정 잠금 시간이 초과되었습니다.") from exc
            except RegistryIntegrityError:
                raise
            except Exception as exc:
                raise RegistryIntegrityError("업로드 예약을 확정하지 못했습니다.") from exc

    def release_reservation(self, reservation_id: str) -> None:
        """Release a reservation only after a confirmed pre-upload failure."""
        with self._lock:
            try:
                with self._file_lock:
                    disk = self._read_file(self._path)
                    if disk["reservations"].pop(str(reservation_id), None) is None:
                        return
                    self._atomic_write(self._path, disk)
                    self._atomic_write(self._backup_path, disk)
                    self._assign(disk)
            except FileLockTimeout as exc:
                raise RegistryIntegrityError("업로드 예약 해제 잠금 시간이 초과되었습니다.") from exc
            except RegistryIntegrityError:
                raise
            except Exception as exc:
                raise RegistryIntegrityError("업로드 예약을 해제하지 못했습니다.") from exc

    def stale_reservations(self, older_than_seconds: int = 24 * 60 * 60) -> Dict[str, dict]:
        """Return uncertain stale reservations for explicit operator reconciliation."""
        cutoff = time.time() - max(60, int(older_than_seconds))
        with self._lock:
            try:
                with self._file_lock:
                    disk = self._read_file(self._path)
                    self._assign(disk)
                    return {
                        reservation_id: dict(record)
                        for reservation_id, record in disk["reservations"].items()
                        if float(record.get("at") or 0) <= cutoff
                    }
            except FileLockTimeout as exc:
                raise RegistryIntegrityError("오래된 업로드 예약 조회 잠금 시간이 초과되었습니다.") from exc

    def reconcile_reservation(
        self,
        reservation_id: str,
        *,
        uploaded: bool,
        video_id: str = "",
    ) -> None:
        """Resolve an uncertain reservation after checking the remote platform."""
        if uploaded:
            self.finalize_reservation(reservation_id, video_id=video_id)
        else:
            self.release_reservation(reservation_id)

    def record(self, product_key: str = "", video_path: str = "", platform: str = "youtube", video_id: str = "") -> None:
        """업로드 성공 기록."""
        with self._lock:
            key = (product_key or "").strip()
            if key:
                self._product_keys[key] = {"platform": platform, "video_id": video_id, "at": time.time()}
            vh = frame_ahash(video_path)
            if vh is not None:
                self._hashes.append({"hash": vh, "key": key, "platform": platform, "at": time.time()})
            self._save()


_registry: Optional[UploadedRegistry] = None
_registry_init_lock = threading.Lock()


def get_uploaded_registry() -> UploadedRegistry:
    global _registry
    if _registry is None:
        with _registry_init_lock:
            if _registry is None:
                _registry = UploadedRegistry()
    return _registry
