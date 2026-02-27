from __future__ import annotations

import ast
from pathlib import Path

from engineeringagent.checks import emit_fitness_result
from engineeringagent.checks.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.repo-validators-boundary"

_ORCHESTRATOR_PATH = Path("src/engineeringagent/checks/validate/repo_validators.py")
_POLICY_MODULE_PATHS = (
    Path("src/engineeringagent/checks/validate/repo_policy_feature_ids.py"),
    Path("src/engineeringagent/checks/validate/repo_policy_docs_map.py"),
    Path("src/engineeringagent/checks/validate/repo_policy_purge_invariant.py"),
)
_REQUIRED_IMPORTS: dict[str, tuple[str, ...]] = {
    "engineeringagent.checks.validate.repo_policy_feature_ids": (
        "append_feature_id_invariant_issues",
    ),
    "engineeringagent.checks.validate.repo_policy_docs_map": (
        "append_agents_docs_map_issues",
    ),
    "engineeringagent.checks.validate.repo_policy_purge_invariant": (
        "append_purge_invariant_issues",
    ),
}
_FORBIDDEN_ORCHESTRATOR_DEFINITIONS = {
    "_collect_feature_id_entries",
    "_feature_id_entry_from_file",
    "_duplicate_base_id_occurrences",
    "_append_duplicate_base_id_messages",
    "_duplicate_base_id_message_active",
    "_duplicate_base_id_message_done_only",
    "_filename_id_token",
    "_normalized_base_id",
    "_format_base_id",
    "_agents_docs_map_section_line",
    "_find_agents_docs_map_section_start",
    "_is_agents_docs_map_header",
    "_docs_map_reference_candidates",
    "_iter_docs_references",
    "_is_glob_reference",
    "_purge_forbidden_needles",
}


def _required_module_violations(project_root: Path) -> list[tuple[int, str]]:
    violations: list[tuple[int, str]] = []
    for module_path in _POLICY_MODULE_PATHS:
        target = project_root / module_path
        if target.is_file():
            continue
        violations.append((1, f"{module_path}:1 missing extracted repo policy module"))
    return violations


def _orchestrator_import_violations(
    *,
    tree: ast.Module,
) -> list[tuple[int, str]]:
    imported: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        imported.setdefault(node.module, set()).update(
            alias.name for alias in node.names if alias.name != "*"
        )

    violations: list[tuple[int, str]] = []
    for module, required_names in sorted(_REQUIRED_IMPORTS.items()):
        available_names = imported.get(module, set())
        for name in required_names:
            if name in available_names:
                continue
            violations.append(
                (
                    1,
                    f"{_ORCHESTRATOR_PATH}:1 missing import {name!r} from {module!r}",
                )
            )
    return violations


def _orchestrator_definition_violations(
    *,
    tree: ast.Module,
    module_path: Path,
) -> list[tuple[int, str]]:
    violations: list[tuple[int, str]] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if node.name not in _FORBIDDEN_ORCHESTRATOR_DEFINITIONS:
            continue
        violations.append(
            (
                node.lineno,
                f"{module_path}:{node.lineno} owns extracted policy definition {node.name!r}",
            )
        )
    return violations


def _collect_violations(project_root: Path) -> list[str]:
    violations: list[tuple[int, str]] = []
    violations.extend(_required_module_violations(project_root))

    module_path = project_root / _ORCHESTRATOR_PATH
    if not module_path.is_file():
        violations.append((1, f"{_ORCHESTRATOR_PATH}:1 missing orchestrator module"))
        return [message for _, message in sorted(violations, key=lambda item: item[1])]

    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    violations.extend(_orchestrator_import_violations(tree=tree))
    violations.extend(
        _orchestrator_definition_violations(
            tree=tree,
            module_path=_ORCHESTRATOR_PATH,
        )
    )
    return [message for _, message in sorted(violations, key=lambda item: (item[0], item[1]))]


def main() -> int:
    """Run repo validators boundary guardrail fitness rule."""
    status = RuleStatus.PASS
    summary = "Repo validators boundary constraints satisfied."
    violations: list[str] = []

    try:
        violations = _collect_violations(Path("."))
        status = RuleStatus.PASS if not violations else RuleStatus.FAIL
        if status == RuleStatus.FAIL:
            summary = f"Detected {len(violations)} repo validators boundary violation(s)."
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        status = RuleStatus.ERROR
        summary = f"Repo validators boundary scan failed: {exc}"

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
