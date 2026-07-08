# -*- coding: utf-8 -*-
"""
Multi-account registry (TRIAL) for SSMaker.

Additive, standalone data layer for managing up to 10 upload account
profiles across YouTube / Instagram. It does NOT modify the existing
single-account managers (youtube_manager / instagram_manager). It only
persists account profile metadata + niche routing to
``~/.ssmaker/accounts.json`` so the multi-account console UI has
something to read and write.

OAuth/token wiring per account is intentionally out of scope for this
trial — this layer just records which accounts exist, their niche, and
their per-lane stagger offset. Removing this file + the console panel
fully reverts the trial.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

MAX_ACCOUNTS = 10
PLATFORMS = ("youtube", "instagram")
DEFAULT_STAGGER_MINUTES = 8


def data_dir() -> str:
    return os.path.join(os.path.expanduser("~"), ".ssmaker")


def registry_path() -> str:
    return os.path.join(data_dir(), "accounts.json")


@dataclass
class Account:
    """One upload account profile."""

    id: str
    platform: str            # "youtube" | "instagram"
    name: str
    niche: str = ""
    auto_upload: bool = True
    interval_hours: int = 4
    offset_minutes: int = 0      # stagger within its own platform lane
    daily_limit: int = 5
    status: str = "ok"           # ok | paused | error
    today_count: int = 0
    next_time: str = "-"
    title_prompt: str = ""
    hashtag_prompt: str = ""

    @property
    def token_path(self) -> str:
        """Where this account's OAuth token WOULD live (follow-up work)."""
        return os.path.join(data_dir(), f"{self.platform}_token_{self.id}.json")


class AccountRegistry:
    """Load / save / CRUD for account profiles (thread-safe via RLock)."""

    def __init__(self, path: Optional[str] = None) -> None:
        self._path = path or registry_path()
        self._lock = threading.RLock()
        self._accounts: List[Account] = []
        self._timing: Dict[str, object] = {
            "mode": "hybrid",
            "lane_stagger_minutes": DEFAULT_STAGGER_MINUTES,
        }
        self.load()

    # ---------- persistence ----------
    def load(self) -> None:
        with self._lock:
            self._accounts = []
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                data = {}
            self._timing = data.get("timing", self._timing) or self._timing
            fields = set(Account.__dataclass_fields__.keys())
            for raw in data.get("accounts", []):
                if not isinstance(raw, dict):
                    continue
                kwargs = {k: v for k, v in raw.items() if k in fields}
                try:
                    self._accounts.append(Account(**kwargs))
                except TypeError:
                    continue

    def save(self) -> None:
        with self._lock:
            os.makedirs(data_dir(), exist_ok=True)
            payload = {
                "version": 1,
                "timing": self._timing,
                "accounts": [asdict(a) for a in self._accounts],
            }
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)

    # ---------- queries ----------
    def all(self) -> List[Account]:
        with self._lock:
            return list(self._accounts)

    def by_platform(self, platform: str) -> List[Account]:
        return [a for a in self.all() if a.platform == platform]

    def get(self, account_id: str) -> Optional[Account]:
        for a in self.all():
            if a.id == account_id:
                return a
        return None

    def count(self) -> int:
        with self._lock:
            return len(self._accounts)

    def slots_remaining(self) -> int:
        return max(0, MAX_ACCOUNTS - self.count())

    @property
    def stagger_minutes(self) -> int:
        try:
            return int(self._timing.get("lane_stagger_minutes", DEFAULT_STAGGER_MINUTES))
        except (TypeError, ValueError):
            return DEFAULT_STAGGER_MINUTES

    # ---------- mutations ----------
    def add(self, platform: str, name: str, niche: str = "", **kw) -> Account:
        with self._lock:
            if self.count() >= MAX_ACCOUNTS:
                raise ValueError(f"최대 {MAX_ACCOUNTS}개 계정까지만 추가할 수 있어요.")
            if platform not in PLATFORMS:
                raise ValueError(f"지원하지 않는 플랫폼입니다: {platform}")
            name = (name or "").strip()
            if not name:
                raise ValueError("계정 이름을 입력해 주세요.")
            offset = kw.pop("offset_minutes", None)
            if offset is None:
                offset = len(self.by_platform(platform)) * self.stagger_minutes
            acc = Account(
                id=self._new_id(platform, name),
                platform=platform,
                name=name,
                niche=(niche or "").strip(),
                offset_minutes=int(offset),
                **kw,
            )
            self._accounts.append(acc)
            self.save()
            return acc

    def update(self, account_id: str, **fields) -> Optional[Account]:
        with self._lock:
            acc = self.get(account_id)
            if acc is None:
                return None
            valid = set(Account.__dataclass_fields__.keys())
            for k, v in fields.items():
                if k in valid and k != "id":
                    setattr(acc, k, v)
            self.save()
            return acc

    def remove(self, account_id: str) -> bool:
        with self._lock:
            before = len(self._accounts)
            self._accounts = [a for a in self._accounts if a.id != account_id]
            changed = len(self._accounts) != before
            if changed:
                self.save()
            return changed

    def _new_id(self, platform: str, name: str) -> str:
        base = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower() or "acct"
        cand = f"{platform[:2]}_{base}"
        existing = {a.id for a in self._accounts}
        if cand not in existing:
            return cand
        return f"{cand}_{int(time.time()) % 100000}"

    # ---------- routing ----------
    def routing_map(self) -> Dict[str, List[Account]]:
        """niche -> [accounts], derived from each account's niche."""
        out: Dict[str, List[Account]] = {}
        for a in self.all():
            key = a.niche.strip() or "그 외"
            out.setdefault(key, []).append(a)
        return out

    # ---------- trial helper ----------
    def seed_samples(self) -> int:
        """Populate example accounts so the console is explorable. Returns count added."""
        samples = [
            dict(platform="youtube", name="가전_리뷰_01", niche="가전", status="ok", today_count=3, next_time="14:08"),
            dict(platform="youtube", name="주방_꿀템_02", niche="주방", status="ok", today_count=4, next_time="14:16"),
            dict(platform="instagram", name="뷰티_데일리_03", niche="뷰티", status="ok", today_count=2, next_time="14:08"),
            dict(platform="instagram", name="반려_라이프_04", niche="반려동물", status="ok", today_count=5, next_time="내일 09:00"),
            dict(platform="youtube", name="캠핑_기어_05", niche="캠핑", status="paused", today_count=1, next_time="일시정지"),
            dict(platform="instagram", name="홈오피스_06", niche="홈오피스", status="ok", today_count=3, next_time="14:16"),
            dict(platform="youtube", name="헬스_기어_07", niche="헬스", status="error", today_count=0, next_time="토큰 재인증"),
        ]
        added = 0
        with self._lock:
            existing_names = {a.name for a in self._accounts}
            for s in samples:
                if self.count() >= MAX_ACCOUNTS:
                    break
                if s["name"] in existing_names:
                    continue
                self.add(**s)
                added += 1
        return added
