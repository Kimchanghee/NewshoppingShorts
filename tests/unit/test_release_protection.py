from __future__ import annotations

import ast
import importlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "scripts"
POLICY_PATH = SCRIPT_DIR / "release_protection_policy.py"
BUILD_SCRIPT_PATH = SCRIPT_DIR / "build_protected_modules.py"
VERIFY_SCRIPT_PATH = SCRIPT_DIR / "verify_release_confidentiality.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_protected_module_exists_and_is_unique():
    policy = _load_module("release_protection_policy_test", POLICY_PATH)
    modules = policy.PROTECTED_MODULES
    assert modules
    assert len(modules) == len(set(modules))
    for module_name in modules:
        assert policy.module_source_path(ROOT, module_name).is_file(), module_name


def test_every_prompt_like_literal_is_covered_by_native_protection():
    policy = _load_module("release_protection_prompt_coverage_test", POLICY_PATH)
    assert policy.unprotected_prompt_literal_modules(ROOT) == set()


def test_protected_import_graph_keeps_first_party_dependencies_visible():
    policy = _load_module("release_protection_policy_imports_test", POLICY_PATH)
    hidden = set(policy.protected_hidden_imports(ROOT))
    assert "core.video.batch.utils" in hidden
    assert "prompts" in hidden
    assert "utils.logging_config" in hidden


def test_string_transform_removes_plaintext_and_preserves_behavior(tmp_path):
    # The build module imports the sibling policy as a top-level module when it
    # runs as a script, so make that resolution available for this unit test.
    import sys

    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        build = _load_module("build_protected_modules_test", BUILD_SCRIPT_PATH)
    finally:
        sys.path.remove(str(SCRIPT_DIR))

    source = tmp_path / "sample.py"
    source.write_text(
        '"module docs"\n'
        "from __future__ import annotations\n"
        "VALUE = '기밀 프롬프트 문자열입니다'\n"
        "def render(name):\n"
        "    \"function docs\"\n"
        "    return f'안녕하세요 {name!r:>8}!'\n",
        encoding="utf-8",
    )
    rendered = build._render_protected_source(source, "sample")
    assert "기밀 프롬프트 문자열입니다" not in rendered
    assert "안녕하세요" not in rendered
    assert "module docs" not in rendered
    assert "function docs" not in rendered

    namespace: dict[str, object] = {}
    exec(compile(ast.parse(rendered), str(source), "exec"), namespace)
    assert namespace["VALUE"] == "기밀 프롬프트 문자열입니다"
    assert namespace["render"]("철수") == f"안녕하세요 {'철수'!r:>8}!"


def test_protected_prompt_sources_preserve_exact_runtime_output():
    import sys

    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        build = _load_module("build_protected_prompts_test", BUILD_SCRIPT_PATH)
    finally:
        sys.path.remove(str(SCRIPT_DIR))

    cases = {
        "prompts.audio_analysis": (
            "get_audio_analysis_prompt",
            (["첫 문장", "둘째 문장"],),
            {},
        ),
        "prompts.subtitle_split": (
            "get_subtitle_split_prompt",
            ("자막을 자연스럽게 나눠 주세요",),
            {},
        ),
        "prompts.translation": (
            "get_translation_prompt",
            ("原文", 30.0, 27.0, 90, "짧게", ["첫째", "둘째", "셋째"]),
            {},
        ),
        "prompts.video_analysis": (
            "get_video_analysis_prompt",
            (["첫째", "둘째", "셋째"],),
            {},
        ),
        "prompts.video_validation": (
            "get_video_validation_prompt",
            (),
            {},
        ),
    }
    for module_name, (function_name, args, kwargs) in cases.items():
        source_path = ROOT.joinpath(*module_name.split(".")).with_suffix(".py")
        rendered = build._render_protected_source(source_path, module_name)
        namespace = {"__name__": module_name, "__file__": str(source_path)}
        exec(compile(rendered, str(source_path), "exec"), namespace)
        original = importlib.import_module(module_name)
        assert namespace[function_name](*args, **kwargs) == getattr(
            original,
            function_name,
        )(*args, **kwargs)


def test_protected_runtime_smoke_imports_contract_and_writes_no_prompt(
    tmp_path,
    monkeypatch,
):
    import ssmaker

    policy = _load_module("release_protection_runtime_test", POLICY_PATH)
    report_path = tmp_path / "protected-runtime.json"
    monkeypatch.setenv("SSMAKER_PROTECTED_RUNTIME_REPORT", str(report_path))

    assert ssmaker.run_protected_runtime_smoke() == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["prompt_contract"] is True
    assert set(report["modules"]) == set(policy.PROTECTED_MODULES)
    serialized = report_path.read_text(encoding="utf-8")
    assert "중국어 대본" not in serialized
    assert "자기검증" not in serialized


def test_release_build_executes_frozen_protected_runtime_smoke():
    build_script = (SCRIPT_DIR / "build_exe.ps1").read_text(encoding="utf-8")
    assert "--protected-runtime-smoke" in build_script
    assert "SSMAKER_PROTECTED_RUNTIME_REPORT" in build_script


def test_protected_native_build_enables_windows_exploit_mitigations():
    build_script = BUILD_SCRIPT_PATH.read_text(encoding="utf-8")

    for flag in (
        '"/GS"',
        '"/guard:cf"',
        '"/GUARD:CF"',
        '"/DYNAMICBASE"',
        '"/NXCOMPAT"',
        '"/HIGHENTROPYVA"',
        '"/CETCOMPAT"',
    ):
        assert flag in build_script


def test_release_build_runs_hash_pinned_redacted_oss_security_gates():
    release_script = (SCRIPT_DIR / "build_exe.ps1").read_text(encoding="utf-8")
    gitleaks_script = (SCRIPT_DIR / "run_gitleaks.ps1").read_text(encoding="utf-8")
    binskim_script = (SCRIPT_DIR / "run_binskim.ps1").read_text(encoding="utf-8")

    assert "run_gitleaks.ps1" in release_script
    assert "run_binskim.ps1" in release_script
    assert "--redact=100" in gitleaks_script
    assert "d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e" in gitleaks_script
    assert "HVko8xQVQgXwVx2EuC8D5iQeA6kcyFBwL+u1XTHIjATwbb2gP6btZDmiYU9jU60mb3HAOZf1+MsBGSkIuE/xYg==" in binskim_script
    assert "BA2008;BA2009;BA2010;BA2015;BA2016;BA2019;BA2021" in binskim_script


def test_source_entrypoint_refuses_an_interrupted_native_overlay():
    source = (ROOT / "ssmaker.py").read_text(encoding="utf-8")
    assert "protected_modules_manifest.json" in source
    assert "_refuse_interrupted_protected_overlay()" in source


def test_verifier_leak_diagnostics_never_echo_protected_plaintext():
    import sys

    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        verifier = _load_module("verify_release_confidentiality_test", VERIFY_SCRIPT_PATH)
    finally:
        sys.path.remove(str(SCRIPT_DIR))

    secret = "절대로 CI 로그에 출력하면 안 되는 보호 프롬프트 문자열"
    fingerprint = __import__("hashlib").sha256(secret.encode("utf-8")).hexdigest()[:12]
    detail = verifier._format_leak(Path("module.pyd"), fingerprint, len(secret))
    assert secret not in detail
    assert fingerprint in detail
    assert f"length={len(secret)}" in detail


def test_verifier_scans_literals_across_chunk_and_artifact_boundaries(tmp_path):
    import sys

    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        verifier = _load_module("verify_release_scan_test", VERIFY_SCRIPT_PATH)
    finally:
        sys.path.remove(str(SCRIPT_DIR))

    literal = "보호 대상 프롬프트가 다른 네이티브 모듈로 복사되어도 탐지해야 합니다"
    index = verifier._encoded_literal_index({literal})
    pattern = verifier._literal_pattern(set(index))
    encoded = literal.encode("utf-8")
    artifact = tmp_path / "unrelated-module.pyd"
    artifact.write_bytes(b"x" * (verifier._CHUNK_SIZE - 7) + encoded + b"tail")

    matched = verifier._find_literal(artifact, pattern, max(map(len, index)))
    assert matched in index
    assert matched in encoded
