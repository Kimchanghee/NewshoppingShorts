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
import threading
import time
from typing import Dict, List, Optional

from utils.logging_config import get_logger

logger = get_logger(__name__)

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

    def __init__(self, path: Optional[str] = None):
        self._path = path or _registry_path()
        self._lock = threading.RLock()
        self._product_keys: Dict[str, dict] = {}
        self._hashes: List[dict] = []  # [{"hash": int, "key": str, "at": ts}]
        self._sources: Dict[str, dict] = {}  # 소스 영상 URL/ID → 사용 기록
        self._load()

    def _load(self) -> None:
        try:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._product_keys = data.get("product_keys", {}) or {}
                self._hashes = data.get("hashes", []) or []
                self._sources = data.get("sources", {}) or {}
        except Exception as e:
            logger.debug("[Registry] load skipped: %s", e)

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump({"product_keys": self._product_keys, "hashes": self._hashes,
                           "sources": self._sources},
                          f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("[Registry] save failed: %s", e)

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
            vh = frame_ahash(video_path)
            if vh is not None:
                for rec in self._hashes:
                    try:
                        if _hamming(int(rec["hash"]), vh) <= self.HASH_DISTANCE_THRESHOLD:
                            return True, "유사 영상 이미 업로드됨(프레임 해시)"
                    except Exception:
                        continue
            return False, ""

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


def get_uploaded_registry() -> UploadedRegistry:
    global _registry
    if _registry is None:
        _registry = UploadedRegistry()
    return _registry
