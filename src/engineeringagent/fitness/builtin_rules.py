from __future__ import annotations

import ast
import re
from pathlib import Path

from .contracts import CONTRACT_VERSION, RuleSeverity, RuleStatus

DEPENDENCY_DIRECTIONALITY_RULE_ID = "architecture.dep-directionality"
LOOP_SUBPROCESS_BOUNDARY_RULE_ID = "architecture.loop-subprocess-boundary"
PROMPT_LOCALITY_RULE_ID = "architecture.prompt-locality"
SCAFFOLD_TEMPLATE_LOCALITY_RULE_ID = "architecture.scaffold-template-locality"
MARKDOWN_LOCALITY_REFERENCE_COVERAGE_RULE_ID = (
    "architecture.markdown-locality-reference-coverage"
)

_DISALLOWED_IMPORTS: dict[str, tuple[str, ...]] = {
    "engineeringagent.specs": (
        "engineeringagent.cli",
        "engineeringagent.loop",
        "engineeringagent.loop_runtime",
        "engineeringagent.gates",
        "engineeringagent.validator",
    ),
    "engineeringagent.validator": (
        "engineeringagent.cli",
        "engineeringagent.loop",
        "engineeringagent.loop_runtime",
    ),
    "engineeringagent.gates": (
        "engineeringagent.cli",
        "engineeringagent.loop",
        "engineeringagent.loop_runtime",
    ),
    "engineeringagent.cli": ("engineeringagent.loop_runtime",),
    "engineeringagent.loop": ("engineeringagent.cli",),
}

_BLOCKED_SUBPROCESS_CALLS = {
    "run",
    "Popen",
    "call",
    "check_call",
    "check_output",
}
_SOURCE_PACKAGE_ROOT = Path("src/engineeringagent")
_SUBPROCESS_ALLOWLIST_MODULES = (
    "engineeringagent.commit_messages",
    "engineeringagent.fitness.adapters",
    "engineeringagent.gates",
    "engineeringagent.git.client",
    "engineeringagent.opencode.client",
)
_SUBPROCESS_ALLOWLIST = {
    _SOURCE_PACKAGE_ROOT
    / f"{module.removeprefix('engineeringagent.').replace('.', '/')}.py"
    for module in _SUBPROCESS_ALLOWLIST_MODULES
}

_PROMPT_TEMPLATE_ROOT = _SOURCE_PACKAGE_ROOT / "prompts" / "templates"
_REQUIRED_PROMPT_TEMPLATES = (
    "loop_selector.md",
    "loop_implementation.md",
    "loop_retry_feedback.md",
)
_PROMPT_ALLOWED_ROOT = _SOURCE_PACKAGE_ROOT / "prompts"
_CANONICAL_PROMPT_BUILDERS = {
    "_build_selector_prompt",
    "build_ralph_opencode_prompt",
}
_PROMPT_CANARY_TOKENS = (
    ("choose", "the", "next", "feature", "spec"),
    ("exactly", "one", "feature", "path"),
    ("read", "and", "use", "this", "feature", "spec", "from", "disk"),
    ("previous", "retry", "feedback", "is", "available"),
)
_PROMPT_LOCALITY_REMEDIATION = (
    "move canonical prompt text and template reads into "
    "src/engineeringagent/prompts/templates and approved modules under "
    "src/engineeringagent/prompts/."
)

_SCAFFOLD_TEMPLATE_ROOT = _SOURCE_PACKAGE_ROOT / "scaffold_templates"
_REQUIRED_SCAFFOLD_TEMPLATES = (
    "AGENTS.md",
    "precommit.core.yaml",
    "precommit.python_uv.yaml",
    "reference.docs-architecture-llms.md",
    "reference.workflow-llms.md",
)
_SCAFFOLD_TEMPLATE_ALLOWED_ROOT = _SOURCE_PACKAGE_ROOT / "scaffold_templates"
_SCAFFOLD_TEMPLATE_CANARY_TOKENS = (
    ("agent", "operating", "guide", "for", "this", "repository"),
    ("keep", "this", "file", "concise"),
    ("first", "window", "boot", "sequence"),
    ("audience", "split"),
)
_SCAFFOLD_TEMPLATE_LOCALITY_REMEDIATION = (
    "move scaffold template content into "
    "src/engineeringagent/scaffold_templates and keep scaffold content reads "
    "inside engineeringagent.init_scaffold."
)

_MARKDOWN_ALLOWED_ROOTS = (
    Path("docs"),
    _SOURCE_PACKAGE_ROOT / "prompts",
    _SOURCE_PACKAGE_ROOT / "scaffold_templates",
)
_MARKDOWN_ALLOWED_ROOT_FILES = (
    Path("README.md"),
    Path("AGENTS.md"),
)
_MARKDOWN_REFERENCE_SCAN_SUFFIXES = {
    ".cfg",
    ".ini",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
_MARKDOWN_IGNORE_DIRECTORIES = {
    ".git",
    ".opencode",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
    "output",
    "tmp",
}
_MARKDOWN_LOCALITY_REMEDIATION = (
    "move markdown files under docs/, src/engineeringagent/prompts/, or "
    "src/engineeringagent/scaffold_templates/; only repository-root README.md "
    "and AGENTS.md are exempt from locality restrictions."
)


def _iter_markdown_files(project_root: Path) -> list[Path]:
    markdown_paths: list[Path] = []
    for path in sorted(project_root.rglob("*.md")):
        relative = path.relative_to(project_root)
        if _path_contains_ignored_directory(relative):
            continue
        markdown_paths.append(relative)
    return markdown_paths


def _path_contains_ignored_directory(relative_path: Path) -> bool:
    return any(part in _MARKDOWN_IGNORE_DIRECTORIES for part in relative_path.parts)


def _is_allowed_markdown_locality(relative_path: Path) -> bool:
    if relative_path in _MARKDOWN_ALLOWED_ROOT_FILES:
        return True
    return any(
        relative_path == allowed_root or allowed_root in relative_path.parents
        for allowed_root in _MARKDOWN_ALLOWED_ROOTS
    )


def _is_outside_docs(relative_path: Path) -> bool:
    return relative_path != Path("docs") and Path("docs") not in relative_path.parents


def evaluate_markdown_locality_reference_coverage(
    project_root: Path,
) -> dict[str, object]:
    """Enforce markdown locality and non-doc reference coverage contracts."""
    violations: list[str] = []
    markdown_paths = _iter_markdown_files(project_root)
    for relative_path in markdown_paths:
        if _is_allowed_markdown_locality(relative_path):
            continue
        violations.append(
            f"{relative_path}:1 markdown file is outside approved locality roots; "
            f"{_MARKDOWN_LOCALITY_REMEDIATION}"
        )

    references_by_markdown = _collect_markdown_references(project_root, markdown_paths)
    for relative_path in markdown_paths:
        if not _is_outside_docs(relative_path):
            continue
        if references_by_markdown.get(relative_path):
            continue
        violations.append(
            f"{relative_path}:1 markdown file outside docs/ has no in-repo non-self "
            "reference; add at least one deterministic path reference from another "
            "repository file."
        )

    return {
        "contract_version": CONTRACT_VERSION,
        "rule_id": MARKDOWN_LOCALITY_REFERENCE_COVERAGE_RULE_ID,
        "status": RuleStatus.PASS if not violations else RuleStatus.FAIL,
        "severity": RuleSeverity.ERROR,
        "summary": (
            "Markdown locality and reference coverage constraints satisfied."
            if not violations
            else (
                f"Detected {len(violations)} markdown locality/reference violation(s)."
            )
        ),
        "violations": sorted(violations),
    }


def _collect_markdown_references(
    project_root: Path,
    markdown_paths: list[Path],
) -> dict[Path, list[str]]:
    references: dict[Path, list[str]] = {path: [] for path in markdown_paths}
    patterns_by_path = {
        path: _markdown_reference_patterns(path) for path in markdown_paths
    }

    for scan_relative in _iter_reference_scan_files(project_root):
        scan_path = project_root / scan_relative
        try:
            content = scan_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        for line_number, line in enumerate(content.splitlines(), start=1):
            for markdown_path, patterns in patterns_by_path.items():
                if scan_relative == markdown_path:
                    continue
                if any(pattern in line for pattern in patterns):
                    references[markdown_path].append(f"{scan_relative}:{line_number}")

    return references


def _iter_reference_scan_files(project_root: Path) -> list[Path]:
    scan_paths: list[Path] = []
    for path in sorted(project_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(project_root)
        if _path_contains_ignored_directory(relative):
            continue
        if path.suffix not in _MARKDOWN_REFERENCE_SCAN_SUFFIXES:
            continue
        scan_paths.append(relative)
    return scan_paths


def _markdown_reference_patterns(markdown_path: Path) -> tuple[str, ...]:
    posix = markdown_path.as_posix()
    return (
        posix,
        f"./{posix}",
    )


def evaluate_dependency_directionality(project_root: Path) -> dict[str, object]:
    """Evaluate import directionality constraints for core modules."""
    violations: list[str] = []
    for module_name, blocked_modules in sorted(_DISALLOWED_IMPORTS.items()):
        module_path = _module_path(project_root, module_name)
        if not module_path.exists():
            violations.append(f"missing module for directionality check: {module_name}")
            continue

        for imported in sorted(_collect_imports(module_path, module_name)):
            for blocked in blocked_modules:
                if imported == blocked or imported.startswith(f"{blocked}."):
                    violations.append(
                        f"{module_name} imports blocked dependency {imported}"
                    )

    return {
        "contract_version": CONTRACT_VERSION,
        "rule_id": DEPENDENCY_DIRECTIONALITY_RULE_ID,
        "status": RuleStatus.PASS if not violations else RuleStatus.FAIL,
        "severity": RuleSeverity.ERROR,
        "summary": (
            "Dependency directionality constraints satisfied."
            if not violations
            else f"Detected {len(violations)} dependency directionality violation(s)."
        ),
        "violations": sorted(violations),
    }


def evaluate_loop_subprocess_boundary(project_root: Path) -> dict[str, object]:
    """Reject subprocess calls outside strict command-boundary allowlist."""
    violations: list[str] = []
    source_root = project_root / _SOURCE_PACKAGE_ROOT
    if not source_root.exists():
        violations.append(f"missing source package root: {_SOURCE_PACKAGE_ROOT}")
    else:
        for file_path in sorted(source_root.rglob("*.py")):
            relative = file_path.relative_to(project_root)
            if relative in _SUBPROCESS_ALLOWLIST:
                continue
            violations.extend(_subprocess_call_violations(file_path, project_root))

    return {
        "contract_version": CONTRACT_VERSION,
        "rule_id": LOOP_SUBPROCESS_BOUNDARY_RULE_ID,
        "status": RuleStatus.PASS if not violations else RuleStatus.FAIL,
        "severity": RuleSeverity.ERROR,
        "summary": (
            "Subprocess boundary allowlist constraints satisfied."
            if not violations
            else (
                "Detected "
                f"{len(violations)} subprocess invocation(s) outside allowlisted modules."
            )
        ),
        "violations": sorted(violations),
    }


def evaluate_prompt_locality(project_root: Path) -> dict[str, object]:
    """Enforce canonical prompt locality to approved prompt modules/templates."""
    violations = _prompt_template_integrity_violations(project_root)
    violations.extend(_prompt_source_locality_violations(project_root))

    return {
        "contract_version": CONTRACT_VERSION,
        "rule_id": PROMPT_LOCALITY_RULE_ID,
        "status": RuleStatus.PASS if not violations else RuleStatus.FAIL,
        "severity": RuleSeverity.ERROR,
        "summary": (
            "Prompt locality constraints satisfied."
            if not violations
            else f"Detected {len(violations)} prompt locality violation(s)."
        ),
        "violations": sorted(violations),
    }


def evaluate_scaffold_template_locality(project_root: Path) -> dict[str, object]:
    """Enforce scaffold template locality to file-based assets on disk."""
    violations = _scaffold_template_integrity_violations(project_root)
    violations.extend(_scaffold_template_source_locality_violations(project_root))

    return {
        "contract_version": CONTRACT_VERSION,
        "rule_id": SCAFFOLD_TEMPLATE_LOCALITY_RULE_ID,
        "status": RuleStatus.PASS if not violations else RuleStatus.FAIL,
        "severity": RuleSeverity.ERROR,
        "summary": (
            "Scaffold template locality constraints satisfied."
            if not violations
            else f"Detected {len(violations)} scaffold template locality violation(s)."
        ),
        "violations": sorted(violations),
    }


def _module_path(project_root: Path, module_name: str) -> Path:
    _, _, suffix = module_name.partition("engineeringagent.")
    return project_root / "src" / "engineeringagent" / f"{suffix.replace('.', '/')}.py"


def _scaffold_template_integrity_violations(project_root: Path) -> list[str]:
    template_root = project_root / _SCAFFOLD_TEMPLATE_ROOT
    violations: list[str] = []
    if not template_root.exists() or not template_root.is_dir():
        violations.append(
            "src/engineeringagent/scaffold_templates:1 missing scaffold template "
            f"directory; {_SCAFFOLD_TEMPLATE_LOCALITY_REMEDIATION}"
        )
        return violations

    for template_name in _REQUIRED_SCAFFOLD_TEMPLATES:
        template_path = template_root / template_name
        relative = template_path.relative_to(project_root)
        if not template_path.exists() or not template_path.is_file():
            violations.append(
                f"{relative}:1 missing required scaffold template "
                f"'{template_name}'; {_SCAFFOLD_TEMPLATE_LOCALITY_REMEDIATION}"
            )
            continue
        if not template_path.read_text(encoding="utf-8").strip():
            violations.append(
                f"{relative}:1 required scaffold template '{template_name}' is empty; "
                f"{_SCAFFOLD_TEMPLATE_LOCALITY_REMEDIATION}"
            )

    return violations


def _scaffold_template_source_locality_violations(project_root: Path) -> list[str]:
    source_root = project_root / _SOURCE_PACKAGE_ROOT
    violations: list[str] = []
    if not source_root.exists():
        violations.append(
            f"{_SOURCE_PACKAGE_ROOT}:1 missing source package root; "
            f"{_SCAFFOLD_TEMPLATE_LOCALITY_REMEDIATION}"
        )
        return violations

    canaries = tuple(" ".join(tokens) for tokens in _SCAFFOLD_TEMPLATE_CANARY_TOKENS)
    normalized_canaries = {
        canary: _normalize_for_canary_matching(canary) for canary in canaries
    }

    for file_path in sorted(source_root.rglob("*.py")):
        relative = file_path.relative_to(project_root)
        if _is_scaffold_template_allowed_path(relative):
            continue

        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for line, segment in _iter_literal_string_segments(tree):
            normalized_segment = _normalize_for_canary_matching(segment)
            if not normalized_segment:
                continue
            for canary, normalized_canary in normalized_canaries.items():
                if normalized_canary and normalized_canary in normalized_segment:
                    violations.append(
                        f"{relative}:{line} contains scaffold template canary "
                        f"'{canary}' outside scaffold template assets; "
                        f"{_SCAFFOLD_TEMPLATE_LOCALITY_REMEDIATION}"
                    )

    return violations


def _is_scaffold_template_allowed_path(relative_path: Path) -> bool:
    return (
        relative_path == _SCAFFOLD_TEMPLATE_ALLOWED_ROOT
        or _SCAFFOLD_TEMPLATE_ALLOWED_ROOT in relative_path.parents
    )


def _prompt_template_integrity_violations(project_root: Path) -> list[str]:
    template_root = project_root / _PROMPT_TEMPLATE_ROOT
    violations: list[str] = []
    if not template_root.exists() or not template_root.is_dir():
        violations.append(
            "src/engineeringagent/prompts/templates:1 missing prompt template "
            f"directory; {_PROMPT_LOCALITY_REMEDIATION}"
        )
        return violations

    for template_name in _REQUIRED_PROMPT_TEMPLATES:
        template_path = template_root / template_name
        relative = template_path.relative_to(project_root)
        if not template_path.exists() or not template_path.is_file():
            violations.append(
                f"{relative}:1 missing required prompt template '{template_name}'; "
                f"{_PROMPT_LOCALITY_REMEDIATION}"
            )
            continue
        if not template_path.read_text(encoding="utf-8").strip():
            violations.append(
                f"{relative}:1 required prompt template '{template_name}' is empty; "
                f"{_PROMPT_LOCALITY_REMEDIATION}"
            )

    return violations


def _prompt_source_locality_violations(project_root: Path) -> list[str]:
    source_root = project_root / _SOURCE_PACKAGE_ROOT
    violations: list[str] = []
    if not source_root.exists():
        violations.append(
            f"{_SOURCE_PACKAGE_ROOT}:1 missing source package root; "
            f"{_PROMPT_LOCALITY_REMEDIATION}"
        )
        return violations

    for file_path in sorted(source_root.rglob("*.py")):
        relative = file_path.relative_to(project_root)
        if _is_prompt_allowed_path(relative):
            continue
        violations.extend(_prompt_boundary_violations(file_path, project_root))

    return violations


def _is_prompt_allowed_path(relative_path: Path) -> bool:
    return (
        relative_path == _PROMPT_ALLOWED_ROOT
        or _PROMPT_ALLOWED_ROOT in relative_path.parents
    )


def _prompt_boundary_violations(file_path: Path, project_root: Path) -> list[str]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    relative = file_path.relative_to(project_root)
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in _CANONICAL_PROMPT_BUILDERS:
                violations.append(
                    f"{relative}:{node.lineno} defines canonical prompt builder "
                    f"'{node.name}' outside approved prompt modules; "
                    f"{_PROMPT_LOCALITY_REMEDIATION}"
                )
            continue

        if isinstance(node, ast.Call) and _call_targets_template_markdown(node):
            violations.append(
                f"{relative}:{node.lineno} reads prompt template markdown outside "
                f"approved prompt modules; {_PROMPT_LOCALITY_REMEDIATION}"
            )

    violations.extend(_prompt_canary_violations(tree, relative))
    return violations


def _call_targets_template_markdown(node: ast.Call) -> bool:
    func = node.func
    is_read_text = isinstance(func, ast.Attribute) and func.attr == "read_text"
    is_open = isinstance(func, ast.Name) and func.id == "open"
    if not is_read_text and not is_open:
        return False

    for value in _string_literals_from_node(node):
        normalized = value.lower()
        if "prompts/templates" in normalized and ".md" in normalized:
            return True
        if "templates" in normalized and normalized.endswith(".md"):
            return True
    return False


def _prompt_canary_violations(tree: ast.AST, relative: Path) -> list[str]:
    canaries = tuple(" ".join(tokens) for tokens in _PROMPT_CANARY_TOKENS)
    normalized_canaries = {
        canary: _normalize_for_canary_matching(canary) for canary in canaries
    }
    violations: list[str] = []

    for line, segment in _iter_literal_string_segments(tree):
        normalized_segment = _normalize_for_canary_matching(segment)
        if not normalized_segment:
            continue
        for canary, normalized_canary in normalized_canaries.items():
            if normalized_canary and normalized_canary in normalized_segment:
                violations.append(
                    f"{relative}:{line} contains canonical prompt canary '{canary}' "
                    f"outside approved prompt modules; "
                    f"{_PROMPT_LOCALITY_REMEDIATION}"
                )

    return violations


def _iter_literal_string_segments(tree: ast.AST) -> list[tuple[int, str]]:
    segments: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            line = getattr(node, "lineno", 1)
            segments.append((line, node.value))
            continue
        if isinstance(node, ast.JoinedStr):
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    line = getattr(value, "lineno", getattr(node, "lineno", 1))
                    segments.append((line, value.value))
    return segments


def _string_literals_from_node(node: ast.AST) -> list[str]:
    values: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            values.append(child.value)
    return values


def _normalize_for_canary_matching(value: str) -> str:
    lowered = value.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(normalized.split())


def _collect_imports(path: Path, module_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_import_from_base(module_name, node)
            if base is None:
                continue
            imports.add(base)
            for alias in node.names:
                imports.add(f"{base}.{alias.name}")
    return imports


def _resolve_import_from_base(module_name: str, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module

    module_parts = module_name.split(".")
    if node.level > len(module_parts):
        return None

    base_parts = module_parts[: -node.level]
    if node.module:
        base_parts.extend(node.module.split("."))
    if not base_parts:
        return None
    return ".".join(base_parts)


def _subprocess_call_violations(file_path: Path, project_root: Path) -> list[str]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    relative = file_path.relative_to(project_root)
    module_aliases, imported_call_aliases = _collect_subprocess_aliases(tree)
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        violation = _subprocess_call_violation(
            node,
            relative=relative,
            module_aliases=module_aliases,
            imported_call_aliases=imported_call_aliases,
        )
        if violation is not None:
            violations.append(violation)
    return violations


def _collect_subprocess_aliases(tree: ast.AST) -> tuple[set[str], set[str]]:
    module_aliases: set[str] = set()
    imported_call_aliases: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name != "subprocess":
                    continue
                module_aliases.add(alias.asname or alias.name)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level != 0 or node.module != "subprocess":
            continue
        for alias in node.names:
            if alias.name not in _BLOCKED_SUBPROCESS_CALLS:
                continue
            imported_call_aliases.add(alias.asname or alias.name)
    return module_aliases, imported_call_aliases


def _subprocess_call_violation(
    node: ast.Call,
    *,
    relative: Path,
    module_aliases: set[str],
    imported_call_aliases: set[str],
) -> str | None:
    func = node.func

    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id in module_aliases
        and func.attr in _BLOCKED_SUBPROCESS_CALLS
    ):
        return f"{relative}:{node.lineno} uses {func.value.id}.{func.attr}; move this command call to an approved client/adapter module"

    if isinstance(func, ast.Name) and func.id in imported_call_aliases:
        return f"{relative}:{node.lineno} uses {func.id}(...) from subprocess; move this command call to an approved client/adapter module"

    return None
