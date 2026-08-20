"""Single source of truth for desktop release confidentiality controls.

The modules below contain prompt templates or implementation details that must
not be shipped as recoverable Python bytecode.  Release builds compile them to
native extensions from a generated, string-obfuscated source tree.
"""

from __future__ import annotations

import ast
from pathlib import Path


PROTECTED_MODULES: tuple[str, ...] = (
    # Proprietary model instructions.
    "prompts.audio_analysis",
    "prompts.subtitle_split",
    "prompts.translation",
    "prompts.video_analysis",
    "prompts.video_validation",
    # Model selection/call orchestration and the core generation pipeline.
    "core.providers",
    "core.audio.pipeline",
    "core.video.CreateFinalVideo",
    "core.video.reeditor",
    "core.video.render_integrity",
    "core.video.video_validator",
    "core.video.batch.analysis",
    "core.video.batch.encoder",
    "core.video.batch.processor",
    "core.video.batch.subtitle_handler",
    "core.video.batch.tts_generator",
    "core.video.batch.tts_speed",
    "core.video.batch.utils",
    "core.video.batch.whisper_analyzer",
    # Sourcing/ranking/automation techniques.
    "core.sourcing.coupang_scraper",
    "core.sourcing.gemini_computer_use",
    "core.sourcing.keyword_converter",
    "core.sourcing.pipeline",
    "core.sourcing.platform_pipeline",
    "core.sourcing.platform_shorts_searcher",
    "core.sourcing.platform_video_collector",
    "core.sourcing.product_searcher",
    # Subtitle, speech, composition, and generated-metadata policies.
    "processors.subtitle_detector",
    "processors.subtitle_processor",
    "processors.tts_processor",
    "processors.video_composer",
    "managers.settings_manager",
    # UI orchestration containing complete Computer Use/Codex instructions.
    "ui.panels.settings_tab",
    "ui.panels.upload_panel",
)

_PROMPT_SCAN_ROOTS: tuple[str, ...] = (
    "core",
    "managers",
    "processors",
    "prompts",
    "ui",
)
_PROMPT_NAME_MARKERS: tuple[str, ...] = ("prompt", "instruction")
_MIN_PROMPT_LITERAL_LENGTH = 40


def module_source_path(project_root: Path, module_name: str) -> Path:
    """Return the checked-in Python source path for a protected module."""

    return project_root.joinpath(*module_name.split(".")).with_suffix(".py")


def module_relative_path(module_name: str) -> Path:
    """Return the platform-neutral relative module path without a suffix."""

    return Path(*module_name.split("."))


def _assigned_names(target: ast.AST) -> set[str]:
    return {
        node.id if isinstance(node, ast.Name) else node.attr
        for node in ast.walk(target)
        if isinstance(node, (ast.Name, ast.Attribute))
    }


def _contains_long_literal(value: ast.AST) -> bool:
    return any(
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and len(node.value.strip()) >= _MIN_PROMPT_LITERAL_LENGTH
        for node in ast.walk(value)
    )


def _long_literals(value: ast.AST) -> set[str]:
    return {
        node.value
        for node in ast.walk(value)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and len(node.value.strip()) >= _MIN_PROMPT_LITERAL_LENGTH
    }


def _named_prompt_values(tree: ast.AST) -> list[ast.AST]:
    values: list[ast.AST] = []
    for node in ast.walk(tree):
        value: ast.AST | None = None
        names: set[str] = set()
        if isinstance(node, ast.Assign):
            value = node.value
            for target in node.targets:
                names.update(_assigned_names(target))
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            names.update(_assigned_names(node.target))
        elif isinstance(node, ast.keyword) and node.arg:
            value = node.value
            names.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            value = node
            names.add(node.name)
        if value is not None and any(
            marker in name.lower()
            for name in names
            for marker in _PROMPT_NAME_MARKERS
        ):
            values.append(value)
    return values


def confidential_prompt_literals(project_root: Path) -> set[str]:
    """Return the explicit plaintext canary set scanned across a release.

    Every long literal in the dedicated prompt package is confidential.  In
    the rest of the protected client, long literals flowing through a value or
    function named prompt/instruction are confidential as well.
    """

    literals: set[str] = set()
    for module_name in PROTECTED_MODULES:
        source_path = module_source_path(project_root, module_name)
        tree = ast.parse(
            source_path.read_text(encoding="utf-8-sig"),
            filename=str(source_path),
        )
        if module_name.startswith("prompts."):
            literals.update(_long_literals(tree))
            continue
        for value in _named_prompt_values(tree):
            literals.update(_long_literals(value))
    return literals


def prompt_literal_modules(project_root: Path) -> set[str]:
    """Find first-party modules that embed prompt/instruction-like literals.

    This is a release coverage gate, not a secret classifier.  A newly added
    long literal assigned or passed through a prompt/instruction-named value
    must be compiled natively or explicitly refactored out of the client.
    """

    owners: set[str] = set()
    for root_name in _PROMPT_SCAN_ROOTS:
        source_root = project_root / root_name
        if not source_root.is_dir():
            continue
        for source_path in source_root.rglob("*.py"):
            tree = ast.parse(
                source_path.read_text(encoding="utf-8-sig"),
                filename=str(source_path),
            )
            found = root_name == "prompts" and _contains_long_literal(tree)
            if not found:
                found = any(
                    _contains_long_literal(value)
                    for value in _named_prompt_values(tree)
                )
            if found:
                relative = source_path.relative_to(project_root).with_suffix("")
                owners.add(".".join(relative.parts))
    return owners


def unprotected_prompt_literal_modules(project_root: Path) -> set[str]:
    """Return prompt-bearing modules that would otherwise ship as bytecode."""

    return prompt_literal_modules(project_root) - set(PROTECTED_MODULES)


def _project_module_exists(project_root: Path, module_name: str) -> bool:
    path = project_root.joinpath(*module_name.split("."))
    return path.with_suffix(".py").is_file() or (path / "__init__.py").is_file()


def protected_hidden_imports(project_root: Path) -> list[str]:
    """Collect imports hidden when PyInstaller sees native extensions only.

    PyInstaller cannot inspect Python imports inside a compiled Cython module.
    Keep the dependency graph complete by deriving direct imports from the
    checked-in protected sources at spec evaluation time.
    """

    imports: set[str] = set()
    for module_name in PROTECTED_MODULES:
        source_path = module_source_path(project_root, module_name)
        tree = ast.parse(
            source_path.read_text(encoding="utf-8-sig"),
            filename=str(source_path),
        )
        package_parts = module_name.split(".")[:-1]
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
                continue
            if not isinstance(node, ast.ImportFrom):
                continue

            if node.level:
                keep = len(package_parts) - (node.level - 1)
                if keep < 0:
                    continue
                base_parts = package_parts[:keep]
                if node.module:
                    base_parts.extend(node.module.split("."))
                base = ".".join(base_parts)
            else:
                base = str(node.module or "")
            if base:
                imports.add(base)

            # ``from . import helper`` and ``from pkg import submodule`` need
            # the concrete child only when it is a project module.  Function
            # and class imports must not be misreported as hidden modules.
            for alias in node.names:
                if alias.name == "*":
                    continue
                candidate = f"{base}.{alias.name}" if base else alias.name
                if _project_module_exists(project_root, candidate):
                    imports.add(candidate)

    imports.discard("")
    return sorted(imports)
