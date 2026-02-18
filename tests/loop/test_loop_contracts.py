from __future__ import annotations

import inspect
import json
import subprocess
import sys
from inspect import Parameter
from pathlib import Path

import engineeringagent.loop as loop_module
from engineeringagent.progress import paths as progress_paths
import pytest
import yaml
from pydantic import BaseModel, ValidationError

from engineeringagent.loop_runtime.models import (
    FeatureIterationInputs,
    ImplementStepInputs,
    IterationTelemetryInputs,
)
from engineeringagent.loop_runtime.run_context import (
    LoopRun,
    RunConfig,
    RunServices,
    RunState,
)
from engineeringagent.loop_runtime.implement import run_implement_step_from_inputs
import engineeringagent.loop_runtime.implement as implement_module
from engineeringagent.loop_runtime.telemetry import write_iteration_telemetry


def test_progress_paths_contract(tmp_path: Path) -> None:
    assert progress_paths.runs_jsonl_path(tmp_path) == (
        tmp_path / "progress" / "runs.jsonl"
    )
    assert progress_paths.run_feature_log_path(tmp_path, "FEAT-040") == (
        tmp_path / "progress" / "run-feature-FEAT-040.txt"
    )
    assert progress_paths.run_feature_log_reference(tmp_path, "FEAT-040") == (
        "progress/run-feature-FEAT-040.txt"
    )
    assert progress_paths.run_feature_log_reference(tmp_path, "FEAT 040/../../") == (
        "progress/run-feature-FEAT_040.txt"
    )
    assert progress_paths.run_feature_log_reference(tmp_path, "!!!") == (
        "progress/run-feature-unknown-feature.txt"
    )


def test_progress_path_references_fall_back_when_not_repo_relative(
    tmp_path: Path,
    monkeypatch,
) -> None:
    external_progress_root = tmp_path.parent / "external_progress"
    monkeypatch.setattr(
        progress_paths,
        "progress_dir",
        lambda _project_root: external_progress_root,
    )

    runs_path = external_progress_root / progress_paths.RUNS_JSONL_FILENAME
    assert progress_paths.runs_jsonl_reference(tmp_path) == str(runs_path)

    log_path = external_progress_root / progress_paths.run_feature_log_filename(
        "FEAT-1"
    )
    assert progress_paths.run_feature_log_reference(tmp_path, "FEAT-1") == str(log_path)

    template_path = external_progress_root / "run-feature-<FEATURE_ID>.txt"
    assert progress_paths.run_feature_log_template_reference(tmp_path) == str(
        template_path
    )


def _stub_run_config() -> RunConfig:
    return RunConfig(
        project_root=Path("/tmp/project"),
        feature_paths=("docs/spec/features/FEAT-078.yaml",),
        dry_run=False,
    )


def _stub_run_services() -> RunServices:
    return RunServices(
        resolve_run_targets=lambda *_args, **_kwargs: [],
        emit_run_all_snapshot_feedback=lambda *_args, **_kwargs: None,
        handle_dry_run=lambda *_args, **_kwargs: None,
        enforce_worktree_precondition=lambda *_args, **_kwargs: None,
        run_permission_precheck=lambda **_kwargs: True,
        run_selected_feature_iterations=lambda *_args, **_kwargs: 0,
    )


def test_loop_entrypoint_signature_uses_looprun_context() -> None:
    signature = inspect.signature(loop_module.run_loop)
    parameters = signature.parameters

    assert tuple(parameters) == ("loop_run",)

    loop_run_parameter = parameters["loop_run"]
    assert loop_run_parameter.kind is Parameter.POSITIONAL_OR_KEYWORD
    assert loop_run_parameter.default is Parameter.empty
    assert loop_run_parameter.annotation in {"LoopRun", LoopRun}
    assert all(
        parameter.kind not in {Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD}
        for parameter in parameters.values()
    )


def test_run_implement_step_signature_is_explicit() -> None:
    signature = inspect.signature(loop_module.run_implement_step)
    parameters = signature.parameters

    assert tuple(parameters) == (
        "project_root",
        "feature",
        "feature_path",
        "hook_feedback",
        "verbose_output",
    )
    assert all(
        parameter.kind not in {Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD}
        for parameter in parameters.values()
    )
    assert not hasattr(loop_module.run_implement_step, "__signature__")


def test_run_feature_iteration_signature_is_explicit() -> None:
    signature = inspect.signature(loop_module._run_feature_iteration)
    parameters = signature.parameters

    assert tuple(parameters) == (
        "project_root",
        "feature_path",
        "run_all",
        "attempt",
        "hook_feedback",
        "verbose_output",
        "opencode_prompt",
    )
    assert all(
        parameter.kind not in {Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD}
        for parameter in parameters.values()
    )
    assert parameters["opencode_prompt"].default is None
    assert not hasattr(loop_module._run_feature_iteration, "__signature__")


def test_print_summary_signature_is_explicit() -> None:
    signature = inspect.signature(loop_module.print_summary)
    parameters = signature.parameters

    assert tuple(parameters) == (
        "feature_id",
        "result",
        "failed_gate",
        "attempt",
        "next_action",
        "selected_path",
        "implement_step",
        "log_path",
        "archived_selection_path",
        "verification_status",
        "verification_failed_command",
        "reviewer_status",
        "reviewer_decision",
        "failed_reviewer_id",
    )
    assert all(
        parameter.kind not in {Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD}
        for parameter in parameters.values()
    )
    assert not hasattr(loop_module.print_summary, "__signature__")


def test_loop_run_context_contract_immutability_and_extra_forbid() -> None:
    config = _stub_run_config()
    services = _stub_run_services()
    state = RunState()
    loop_run = LoopRun(config=config, services=services, state=state)

    assert RunConfig.model_config.get("frozen") is True
    assert RunServices.model_config.get("frozen") is True
    assert RunState.model_config.get("frozen") is True
    assert RunConfig.model_config.get("extra") == "forbid"
    assert RunServices.model_config.get("extra") == "forbid"
    assert RunState.model_config.get("extra") == "forbid"
    assert "make_iteration_config" not in RunServices.model_fields
    assert loop_run.state is state

    with pytest.raises(ValidationError):
        RunConfig.model_validate(
            {
                "project_root": config.project_root,
                "feature_paths": config.feature_paths,
                "dry_run": config.dry_run,
                "unexpected": True,
            }
        )


def test_run_state_copy_on_write_uses_model_copy_update() -> None:
    state = RunState(total_iterations=0)

    next_state = state.model_copy(update={"total_iterations": 1})
    next_run = LoopRun(
        config=_stub_run_config(),
        services=_stub_run_services(),
    ).model_copy(update={"state": next_state})

    assert state.total_iterations == 0
    assert next_state.total_iterations == 1
    assert next_run.state.total_iterations == 1


def test_iteration_outcome_remains_exposed_on_facade() -> None:
    assert hasattr(loop_module, "IterationOutcome")
    assert issubclass(loop_module.IterationOutcome, BaseModel)


def test_loop_monkeypatch_seams_remain_available() -> None:
    seam_symbols = (
        "run_agent",
        "run_permission_probe",
        "_require_clean_worktree",
        "_run_opencode_permission_precheck",
        "_choose_feature_with_selector",
        "run_implement_step",
        "_run_feature_iteration",
    )

    for symbol in seam_symbols:
        assert hasattr(loop_module, symbol)


def test_run_implement_step_from_inputs_requires_opencode_when_available(
    tmp_path: Path,
) -> None:
    inputs = ImplementStepInputs(
        project_root=tmp_path,
        feature={"id": "FEAT-999"},
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-999.yaml",
        hook_feedback=None,
        verbose_output=False,
    )

    result = run_implement_step_from_inputs(
        inputs,
        run_agent_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            FileNotFoundError()
        ),
    )

    assert result == (
        False,
        "opencode_missing",
        "[implement] opencode executable missing",
    )


def test_format_opencode_run_command_is_stable() -> None:
    assert (
        implement_module._format_opencode_run_command("engineeringagent")
        == "opencode run --agent engineeringagent <prompt>"
    )


def test_drop_completed_feature_from_snapshot_keeps_existing_paths(
    tmp_path: Path,
) -> None:
    feature_path = tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml"
    feature_path.parent.mkdir(parents=True)
    feature_path.write_text("id: FEAT-001\n", encoding="utf-8")

    resolved = [feature_path]
    assert (
        loop_module._drop_completed_feature_from_snapshot(resolved, feature_path)
        is resolved
    )


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


def test_loop_facade_line_budget_enforced() -> None:
    loop_path = Path("src/engineeringagent/loop.py")
    lines = len(loop_path.read_text(encoding="utf-8").splitlines())
    assert lines <= 650


def test_source_first_loop_command_rule_configuration() -> None:
    manifest_path = Path("harness/fitness-functions/rules.yaml")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    rules = manifest["rules"]
    source_first_rules = [
        rule
        for rule in rules
        if isinstance(rule, dict)
        and rule.get("rule_id") == "architecture.source-first-loop-command-policy"
    ]

    assert len(source_first_rules) == 1
    rule = source_first_rules[0]
    assert rule["adapter"] == "command"
    assert rule["severity"] == "error"
    assert rule["command"] == [
        "uv",
        "run",
        "python",
        "harness/fitness-functions/check_source_first_loop_commands.py",
    ]


def test_harness_root_yaml_only_rule_configuration() -> None:
    manifest_path = Path("harness/fitness-functions/rules.yaml")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    rules = manifest["rules"]
    harness_root_rules = [
        rule
        for rule in rules
        if isinstance(rule, dict)
        and rule.get("rule_id") == "architecture.harness-root-yaml-only"
    ]

    assert len(harness_root_rules) == 1
    rule = harness_root_rules[0]
    assert rule["adapter"] == "command"
    assert rule["severity"] == "error"
    assert rule["command"] == [
        "uv",
        "run",
        "python",
        "harness/fitness-functions/check_harness_root_yaml_only.py",
    ]


def test_progress_log_path_locality_rule_configuration() -> None:
    manifest_path = Path("harness/fitness-functions/rules.yaml")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    rules = manifest["rules"]
    locality_rules = [
        rule
        for rule in rules
        if isinstance(rule, dict)
        and rule.get("rule_id") == "architecture.progress-log-path-locality"
    ]

    assert len(locality_rules) == 1
    rule = locality_rules[0]
    assert rule["adapter"] == "command"
    assert rule["severity"] == "error"
    assert rule["command"] == [
        "uv",
        "run",
        "python",
        "harness/fitness-functions/check_progress_log_locality.py",
    ]


def test_progress_log_path_locality_rule_detects_inline_paths(
    tmp_path: Path,
    pytestconfig: pytest.Config,
) -> None:
    project_root = tmp_path
    source_root = project_root / "src" / "engineeringagent"
    source_root.mkdir(parents=True)
    (source_root / "progress_paths.py").write_text(
        'RUNS_JSONL_FILENAME = "runs.jsonl"\n',
        encoding="utf-8",
    )
    (source_root / "bad_paths.py").write_text(
        'RUNS_PATH = "progress/runs.jsonl"\n',
        encoding="utf-8",
    )

    repo_root = Path(pytestconfig.rootpath)
    script_path = (
        repo_root / "harness" / "fitness-functions" / "check_progress_log_locality.py"
    )
    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )

    envelope = json.loads(completed.stdout)
    assert envelope["rule_id"] == "architecture.progress-log-path-locality"
    assert envelope["status"] == "fail"
    assert any(
        violation.startswith("src/engineeringagent/bad_paths.py:1")
        for violation in envelope["violations"]
    )


def test_progress_log_path_locality_rule_detects_direct_writes(
    tmp_path: Path,
    pytestconfig: pytest.Config,
) -> None:
    project_root = tmp_path
    source_root = project_root / "src" / "engineeringagent"
    source_root.mkdir(parents=True)
    (source_root / "progress_paths.py").write_text(
        'RUNS_JSONL_FILENAME = "runs.jsonl"\n',
        encoding="utf-8",
    )
    (source_root / "bad_writes.py").write_text(
        """
from engineeringagent.progress import paths as progress_paths


def write_bad(root):
    log_path = progress_paths.runs_jsonl_path(root)
    with log_path.open(\"a\", encoding=\"utf-8\") as handle:
        handle.write(\"{}\\n\")
""".lstrip(),
        encoding="utf-8",
    )

    repo_root = Path(pytestconfig.rootpath)
    script_path = (
        repo_root / "harness" / "fitness-functions" / "check_progress_log_locality.py"
    )
    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )

    envelope = json.loads(completed.stdout)
    assert envelope["rule_id"] == "architecture.progress-log-path-locality"
    assert envelope["status"] == "fail"
    assert any(
        violation.startswith("src/engineeringagent/bad_writes.py:6")
        for violation in envelope["violations"]
    )


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
        reviewer_status="failed:request_changes",
        reviewer_decision="request_changes",
        failed_reviewer_id="security-reviewer",
        implement_output="",
        gate_output="",
        verification_output="E       assert 1 == 2",
        reviewer_output="[reviewer:security-reviewer] decision=request_changes",
        hook_feedback="[verification] uv run pytest -q\nE       assert 1 == 2",
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: None,
    )

    run = json.loads((tmp_path / "progress" / "runs.jsonl").read_text(encoding="utf-8"))
    assert run["verification_status"] == "failed:uv run pytest -q"
    assert run["verification_failed_command"] == "uv run pytest -q"
    assert run["reviewer_status"] == "failed:request_changes"
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
        "reviewer=failed:request_changes decision=request_changes "
        "failed_reviewer=security-reviewer" in feature_log
    )
    assert "detail=[verification] uv run pytest -q" in feature_log
