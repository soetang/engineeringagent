from __future__ import annotations

import dataclasses
import inspect
from inspect import Parameter
from pathlib import Path

import engineeringagent.loop as loop_module
import yaml


def _assert_signature_parameters(
    signature: inspect.Signature,
    expected_names: tuple[str, ...],
    expected_defaults: dict[str, object],
) -> None:
    parameters = signature.parameters
    assert tuple(parameters) == expected_names
    for name in expected_names:
        parameter = parameters[name]
        assert parameter.kind is Parameter.POSITIONAL_OR_KEYWORD
        assert parameter.default == expected_defaults[name]


def test_loop_facade_signatures_remain_stable() -> None:
    _assert_signature_parameters(
        inspect.signature(loop_module.run_implement_step),
        (
            "project_root",
            "feature",
            "feature_path",
            "implement_command",
            "opencode_prompt",
            "skip_implement",
            "hook_feedback",
            "verbose_output",
        ),
        {
            "project_root": Parameter.empty,
            "feature": Parameter.empty,
            "feature_path": Parameter.empty,
            "implement_command": Parameter.empty,
            "opencode_prompt": Parameter.empty,
            "skip_implement": Parameter.empty,
            "hook_feedback": Parameter.empty,
            "verbose_output": Parameter.empty,
        },
    )

    _assert_signature_parameters(
        inspect.signature(loop_module._run_feature_iteration),
        (
            "project_root",
            "feature_path",
            "gate_profile",
            "implement_command",
            "opencode_prompt",
            "skip_implement",
            "attempt",
            "hook_feedback",
            "verbose_output",
        ),
        {
            "project_root": Parameter.empty,
            "feature_path": Parameter.empty,
            "gate_profile": Parameter.empty,
            "implement_command": Parameter.empty,
            "opencode_prompt": Parameter.empty,
            "skip_implement": Parameter.empty,
            "attempt": Parameter.empty,
            "hook_feedback": Parameter.empty,
            "verbose_output": Parameter.empty,
        },
    )

    _assert_signature_parameters(
        inspect.signature(loop_module.run_loop),
        (
            "project_root",
            "feature_paths",
            "gate_profile",
            "implement_command",
            "opencode_prompt",
            "skip_implement",
            "dry_run",
            "run_all",
            "max_iterations",
            "allow_dirty",
            "verbose_output",
        ),
        {
            "project_root": Parameter.empty,
            "feature_paths": Parameter.empty,
            "gate_profile": Parameter.empty,
            "implement_command": Parameter.empty,
            "opencode_prompt": Parameter.empty,
            "skip_implement": Parameter.empty,
            "dry_run": Parameter.empty,
            "run_all": False,
            "max_iterations": 50,
            "allow_dirty": False,
            "verbose_output": False,
        },
    )


def test_iteration_outcome_remains_exposed_on_facade() -> None:
    assert hasattr(loop_module, "IterationOutcome")
    assert dataclasses.is_dataclass(loop_module.IterationOutcome)


def test_loop_monkeypatch_seams_remain_available() -> None:
    seam_symbols = (
        "start_agent",
        "run_permission_probe",
        "run_profile",
        "_require_clean_worktree",
        "_run_opencode_permission_precheck",
        "_choose_feature_with_selector",
        "run_implement_step",
        "_run_feature_iteration",
    )

    for symbol in seam_symbols:
        assert hasattr(loop_module, symbol)


def test_loop_facade_line_budget_rule_configuration() -> None:
    manifest_path = Path("harness/fitness-functions/rules.yaml")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    rules = manifest["rules"]
    line_budget_rules = [
        rule
        for rule in rules
        if isinstance(rule, dict)
        and rule.get("rule_id") == "architecture.loop-facade-line-budget"
    ]

    assert len(line_budget_rules) == 1
    rule = line_budget_rules[0]
    assert rule["adapter"] == "command"
    assert rule["severity"] == "error"
    assert rule["command"] == [
        "uv",
        "run",
        "python",
        "harness/fitness-functions/check_loop_facade_line_budget.py",
    ]
