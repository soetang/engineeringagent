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


RULE_ID = "architecture.legacy-agents-submodule-imports"
PROJECT_ROOT = Path(".")
SRC_ROOT = PROJECT_ROOT / "src" / "engineeringagent"
LEGACY_HELPERS_MODULE = "engineeringagent.agents.helpers"
LEGACY_CONTRACTS_MODULE = "engineeringagent.agents.contracts"
ALLOWED_PATHS = {
    SRC_ROOT / "agents" / "__init__.py",
    SRC_ROOT / "agents" / "helpers.py",
    SRC_ROOT / "agents" / "contracts.py",
}


def _iter_python_files() -> tuple[Path, ...]:
    if not SRC_ROOT.is_dir():
        return ()
    return tuple(
        sorted(
            path
            for path in SRC_ROOT.rglob("*.py")
            if "__pycache__" not in path.parts and path not in ALLOWED_PATHS
        )
    )


def _parse_module(path: Path) -> ast.AST:
    relative_path = path.relative_to(PROJECT_ROOT).as_posix()
    source = path.read_text(encoding="utf-8")
    return ast.parse(source, filename=relative_path)


def _collect_violations() -> list[str]:
    violations: list[str] = []
    for path in _iter_python_files():
        relative_path = path.relative_to(PROJECT_ROOT).as_posix()
        tree = _parse_module(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module in {LEGACY_HELPERS_MODULE, LEGACY_CONTRACTS_MODULE}:
                    violations.append(
                        f"{relative_path}:{node.lineno} import adapter-owned agent "
                        f"support from engineeringagent.adapters.agents instead of {module}"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in {LEGACY_HELPERS_MODULE, LEGACY_CONTRACTS_MODULE}:
                        violations.append(
                            f"{relative_path}:{node.lineno} import adapter-owned agent "
                            "support from engineeringagent.adapters.agents instead of "
                            f"{alias.name}"
                        )
    return sorted(set(violations))


def main() -> int:
    """Emit the legacy agent-submodule import fitness result."""
    violations = _collect_violations()
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "engineeringagent source imports adapter-owned agent support directly."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} legacy agent-submodule import violation(s)."
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
