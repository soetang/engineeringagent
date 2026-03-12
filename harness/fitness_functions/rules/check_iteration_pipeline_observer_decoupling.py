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


RULE_ID = "architecture.iteration-pipeline-observer-decoupling"
_ITERATION_PIPELINE_PATH = Path(
    "src/engineeringagent/application/feature_iteration_runtime/pipeline.py"
)
_TELEMETRY_SINKS = {"write_iteration_telemetry"}
_CONSOLE_SINKS = {"print", "print_summary", "print_line"}
_ALL_BANNED_SINKS = _TELEMETRY_SINKS | _CONSOLE_SINKS
_REMEDIATION = (
    "move telemetry/console side effects out of iteration pipeline and publish an "
    "IterationReport to observers instead"
)


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _sink_kind(sink_name: str) -> str:
    if sink_name in _TELEMETRY_SINKS:
        return "telemetry"
    return "console output"


def _observer_decoupling_violations(project_root: Path) -> list[str]:
    module_path = project_root / _ITERATION_PIPELINE_PATH
    if not module_path.exists() or not module_path.is_file():
        return [
            f"{_ITERATION_PIPELINE_PATH}:1 missing iteration pipeline module; {_REMEDIATION}"
        ]

    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    relative = module_path.relative_to(project_root)
    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        sink_name = _call_name(node)
        if sink_name not in _ALL_BANNED_SINKS:
            continue
        violations.append(
            (
                node.lineno,
                f"{relative}:{node.lineno} invokes {_sink_kind(sink_name)} sink "
                f"'{sink_name}' inside iteration pipeline; {_REMEDIATION}",
            )
        )

    return [violation for _, violation in sorted(violations)]


def main() -> int:
    """Run iteration pipeline observer-decoupling fitness rule."""
    violations = _observer_decoupling_violations(Path("."))
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Iteration pipeline observer-decoupling constraints satisfied."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} iteration pipeline side-effect violation(s)."
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
