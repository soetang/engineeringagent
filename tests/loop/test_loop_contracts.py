from __future__ import annotations

import inspect
import json
import subprocess
import sys
from inspect import Parameter
from pathlib import Path
from typing import Any, Sequence

import pytest
import yaml
from pydantic import BaseModel, ValidationError

import engineeringagent.loop as loop_module
from engineeringagent.adapters.progress import FilesystemProgressJournal
from engineeringagent.adapters.progress.iteration_telemetry import (
    write_iteration_telemetry,
)
from engineeringagent.adapters.prompts import FilesystemPromptDefinitionRepository
from engineeringagent.application import PromptBuilder
from engineeringagent.ports import AgentRunRequest, AgentRunner
from engineeringagent.loop import (
    _drop_completed_feature_from_snapshot,
    _run_feature_iteration,
)
from engineeringagent.bootstrap.runtime_execution import run_loop_controller
from engineeringagent.application.feature_iteration.models import (
    FeatureIterationInputs,
    ImplementStepInputs,
    IterationTelemetryInputs,
)
from engineeringagent.agents.contracts import AgentOutputValidationError
from engineeringagent.loop_runtime.implement import (
    run_implement_step_from_inputs,
)
from engineeringagent.loop_runtime.run_context import (
    LoopRun,
    RunConfig,
    RunServices,
    RunState,
)
from engineeringagent.adapters.progress.handoff import ImplementProgressEnvelope
from engineeringagent.adapters.progress.handoff import (
    fallback_implement_progress_envelope,
)
from engineeringagent.adapters.progress import paths as progress_paths
from engineeringagent.config import resolve_harness_root
from tests.loop.feature_iteration_support import copy_canonical_prompts
from tests.loop.feature_iteration_support import make_bundled_project_root


_PROGRESS_ROOT_PARTS = (".engineeringagent", "progress")


@pytest.fixture(autouse=True)
def _materialize_prompt_definitions(tmp_path: Path) -> None:
    copy_canonical_prompts(tmp_path)


def _progress_root(project_root: Path) -> Path:
    return project_root.joinpath(*_PROGRESS_ROOT_PARTS)


class _StubAgentRunner(AgentRunner):
    def __init__(self, response: object | Exception) -> None:
        self._response = response
        self.requests: list[AgentRunRequest] = []

    def run(self, request: AgentRunRequest) -> object:
        self.requests.append(request)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _loop_prompt_builder(project_root: Path) -> PromptBuilder:
    return PromptBuilder(
        FilesystemPromptDefinitionRepository(
            resolve_harness_root(project_root) / "prompts"
        )
    )


def test_progress_paths_contract(tmp_path: Path) -> None:
    assert progress_paths.runs_jsonl_path(tmp_path) == (
        _progress_root(tmp_path) / "runs" / "runs.jsonl"
    )
    assert progress_paths.run_feature_log_path(tmp_path, "FEAT-040") == (
        _progress_root(tmp_path) / "features" / "FEAT-040" / "run.txt"
    )
    assert progress_paths.run_feature_log_reference(tmp_path, "FEAT-040") == (
        ".engineeringagent/progress/features/FEAT-040/run.txt"
    )
    assert progress_paths.run_feature_log_reference(tmp_path, "FEAT 040/../../") == (
        ".engineeringagent/progress/features/FEAT_040/run.txt"
    )
    assert progress_paths.run_feature_log_reference(tmp_path, "!!!") == (
        ".engineeringagent/progress/features/unknown-feature/run.txt"
    )


def test_progress_paths_contract_uses_configured_progress_root(tmp_path: Path) -> None:
    (tmp_path / "engineeringagent.toml").write_text(
        '[paths]\nprogress_root = "runtime/progress-artifacts"\n',
        encoding="utf-8",
    )

    configured_root = tmp_path / "runtime" / "progress-artifacts"
    assert progress_paths.progress_dir(tmp_path) == configured_root
    assert progress_paths.runs_jsonl_path(tmp_path) == (
        configured_root / "runs" / "runs.jsonl"
    )
    assert progress_paths.run_feature_log_path(tmp_path, "FEAT-040") == (
        configured_root / "features" / "FEAT-040" / "run.txt"
    )
    assert progress_paths.run_feature_log_reference(tmp_path, "FEAT-040") == (
        "runtime/progress-artifacts/features/FEAT-040/run.txt"
    )


def test_handoff_paths_contract(tmp_path: Path) -> None:
    assert progress_paths.handoff_markdown_path(tmp_path, "FEAT-040") == (
        _progress_root(tmp_path) / "features" / "FEAT-040" / "handoff.md"
    )
    assert progress_paths.handoff_markdown_reference(tmp_path, "FEAT-040") == (
        ".engineeringagent/progress/features/FEAT-040/handoff.md"
    )
    assert progress_paths.handoff_markdown_template_reference(tmp_path) == (
        ".engineeringagent/progress/features/<FEATURE_ID>/handoff.md"
    )
    assert progress_paths.iteration_report_reference(tmp_path, "FEAT-040") == (
        ".engineeringagent/progress/features/FEAT-040/iteration-report.json"
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

    runs_path = (
        external_progress_root
        / progress_paths.PROGRESS_RUNS_DIRNAME
        / progress_paths.RUNS_JSONL_FILENAME
    )
    assert progress_paths.runs_jsonl_reference(tmp_path) == str(runs_path)

    log_path = (
        external_progress_root
        / progress_paths.PROGRESS_FEATURES_DIRNAME
        / "FEAT-1"
        / progress_paths.run_feature_log_filename()
    )
    assert progress_paths.run_feature_log_reference(tmp_path, "FEAT-1") == str(log_path)

    template_path = (
        external_progress_root
        / progress_paths.PROGRESS_FEATURES_DIRNAME
        / "<FEATURE_ID>"
        / progress_paths.FEATURE_RUN_LOG_FILENAME
    )
    assert progress_paths.run_feature_log_template_reference(tmp_path) == str(
        template_path
    )

    handoff_path = (
        external_progress_root
        / progress_paths.PROGRESS_FEATURES_DIRNAME
        / "FEAT-1"
        / progress_paths.FEATURE_HANDOFF_FILENAME
    )
    assert progress_paths.handoff_markdown_reference(tmp_path, "FEAT-1") == str(
        handoff_path
    )

    handoff_template_path = (
        external_progress_root
        / progress_paths.PROGRESS_FEATURES_DIRNAME
        / "<FEATURE_ID>"
        / progress_paths.FEATURE_HANDOFF_FILENAME
    )
    assert progress_paths.handoff_markdown_template_reference(tmp_path) == str(
        handoff_template_path
    )


def _stub_run_config() -> RunConfig:
    return RunConfig(
        project_root=Path("/tmp/project"),
        feature_paths=("docs/spec/features/FEAT-078/spec.yaml",),
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
    signature = inspect.signature(run_loop_controller)
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
        "feedback",
        "verbose_output",
    )
    assert all(
        parameter.kind not in {Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD}
        for parameter in parameters.values()
    )
    assert not hasattr(loop_module.run_implement_step, "__signature__")


def test_run_feature_iteration_signature_is_explicit() -> None:
    signature = inspect.signature(_run_feature_iteration)
    parameters = signature.parameters

    assert tuple(parameters) == (
        "project_root",
        "feature_path",
        "run_all",
        "attempt",
        "feedback",
        "verbose_output",
    )
    assert all(
        parameter.kind not in {Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD}
        for parameter in parameters.values()
    )
    assert not hasattr(_run_feature_iteration, "__signature__")


def test_print_summary_signature_is_explicit() -> None:
    signature = inspect.signature(loop_module.print_summary)
    parameters = signature.parameters

    assert tuple(parameters) == ("summary",)
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

    fields = dict(RunServices.model_fields)
    assert "make_iteration_config" not in fields
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
        "preflight",
        "_choose_feature_with_selector",
        "run_implement_step",
        "_run_feature_iteration",
    )

    for symbol in seam_symbols:
        assert hasattr(loop_module, symbol)


def test_run_implement_step_from_inputs_requires_backend_binary_when_available(
    tmp_path: Path,
) -> None:
    inputs = ImplementStepInputs(
        project_root=tmp_path,
        feature={"id": "FEAT-999"},
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-999.yaml",
        feedback=None,
        verbose_output=False,
    )

    result = run_implement_step_from_inputs(
        inputs,
        agent_runner=_StubAgentRunner(FileNotFoundError()),
        prompt_builder=_loop_prompt_builder(inputs.project_root),
        progress_journal=FilesystemProgressJournal(),
    )

    assert len(result) == 5
    ok, failed_gate, command_output, envelope, used_fallback = result
    assert ok is False
    assert failed_gate == "agent_missing"
    assert command_output == "[implement] backend executable missing"
    assert isinstance(envelope, ImplementProgressEnvelope)
    assert used_fallback is True


def test_run_implement_step_from_inputs_reraises_unexpected_errors(
    tmp_path: Path,
) -> None:
    inputs = ImplementStepInputs(
        project_root=tmp_path,
        feature={"id": "FEAT-999"},
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-999.yaml",
        feedback=None,
        verbose_output=False,
    )

    with pytest.raises(RuntimeError, match="boom"):
        run_implement_step_from_inputs(
            inputs,
            agent_runner=_StubAgentRunner(RuntimeError("boom")),
            prompt_builder=_loop_prompt_builder(inputs.project_root),
            progress_journal=FilesystemProgressJournal(),
        )


def test_run_implement_step_from_inputs_reraises_non_signature_type_error(
    tmp_path: Path,
) -> None:
    inputs = ImplementStepInputs(
        project_root=tmp_path,
        feature={"id": "FEAT-999"},
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-999.yaml",
        feedback=None,
        verbose_output=False,
    )

    with pytest.raises(TypeError, match="boom"):
        run_implement_step_from_inputs(
            inputs,
            agent_runner=_StubAgentRunner(TypeError("boom")),
            prompt_builder=_loop_prompt_builder(inputs.project_root),
            progress_journal=FilesystemProgressJournal(),
        )


def test_run_implement_step_from_inputs_uses_fallback_on_validation_error(
    tmp_path: Path,
) -> None:
    inputs = ImplementStepInputs(
        project_root=tmp_path,
        feature={"id": "FEAT-999"},
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-999.yaml",
        feedback=None,
        verbose_output=False,
    )

    result = run_implement_step_from_inputs(
        inputs,
        agent_runner=_StubAgentRunner(
            AgentOutputValidationError(
                backend="opencode",
                attempts=2,
                last_text="raw output",
                error_summary="missing field",
            )
        ),
        prompt_builder=_loop_prompt_builder(inputs.project_root),
        progress_journal=FilesystemProgressJournal(),
    )

    assert len(result) == 5
    ok, failed_gate, command_output, envelope, used_fallback = result
    assert ok is True
    assert failed_gate is None
    assert "structured_output=invalid" in command_output
    assert isinstance(envelope, ImplementProgressEnvelope)
    assert used_fallback is True


def test_run_implement_step_from_inputs_accepts_structured_envelope_output(
    tmp_path: Path,
) -> None:
    inputs = ImplementStepInputs(
        project_root=tmp_path,
        feature={"id": "FEAT-999"},
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-999.yaml",
        feedback=None,
        verbose_output=False,
    )

    result = run_implement_step_from_inputs(
        inputs,
        agent_runner=_StubAgentRunner(
            ImplementProgressEnvelope(
                summary="done",
                completed_work=["a"],
                verification=["b"],
                remaining_work=["c"],
            )
        ),
        prompt_builder=_loop_prompt_builder(inputs.project_root),
        progress_journal=FilesystemProgressJournal(),
    )

    assert len(result) == 5
    assert result[0] is True
    assert result[4] is False


def test_run_implement_step_from_inputs_preserves_phase_context_in_fallback_envelope(
    tmp_path: Path,
) -> None:
    feature_data = {
        "id": "FEAT-999",
        "title": "Bundled fallback handoff context",
        "type": "feature",
        "expected_commit_subject": "feat: preserve bundled fallback handoff context",
        "status": "in_progress",
        "priority": "high",
        "objective": "Keep fallback handoff output phase-oriented.",
        "acceptance": ["Fallback output references the current phase."],
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
        "updated_at": "2026-03-09T00:00:00Z",
    }
    plan_frontmatter = {
        "plan_id": "FEAT-999",
        "feature_id": "FEAT-999",
        "status": "in_progress",
        "source_spec": "spec.yaml",
        "planning_tier": "planned",
        "phases": [
            {"id": "P1", "title": "Preserve fallback context", "status": "in_progress"}
        ],
    }
    project_root, feature_path, _plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter=plan_frontmatter,
    )
    inputs = ImplementStepInputs(
        project_root=project_root,
        feature=feature_data,
        feature_path=feature_path,
        feedback=None,
        verbose_output=False,
    )

    ok, failed_gate, command_output, envelope, used_fallback = (
        run_implement_step_from_inputs(
            inputs,
            agent_runner=_StubAgentRunner('{"summary":""}'),
            prompt_builder=_loop_prompt_builder(inputs.project_root),
            progress_journal=FilesystemProgressJournal(),
        )
    )

    assert ok is True
    assert failed_gate is None
    assert "returncode=0" in command_output
    assert used_fallback is True
    assert envelope.remaining_work == [
        "Review latest progress logs and continue the highest-priority open phase (P1: Preserve fallback context)."
    ]


def test_run_implement_step_from_inputs_uses_raw_phase_context_for_invalid_plan_contract(
    tmp_path: Path,
) -> None:
    feature_data = {
        "id": "FEAT-996",
        "title": "Bundled invalid plan fallback handoff context",
        "type": "feature",
        "expected_commit_subject": "feat: preserve invalid bundled fallback handoff context",
        "status": "in_progress",
        "priority": "high",
        "objective": "Keep fallback handoff output on the raw phase surface.",
        "acceptance": ["Fallback output recovers parseable raw phase metadata."],
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
        "updated_at": "2026-03-09T00:00:00Z",
    }
    plan_frontmatter = {
        "plan_id": "FEAT-996",
        "status": "in_progress",
        "source_spec": "spec.yaml",
        "planning_tier": "planned",
        "phases": [
            {
                "id": "P1",
                "title": "Recover fallback context from invalid plan contract",
                "status": "in_progress",
            }
        ],
    }
    project_root, feature_path, _plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter=plan_frontmatter,
    )
    inputs = ImplementStepInputs(
        project_root=project_root,
        feature=feature_data,
        feature_path=feature_path,
        feedback=None,
        verbose_output=False,
    )

    ok, failed_gate, command_output, envelope, used_fallback = (
        run_implement_step_from_inputs(
            inputs,
            agent_runner=_StubAgentRunner('{"summary":""}'),
            prompt_builder=_loop_prompt_builder(inputs.project_root),
            progress_journal=FilesystemProgressJournal(),
        )
    )

    assert ok is True
    assert failed_gate is None
    assert "returncode=0" in command_output
    assert used_fallback is True
    assert envelope.remaining_work == [
        "Review latest progress logs and continue the highest-priority open phase (P1: Recover fallback context from invalid plan contract)."
    ]


def test_run_implement_step_from_inputs_does_not_project_feature_context_onto_missing_phase(
    tmp_path: Path,
) -> None:
    feature_data = {
        "id": "FEAT-997",
        "title": "Bundled fallback without concrete phase",
        "type": "feature",
        "expected_commit_subject": "feat: preserve missing phase fallback context",
        "status": "in_progress",
        "priority": "high",
        "objective": "Keep fallback output off feature-projected phase references.",
        "acceptance": ["Fallback output omits synthetic phase identifiers."],
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
        "updated_at": "2026-03-09T00:00:00Z",
    }
    plan_frontmatter = {
        "plan_id": "FEAT-997",
        "feature_id": "FEAT-997",
        "status": "in_progress",
        "source_spec": "spec.yaml",
        "planning_tier": "planned",
        "phases": [],
    }
    project_root, feature_path, _plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter=plan_frontmatter,
    )
    inputs = ImplementStepInputs(
        project_root=project_root,
        feature=feature_data,
        feature_path=feature_path,
        feedback=None,
        verbose_output=False,
    )

    ok, failed_gate, command_output, envelope, used_fallback = (
        run_implement_step_from_inputs(
            inputs,
            agent_runner=_StubAgentRunner('{"summary":""}'),
            prompt_builder=_loop_prompt_builder(inputs.project_root),
            progress_journal=FilesystemProgressJournal(),
        )
    )

    assert ok is True
    assert failed_gate is None
    assert "returncode=0" in command_output
    assert used_fallback is True
    assert envelope.remaining_work == [
        "Review latest progress logs and continue the highest-priority open phase."
    ]


def test_run_implement_step_from_inputs_preserves_feature_context_in_fallback_envelope(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    feature_path = (
        project_root
        / "docs"
        / "spec"
        / "features"
        / "FEAT-998-direct-bundled"
        / "spec.yaml"
    )
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    feature_data = {
        "id": "FEAT-998",
        "title": "Direct bundled fallback handoff context",
        "type": "spec",
        "expected_commit_subject": "spec: preserve direct bundled fallback handoff context",
        "status": "in_progress",
        "priority": "high",
        "objective": "Keep fallback output feature-oriented for bundled direct work.",
        "acceptance": ["Fallback output references the active bundled feature."],
        "planning_tier": "direct",
        "artifacts": {},
        "updated_at": "2026-03-09T00:00:00Z",
    }
    feature_path.write_text(
        yaml.safe_dump(feature_data, sort_keys=False), encoding="utf-8"
    )
    inputs = ImplementStepInputs(
        project_root=project_root,
        feature=feature_data,
        feature_path=feature_path,
        feedback=None,
        verbose_output=False,
    )

    ok, failed_gate, command_output, envelope, used_fallback = (
        run_implement_step_from_inputs(
            inputs,
            agent_runner=_StubAgentRunner('{"summary":""}'),
            prompt_builder=_loop_prompt_builder(inputs.project_root),
            progress_journal=FilesystemProgressJournal(),
        )
    )

    assert ok is True
    assert failed_gate is None
    assert "returncode=0" in command_output
    assert used_fallback is True
    assert envelope.remaining_work == [
        "Review latest progress logs and continue the highest-priority open implementation step (FEAT-998: Direct bundled fallback handoff context)."
    ]


def test_drop_completed_feature_from_snapshot_keeps_existing_paths(
    tmp_path: Path,
) -> None:
    feature_path = tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml"
    feature_path.parent.mkdir(parents=True)
    feature_path.write_text("id: FEAT-001\n", encoding="utf-8")

    resolved = [feature_path]
    assert _drop_completed_feature_from_snapshot(resolved, feature_path) is resolved


def test_loop_facade_line_budget_rule_configuration() -> None:
    manifest_path = Path("harness/fitness_functions/rules.yaml")
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
        "harness/fitness_functions/rules/check_loop_facade_line_budget.py",
    ]


def test_loop_facade_line_budget_enforced() -> None:
    loop_path = Path("src/engineeringagent/loop.py")
    lines = len(loop_path.read_text(encoding="utf-8").splitlines())
    assert lines <= 650


def test_source_first_loop_command_rule_configuration() -> None:
    manifest_path = Path("harness/fitness_functions/rules.yaml")
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
        "harness/fitness_functions/rules/check_source_first_loop_commands.py",
    ]


def test_harness_root_yaml_only_rule_configuration() -> None:
    manifest_path = Path("harness/fitness_functions/rules.yaml")
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
        "harness/fitness_functions/rules/check_harness_root_yaml_only.py",
    ]


def test_progress_log_path_locality_rule_configuration() -> None:
    manifest_path = Path("harness/fitness_functions/rules.yaml")
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
        "harness/fitness_functions/rules/check_progress_log_locality.py",
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
        repo_root
        / "harness"
        / "fitness_functions"
        / "rules"
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
from engineeringagent.adapters.progress import paths as progress_paths


def write_bad(root):
    log_path = progress_paths.runs_jsonl_path(root)
    with log_path.open(\"a\", encoding=\"utf-8\") as handle:
        handle.write(\"{}\\n\")
""".lstrip(),
        encoding="utf-8",
    )

    repo_root = Path(pytestconfig.rootpath)
    script_path = (
        repo_root
        / "harness"
        / "fitness_functions"
        / "rules"
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
        feedback="verification failed",
        log_path="progress/run-feature-FEAT-040.txt",
    )

    assert outcome.verification_status == "not_run"
    assert outcome.verification_failed_command is None
    assert outcome.reviewer_status == "not_run"
    assert outcome.reviewer_decision is None
    assert outcome.failed_reviewer_id is None


def test_iteration_outcome_from_report_maps_report_fields(tmp_path: Path) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-116.yaml",
        attempt=4,
        feedback="feedback",
        verbose_output=False,
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=0.0,
        feature_id="FEAT-116",
        result="failed",
        failed_gate="spec_validate",
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
        feedback="feedback",
    )
    report = loop_module.IterationReport(
        completed=False,
        result="failed",
        failed_gate="spec_validate",
        next_action="retry_same_feature",
        feedback="feedback",
        feature_id="FEAT-116",
        attempt=4,
        selected_feature_path=str(iteration_inputs.feature_path),
        implement_step="engineeringagent implement",
        verification_status="failed:uv run pytest -q",
        verification_failed_command="uv run pytest -q",
        reviewer_status="failed:request_changes",
        reviewer_decision="request_changes",
        failed_reviewer_id="security-reviewer",
        telemetry_inputs=telemetry_inputs,
        log_path="progress/run-feature-FEAT-116.txt",
    )

    outcome = loop_module.IterationOutcome.from_report(report)

    assert outcome.completed is False
    assert outcome.result == "failed"
    assert outcome.failed_gate == "spec_validate"
    assert outcome.next_action == "retry_same_feature"
    assert outcome.feedback == "feedback"
    assert outcome.log_path == "progress/run-feature-FEAT-116.txt"
    assert outcome.verification_status == "failed:uv run pytest -q"
    assert outcome.verification_failed_command == "uv run pytest -q"
    assert outcome.reviewer_status == "failed:request_changes"
    assert outcome.reviewer_decision == "request_changes"
    assert outcome.failed_reviewer_id == "security-reviewer"


def test_publish_iteration_report_accepts_injected_observers(tmp_path: Path) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-116.yaml",
        attempt=4,
        feedback=None,
        verbose_output=False,
    )
    telemetry_inputs = IterationTelemetryInputs(
        iteration_inputs=iteration_inputs,
        started=0.0,
        feature_id="FEAT-116",
        result="failed",
        failed_gate="spec_validate",
        next_action="retry_same_feature",
        implement_status="passed",
        gate_status="not_run",
        verification_status="not_run",
        verification_failed_command=None,
        reviewer_status="not_run",
        reviewer_decision=None,
        failed_reviewer_id=None,
        implement_output="",
        gate_output="",
        verification_output="",
        reviewer_output="",
        feedback="feedback",
    )
    report = loop_module.IterationReport(
        completed=False,
        result="failed",
        failed_gate="spec_validate",
        next_action="retry_same_feature",
        feedback="feedback",
        feature_id="FEAT-116",
        attempt=4,
        selected_feature_path=str(iteration_inputs.feature_path),
        implement_step="engineeringagent implement",
        verification_status="not_run",
        verification_failed_command=None,
        reviewer_status="not_run",
        reviewer_decision=None,
        failed_reviewer_id=None,
        telemetry_inputs=telemetry_inputs,
    )

    observed: list[str] = []

    def _first(
        input_report: loop_module.IterationReport,
    ) -> loop_module.IterationReport:
        observed.append("first")
        return input_report.model_copy(
            update={"log_path": "progress/run-feature-FEAT-116.txt"}
        )

    def _second(
        input_report: loop_module.IterationReport,
    ) -> loop_module.IterationReport:
        observed.append("second")
        assert input_report.log_path == "progress/run-feature-FEAT-116.txt"
        return input_report

    outcome = loop_module._publish_iteration_report(
        report,
        observers=(_first, _second),
    )

    assert observed == ["first", "second"]
    assert outcome.log_path == "progress/run-feature-FEAT-116.txt"
    assert outcome.result == "failed"
    assert outcome.failed_gate == "spec_validate"


def test_feedback_contract_accepts_verification_failure(tmp_path: Path) -> None:
    iteration_inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-040.yaml",
        attempt=1,
        feedback=None,
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
        feedback="[verification] uv run pytest -q\nE       assert 1 == 2",
    )

    write_iteration_telemetry(
        telemetry_inputs,
        git_head_resolver=lambda _: None,
    )

    run = json.loads(
        (_progress_root(tmp_path) / "runs" / "runs.jsonl").read_text(encoding="utf-8")
    )
    assert run["verification_status"] == "failed:uv run pytest -q"
    assert run["verification_failed_command"] == "uv run pytest -q"
    assert run["reviewer_status"] == "failed:request_changes"
    assert run["reviewer_decision"] == "request_changes"
    assert run["failed_reviewer_id"] == "security-reviewer"

    feature_log = (
        _progress_root(tmp_path) / "features" / "FEAT-040" / "run.txt"
    ).read_text(encoding="utf-8")
    assert (
        "verification=failed:uv run pytest -q failed_command=uv run pytest -q"
        in feature_log
    )
    assert (
        "reviewer=failed:request_changes decision=request_changes "
        "failed_reviewer=security-reviewer" in feature_log
    )
    assert "detail=[verification] uv run pytest -q" in feature_log


def test_run_implement_step_uses_injected_prompt_builder(tmp_path: Path) -> None:
    inputs = ImplementStepInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-900" / "spec.yaml",
        feature={"id": "FEAT-900", "title": "Prompt seam", "status": "in_progress"},
        feedback=None,
        verbose_output=False,
    )
    recorded_calls: list[dict[str, object]] = []

    class _PromptBuilder:
        def build_implementation_prompt_from_feature_document(
            self,
            *,
            feature: dict[str, object],
            specification_path: Path,
            feedback: str | None,
            handoff_path: str | None = None,
        ) -> str:
            assert specification_path == inputs.feature_path
            assert feedback is None
            recorded_calls.append(
                {
                    "feature_id": feature["id"],
                    "specification_path": specification_path,
                    "feedback": feedback,
                    "handoff_path": handoff_path,
                }
            )
            return "PROMPT FROM INJECTED BUILDER"

    agent_runner = _StubAgentRunner(fallback_implement_progress_envelope())

    result = run_implement_step_from_inputs(
        inputs,
        agent_runner=agent_runner,
        prompt_builder=_PromptBuilder(),
        progress_journal=FilesystemProgressJournal(),
    )

    assert result[0] is True
    assert agent_runner.requests == [
        AgentRunRequest(
            project_root=tmp_path,
            prompt="PROMPT FROM INJECTED BUILDER",
            output_type=ImplementProgressEnvelope,
        )
    ]
    assert recorded_calls == [
        {
            "feature_id": "FEAT-900",
            "specification_path": inputs.feature_path,
            "feedback": None,
            "handoff_path": None,
        }
    ]


def test_run_implement_step_passes_handoff_path_only_when_persisted(
    tmp_path: Path,
) -> None:
    _, feature_path, _plan_path = make_bundled_project_root(
        tmp_path,
        feature_data={
            "id": "FEAT-900",
            "title": "Prompt seam",
            "type": "feature",
            "expected_commit_subject": "feat: preserve persisted handoff prompt seam",
            "status": "in_progress",
            "priority": "high",
            "objective": "Pass persisted handoff state into prompt assembly.",
            "acceptance": ["Persisted handoff paths are passed through to prompts."],
            "planning_tier": "planned",
            "artifacts": {"plan": "plan.md"},
        },
        plan_frontmatter={
            "plan_id": "FEAT-900",
            "feature_id": "FEAT-900",
            "status": "in_progress",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [{"id": "P1", "title": "Prompt seam", "status": "in_progress"}],
        },
    )
    inputs = ImplementStepInputs(
        project_root=tmp_path,
        feature=yaml.safe_load(feature_path.read_text(encoding="utf-8")),
        feature_path=feature_path,
        feedback=None,
        verbose_output=False,
    )
    handoff_path = (
        tmp_path
        / ".engineeringagent"
        / "progress"
        / "features"
        / "FEAT-900"
        / "handoff.md"
    )
    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_path.write_text("# Handoff\n", encoding="utf-8")
    recorded_calls: list[dict[str, object]] = []

    class _PromptBuilder:
        def build_implementation_prompt_from_feature_document(
            self,
            *,
            feature: dict[str, object],
            specification_path: Path,
            feedback: str | None,
            handoff_path: str | None = None,
        ) -> str:
            assert specification_path == inputs.feature_path
            assert feedback is None
            recorded_calls.append(
                {
                    "feature_id": feature["id"],
                    "specification_path": specification_path,
                    "feedback": feedback,
                    "handoff_path": handoff_path,
                }
            )
            return "PROMPT FROM INJECTED BUILDER"

    agent_runner = _StubAgentRunner(fallback_implement_progress_envelope())

    result = run_implement_step_from_inputs(
        inputs,
        agent_runner=agent_runner,
        prompt_builder=_PromptBuilder(),
        progress_journal=FilesystemProgressJournal(),
    )

    assert result[0] is True
    assert agent_runner.requests == [
        AgentRunRequest(
            project_root=tmp_path,
            prompt="PROMPT FROM INJECTED BUILDER",
            output_type=ImplementProgressEnvelope,
        )
    ]
    assert recorded_calls == [
        {
            "feature_id": "FEAT-900",
            "specification_path": inputs.feature_path,
            "feedback": None,
            "handoff_path": ".engineeringagent/progress/features/FEAT-900/handoff.md",
        }
    ]


def test_run_implement_step_preserves_non_repo_handoff_path_reference(
    tmp_path: Path,
) -> None:
    _, feature_path, _plan_path = make_bundled_project_root(
        tmp_path,
        feature_data={
            "id": "FEAT-901",
            "title": "External handoff seam",
            "type": "feature",
            "expected_commit_subject": "feat: preserve external handoff references",
            "status": "in_progress",
            "priority": "high",
            "objective": "Keep persisted handoff paths stable when they live outside the repo.",
            "acceptance": ["Prompt assembly preserves non-repo handoff paths."],
            "planning_tier": "planned",
            "artifacts": {"plan": "plan.md"},
        },
        plan_frontmatter={
            "plan_id": "FEAT-901",
            "feature_id": "FEAT-901",
            "status": "in_progress",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [
                {"id": "P1", "title": "External handoff seam", "status": "in_progress"}
            ],
        },
    )
    inputs = ImplementStepInputs(
        project_root=tmp_path,
        feature=yaml.safe_load(feature_path.read_text(encoding="utf-8")),
        feature_path=feature_path,
        feedback=None,
        verbose_output=False,
    )
    external_handoff_path = (
        tmp_path.parent / "external-progress" / "FEAT-901" / "handoff.md"
    )
    recorded_calls: list[dict[str, object]] = []

    class _PromptBuilder:
        def build_implementation_prompt_from_feature_document(
            self,
            *,
            feature: dict[str, object],
            specification_path: Path,
            feedback: str | None,
            handoff_path: str | None = None,
        ) -> str:
            recorded_calls.append(
                {
                    "feature_id": feature["id"],
                    "specification_path": specification_path,
                    "feedback": feedback,
                    "handoff_path": handoff_path,
                }
            )
            return "PROMPT FROM INJECTED BUILDER"

    class _ProgressJournal:
        def append(
            self,
            *,
            project_root: Path,
            event: Any,
        ) -> None:
            raise AssertionError("append should not be called in this test")

        def latest_handoff_path(
            self, *, project_root: Path, feature_id: str
        ) -> Path | None:
            assert project_root == tmp_path
            assert feature_id == "FEAT-901"
            return external_handoff_path

        def append_feature_log(
            self,
            *,
            project_root: Path,
            feature_id: str,
            lines: Sequence[str],
        ) -> None:
            assert project_root == tmp_path
            assert feature_id == "FEAT-901"
            assert lines

        def write_iteration_report(
            self,
            *,
            project_root: Path,
            feature_id: str,
            payload: dict[str, Any],
        ) -> None:
            raise AssertionError(
                "write_iteration_report should not be called in this test"
            )

        def write_handoff(
            self,
            *,
            project_root: Path,
            feature_id: str,
            lines: Sequence[str],
        ) -> None:
            raise AssertionError("write_handoff should not be called in this test")

    agent_runner = _StubAgentRunner(fallback_implement_progress_envelope())

    result = run_implement_step_from_inputs(
        inputs,
        agent_runner=agent_runner,
        prompt_builder=_PromptBuilder(),
        progress_journal=_ProgressJournal(),
    )

    assert result[0] is True
    assert recorded_calls == [
        {
            "feature_id": "FEAT-901",
            "specification_path": inputs.feature_path,
            "feedback": None,
            "handoff_path": str(external_handoff_path),
        }
    ]
