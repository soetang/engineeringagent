from __future__ import annotations

import ast
from pathlib import Path

from engineeringagent.checks import emit_fitness_result
from engineeringagent.adapters.quality.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.shared-kernel-locality"
PROJECT_ROOT = Path(".")
SHARED_ENUMS = PROJECT_ROOT / "src/engineeringagent/domain/shared/enums.py"
SHARED_IDS = PROJECT_ROOT / "src/engineeringagent/domain/shared/ids.py"
LOCAL_DEFINITION_TARGETS = {
    "src/engineeringagent/specs.py": {
        "class": {"FeatureStatus", "PlanningTier"},
        "assign": {"FeatureId"},
    },
    "src/engineeringagent/domain/specification/feature_specification.py": {
        "class": {"FeatureStatus", "PlanningTier"},
        "assign": {"FeatureId", "PhaseId"},
    },
    "src/engineeringagent/domain/quality/checks.py": {
        "class": {"HarnessCheckPhase", "CheckPhase"},
        "assign": set(),
    },
}


def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())


def _assigned_names(node: ast.Assign | ast.AnnAssign) -> set[str]:
    names: set[str] = set()
    targets = [node.target] if isinstance(node, ast.AnnAssign) else list(node.targets)
    for target in targets:
        if isinstance(target, ast.Name):
            names.add(target.id)
    return names


def _shared_file_violations(path: Path, *, required_names: set[str]) -> list[str]:
    if not path.is_file():
        return [f"{path.as_posix()}:1 missing shared-kernel module"]

    tree = _parse(path)
    exported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            exported.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            exported.update(_assigned_names(node))

    violations: list[str] = []
    for name in sorted(required_names - exported):
        violations.append(
            f"{path.as_posix()}:1 missing shared-kernel definition {name}; "
            "define cross-domain shared types under engineeringagent.domain.shared."
        )
    return violations


def _local_redefinition_violations(path: Path, *, forbidden: dict[str, set[str]]) -> list[str]:
    tree = _parse(path)
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name in forbidden["class"]:
            violations.append(
                f"{path.as_posix()}:{node.lineno} redefines shared-kernel type {node.name}; "
                "import it from engineeringagent.domain.shared instead."
            )
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            duplicated = forbidden["assign"] & _assigned_names(node)
            for name in sorted(duplicated):
                violations.append(
                    f"{path.as_posix()}:{getattr(node, 'lineno', 1)} redefines shared-kernel type {name}; "
                    "import it from engineeringagent.domain.shared instead."
                )
    return violations


def main() -> int:
    """Run the shared-kernel locality fitness rule."""
    violations = [
        *_shared_file_violations(
            SHARED_ENUMS,
            required_names={"FeatureStatus", "PlanningTier", "CheckPhase"},
        ),
        *_shared_file_violations(
            SHARED_IDS,
            required_names={"FeatureId", "PhaseId", "CheckId", "TopicId"},
        ),
    ]

    for relpath, forbidden in sorted(LOCAL_DEFINITION_TARGETS.items()):
        path = PROJECT_ROOT / relpath
        if not path.is_file():
            continue
        violations.extend(_local_redefinition_violations(path, forbidden=forbidden))

    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Shared-kernel identifiers and enums are localized under engineeringagent.domain.shared."
        if status == RuleStatus.PASS
        else "Detected cross-domain identifiers or enums defined outside engineeringagent.domain.shared."
    )
    emit_fitness_result(
        FitnessRuleResult(
            contract_version=CONTRACT_VERSION,
            rule_id=RULE_ID,
            status=status,
            severity=RuleSeverity.ERROR,
            summary=summary,
            violations=sorted(violations),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
