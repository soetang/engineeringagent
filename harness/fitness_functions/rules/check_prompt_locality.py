from __future__ import annotations

import ast
import re
from pathlib import Path

from engineeringagent.checks import emit_fitness_result
from engineeringagent.adapters.quality.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.prompt-locality"

_SOURCE_PACKAGE_ROOT = Path("src/engineeringagent")
_PROMPT_DEFINITION_ROOT = Path("harness/prompts")
_REQUIRED_PROMPT_DEFINITIONS = (
    "implementation_default.py",
)
_PROMPT_ALLOWED_ROOT = _PROMPT_DEFINITION_ROOT
_CANONICAL_PROMPT_BUILDERS = {
    "build_ralph_opencode_prompt",
}
_PROMPT_CANARY_TOKENS = (
    ("read", "and", "use", "this", "feature", "spec", "from", "disk"),
    ("previous", "feedback", "is", "available"),
)
_PROMPT_LOCALITY_REMEDIATION = (
    "move canonical prompt text into harness/prompts and keep prompt-building "
    "logic free of inlined canonical prompt text outside that directory."
)


def _prompt_definition_integrity_violations(project_root: Path) -> list[str]:
    definitions_root = project_root / _PROMPT_DEFINITION_ROOT
    violations: list[str] = []
    if not definitions_root.exists() or not definitions_root.is_dir():
        violations.append(
            "harness/prompts:1 missing prompt definition "
            f"directory; {_PROMPT_LOCALITY_REMEDIATION}"
        )
        return violations

    for definition_name in _REQUIRED_PROMPT_DEFINITIONS:
        definition_path = definitions_root / definition_name
        relative = definition_path.relative_to(project_root)
        if not definition_path.exists() or not definition_path.is_file():
            violations.append(
                f"{relative}:1 missing required prompt definition '{definition_name}'; "
                f"{_PROMPT_LOCALITY_REMEDIATION}"
            )
            continue
        if not definition_path.read_text(encoding="utf-8").strip():
            violations.append(
                f"{relative}:1 required prompt definition '{definition_name}' is empty; "
                f"{_PROMPT_LOCALITY_REMEDIATION}"
            )

    return violations


def _is_prompt_allowed_path(relative_path: Path) -> bool:
    return (
        relative_path == _PROMPT_ALLOWED_ROOT
        or _PROMPT_ALLOWED_ROOT in relative_path.parents
    )


def _string_literals_from_node(node: ast.AST) -> list[str]:
    values: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            values.append(child.value)
    return values


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


def _normalize_for_canary_matching(value: str) -> str:
    lowered = value.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(normalized.split())


def _call_targets_template_markdown(node: ast.Call) -> bool:
    func = node.func
    is_read_text = isinstance(func, ast.Attribute) and func.attr == "read_text"
    is_open = isinstance(func, ast.Name) and func.id == "open"
    if not is_read_text and not is_open:
        return False

    for value in _string_literals_from_node(node):
        normalized = value.lower()
        if "prompts/definitions" in normalized and ".py" in normalized:
            return True
        if "harness/prompts" in normalized and ".py" in normalized:
            return True
        if "definitions" in normalized and normalized.endswith(".py"):
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
                f"{relative}:{node.lineno} reads prompt definition source outside "
                f"approved prompt modules; {_PROMPT_LOCALITY_REMEDIATION}"
            )

    violations.extend(_prompt_canary_violations(tree, relative))
    return violations


def _prompt_source_locality_violations(project_root: Path) -> list[str]:
    violations: list[str] = []
    for scan_root in (_SOURCE_PACKAGE_ROOT, Path("harness")):
        root_path = project_root / scan_root
        if not root_path.exists():
            continue
        for file_path in sorted(root_path.rglob("*.py")):
            relative = file_path.relative_to(project_root)
            if _is_prompt_allowed_path(relative):
                continue
            violations.extend(_prompt_boundary_violations(file_path, project_root))

    return violations


def _prompt_locality_violations(project_root: Path) -> list[str]:
    violations = _prompt_definition_integrity_violations(project_root)
    violations.extend(_prompt_source_locality_violations(project_root))
    return sorted(violations)


def main() -> int:
    """Run the prompt locality fitness rule."""
    violations = _prompt_locality_violations(Path("."))
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Prompt locality constraints satisfied."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} prompt locality violation(s)."
    )

    emit_fitness_result(
        FitnessRuleResult(
            contract_version=CONTRACT_VERSION,
            rule_id=RULE_ID,
            status=status,
            severity=RuleSeverity.ERROR,
            summary=summary,
            violations=violations,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
