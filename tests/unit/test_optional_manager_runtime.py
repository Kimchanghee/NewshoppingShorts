import json
from pathlib import Path

import ssmaker


ROOT = Path(__file__).resolve().parents[2]


def test_optional_manager_source_runtime_smoke(tmp_path, monkeypatch):
    report_path = tmp_path / "optional-managers.json"
    monkeypatch.setenv("SSMAKER_OPTIONAL_MANAGER_RUNTIME_REPORT", str(report_path))

    assert ssmaker.run_optional_manager_runtime_smoke() == 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["managers"]["inpock"]["ok"] is True
    assert report["managers"]["sourcing"]["ok"] is True


def test_release_bundle_declares_and_executes_lazy_manager_smoke():
    spec = (ROOT / "ssmaker.spec").read_text(encoding="utf-8")
    build_script = (ROOT / "scripts" / "build_exe.ps1").read_text(
        encoding="utf-8-sig"
    )

    assert "'managers.inpock_manager'" in spec
    assert "'managers.sourcing_manager'" in spec
    assert "--optional-manager-runtime-smoke" in build_script
    assert "SSMAKER_OPTIONAL_MANAGER_RUNTIME_REPORT" in build_script
