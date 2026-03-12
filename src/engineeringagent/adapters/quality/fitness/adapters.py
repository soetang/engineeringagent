from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .contracts import CONTRACT_VERSION, FitnessRuleResult, RuleAdapter, RuleStatus
from .registry import FitnessRuleDefinition


def execute_rule_definition(
    definition: FitnessRuleDefinition,
    project_root: Path,
) -> FitnessRuleResult:
    """Execute one rule definition through its configured adapter."""
    if definition.metadata.side_effect_free is not True:
        return _error_result(
            definition,
            "Rule metadata must declare side_effect_free=true.",
        )

    try:
        payload = _adapter_payload(definition, project_root)
        return _normalize_result(definition, payload)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return _error_result(
            definition,
            f"Adapter execution failed: {exc}",
        )


def _adapter_payload(definition: FitnessRuleDefinition, project_root: Path) -> Any:
    if definition.metadata.adapter == RuleAdapter.COMMAND:
        return _run_command_adapter(definition, project_root)
    if definition.metadata.adapter == RuleAdapter.PYTHON:
        return _run_python_adapter(definition, project_root)
    raise ValueError(f"unsupported rule adapter: {definition.metadata.adapter}")


def _run_command_adapter(
    definition: FitnessRuleDefinition, project_root: Path
) -> dict[str, Any]:
    command = definition.command
    if not command:
        raise ValueError("command adapter requires a non-empty command")
    command_argv = list(command)
    if definition.config_file is not None:
        command_argv.extend(("--config-file", str(definition.config_file)))

    env = os.environ.copy()
    if definition.env:
        env.update(definition.env)

    try:
        proc = subprocess.run(
            command_argv,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=definition.timeout_seconds,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError(
            f"command timed out after {definition.timeout_seconds} second(s): {command_argv}"
        ) from exc

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        message = f"command exited non-zero ({proc.returncode})"
        if stderr:
            message = f"{message}: {stderr}"
        raise ValueError(message)

    stdout = (proc.stdout or "").strip()
    if not stdout:
        raise ValueError("command produced empty stdout; expected JSON result envelope")

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("command stdout is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("command result envelope must be a JSON object")
    return payload


def _run_python_adapter(definition: FitnessRuleDefinition, project_root: Path) -> Any:
    runner = definition.python_callable
    if runner is None:
        raise ValueError("python adapter requires python_callable")
    return runner(project_root)


def _normalize_result(
    definition: FitnessRuleDefinition,
    payload: FitnessRuleResult | dict[str, Any],
) -> FitnessRuleResult:
    validated = FitnessRuleResult.model_validate(payload)
    if validated.rule_id != definition.metadata.rule_id:
        raise ValueError(
            "result envelope rule_id does not match rule definition: "
            f"{validated.rule_id} != {definition.metadata.rule_id}"
        )
    if validated.severity != definition.metadata.severity:
        raise ValueError(
            "result envelope severity does not match rule definition: "
            f"{validated.severity} != {definition.metadata.severity}"
        )
    return validated


def _error_result(
    definition: FitnessRuleDefinition,
    summary: str,
) -> FitnessRuleResult:
    return FitnessRuleResult(
        contract_version=CONTRACT_VERSION,
        rule_id=definition.metadata.rule_id,
        status=RuleStatus.ERROR,
        severity=definition.metadata.severity,
        summary=summary,
        violations=[],
    )
