"""One-shot fixer: add `from __future__ import annotations` to every project
.py file that uses PEP 604 union syntax (X | None, X | Y) in annotations.

This makes the code importable on Python 3.9 without changing semantics on 3.10+.

Run once from VS Code (Run button) with the project python interpreter.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
SKIP_DIRS = {".venv", "venv", ".git", "__pycache__", "node_modules", "build", "dist"}

# Heuristic: a line that looks like a type annotation with PEP 604 `|`.
# Examples matched:
#   def f(x: str | None) -> int | None:
#   foo: list[str] | None = None
#   -> dict | None:
#   def g(x: "Foo") -> Foo | None:
PEP604_RE = re.compile(
    r"(?:->|:)\s*"                    # annotation prefix
    r"[\w\[\].\"', ]+?"               # a type-ish blob (non-greedy)
    r"\s*\|\s*"                       # the PEP 604 bar
    r"[\w\[\].\"', ]+"                # right-hand type
)

FUTURE_LINE = "from __future__ import annotations"


def has_future_import(src: str) -> bool:
    return FUTURE_LINE in src


def uses_pep604(src: str) -> bool:
    # Only check *non-string, non-comment* lines roughly: drop strings/comments.
    # Quick & dirty: strip '#...' tails and '"..."'/"'...'" inline strings.
    cleaned_lines = []
    in_triple = None
    for line in src.splitlines():
        stripped = line
        if in_triple:
            if in_triple in stripped:
                stripped = stripped.split(in_triple, 1)[1]
                in_triple = None
            else:
                continue
        # detect triple-quoted blocks starting on this line
        for q in ('"""', "'''"):
            if q in stripped and stripped.count(q) % 2 == 1:
                stripped = stripped.split(q, 1)[0]
                in_triple = q
                break
        # drop comments
        if "#" in stripped:
            stripped = stripped.split("#", 1)[0]
        cleaned_lines.append(stripped)
    cleaned = "\n".join(cleaned_lines)
    return bool(PEP604_RE.search(cleaned))


def insertion_index(src: str) -> int:
    """Return the line index where we should insert the future import.

    Rule: after the module docstring (if any) and after any leading
    `# -*- coding: ... -*-` / shebang lines, but before other imports.
    """
    lines = src.splitlines()
    i = 0
    # 1) shebang + encoding header
    while i < len(lines) and (lines[i].startswith("#!") or "coding" in lines[i][:40]):
        i += 1
    # 2) blank lines
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    # 3) module docstring (triple-quoted)
    if i < len(lines):
        stripped = lines[i].lstrip()
        for q in ('"""', "'''"):
            if stripped.startswith(q):
                # find closing on same line or later
                if stripped.count(q) >= 2 and len(stripped) > len(q):
                    i += 1
                else:
                    j = i + 1
                    while j < len(lines) and q not in lines[j]:
                        j += 1
                    i = j + 1
                break
    # 4) blank lines after docstring
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    return i


def fix_file(path: Path) -> bool:
    try:
        src = path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  SKIP {path} ({e})")
        return False

    if has_future_import(src):
        return False
    if not uses_pep604(src):
        return False

    lines = src.splitlines(keepends=True)
    idx = insertion_index(src)
    insert = FUTURE_LINE + "\n"
    if idx < len(lines) and lines[idx].strip():
        insert += "\n"  # blank line separator
    lines.insert(idx, insert)
    path.write_text("".join(lines), encoding="utf-8")
    return True


def main():
    touched = 0
    scanned = 0
    for root, dirs, files in os.walk(PROJECT_DIR):
        # prune skip dirs in-place
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if not name.endswith(".py"):
                continue
            p = Path(root) / name
            # Don't touch ourselves
            if p.resolve() == Path(__file__).resolve():
                continue
            scanned += 1
            if fix_file(p):
                touched += 1
                print(f"  FIXED {p.relative_to(PROJECT_DIR)}")
    print(f"\nScanned {scanned} .py files. Added future import to {touched} files.")


if __name__ == "__main__":
    main()
