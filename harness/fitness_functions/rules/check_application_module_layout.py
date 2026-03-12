from __future__ import annotations

from pathlib import Path

from engineeringagent.checks import emit_fitness_result
from engineeringagent.adapters.quality.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.application-module-layout"
PROJECT_ROOT = Path(".")
APPLICATION_ROOT = PROJECT_ROOT / "src" / "engineeringagent" / "application"
ALLOWED_ROOT_MODULES = frozenset(
    {
        "__init__.py",
        "checks_service.py",
        "feature_iteration_service.py",
        "guidance_service.py",
        "prompt_builder.py",
        "run_loop_service.py",
        "validation_service.py",
    }
)
WORKSPACE_ROOT = APPLICATION_ROOT / "workspace"
ALLOWED_WORKSPACE_MODULES = frozenset(
    {
        "__init__.py",
        "init_service.py",
        "recovery_service.py",
    }
)


def _application_module_layout_violations() -> list[str]:
    if not APPLICATION_ROOT.is_dir():
        return []

    violations: list[str] = []
    for path in sorted(APPLICATION_ROOT.glob("*.py")):
        if path.name in ALLOWED_ROOT_MODULES:
            continue
        rel_path = path.relative_to(PROJECT_ROOT).as_posix()
        violations.append(
            f"{rel_path}: application root may only contain workflow-service modules; "
            "keep only documented workflow-service modules at the application root; "
            "move helpers into an explicit subpackage such as "
            "engineeringagent.application.feature_iteration, or delete the legacy module"
        )
    if WORKSPACE_ROOT.exists():
        for path in sorted(WORKSPACE_ROOT.rglob("*.py")):
            if path.name in ALLOWED_WORKSPACE_MODULES:
                continue
            rel_path = path.relative_to(PROJECT_ROOT).as_posix()
            violations.append(
                f"{rel_path}: workspace application package may only contain the "
                "documented workspace workflow-service modules; keep "
                "engineeringagent.application.workspace limited to init_service.py, "
                "recovery_service.py, and __init__.py"
            )
    return violations


def main() -> int:
    """Emit the application-module-layout fitness result."""
    violations = _application_module_layout_violations()
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "engineeringagent.application root only contains workflow-service modules."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} application module-layout violation(s)."
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
