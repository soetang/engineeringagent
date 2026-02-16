from __future__ import annotations

import inspect
import json
import subprocess
import sys
from inspect import Parameter
from pathlib import Path

import engineeringagent.loop as loop_module
import engineeringagent.progress_paths as progress_paths
import yaml
from pydantic import BaseModel

from engineeringagent.loop_runtime.models import (
    FeatureIterationInputs,
    ImplementStepInputs,
    IterationTelemetryInputs,
)
from engineeringagent.loop_runtime.implement import run_implement_step_from_inputs
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
            "skip_implement",
            "hook_feedback",
            "verbose_output",
        ),
        {
            "project_root": Parameter.empty,
            "feature": Parameter.empty,
            "feature_path": Parameter.empty,
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
            "skip_implement",
            "attempt",
            "hook_feedback",
            "verbose_output",
        ),
        {
            "project_root": Parameter.empty,
            "feature_path": Parameter.empty,
            "gate_profile": Parameter.empty,
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


def test_run_implement_step_from_inputs_skipped_mode_does_not_require_shell_override(
    tmp_path: Path,
) -> None:
    inputs = ImplementStepInputs(
        project_root=tmp_path,
        feature={"id": "FEAT-999"},
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-999.yaml",
        skip_implement=True,
        hook_feedback=None,
        verbose_output=False,
    )

    result = run_implement_step_from_inputs(
        inputs,
        start_agent_fn=lambda *_args, **_kwargs: None,
    )

    assert result == (True, None, "[implement] skipped")


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


def test_progress_log_path_locality_rule_detects_inline_paths(tmp_path: Path) -> None:
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

    script_path = (
        Path(__file__).resolve().parents[1]
        / "harness"
        / "fitness-functions"
        / "check_progress_log_locality.py"
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


def test_progress_log_path_locality_rule_detects_direct_writes(tmp_path: Path) -> None:
    project_root = tmp_path
    source_root = project_root / "src" / "engineeringagent"
    source_root.mkdir(parents=True)
    (source_root / "progress_paths.py").write_text(
        'RUNS_JSONL_FILENAME = "runs.jsonl"\n',
        encoding="utf-8",
    )
    (source_root / "bad_writes.py").write_text(
        """
import engineeringagent.progress_paths as progress_paths


def write_bad(root):
    log_path = progress_paths.runs_jsonl_path(root)
    with log_path.open(\"a\", encoding=\"utf-8\") as handle:
        handle.write(\"{}\\n\")
""".lstrip(),
        encoding="utf-8",
    )

    script_path = (
        Path(__file__).resolve().parents[1]
        / "harness"
        / "fitness-functions"
        / "check_progress_log_locality.py"
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
        gate_profile="loop_fast",
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
