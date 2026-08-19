import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOTS = ("app", "core", "managers", "startup", "ui")
POPUP_FUNCTIONS = {
    "show_error",
    "show_warning",
    "show_info",
    "show_success",
    "show_question",
}
EXCEPTION_NAMES = {"e", "exc", "error", "exception", "err"}


def _iter_source_files():
    for root_name in SOURCE_ROOTS:
        yield from (ROOT / root_name).rglob("*.py")
    yield ROOT / "main.py"
    yield ROOT / "ssmaker.py"


def _call_name(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _is_qmessagebox_critical(call: ast.Call) -> bool:
    return (
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "critical"
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "QMessageBox"
    )


def _contains_raw_exception(node: ast.AST) -> bool:
    if isinstance(node, ast.Call) and _call_name(node) == "sanitize_user_message":
        return False
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id in EXCEPTION_NAMES:
            return True
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == "str"
            and child.args
            and isinstance(child.args[0], ast.Name)
            and child.args[0].id in EXCEPTION_NAMES
        ):
            return True
    return False


def test_popup_calls_do_not_embed_raw_exception_objects():
    violations = []
    for path in _iter_source_files():
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or _call_name(node) not in POPUP_FUNCTIONS:
                continue
            if any(_contains_raw_exception(arg) for arg in node.args[1:]):
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")

    assert violations == []


def test_critical_popups_do_not_contain_mojibake_or_raw_exception_details():
    violations = []
    suspicious = ("?낅", "?ㅻ쪟", "硫붿", "鍮꾨뵒???", "WinError", "Traceback")
    for path in _iter_source_files():
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_qmessagebox_critical(node):
                continue
            rendered = ast.dump(node)
            if any(token in rendered for token in suspicious) or any(
                _contains_raw_exception(arg) for arg in node.args[1:]
            ):
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")

    assert violations == []


def test_common_inline_surfaces_use_the_shared_sanitizer():
    required = {
        "app/mixins/logging_mixin.py": "sanitize_user_message(message",
        "managers/progress_manager.py": "ui_highlight_message = sanitize_user_message(",
        "ui/components/status_bar.py": "sanitize_user_message(message",
        "ui/panels/multi_account_panel.py": "msg = sanitize_user_message(",
        "ui/panels/progress_panel.py": "sanitize_user_message(task_text",
        "ui/windows/startup_splash.py": "self._status_text = sanitize_user_message(",
        "ui/windows/update_dialog.py": "self._status_text = sanitize_user_message(",
    }
    for relative_path, marker in required.items():
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert marker in source, relative_path
