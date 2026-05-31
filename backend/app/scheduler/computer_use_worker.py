# -*- coding: utf-8 -*-
"""Background worker for server-side Computer Use bridge jobs."""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.configuration import get_settings
from app.database import SessionLocal
from app.models.computer_use_job import ComputerUseJob, ComputerUseJobStatus
from app.models.user_log import UserLog

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_codex_cli_args(prompt: str) -> List[str]:
    """Build Codex CLI argv from worker settings."""
    settings = get_settings()
    cli_path = str(settings.COMPUTER_USE_WORKER_CLI_PATH or "codex").strip() or "codex"
    workdir = str(settings.COMPUTER_USE_WORKER_WORKDIR or "").strip()
    model_name = str(settings.COMPUTER_USE_WORKER_MODEL or "").strip()

    args: List[str] = [cli_path]
    if workdir:
        args.extend(["--cd", workdir])
    if model_name:
        args.extend(["--model", model_name])
    args.append(str(prompt or ""))
    return args


def summarize_process_output(stdout_bytes: bytes, stderr_bytes: bytes, limit_chars: int) -> str:
    """Return compact output summary from worker subprocess result."""
    stdout_text = (stdout_bytes or b"").decode("utf-8", errors="replace").strip()
    stderr_text = (stderr_bytes or b"").decode("utf-8", errors="replace").strip()

    parts: List[str] = []
    if stdout_text:
        parts.append(f"stdout:\n{stdout_text}")
    if stderr_text:
        parts.append(f"stderr:\n{stderr_text}")
    merged = "\n\n".join(parts).strip()
    if not merged:
        merged = "(no output)"

    max_chars = max(256, int(limit_chars or 4000))
    if len(merged) > max_chars and stdout_text and stderr_text:
        # Preserve both stream labels even when truncating aggressively.
        fixed_overhead = len("stdout:\n\n\nstderr:\n")
        per_stream_budget = max(64, (max_chars - fixed_overhead) // 2)
        clipped_stdout = stdout_text[: max(0, per_stream_budget - 3)] + "..."
        clipped_stderr = stderr_text[: max(0, per_stream_budget - 3)] + "..."
        merged = f"stdout:\n{clipped_stdout}\n\nstderr:\n{clipped_stderr}"
    if len(merged) > max_chars:
        return merged[: max_chars - 3] + "..."
    return merged


def _claim_next_job(worker_id: str) -> Optional[Dict[str, str]]:
    """
    Claim one queued job.

    Uses compare-and-set update on status to avoid duplicate claims.
    """
    db = SessionLocal()
    try:
        for _ in range(3):
            row = (
                db.query(ComputerUseJob.id)
                .filter(ComputerUseJob.status == ComputerUseJobStatus.QUEUED)
                .order_by(ComputerUseJob.created_at.asc(), ComputerUseJob.id.asc())
                .first()
            )
            if not row:
                return None

            job_pk = int(row[0])
            started_at = _utcnow()
            updated = (
                db.query(ComputerUseJob)
                .filter(
                    ComputerUseJob.id == job_pk,
                    ComputerUseJob.status == ComputerUseJobStatus.QUEUED,
                )
                .update(
                    {
                        ComputerUseJob.status: ComputerUseJobStatus.PROCESSING,
                        ComputerUseJob.worker_id: worker_id,
                        ComputerUseJob.started_at: started_at,
                        ComputerUseJob.attempt_count: ComputerUseJob.attempt_count + 1,
                        ComputerUseJob.error_message: None,
                    },
                    synchronize_session=False,
                )
            )
            if not updated:
                db.rollback()
                continue

            db.commit()
            claimed = db.query(ComputerUseJob).filter(ComputerUseJob.id == job_pk).first()
            if not claimed:
                return None
            return {
                "id": str(claimed.id),
                "job_id": str(claimed.job_id),
                "user_id": str(claimed.user_id),
                "prompt": str(claimed.prompt or ""),
            }
        return None
    except Exception:
        db.rollback()
        logger.exception("[ComputerUseWorker] Failed to claim queued job")
        return None
    finally:
        db.close()


def _append_user_log(user_id: int, level: str, action: str, content: str) -> None:
    db = SessionLocal()
    try:
        db.add(
            UserLog(
                user_id=int(user_id),
                level=str(level or "INFO"),
                action=str(action or "computer_use_bridge"),
                content=str(content or ""),
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("[ComputerUseWorker] Failed to persist user log")
    finally:
        db.close()


def _mark_job_result(
    *,
    job_id: str,
    status: ComputerUseJobStatus,
    summary: Optional[str],
    error: Optional[str],
) -> None:
    db = SessionLocal()
    try:
        finished_at = _utcnow()
        updated = (
            db.query(ComputerUseJob)
            .filter(ComputerUseJob.job_id == str(job_id))
            .update(
                {
                    ComputerUseJob.status: status,
                    ComputerUseJob.finished_at: finished_at,
                    ComputerUseJob.result_summary: summary,
                    ComputerUseJob.error_message: error,
                },
                synchronize_session=False,
            )
        )
        if not updated:
            db.rollback()
            logger.warning("[ComputerUseWorker] Job row missing when finalizing: %s", job_id)
            return
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("[ComputerUseWorker] Failed to finalize job: %s", job_id)
    finally:
        db.close()


async def _execute_codex_job(job: Dict[str, str], worker_id: str) -> None:
    settings = get_settings()
    timeout_seconds = max(30, int(settings.COMPUTER_USE_WORKER_TIMEOUT_SECONDS or 900))
    output_limit_chars = max(512, int(settings.COMPUTER_USE_WORKER_OUTPUT_LIMIT_CHARS or 4000))
    job_id = str(job.get("job_id") or "")
    user_id = int(job.get("user_id") or 0)
    prompt = str(job.get("prompt") or "")

    args = build_codex_cli_args(prompt)
    workdir = str(settings.COMPUTER_USE_WORKER_WORKDIR or "").strip() or None
    if workdir and not os.path.isdir(workdir):
        _mark_job_result(
            job_id=job_id,
            status=ComputerUseJobStatus.FAILED,
            summary=None,
            error=f"Configured workdir does not exist: {workdir}",
        )
        _append_user_log(
            user_id,
            "ERROR",
            "computer_use_bridge_job_failed",
            f"job_id={job_id} worker={worker_id} error=invalid_workdir",
        )
        return

    logger.info("[ComputerUseWorker] Executing job_id=%s worker=%s", job_id, worker_id)
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workdir,
        )
    except Exception as exc:
        _mark_job_result(
            job_id=job_id,
            status=ComputerUseJobStatus.FAILED,
            summary=None,
            error=f"Failed to start codex CLI: {exc}",
        )
        _append_user_log(
            user_id,
            "ERROR",
            "computer_use_bridge_job_failed",
            f"job_id={job_id} worker={worker_id} error=start_failed",
        )
        return

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        proc.kill()
        try:
            await proc.communicate()
        except Exception:
            pass
        _mark_job_result(
            job_id=job_id,
            status=ComputerUseJobStatus.FAILED,
            summary=None,
            error=f"Worker timeout after {timeout_seconds}s",
        )
        _append_user_log(
            user_id,
            "ERROR",
            "computer_use_bridge_job_failed",
            f"job_id={job_id} worker={worker_id} error=timeout",
        )
        return

    summary = summarize_process_output(stdout_bytes, stderr_bytes, output_limit_chars)
    if proc.returncode == 0:
        _mark_job_result(
            job_id=job_id,
            status=ComputerUseJobStatus.SUCCEEDED,
            summary=summary,
            error=None,
        )
        _append_user_log(
            user_id,
            "INFO",
            "computer_use_bridge_job_succeeded",
            f"job_id={job_id} worker={worker_id}",
        )
        return

    _mark_job_result(
        job_id=job_id,
        status=ComputerUseJobStatus.FAILED,
        summary=summary,
        error=f"Codex CLI exit code {proc.returncode}",
    )
    _append_user_log(
        user_id,
        "ERROR",
        "computer_use_bridge_job_failed",
        f"job_id={job_id} worker={worker_id} error=exit_{proc.returncode}",
    )


async def run_computer_use_worker_loop(stop_event: asyncio.Event) -> None:
    """Background poll loop for centralized computer-use jobs."""
    settings = get_settings()
    if not bool(settings.COMPUTER_USE_WORKER_ENABLED):
        logger.info("[ComputerUseWorker] Disabled by COMPUTER_USE_WORKER_ENABLED=false")
        return

    poll_seconds = max(1, int(settings.COMPUTER_USE_WORKER_POLL_SECONDS or 3))
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    logger.info(
        "[ComputerUseWorker] Started worker_id=%s poll=%ss cli=%s",
        worker_id,
        poll_seconds,
        str(settings.COMPUTER_USE_WORKER_CLI_PATH or "codex"),
    )

    while not stop_event.is_set():
        job = _claim_next_job(worker_id)
        if not job:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=poll_seconds)
            except asyncio.TimeoutError:
                continue
            continue

        try:
            await _execute_codex_job(job, worker_id=worker_id)
        except Exception:
            job_id = str(job.get("job_id") or "")
            user_id = int(job.get("user_id") or 0)
            logger.exception("[ComputerUseWorker] Unexpected processing error job_id=%s", job_id)
            _mark_job_result(
                job_id=job_id,
                status=ComputerUseJobStatus.FAILED,
                summary=None,
                error="Unexpected worker exception",
            )
            _append_user_log(
                user_id,
                "ERROR",
                "computer_use_bridge_job_failed",
                f"job_id={job_id} worker={worker_id} error=exception",
            )

    logger.info("[ComputerUseWorker] Stop requested")
