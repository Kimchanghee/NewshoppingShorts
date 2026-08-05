"""Fail CI when tracked text files are not UTF-8 or contain common mojibake.

Run from the repository root with ``python scripts/check_utf8.py``.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".bat", ".cmd", ".css", ".env", ".html", ".ini", ".js", ".json",
    ".jsx", ".md", ".mjs", ".ps1", ".py", ".sh", ".toml", ".ts",
    ".tsx", ".txt", ".yaml", ".yml",
}
MOJIBAKE_PATTERNS = (
    ("Unicode replacement character", re.compile("\ufffd")),  # utf8-guard-allow
    ("mis-decoded UTF-8", re.compile(r"(?:Ã.|Â.|â[€-™])")),
)


def tracked_text_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    paths = result.stdout.decode("utf-8").split("\0")
    return [ROOT / path for path in paths if path and Path(path).suffix.lower() in TEXT_SUFFIXES]


def main() -> int:
    failures: list[str] = []
    files = tracked_text_files()
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            failures.append(f"{path.relative_to(ROOT)}: invalid UTF-8 ({exc})")
            continue
        lines = text.splitlines()
        for label, pattern in MOJIBAKE_PATTERNS:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                if (
                    "utf8-guard-allow" in lines[line - 1]
                    or path.resolve() == Path(__file__).resolve()
                ):
                    continue
                failures.append(f"{path.relative_to(ROOT)}:{line}: {label}")

    if failures:
        print("UTF-8 validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"UTF-8 validation passed for {len(files)} tracked text files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
