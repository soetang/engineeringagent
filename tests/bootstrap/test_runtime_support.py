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
