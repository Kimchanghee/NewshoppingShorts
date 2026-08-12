import json
import logging
import sys

from startup import diagnostics
from startup.diagnostics import StartupIssue


def _read_records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_record_startup_exception_writes_complete_redacted_jsonl(tmp_path, monkeypatch):
    log_path = tmp_path / "startup.jsonl"
    secret = "sk_test_super_private_value_123456789"
    monkeypatch.setattr(diagnostics, "get_startup_log_path", lambda: log_path)
    monkeypatch.setenv("PAYMENT_API_KEY", secret)

    def inner_failure():
        raise RuntimeError(
            f"authorization: Bearer bearer_private_value_123; api_key={secret}; "
            "client_secret='quoted_private_value_456'; "
            "url=https://service.invalid/path?token=query_private_value_789"
        )

    try:
        inner_failure()
    except RuntimeError as exc:
        issue = diagnostics.record_startup_exception(
            "initialization",
            "core_modules",
            exc,
            recoverable=False,
        )

    records = _read_records(log_path)
    assert len(records) == 1
    record = records[0]
    assert record["schema_version"] == 1
    assert record["event"] == "startup_exception"
    assert record["run_id"] == issue.run_id == diagnostics.get_startup_run_id()
    assert record["timestamp"].endswith("Z")
    assert record["app_version"]
    assert "app_build" in record
    assert record["frozen"] is bool(getattr(sys, "frozen", False))
    assert record["phase"] == "initialization"
    assert record["component"] == "core_modules"
    assert record["code"] == "startup_unexpected_error"
    assert record["exception_type"] == "RuntimeError"
    assert "inner_failure" in record["traceback"]
    assert "RuntimeError" in record["traceback"]
    serialized = log_path.read_text(encoding="utf-8")
    assert secret not in serialized
    assert "bearer_private_value_123" not in serialized
    assert "quoted_private_value_456" not in serialized
    assert "query_private_value_789" not in serialized
    assert "<redacted>" in record["exception_message"]


def test_new_aq_gemini_key_is_redacted_as_a_standalone_value():
    aq_key = "AQ.Ab8RN6JvdXUtxAuthKeyExample1234567890abcdefg"

    redacted = diagnostics.redact_sensitive_text(f"provider failed with {aq_key}")

    assert aq_key not in redacted
    assert "<redacted>" in redacted


def test_startup_issue_contract_and_user_message_are_safe():
    issue = StartupIssue(
        code="startup_network_unavailable",
        component="api",
        phase="initialization",
        run_id="run-123",
        recoverable=True,
        offline_allowed=True,
    )

    assert issue.to_dict() == {
        "code": "startup_network_unavailable",
        "component": "api",
        "phase": "initialization",
        "run_id": "run-123",
        "recoverable": True,
        "offline_allowed": True,
    }
    assert "오프라인" in issue.user_message()
    assert "run-123" not in issue.user_message()
    assert diagnostics.startup_issue_user_message(issue.to_dict()) == issue.user_message()


def test_classifier_returns_stable_codes():
    assert (
        diagnostics.classify_startup_exception(
            "bootstrap", "imports", ModuleNotFoundError("missing")
        )
        == "startup_dependency_missing"
    )
    assert (
        diagnostics.classify_startup_exception(
            "bootstrap", "files", PermissionError("denied")
        )
        == "startup_permission_denied"
    )
    assert (
        diagnostics.classify_startup_exception(
            "bootstrap", "network", TimeoutError("slow")
        )
        == "startup_network_timeout"
    )
    assert (
        diagnostics.classify_startup_exception(
            "bootstrap", "network", ConnectionError("offline")
        )
        == "startup_network_unavailable"
    )


def test_initializer_emits_failed_without_finished_on_unexpected_error(
    tmp_path, monkeypatch
):
    from startup import initializer as initializer_module

    log_path = tmp_path / "startup.jsonl"
    monkeypatch.setattr(diagnostics, "get_startup_log_path", lambda: log_path)
    monkeypatch.setattr(initializer_module.time, "sleep", lambda _seconds: None)

    def fail_system_check():
        raise RuntimeError("system probe failed")

    monkeypatch.setattr(initializer_module, "check_system_requirements", fail_system_check)
    initializer = initializer_module.Initializer()
    finished = []
    failed = []
    initializer.finished.connect(lambda: finished.append(True))
    initializer.failed.connect(failed.append)

    initializer.run()

    assert finished == []
    assert len(failed) == 1
    assert failed[0]["phase"] == "initialization"
    assert failed[0]["component"] == "system_requirements"
    assert failed[0]["recoverable"] is False
    assert _read_records(log_path)[0]["exception_type"] == "RuntimeError"


def test_ocr_failure_remains_nonfatal_and_is_recorded(tmp_path, monkeypatch):
    from startup import initializer as initializer_module
    from utils import ocr_backend

    log_path = tmp_path / "startup.jsonl"
    monkeypatch.setattr(diagnostics, "get_startup_log_path", lambda: log_path)

    def fail_ocr():
        raise RuntimeError("OCR backend unavailable")

    monkeypatch.setattr(ocr_backend, "create_ocr_reader", fail_ocr)
    initializer = initializer_module.Initializer()
    check_items = []
    initializer.checkItemChanged.connect(lambda *args: check_items.append(args))

    initializer._init_ocr()

    assert check_items[-1][0:2] == ("ocr", "warning")
    record = _read_records(log_path)[0]
    assert record["code"] == "startup_ocr_unavailable"
    assert record["recoverable"] is True
    assert record["offline_allowed"] is True


def test_entry_excepthook_logs_and_records_full_traceback(tmp_path, monkeypatch):
    import ssmaker

    log_path = tmp_path / "startup.jsonl"
    original_calls = []
    critical_calls = []
    monkeypatch.setattr(diagnostics, "get_startup_log_path", lambda: log_path)
    monkeypatch.setattr(sys, "excepthook", lambda *args: original_calls.append(args))
    monkeypatch.setattr(
        logging,
        "critical",
        lambda *args, **kwargs: critical_calls.append((args, kwargs)),
    )
    ssmaker.install_keyboardinterrupt_hook()

    try:
        raise LookupError("entry failure")
    except LookupError:
        exc_type, exc_value, exc_traceback = sys.exc_info()
    sys.excepthook(exc_type, exc_value, exc_traceback)

    assert original_calls[0] == (exc_type, exc_value, exc_traceback)
    assert critical_calls[0][1]["exc_info"] == (exc_type, exc_value, exc_traceback)
    record = _read_records(log_path)[0]
    assert record["code"] == "startup_uncaught_exception"
    assert "test_entry_excepthook_logs_and_records_full_traceback" in record["traceback"]
