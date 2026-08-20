"""Build and temporarily install native protected modules for PyInstaller.

This is a release-build control, not a claim that locally executed code can be
made impossible to reverse engineer.  It removes recoverable first-party
bytecode and plaintext string constants from the normal desktop artifact.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.machinery
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Iterable

from release_protection_policy import (
    PROTECTED_MODULES,
    module_relative_path,
    module_source_path,
)


_DECODER_NAME = "_ssmaker_native_string_decode_7f3a"
_KEY_NAME = "_ssmaker_native_string_key_7f3a"


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _safe_remove_tree(path: Path, project_root: Path) -> None:
    resolved = path.resolve()
    allowed = (project_root / "build_staging").resolve()
    if not _is_relative_to(resolved, allowed) or resolved == allowed:
        raise RuntimeError(f"Refusing to remove path outside build_staging: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def _strip_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        stripped = body[1:]
        return stripped or [ast.Pass()]
    return body


class _ConfidentialStringTransformer(ast.NodeTransformer):
    """Replace string literals with encrypted bytes decoded at runtime."""

    def __init__(self, key: bytes):
        self._key = key

    def _decode_call(self, value: str, node: ast.AST) -> ast.Call:
        raw = value.encode("utf-8")
        encrypted = bytes(
            byte ^ self._key[index % len(self._key)]
            for index, byte in enumerate(raw)
        )
        call = ast.Call(
            func=ast.Name(id=_DECODER_NAME, ctx=ast.Load()),
            args=[ast.Constant(value=encrypted)],
            keywords=[],
        )
        return ast.copy_location(call, node)

    def visit_Module(self, node: ast.Module) -> ast.AST:
        node.body = _strip_docstring(node.body)
        return self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        node.body = _strip_docstring(node.body)
        return self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        node.body = _strip_docstring(node.body)
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        node.body = _strip_docstring(node.body)
        return self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> ast.AST:
        # Bytes literals cannot be emitted safely inside an f-string expression
        # on Python 3.11 because their repr may contain backslashes.  Lower the
        # f-string to ``''.join([...])`` while preserving !s/!r/!a conversion
        # and dynamic format specifications.
        values: list[ast.expr] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                if not value.value:
                    continue
                values.append(self._decode_call(value.value, value))
            elif isinstance(value, ast.FormattedValue):
                formatted_value = self.visit(value.value)
                if value.conversion == ord("s"):
                    formatted_value = ast.Call(
                        func=ast.Name(id="str", ctx=ast.Load()),
                        args=[formatted_value],
                        keywords=[],
                    )
                elif value.conversion == ord("r"):
                    formatted_value = ast.Call(
                        func=ast.Name(id="repr", ctx=ast.Load()),
                        args=[formatted_value],
                        keywords=[],
                    )
                elif value.conversion == ord("a"):
                    formatted_value = ast.Call(
                        func=ast.Name(id="ascii", ctx=ast.Load()),
                        args=[formatted_value],
                        keywords=[],
                    )
                format_spec = (
                    self.visit(value.format_spec)
                    if value.format_spec is not None
                    else ast.Constant(value="")
                )
                values.append(
                    ast.copy_location(
                        ast.Call(
                            func=ast.Name(id="format", ctx=ast.Load()),
                            args=[formatted_value, format_spec],
                            keywords=[],
                        ),
                        value,
                    )
                )
            else:
                transformed = self.visit(value)
                if transformed is not None:
                    values.append(transformed)
        return ast.copy_location(
            ast.Call(
                func=ast.Attribute(
                    value=ast.Constant(value=""),
                    attr="join",
                    ctx=ast.Load(),
                ),
                args=[ast.List(elts=values, ctx=ast.Load())],
                keywords=[],
            ),
            node,
        )

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if isinstance(node.value, str) and node.value:
            return self._decode_call(node.value, node)
        return node


def _module_key(module_name: str, source_bytes: bytes) -> bytes:
    # Deterministic per source revision so local/CI builds remain reproducible.
    # This is an obfuscation key embedded in native code, not a cryptographic
    # secret; actual secrets must never be shipped in the client.
    return hashlib.sha256(
        b"SSMaker/native-string-v1\0"
        + module_name.encode("utf-8")
        + b"\0"
        + source_bytes
    ).digest()


def _decoder_nodes(key: bytes) -> list[ast.stmt]:
    source = f"""
{_KEY_NAME} = {key!r}
def {_DECODER_NAME}(_payload):
    return bytes(
        _byte ^ {_KEY_NAME}[_index % len({_KEY_NAME})]
        for _index, _byte in enumerate(_payload)
    ).decode("utf-8")
"""
    return ast.parse(source).body


def _future_import_boundary(body: list[ast.stmt]) -> int:
    index = 0
    while index < len(body):
        statement = body[index]
        if isinstance(statement, ast.ImportFrom) and statement.module == "__future__":
            index += 1
            continue
        break
    return index


def _render_protected_source(source_path: Path, module_name: str) -> str:
    source_bytes = source_path.read_bytes()
    source_text = source_bytes.decode("utf-8-sig")
    tree = ast.parse(source_text, filename=str(source_path))
    key = _module_key(module_name, source_bytes)
    transformed = _ConfidentialStringTransformer(key).visit(tree)
    if not isinstance(transformed, ast.Module):
        raise RuntimeError(f"Unexpected transformed AST for {module_name}")
    boundary = _future_import_boundary(transformed.body)
    transformed.body[boundary:boundary] = _decoder_nodes(key)
    ast.fix_missing_locations(transformed)
    rendered = ast.unparse(transformed)
    # Fail closed if a representative long source literal survived the AST
    # rewrite.  The artifact verifier performs the definitive binary scan.
    candidates = sorted(
        {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and len(node.value.strip()) >= 48
        },
        key=len,
        reverse=True,
    )
    for literal in candidates[:10]:
        if literal in rendered:
            raise RuntimeError(
                f"Plaintext literal survived protected-source rewrite: {module_name}"
            )
    return rendered + "\n"


def _find_built_extension(build_lib: Path, module_name: str) -> Path:
    base = build_lib / module_relative_path(module_name)
    candidates: list[Path] = []
    for suffix in importlib.machinery.EXTENSION_SUFFIXES:
        candidate = Path(f"{base}{suffix}")
        if candidate.is_file():
            candidates.append(candidate)
    if len(candidates) != 1:
        raise RuntimeError(
            f"Expected one native extension for {module_name}, found: {candidates}"
        )
    return candidates[0]


def _write_manifest(manifest_path: Path, installed_files: Iterable[Path], root: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": 1,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "modules": list(PROTECTED_MODULES),
        "installed_files": [
            str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
            for path in installed_files
        ],
    }
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def cleanup(project_root: Path, manifest_path: Path) -> None:
    if manifest_path.is_file():
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        for relative in payload.get("installed_files", []):
            target = (project_root / str(relative)).resolve()
            if not _is_relative_to(target, project_root.resolve()):
                raise RuntimeError(f"Refusing to remove file outside project: {target}")
            if target.suffix.lower() != ".pyd":
                raise RuntimeError(f"Refusing to remove non-extension artifact: {target}")
            if target.is_file():
                target.unlink()
        manifest_path.unlink(missing_ok=True)

    # Generated Python/C sources are obfuscated but still build-only material.
    # Remove the exact validated staging subtree after PyInstaller consumes the
    # native overlay, and after failed local/CI attempts as well.
    _safe_remove_tree(
        project_root / "build_staging" / "protected_modules",
        project_root,
    )


def prepare(project_root: Path, manifest_path: Path) -> None:
    if sys.platform != "win32" or sys.version_info[:2] != (3, 11):
        raise RuntimeError("Protected release modules require Windows Python 3.11")

    cleanup(project_root, manifest_path)
    missing = [
        str(module_source_path(project_root, module))
        for module in PROTECTED_MODULES
        if not module_source_path(project_root, module).is_file()
    ]
    if missing:
        raise RuntimeError(f"Protected module source missing: {missing}")

    try:
        from Cython.Build import cythonize
        from Cython.Compiler import Options
        from setuptools import Extension
        from setuptools.dist import Distribution
    except ImportError as exc:
        raise RuntimeError(
            "Cython is required for release protection; install the locked release dependencies"
        ) from exc

    work_root = project_root / "build_staging" / "protected_modules"
    _safe_remove_tree(work_root, project_root)
    source_root = work_root / "source"
    build_lib = work_root / "lib"
    build_temp = work_root / "temp"
    source_root.mkdir(parents=True, exist_ok=True)

    extensions = []
    for module_name in PROTECTED_MODULES:
        original = module_source_path(project_root, module_name)
        generated = source_root / module_relative_path(module_name).with_suffix(".py")
        generated.parent.mkdir(parents=True, exist_ok=True)
        generated.write_text(
            _render_protected_source(original, module_name),
            encoding="utf-8",
            newline="\n",
        )
        compile_args = (
            ["/O2", "/GL", "/GS", "/guard:cf"]
            if os.name == "nt"
            else ["-O3"]
        )
        link_args = (
            [
                "/LTCG",
                "/OPT:REF",
                "/OPT:ICF",
                "/GUARD:CF",
                "/DYNAMICBASE",
                "/NXCOMPAT",
                "/HIGHENTROPYVA",
                "/CETCOMPAT",
            ]
            if os.name == "nt"
            else []
        )
        extensions.append(
            Extension(
                module_name,
                [str(generated)],
                define_macros=[("CYTHON_TRACE", "0"), ("CYTHON_TRACE_NOGIL", "0")],
                extra_compile_args=compile_args,
                extra_link_args=link_args,
            )
        )

    Options.docstrings = False
    Options.embed_pos_in_docstring = False
    compiled_extensions = cythonize(
        extensions,
        compiler_directives={
            "language_level": 3,
            "binding": True,
            "embedsignature": False,
            "linetrace": False,
            "profile": False,
            "emit_code_comments": False,
        },
        annotate=False,
        gdb_debug=False,
        c_line_in_traceback=False,
        emit_linenums=False,
        embedded_metadata=False,
        relative_path_in_code_position_comments=False,
        force=True,
        nthreads=max(1, min(4, os.cpu_count() or 1)),
    )

    distribution = Distribution(
        {
            "name": "ssmaker-protected-release-modules",
            "ext_modules": compiled_extensions,
        }
    )
    command = distribution.get_command_obj("build_ext")
    command.build_lib = str(build_lib)
    command.build_temp = str(build_temp)
    command.force = True
    command.inplace = False
    distribution.run_command("build_ext")

    installed: list[Path] = []
    try:
        _write_manifest(manifest_path, installed, project_root)
        for module_name in PROTECTED_MODULES:
            built = _find_built_extension(build_lib, module_name)
            destination = module_source_path(project_root, module_name).parent / built.name
            if destination.exists():
                raise RuntimeError(
                    f"Refusing to overwrite pre-existing native module: {destination}"
                )
            installed.append(destination)
            # Record the exact cleanup target before copying so an interrupted
            # build cannot strand an untracked native overlay in the source tree.
            _write_manifest(manifest_path, installed, project_root)
            shutil.copy2(built, destination)
    except Exception:
        for path in installed:
            path.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        raise

    # Avoid importing application packages during the build (some package
    # initializers have runtime side effects).  PyInstaller's spec performs the
    # definitive graph check and fails if any protected module resolves to PYZ.
    failures = [str(path) for path in installed if not path.is_file()]
    if failures:
        cleanup(project_root, manifest_path)
        raise RuntimeError(
            "Native protected-module installation failed: " + "; ".join(failures)
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "cleanup"))
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("build_staging/protected_modules_manifest.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = args.project_root.resolve()
    manifest = args.manifest
    if not manifest.is_absolute():
        manifest = project_root / manifest
    manifest = manifest.resolve()
    if not _is_relative_to(manifest, (project_root / "build_staging").resolve()):
        raise RuntimeError("Protection manifest must be inside build_staging")
    if args.action == "prepare":
        try:
            prepare(project_root, manifest)
        except Exception:
            cleanup(project_root, manifest)
            raise
        print(f"Protected native modules prepared: {len(PROTECTED_MODULES)}")
    else:
        cleanup(project_root, manifest)
        print("Protected native-module source overlay removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
