# -*- coding: utf-8 -*-
"""Unit tests for computer-use worker helpers."""

from __future__ import annotations

import asyncio
import os

# Ensure required settings can load.
os.environ.setdefault("DB_USER", "test_user")
os.environ.setdefault("DB_PASSWORD", "test_password")
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "unit-test-placeholder-not-a-production-secret",  # gitleaks:allow
)

from app.configuration import get_settings
from app.scheduler.computer_use_worker import (
    _execute_codex_job,
    build_codex_cli_args,
    resolve_template_prompt,
    summarize_process_output,
)


def test_build_codex_cli_args_with_model_and_workdir(monkeypatch):
    monkeypatch.setenv("COMPUTER_USE_WORKER_CLI_PATH", "/usr/local/bin/codex")
    monkeypatch.setenv("COMPUTER_USE_WORKER_WORKDIR", "/tmp/worker-space")
    monkeypatch.setenv("COMPUTER_USE_WORKER_MODEL", "gpt-5.5")
    get_settings.cache_clear()

    args = build_codex_cli_args()
    assert args == [
        "/usr/local/bin/codex",
        "exec",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--cd",
        "/tmp/worker-space",
        "--model",
        "gpt-5.5",
        "-",
    ]
    assert "run step now" not in args


def test_resolve_template_prompt_only_at_execution_time(monkeypatch):
    prompt = "This instruction is resolved only inside the worker at execution time."
    monkeypatch.setenv(
        "COMPUTER_USE_PROMPT_TEMPLATES_JSON",
        '{"setup_target_test": "' + prompt + '"}',
    )
    get_settings.cache_clear()

    assert resolve_template_prompt("setup_target_test") == prompt


def test_summarize_process_output_discards_raw_stream_contents():
    secret_prompt = "private server instruction must never be returned"
    stdout = (secret_prompt + "\n").encode("utf-8")
    stderr = ("internal execution technology\n").encode("utf-8")

    summary = summarize_process_output(stdout, stderr, limit_chars=200)
    assert summary == (
        "Worker output captured securely and discarded "
        f"(stdout_chars={len(secret_prompt) + 1}, stderr_chars=30)"
    )
    assert secret_prompt not in summary
    assert "execution technology" not in summary


def test_summarize_process_output_empty_streams():
    summary = summarize_process_output(b"", b"", limit_chars=300)
    assert summary == "Worker completed without retained output"


def test_execute_job_rejects_changed_template_revision(monkeypatch):
    prompt = "This private server instruction is long enough for the template store."
    monkeypatch.setenv(
        "COMPUTER_USE_PROMPT_TEMPLATES_JSON",
        '{"setup_target_test": "' + prompt + '"}',
    )
    get_settings.cache_clear()

    recorded = {}
    monkeypatch.setattr(
        "app.scheduler.computer_use_worker._mark_job_result",
        lambda **kwargs: recorded.update(kwargs),
    )
    monkeypatch.setattr(
        "app.scheduler.computer_use_worker._append_user_log",
        lambda *args, **kwargs: None,
    )

    asyncio.run(
        _execute_codex_job(
            {
                "job_id": "job-1",
                "user_id": "7",
                "template_id": "setup_target_test",
                "template_sha256": "0" * 64,
            },
            worker_id="worker-1",
        )
    )

    assert recorded["status"].value == "failed"
    assert recorded["summary"] is None
    assert recorded["error"] == "Server template changed after the job was queued"
