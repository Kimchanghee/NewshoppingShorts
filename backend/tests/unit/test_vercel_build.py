"""Vercel build-mode regressions."""

import importlib.util
from pathlib import Path


script_path = Path(__file__).parents[2] / "scripts" / "vercel_build.py"
spec = importlib.util.spec_from_file_location("vercel_build", script_path)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def _unexpected_call(*_args, **_kwargs):
    raise AssertionError("preview builds must not touch protected backend operations")


def test_preview_build_skips_protected_backend_operations(monkeypatch, capsys):
    monkeypatch.setenv("VERCEL_ENV", "preview")
    monkeypatch.setattr(module, "_load_backend_steps", _unexpected_call)
    monkeypatch.setattr(module.subprocess, "run", _unexpected_call)

    assert module.main() == 0
    assert "skipping backend preflight, migrations, and account recovery" in capsys.readouterr().out


def test_production_build_keeps_fail_closed_backend_sequence(monkeypatch):
    calls = []
    monkeypatch.setenv("VERCEL_ENV", "production")
    verify = lambda: calls.append("preflight") or 0
    recover = lambda: calls.append("recovery") or 0
    monkeypatch.setattr(module, "_load_backend_steps", lambda: (recover, verify))
    monkeypatch.setattr(module.subprocess, "run", lambda *_args, **_kwargs: calls.append("migration"))

    assert module.main() == 0
    assert calls == ["preflight", "migration", "recovery"]
