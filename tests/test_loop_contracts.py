from __future__ import annotations

import inspect
import json
from inspect import Parameter
from pathlib import Path

import engineeringagent.loop as loop_module
import yaml
from pydantic import BaseModel

from engineeringagent.loop_runtime.models import (
    FeatureIterationInputs,
    IterationTelemetryInputs,
)
from engineeringagent.loop_runtime.telemetry import write_iteration_telemetry


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
    assert issubclass(loop_module.IterationOutcome, BaseModel)


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


def test_iteration_outcome_includes_verification_status() -> None:
    outcome = loop_module.IterationOutcome(
        completed=False,
        result="failed",
        failed_gate="spec_validate",
        next_action="retry_same_feature",
        hook_feedback="verification failed",
        log_path="progress/run-feature-FEAT-040.txt",
    )

    assert outcome.verification_status == "not_run"
    assert outcome.verification_failed_command is None
    assert outcome.reviewer_status == "not_run"
    assert outcome.reviewer_decision is None
    assert outcome.failed_reviewer_id is None


def test_retry_feedback_contract_accepts_verification_failure(tmp_path: Path) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-040.yaml",
        gate_profile="loop_fast",
        implement_command=None,
        opencode_prompt=None,
        skip_implement=False,
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=0.0,
        feature_id="FEAT-040",
        result="failed",
        failed_gate=None,
        next_action="retry_same_feature",
        implement_status="passed",
        gate_status="not_run",
        verification_status="failed:uv run pytest -q",
        verification_failed_command="uv run pytest -q",
        reviewer_status="failed:blocking",
        reviewer_decision="request_changes",
        failed_reviewer_id="security-reviewer",
        implement_output="",
        gate_output="",
        verification_output="E       assert 1 == 2",
        reviewer_output="[reviewer:security-reviewer] mode=blocking decision=request_changes",
        hook_feedback="[verification] uv run pytest -q\nE       assert 1 == 2",
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: None,
    )

    run = json.loads((tmp_path / "progress" / "runs.jsonl").read_text(encoding="utf-8"))
    assert run["verification_status"] == "failed:uv run pytest -q"
    assert run["verification_failed_command"] == "uv run pytest -q"
    assert run["reviewer_status"] == "failed:blocking"
    assert run["reviewer_decision"] == "request_changes"
    assert run["failed_reviewer_id"] == "security-reviewer"

    feature_log = (tmp_path / "progress" / "run-feature-FEAT-040.txt").read_text(
        encoding="utf-8"
    )
    assert (
        "verification=failed:uv run pytest -q failed_command=uv run pytest -q"
        in feature_log
    )
    assert (
        "reviewer=failed:blocking decision=request_changes "
        "failed_reviewer=security-reviewer" in feature_log
    )
    assert "detail=[verification] uv run pytest -q" in feature_log
