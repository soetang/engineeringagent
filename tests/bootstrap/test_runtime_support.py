from __future__ import annotations

from typing import Any

from engineeringagent.domain.audit import IterationSummaryInputs
from engineeringagent.bootstrap import runtime_support


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
