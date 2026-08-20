# -*- coding: utf-8 -*-
"""Background worker for server-side Computer Use bridge jobs."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
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

_SAFE_ENV_KEYS = {
    "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP",
    "LANG", "LC_ALL", "TERM", "USERPROFILE", "LOCALAPPDATA", "APPDATA",
}


def build_worker_env(source: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Return the minimal OS environment required to launch the CLI."""
    source_env = source if source is not None else os.environ
    return {
        key: str(value)
        for key, value in source_env.items()
        if key.upper() in _SAFE_ENV_KEYS and value is not None
    }


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_codex_cli_args() -> List[str]:
    """Build Codex CLI argv without placing the prompt in process metadata."""
    settings = get_settings()
    cli_path = str(settings.COMPUTER_USE_WORKER_CLI_PATH or "codex").strip() or "codex"
    workdir = str(settings.COMPUTER_USE_WORKER_WORKDIR or "").strip()
    model_name = str(settings.COMPUTER_USE_WORKER_MODEL or "").strip()

    sandbox = str(settings.COMPUTER_USE_WORKER_SANDBOX or "read-only").strip()
    args: List[str] = [cli_path, "exec", "--sandbox", sandbox, "--skip-git-repo-check"]
    if workdir:
        args.extend(["--cd", workdir])
    if model_name:
        args.extend(["--model", model_name])
    # Official Codex CLI contract: PROMPT='-' reads the instruction from stdin.
    args.append("-")
    return args


def _prompt_templates() -> Dict[str, str]:
    settings = get_settings()
    try:
        raw = json.loads(settings.COMPUTER_USE_PROMPT_TEMPLATES_JSON or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("Computer Use templates are invalid") from exc
    if not isinstance(raw, dict):
        raise RuntimeError("Computer Use templates are invalid")
    return {
        str(key): value.strip()
        for key, value in raw.items()
        if isinstance(key, str)
        and isinstance(value, str)
        and len(value.strip()) >= 20
    }


def resolve_template_prompt(template_id: str) -> str:
    """Resolve prompt text from server configuration at execution time only."""

    template = _prompt_templates().get(str(template_id or "").strip())
    if not template:
        raise RuntimeError("Unknown Computer Use template")
    return template


def scrub_legacy_job_prompts() -> int:
    """Replace historical DB prompt plaintext with IDs or a redacted marker."""

    db = SessionLocal()
    try:
        templates = _prompt_templates()
        reverse = {value: key for key, value in templates.items()}
        rows = db.query(ComputerUseJob).all()
        changed = 0
        for row in rows:
            stored = str(row.prompt or "")
            if stored in templates or stored == "__redacted__":
                continue
            row.prompt = reverse.get(stored, "__redacted__")
            changed += 1
        if changed:
            db.commit()
            logger.warning(
                "[ComputerUseWorker] Scrubbed %d legacy prompt values from the job table",
                changed,
            )
        return changed
    except Exception:
        db.rollback()
        logger.exception("[ComputerUseWorker] Failed to scrub legacy prompt values")
        raise
    finally:
        db.close()


def summarize_process_output(stdout_bytes: bytes, stderr_bytes: bytes, limit_chars: int) -> str:
    """Return metadata only; raw model output is never retained or exposed."""

    del limit_chars  # Retained in the call contract for configuration compatibility.
    stdout_len = len((stdout_bytes or b"").decode("utf-8", errors="replace"))
    stderr_len = len((stderr_bytes or b"").decode("utf-8", errors="replace"))
    if stdout_len == 0 and stderr_len == 0:
        return "Worker completed without retained output"
    return (
        "Worker output captured securely and discarded "
        f"(stdout_chars={stdout_len}, stderr_chars={stderr_len})"
    )


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
                "template_id": str(claimed.prompt or ""),
                "template_sha256": str(claimed.template_sha256 or ""),
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
    template_id = str(job.get("template_id") or "")
    queued_template_hash = str(job.get("template_sha256") or "")

    try:
        prompt = resolve_template_prompt(template_id)
    except Exception:
        _mark_job_result(
            job_id=job_id,
            status=ComputerUseJobStatus.FAILED,
            summary=None,
            error="Unknown or unavailable server template",
        )
        _append_user_log(
            user_id,
            "ERROR",
            "computer_use_bridge_job_failed",
            f"job_id={job_id} worker={worker_id} error=invalid_template",
        )
        return

    resolved_template_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    if not queued_template_hash or not hmac.compare_digest(
        resolved_template_hash,
        queued_template_hash,
    ):
        _mark_job_result(
            job_id=job_id,
            status=ComputerUseJobStatus.FAILED,
            summary=None,
            error="Server template changed after the job was queued",
        )
        _append_user_log(
            user_id,
            "ERROR",
            "computer_use_bridge_job_failed",
            f"job_id={job_id} worker={worker_id} error=template_revision_mismatch",
        )
        return

    args = build_codex_cli_args()
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
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workdir,
            env=build_worker_env(),
        )
    except Exception as exc:
        logger.warning(
            "[ComputerUseWorker] Worker process failed to start for job_id=%s: %s",
            job_id,
            type(exc).__name__,
        )
        _mark_job_result(
            job_id=job_id,
            status=ComputerUseJobStatus.FAILED,
            summary=None,
            error="Worker process failed to start",
        )
        _append_user_log(
            user_id,
            "ERROR",
            "computer_use_bridge_job_failed",
            f"job_id={job_id} worker={worker_id} error=start_failed",
        )
        return

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(input=prompt.encode("utf-8")),
            timeout=timeout_seconds,
        )
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
        error=f"Worker process exit code {proc.returncode}",
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

    # Scrub historical plaintext before accepting or executing another job.
    scrub_legacy_job_prompts()

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
