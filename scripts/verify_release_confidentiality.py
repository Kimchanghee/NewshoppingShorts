"""Fail a desktop release if protected source material is recoverable."""

from __future__ import annotations

import argparse
import hashlib
import importlib.machinery
import sys
from pathlib import Path

from release_protection_policy import (
    PROTECTED_MODULES,
    confidential_prompt_literals,
    module_relative_path,
    unprotected_prompt_literal_modules,
)


_CHUNK_SIZE = 4 * 1024 * 1024
_CANARY_BYTES = 48


def _select_canary(encoded: bytes) -> bytes:
    """Choose a stable, distinctive fixed-size fragment from a literal."""

    if len(encoded) <= _CANARY_BYTES:
        return encoded
    best = encoded[:_CANARY_BYTES]
    best_score = (-1, -1)
    # Examine every possible window. Protected literals are small enough for
    # this build-time work, while fixed-size release patterns avoid pathological
    # regex matching on multi-kilobyte prompt alternatives.
    for start in range(0, len(encoded) - _CANARY_BYTES + 1):
        window = encoded[start:start + _CANARY_BYTES]
        score = (
            len(set(window)),
            sum(byte not in b"\x00\t\r\n " for byte in window),
        )
        if score > best_score:
            best = window
            best_score = score
    return best


def _encoded_literal_index(literals: set[str]) -> dict[bytes, tuple[str, int]]:
    encoded: dict[bytes, tuple[str, int]] = {}
    for literal in literals:
        fingerprint = hashlib.sha256(literal.encode("utf-8")).hexdigest()[:12]
        metadata = (fingerprint, len(literal))
        encoded[_select_canary(literal.encode("utf-8"))] = metadata
        encoded[_select_canary(literal.encode("utf-16-le"))] = metadata
    return {needle: metadata for needle, metadata in encoded.items() if needle}


def _literal_pattern(needles: set[bytes]) -> tuple[bytes, ...]:
    if not needles:
        raise RuntimeError("No protected source literals were found")
    return tuple(sorted(needles, key=len, reverse=True))


def _find_literal(
    path: Path,
    patterns: tuple[bytes, ...],
    max_needle_length: int,
) -> bytes | None:
    overlap = max(0, max_needle_length - 1)
    tail = b""
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(_CHUNK_SIZE)
            if not chunk:
                return None
            data = tail + chunk
            # CPython's bytes search is substantially faster here than a large
            # alternation regex and keeps the release scan bounded on model and
            # multimedia assets as well as executable code.
            for needle in patterns:
                if needle in data:
                    return needle
            tail = data[-overlap:] if overlap else b""


def _format_leak(path: Path, fingerprint: str, literal_length: int) -> str:
    """Return leak diagnostics that never reproduce protected source text."""

    return f"{path}: sha256={fingerprint}, length={literal_length}"


def _native_extension_for(dist_dir: Path, module_name: str) -> Path | None:
    base = dist_dir / module_relative_path(module_name)
    direct = Path(f"{base}.pyd")
    if direct.is_file():
        return direct
    for suffix in importlib.machinery.EXTENSION_SUFFIXES:
        candidate = Path(f"{base}{suffix}")
        if candidate.is_file():
            return candidate
    candidates = list(base.parent.glob(f"{base.name}*.pyd"))
    return candidates[0] if len(candidates) == 1 else None


def _pyz_modules(executable: Path) -> set[str]:
    try:
        from PyInstaller.archive.readers import CArchiveReader
    except ImportError as exc:
        raise RuntimeError("PyInstaller is required for release artifact verification") from exc
    archive = CArchiveReader(str(executable))
    pyz_names = [name for name in archive.toc if name.upper().endswith("PYZ.PYZ")]
    if len(pyz_names) != 1:
        raise RuntimeError(f"Expected one embedded PYZ archive, found: {pyz_names}")
    pyz = archive.open_embedded_archive(pyz_names[0])
    return set(pyz.toc)


def verify(project_root: Path, dist_dir: Path) -> None:
    executable = dist_dir / "ssmaker.exe"
    if not executable.is_file():
        raise RuntimeError(f"Release executable missing: {executable}")

    uncovered_prompts = sorted(unprotected_prompt_literal_modules(project_root))
    if uncovered_prompts:
        raise RuntimeError(
            "Prompt/instruction literals are outside native protection: "
            + ", ".join(uncovered_prompts)
        )

    pyz_modules = _pyz_modules(executable)
    bytecode_leaks = sorted(set(PROTECTED_MODULES) & pyz_modules)
    if bytecode_leaks:
        raise RuntimeError(
            "Protected modules were shipped as recoverable Python bytecode: "
            + ", ".join(bytecode_leaks)
        )

    native_modules = {
        module: _native_extension_for(dist_dir, module)
        for module in PROTECTED_MODULES
    }
    missing_native = [module for module, path in native_modules.items() if path is None]
    if missing_native:
        raise RuntimeError(
            "Protected native modules are missing from the artifact: "
            + ", ".join(missing_native)
        )

    forbidden_first_party_suffixes = {".py", ".pyc", ".pyo"}
    first_party_roots = {module.split(".", 1)[0] for module in PROTECTED_MODULES}
    loose_source = []
    for root_name in first_party_roots:
        root = dist_dir / root_name
        if not root.exists():
            continue
        loose_source.extend(
            str(path.relative_to(dist_dir))
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in forbidden_first_party_suffixes
        )
    if loose_source:
        raise RuntimeError(
            "First-party Python source/bytecode found outside the archive: "
            + ", ".join(sorted(loose_source)[:20])
        )

    literals = confidential_prompt_literals(project_root)
    encoded_literals = _encoded_literal_index(literals)
    pattern = _literal_pattern(set(encoded_literals))
    max_needle_length = max(map(len, encoded_literals))
    leaks: list[tuple[Path, str, int]] = []
    for artifact in sorted(path for path in dist_dir.rglob("*") if path.is_file()):
        matched = _find_literal(artifact, pattern, max_needle_length)
        if matched is not None:
            fingerprint, literal_length = encoded_literals[matched]
            leaks.append((artifact, fingerprint, literal_length))
        if len(leaks) >= 10:
            break
    if leaks:
        details = "; ".join(
            _format_leak(path.relative_to(dist_dir), fingerprint, literal_length)
            for path, fingerprint, literal_length in leaks
        )
        raise RuntimeError(f"Protected plaintext recovered from release artifact: {details}")

    print(
        "Release confidentiality verification passed: "
        f"{len(PROTECTED_MODULES)} native modules, "
        f"{len(literals)} confidential prompt/instruction literals, "
        "full-tree plaintext scan passed"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--dist-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = args.project_root.resolve()
    dist_dir = args.dist_dir
    if not dist_dir.is_absolute():
        dist_dir = project_root / dist_dir
    verify(project_root, dist_dir.resolve())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"CONFIDENTIALITY VERIFICATION FAILED: {exc}", file=sys.stderr)
        raise
