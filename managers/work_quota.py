"""Shared durable reserve/finalize/release contract for all production modes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from caller import rest
from managers.work_reservation_store import (
    WorkReservationStore,
    get_work_reservation_store,
)


@dataclass
class DurableWorkReservation:
    user_id: str
    job_key: str
    idempotency_key: str
    store: WorkReservationStore
    reserved: bool = False
    finalized: bool = False

    @property
    def recovery_state(self) -> str:
        return self.store.state(self.job_key, self.user_id)

    @classmethod
    def begin(
        cls,
        user_id: str,
        job_key: str,
        *,
        store: Optional[WorkReservationStore] = None,
    ) -> tuple["DurableWorkReservation", Dict[str, Any]]:
        durable_store = store or get_work_reservation_store()
        key = durable_store.get_or_create(job_key, str(user_id))
        reservation = cls(str(user_id), str(job_key), key, durable_store)

        recovery_state = durable_store.state(job_key, str(user_id))
        if recovery_state == "completed_pending_delivery":
            # Local state is only a recovery hint. The current user's server
            # record remains the authority and must confirm completion.
            result = reservation.finalize()
            if result.get("success") and result.get("reservation_status") == "completed":
                result = dict(result)
                result["recovered_pending_delivery"] = True
            return reservation, result
        if recovery_state == "pending_finalize":
            result = reservation.finalize()
            if result.get("success") and result.get("reservation_status") == "completed":
                result = dict(result)
                result["recovered_pending_delivery"] = True
            return reservation, result

        result = rest.reserveWork(str(user_id), key)
        status = str(result.get("reservation_status") or "")
        if not result.get("success") and status in {"expired", "released"}:
            key = durable_store.rotate(job_key, key, str(user_id))
            reservation.idempotency_key = key
            result = rest.reserveWork(str(user_id), key)
        status = str(result.get("reservation_status") or "")
        reservation.reserved = bool(result.get("success") and status == "reserved")
        reservation.finalized = bool(result.get("success") and status == "completed")
        if reservation.finalized:
            durable_store.remove(job_key, expected_key=key, user_id=str(user_id))
        return reservation, result

    def finalize(self) -> Dict[str, Any]:
        result = rest.finalizeWork(self.user_id, self.idempotency_key)
        if result.get("success") and result.get("reservation_status") == "completed":
            self.finalized = True
            self.reserved = False
            if self.store.state(self.job_key, self.user_id) in {
                "pending_finalize",
                "completed_pending_delivery",
            }:
                self.store.set_state(
                    self.job_key,
                    self.idempotency_key,
                    "completed_pending_delivery",
                    self.user_id,
                )
            else:
                self.store.remove(
                    self.job_key,
                    expected_key=self.idempotency_key,
                    user_id=self.user_id,
                )
        return result

    def mark_pending_finalize(self) -> None:
        if not self.store.set_state(
            self.job_key,
            self.idempotency_key,
            "pending_finalize",
            self.user_id,
        ):
            raise RuntimeError("작업 확정 대기 상태를 안전하게 저장하지 못했습니다.")

    def complete_delivery(self) -> None:
        """Forget the key only after every user-visible/remote delivery step completes."""
        self.store.remove(
            self.job_key,
            expected_key=self.idempotency_key,
            user_id=self.user_id,
        )

    def can_release(self) -> bool:
        return self.store.state(self.job_key, self.user_id) in {"", "reserved"}

    def release(self) -> Dict[str, Any]:
        if not self.can_release():
            return {
                "success": False,
                "message": "완성된 결과의 사용량 확정이 대기 중이어서 예약을 해제하지 않았습니다.",
                "reservation_status": self.store.state(self.job_key, self.user_id),
            }
        result = rest.releaseWork(self.user_id, self.idempotency_key)
        if result.get("success") and result.get("reservation_status") in {
            "released",
            "expired",
        }:
            self.reserved = False
            self.store.remove(
                self.job_key,
                expected_key=self.idempotency_key,
                user_id=self.user_id,
            )
        return result
