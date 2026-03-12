from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import sentinel

from engineeringagent.adapters.progress.handoff import (
    fallback_implement_progress_envelope,
)
from engineeringagent.ports import AgentRunner
from engineeringagent.domain.audit import IterationSummaryInputs
from engineeringagent.bootstrap import runtime_support


class _StubAgentRunner(AgentRunner):
    def __init__(self) -> None:
        self.requests: list[object] = []

    def run(self, request: object) -> object:
        self.requests.append(request)
        return fallback_implement_progress_envelope()


def test_run_implement_step_uses_app_factory_agent_runner(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Route implement-step execution through the configured agent-runner adapter."""

    captured: dict[str, object] = {}
    stub_agent_runner = _StubAgentRunner()

    class _StubAppFactory:
        def __init__(self, project_root: Path) -> None:
            captured["project_root"] = project_root

        def build_agent_runner(self) -> AgentRunner:
            captured["agent_runner_requested"] = True
            return stub_agent_runner

        def build_prompt_builder(self) -> object:
            return sentinel.prompt_builder

        def build_progress_journal(self) -> object:
            return sentinel.progress_journal

    def _fake_run_implement_step_from_inputs(
        implement_inputs: object,
        *,
        agent_runner: object,
        prompt_builder: object,
        progress_journal: object,
        runtime_dependencies: object,
    ) -> object:
        captured["implement_inputs"] = implement_inputs
        captured["agent_runner"] = agent_runner
        captured["prompt_builder"] = prompt_builder
        captured["progress_journal"] = progress_journal
        captured["runtime_dependencies"] = runtime_dependencies
        return sentinel.result

    monkeypatch.setattr(runtime_support, "AppFactory", _StubAppFactory)
    monkeypatch.setattr(
        runtime_support,
        "run_implement_step_from_inputs",
        _fake_run_implement_step_from_inputs,
    )

    result = runtime_support.run_implement_step(
        project_root=tmp_path,
        feature={"id": "FEAT-200"},
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-200" / "spec.yaml",
        feedback="retry",
        verbose_output=True,
    )

    assert result is sentinel.result
    assert captured["project_root"] == tmp_path
    assert captured["agent_runner_requested"] is True
    assert captured["agent_runner"] is stub_agent_runner
    assert captured["prompt_builder"] is sentinel.prompt_builder
    assert captured["progress_journal"] is sentinel.progress_journal
    runtime_dependencies = captured["runtime_dependencies"]
    assert hasattr(runtime_dependencies, "describe_action")
    assert hasattr(runtime_dependencies, "classify_backend_exception")
    assert hasattr(runtime_dependencies, "ensure_progress_artifacts")
    assert hasattr(runtime_dependencies, "repo_relative_label")


def test_print_summary_renders_passed_iteration_details(capsys: Any) -> None:
    """Print the full passed-iteration summary surface."""

    runtime_support.print_summary(
        IterationSummaryInputs(
            feature_id="FEAT-100",
            result="passed",
            failed_gate=None,
            attempt=2,
            next_action="continue_same_feature",
            selected_path="docs/spec/features/FEAT-100/spec.yaml",
            implement_step="opencode run --agent engineeringagent",
            progress_kind="step",
            progress_id="P1",
            progress_title="Wire run builder tests",
            verification_status="failed:uv run pytest -q",
            verification_failed_command="uv run pytest -q",
            reviewer_status="failed",
            reviewer_decision="request_changes",
            failed_reviewer_id="architecture-review",
        )
    )

    output = capsys.readouterr().out
    assert "Iteration 2" in output
    assert "Selected: docs/spec/features/FEAT-100/spec.yaml" in output
    assert "Implement: opencode run --agent engineeringagent" in output
    assert "Progress: implementation step P1 - Wire run builder tests" in output
    assert "Verify: failed (uv run pytest -q)" in output
    assert "Reviewer: failed (request_changes) [architecture-review]" in output
    assert "Loop summary: result=passed feature=FEAT-100 attempt=2" in output


def test_print_summary_renders_failed_iteration_with_archived_selection(
    capsys: Any,
) -> None:
    """Print archived counterpart and failure details for failed iterations."""

    runtime_support.print_summary(
        IterationSummaryInputs(
            feature_id="FEAT-200",
            result="failed",
            failed_gate="git_add",
            attempt=3,
            next_action="retry_same_feature",
            archived_selection_path="docs/spec/features_done/FEAT-200/spec.yaml",
            implement_step="implement",
            log_path=".engineeringagent/progress/FEAT-200/run.txt",
        )
    )

    output = capsys.readouterr().out
    assert "Selected archived counterpart:" in output
    assert "docs/spec/features_done/FEAT-200/spec.yaml" in output
    assert "Log: .engineeringagent/progress/FEAT-200/run.txt" in output
    assert "Failed gate: git_add" in output


def test_print_summary_shows_verification_and_reviewer_failure_details(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    """Render verification and reviewer details through bootstrap-owned output."""
    verification_command = "uv run pytest -q tests/test_loop_output.py"
    monkeypatch.setattr(
        "engineeringagent.presentation.presenters.terminal.stdout_is_tty",
        lambda _stdout: False,
    )
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    runtime_support.print_summary(
        IterationSummaryInputs(
            feature_id="FEAT-040",
            result="failed",
            failed_gate="unknown",
            attempt=2,
            next_action="retry_same_feature",
            selected_path="docs/spec/features/FEAT-040-per-iteration-verification-feedback-and-failure-signaling.yaml",
            implement_step="default opencode implement step",
            log_path=".engineeringagent/progress/FEAT-040/run.txt",
            verification_status=f"failed:{verification_command}",
            verification_failed_command=verification_command,
            reviewer_status="failed:request_changes",
            reviewer_decision="request_changes",
            failed_reviewer_id="security-reviewer",
        )
    )

    output = capsys.readouterr().out
    assert "Verify: failed (uv run pytest -q tests/test_loop_output.py)" in output
    assert (
        "Reviewer: failed:request_changes (request_changes) [security-reviewer]"
        in output
    )
    assert "Failed gate: unknown" in output


def test_print_summary_shows_phase_progress_context(capsys: Any) -> None:
    """Render bundled phase progress metadata through bootstrap-owned output."""
    runtime_support.print_summary(
        IterationSummaryInputs(
            feature_id="FEAT-181",
            result="passed",
            failed_gate=None,
            attempt=3,
            next_action="continue_same_feature",
            selected_path="docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/spec.yaml",
            implement_step="uv run engineeringagent implement",
            progress_kind="phase",
            progress_id="P3",
            progress_title="Move implementation sequencing from subtasks to plan phases",
        )
    )

    output = capsys.readouterr().out
    assert (
        "Progress: phase P3 - Move implementation sequencing from subtasks to plan phases"
        in output
    )
