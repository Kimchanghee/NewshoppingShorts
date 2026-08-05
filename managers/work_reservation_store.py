"""Durable idempotency keys for recoverable work reservations."""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from filelock import FileLock


def _record_key(job_key: str, user_id: str = "") -> str:
    normalized_job_key = str(job_key or "").strip()
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        return normalized_job_key
    return json.dumps(
        [normalized_user_id, normalized_job_key],
        ensure_ascii=False,
        separators=(",", ":"),
    )


class WorkReservationStore:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or (Path.home() / ".ssmaker" / "work_reservations.json"))
        self.lock_path = Path(f"{self.path}.lock")

    def _load_locked(self) -> dict[str, dict[str, str]]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError("작업 예약 복구 파일이 손상되었습니다.") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("작업 예약 복구 파일 형식이 올바르지 않습니다.")
        result: dict[str, dict[str, str]] = {}
        for job_key, value in payload.items():
            if isinstance(value, dict):
                raw_key = value.get("idempotency_key")
                state = str(value.get("state") or "reserved")
                user_id = str(value.get("user_id") or "")
            else:
                # Backward compatibility with the original {job: uuid} format.
                raw_key = value
                state = "reserved"
                user_id = ""
            try:
                normalized_key = str(uuid.UUID(str(raw_key)))
            except (ValueError, TypeError, AttributeError) as exc:
                raise RuntimeError("작업 예약 복구 키가 손상되었습니다.") from exc
            if state not in {"reserved", "pending_finalize", "completed_pending_delivery"}:
                raise RuntimeError("작업 예약 복구 상태가 손상되었습니다.")
            storage_key = str(job_key)
            if user_id:
                try:
                    parsed_key = json.loads(storage_key)
                except (TypeError, ValueError, json.JSONDecodeError):
                    parsed_key = None
                if not (
                    isinstance(parsed_key, list)
                    and len(parsed_key) == 2
                    and str(parsed_key[0]) == user_id
                ):
                    # Migrate the interim owner-field format without discarding
                    # another account's record for the same logical job.
                    storage_key = _record_key(storage_key, user_id)
            result[storage_key] = {
                "idempotency_key": normalized_key,
                "state": state,
                "user_id": user_id,
            }
        return result

    def _save_locked(self, payload: dict[str, dict[str, str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=str(self.path.parent),
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def get_or_create(self, job_key: str, user_id: str = "") -> str:
        normalized_job_key = str(job_key or "").strip()
        normalized_user_id = str(user_id or "").strip()
        storage_key = _record_key(normalized_job_key, normalized_user_id)
        if not normalized_job_key:
            raise ValueError("job_key is required")
        with FileLock(str(self.lock_path), timeout=10):
            payload = self._load_locked()
            existing = payload.get(storage_key)
            if existing:
                return existing["idempotency_key"]
            # Ownerless legacy records are not authority for a logged-in user.
            value = str(uuid.uuid4())
            payload[storage_key] = {
                "idempotency_key": value,
                "state": "reserved",
                "user_id": normalized_user_id,
            }
            self._save_locked(payload)
            return value

    def state(self, job_key: str, user_id: str = "") -> str:
        normalized_job_key = str(job_key or "").strip()
        normalized_user_id = str(user_id or "").strip()
        storage_key = _record_key(normalized_job_key, normalized_user_id)
        with FileLock(str(self.lock_path), timeout=10):
            record = self._load_locked().get(storage_key)
            return str((record or {}).get("state") or "")

    def set_state(
        self,
        job_key: str,
        idempotency_key: str,
        state: str,
        user_id: str = "",
    ) -> bool:
        """Compare-and-set a recovery state without overwriting a newer key."""
        if state not in {"reserved", "pending_finalize", "completed_pending_delivery"}:
            raise ValueError("invalid reservation state")
        normalized_job_key = str(job_key or "").strip()
        normalized_key = str(uuid.UUID(str(idempotency_key)))
        normalized_user_id = str(user_id or "").strip()
        storage_key = _record_key(normalized_job_key, normalized_user_id)
        with FileLock(str(self.lock_path), timeout=10):
            payload = self._load_locked()
            record = payload.get(storage_key)
            if (
                not record
                or record["idempotency_key"] != normalized_key
                or (
                    normalized_user_id
                    and record.get("user_id") != normalized_user_id
                )
            ):
                return False
            record["state"] = state
            self._save_locked(payload)
            return True

    def rotate(self, job_key: str, expected_key: str, user_id: str = "") -> str:
        """CAS-rotate a terminal server key so concurrent retriers share one UUID."""
        normalized_job_key = str(job_key or "").strip()
        normalized_expected = str(uuid.UUID(str(expected_key)))
        normalized_user_id = str(user_id or "").strip()
        storage_key = _record_key(normalized_job_key, normalized_user_id)
        with FileLock(str(self.lock_path), timeout=10):
            payload = self._load_locked()
            record = payload.get(storage_key)
            if record and record["idempotency_key"] != normalized_expected:
                return record["idempotency_key"]
            new_key = str(uuid.uuid4())
            payload[storage_key] = {
                "idempotency_key": new_key,
                "state": "reserved",
                "user_id": normalized_user_id,
            }
            self._save_locked(payload)
            return new_key

    def remove(
        self,
        job_key: str,
        expected_key: Optional[str] = None,
        user_id: str = "",
    ) -> bool:
        normalized_job_key = str(job_key or "").strip()
        storage_key = _record_key(normalized_job_key, str(user_id or "").strip())
        normalized_expected = (
            str(uuid.UUID(str(expected_key))) if expected_key is not None else None
        )
        with FileLock(str(self.lock_path), timeout=10):
            payload = self._load_locked()
            record = payload.get(storage_key)
            if not record:
                return False
            if (
                normalized_expected is not None
                and record["idempotency_key"] != normalized_expected
            ):
                return False
            payload.pop(storage_key, None)
            self._save_locked(payload)
            return True


_STORE: Optional[WorkReservationStore] = None


def get_work_reservation_store() -> WorkReservationStore:
    global _STORE
    if _STORE is None:
        _STORE = WorkReservationStore()
    return _STORE
