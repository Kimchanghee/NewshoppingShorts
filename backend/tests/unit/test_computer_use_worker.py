# -*- coding: utf-8 -*-
"""Unit tests for computer-use worker helpers."""

from __future__ import annotations

import os

# Ensure required settings can load.
os.environ.setdefault("DB_USER", "test_user")
os.environ.setdefault("DB_PASSWORD", "test_password")
os.environ.setdefault("JWT_SECRET_KEY", "0123456789abcdef0123456789abcdef")

from app.configuration import get_settings
from app.scheduler.computer_use_worker import (
    build_codex_cli_args,
    summarize_process_output,
)


def test_build_codex_cli_args_with_model_and_workdir(monkeypatch):
    monkeypatch.setenv("COMPUTER_USE_WORKER_CLI_PATH", "/usr/local/bin/codex")
    monkeypatch.setenv("COMPUTER_USE_WORKER_WORKDIR", "/tmp/worker-space")
    monkeypatch.setenv("COMPUTER_USE_WORKER_MODEL", "gpt-5.5")
    get_settings.cache_clear()

    args = build_codex_cli_args("run step now")
    assert args == [
        "/usr/local/bin/codex",
        "--cd",
        "/tmp/worker-space",
        "--model",
        "gpt-5.5",
        "run step now",
    ]


def test_summarize_process_output_includes_streams_and_truncates():
    stdout = ("ok\n" * 300).encode("utf-8")
    stderr = ("warn\n" * 300).encode("utf-8")

    summary = summarize_process_output(stdout, stderr, limit_chars=200)
    assert summary.startswith("stdout:")
    assert "stderr:" in summary
    # Helper enforces a minimum cap to preserve useful diagnostics.
    assert len(summary) <= 256
    assert summary.endswith("...")


def test_summarize_process_output_empty_streams():
    summary = summarize_process_output(b"", b"", limit_chars=300)
    assert summary == "(no output)"
