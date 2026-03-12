from __future__ import annotations

import argparse
import ast
from pathlib import Path
from typing import Final

import yaml

from engineeringagent.checks import emit_fitness_result
from engineeringagent.adapters.quality.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.loop-subprocess-boundary"
_SOURCE_PACKAGE_ROOT = Path("src/engineeringagent")
_DEFAULT_POLICY = (
    Path(__file__).resolve().parent.parent
    / "policies"
    / "loop_subprocess_boundary_policy.yaml"
)
_DEFAULT_SUBPROCESS_CALL_NAMES: Final[tuple[str, ...]] = (
    "run",
    "Popen",
    "call",
    "check_call",
    "check_output",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-file", default=str(_DEFAULT_POLICY))
    return parser.parse_args()


def _resolve_config_file(path_value: str) -> Path:
    config_file = Path(path_value)
    if not config_file.is_file():
        raise ValueError(f"policy config not found: {config_file}")
    return config_file


def _require_string_list(payload: dict[str, object], field: str) -> list[str]:
    value = payload.get(field)
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ValueError(f"policy field '{field}' must be a list of strings")
    return value


def _load_policy(config_file: Path) -> tuple[set[str], set[str]]:
    try:
        payload = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"failed to read policy config: {config_file}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"policy config is not valid YAML: {config_file}") from exc

    if not isinstance(payload, dict):
        raise ValueError("policy config must be a mapping")

    allowlisted_modules = _require_string_list(payload, "allowlisted_modules")

    subprocess_call_names = payload.get("subprocess_call_names")
    if subprocess_call_names is None:
        call_names: set[str] = set(_DEFAULT_SUBPROCESS_CALL_NAMES)
    else:
        call_names = set(_require_string_list(payload, "subprocess_call_names"))

    return set(allowlisted_modules), call_names


def _collect_python_files(source_root: Path) -> list[Path]:
    return sorted(path for path in source_root.rglob("*.py") if path.is_file())


def _analyze_subprocess_calls(
    source_text: str,
    *,
    call_names: set[str],
) -> list[tuple[int, str]]:
    tree = ast.parse(source_text)
    subprocess_modules: set[str] = set()
    direct_subprocess_calls: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "subprocess":
                    subprocess_modules.add(alias.asname or alias.name)
        if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            for alias in node.names:
                if alias.name == "*":
                    # Treat wildcard imports as exposing all forbidden subprocess call names.
                    direct_subprocess_calls.update(call_names)
                    continue
                if alias.name in call_names:
                    direct_subprocess_calls.add(alias.asname or alias.name)

    findings: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name):
            module_name = function.value.id
            call_name = function.attr
            if module_name in subprocess_modules and call_name in call_names:
                findings.append((node.lineno, f"{module_name}.{call_name}"))
                continue
        if isinstance(function, ast.Name) and function.id in direct_subprocess_calls:
            imported_name = function.id
            findings.append((node.lineno, f"{imported_name}(...) from subprocess"))

    return findings


def _loop_subprocess_boundary_violations(
    project_root: Path, *, config_file: Path
) -> list[str]:
    source_root = project_root / _SOURCE_PACKAGE_ROOT
    if not source_root.exists():
        return [f"missing source package root: {_SOURCE_PACKAGE_ROOT}"]

    allowlisted_modules, call_names = _load_policy(config_file)
    violations: set[str] = set()

    for source_file in _collect_python_files(source_root):
        relative_path = source_file.relative_to(project_root).as_posix()
        if relative_path in allowlisted_modules:
            continue

        try:
            source_text = source_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"failed reading source file: {relative_path}") from exc

        try:
            findings = _analyze_subprocess_calls(source_text, call_names=call_names)
        except SyntaxError as exc:
            raise ValueError(
                f"failed parsing Python module {relative_path}: {exc.msg} at line {exc.lineno}"
            ) from exc

        for line, expression in findings:
            violations.add(
                f"{relative_path}:{line} uses {expression}; move this command call "
                "to an approved client/adapter module"
            )

    return sorted(violations)


def main() -> int:
    """Run the subprocess boundary fitness rule."""
    args = _parse_args()
    violations: list[str] = []
    status = RuleStatus.PASS
    summary = "Subprocess boundary allowlist constraints satisfied."

    try:
        config_file = _resolve_config_file(args.config_file)
        violations = _loop_subprocess_boundary_violations(
            Path("."),
            config_file=config_file,
        )
        status = RuleStatus.PASS if not violations else RuleStatus.FAIL
        if status == RuleStatus.FAIL:
            summary = (
                "Detected "
                f"{len(violations)} subprocess invocation(s) outside allowlisted modules."
            )
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        status = RuleStatus.ERROR
        summary = f"Native subprocess-boundary scan failed: {exc}"

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
