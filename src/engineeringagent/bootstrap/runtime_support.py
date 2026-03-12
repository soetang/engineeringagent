"""Bootstrap-owned support helpers for the legacy loop runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import engineeringagent.agents as agent_runtime
from engineeringagent.adapters.progress import paths as progress_paths
from engineeringagent.agents import classify_backend_exception, describe_action
from engineeringagent.domain.audit import (
    ImplementStepInputs,
    ImplementStepResult,
    IterationSummaryInputs,
)
from engineeringagent.application.implementation_step import (
    ImplementStepRuntimeDependencies,
    run_implement_step_from_inputs,
)
from engineeringagent.config import repo_relative_label
from engineeringagent.presentation.presenters.terminal import RunOutputPresenter
from engineeringagent.specs import progress_kind_label

from .app_factory import AppFactory

# Retained as a legacy monkeypatch seam while loop-contract tests migrate.
_AGENT_RUNTIME_COMPAT = agent_runtime


def git_head_short(project_root: Path) -> str | None:
    """Return the short git HEAD hash for a repository."""
    app_factory = AppFactory(project_root)
    version_control_gateway = app_factory.build_version_control_gateway()
    head_commit = version_control_gateway.head_commit(project_root)
    return head_commit


def build_implement_step_runtime_dependencies() -> ImplementStepRuntimeDependencies:
    """Build runtime-owned helpers for application implement-step orchestration."""

    return ImplementStepRuntimeDependencies(
        describe_action=describe_action,
        classify_backend_exception=classify_backend_exception,
        ensure_progress_artifacts=_ensure_progress_artifacts,
        repo_relative_label=repo_relative_label,
    )


def run_implement_step(
    project_root: Path,
    feature: dict[str, Any],
    feature_path: Path,
    feedback: str | None,
    verbose_output: bool,
) -> ImplementStepResult:
    """Run the implement phase for one loop iteration."""
    app_factory = AppFactory(project_root)
    implement_inputs = ImplementStepInputs(
        project_root=project_root,
        feature=feature,
        feature_path=feature_path,
        feedback=feedback,
        verbose_output=verbose_output,
    )
    return run_implement_step_from_inputs(
        implement_inputs,
        agent_runner=app_factory.build_agent_runner(),
        prompt_builder=app_factory.build_prompt_builder(),
        progress_journal=app_factory.build_progress_journal(),
        runtime_dependencies=build_implement_step_runtime_dependencies(),
    )


def _ensure_progress_artifacts(implement_inputs: ImplementStepInputs) -> None:
    project_root = implement_inputs.project_root
    feature_id = implement_inputs.feature.get("id")
    if not isinstance(feature_id, str) or not feature_id.strip():
        feature_id = "unknown-feature"

    progress_paths.runs_dir(project_root).mkdir(parents=True, exist_ok=True)
    progress_paths.runs_jsonl_path(project_root).touch(exist_ok=True)


def print_summary(summary: IterationSummaryInputs) -> None:
    """Print a one-line loop summary and optional gate failure."""
    presenter = RunOutputPresenter.for_current_terminal()
    if summary.attempt is not None:
        print(f"🔁 Iteration {summary.attempt} · {summary.feature_id or '-'}")
        if summary.archived_selection_path:
            print("  ♻️ Selected archived counterpart:")
            print(f"     {summary.archived_selection_path}")
        else:
            print(f"  🎯 Selected: {summary.selected_path or '-'}")
        print(f"  🛠 Implement: {summary.implement_step or '-'}")
        if summary.progress_kind:
            progress_parts = [
                part for part in (summary.progress_id, summary.progress_title) if part
            ]
            progress_reference = " - ".join(progress_parts) or "-"
            print(
                "  📍 Progress: "
                f"{progress_kind_label(summary.progress_kind)} {progress_reference}"
            )
        verification_label = summary.verification_status or "not_run"
        if (
            verification_label.startswith("failed:")
            and summary.verification_failed_command
        ):
            verification_label = f"failed ({summary.verification_failed_command})"
        print(f"  🧪 Verify: {verification_label}")
        reviewer_label = summary.reviewer_status or "not_run"
        if summary.reviewer_decision:
            reviewer_label = f"{reviewer_label} ({summary.reviewer_decision})"
        if summary.failed_reviewer_id:
            reviewer_label = f"{reviewer_label} [{summary.failed_reviewer_id}]"
        print(f"  👀 Reviewer: {reviewer_label}")
        if summary.result == "passed":
            print(f"  {presenter.format_iteration_passed_line()}")
        else:
            print(f"  {presenter.format_iteration_failed_line(summary.failed_gate)}")
            if summary.log_path:
                print(f"  📄 Log: {summary.log_path}")
        print(f"  ➡️ Next: {summary.next_action}")

    print(
        "Loop summary: "
        f"result={summary.result} feature={summary.feature_id or '-'} "
        f"attempt={summary.attempt if summary.attempt is not None else '-'} "
        f"next={summary.next_action}"
        f"{presenter.format_summary_suffix(summary.result)}"
    )
    if summary.failed_gate:
        print(presenter.format_failed_gate_line(summary.failed_gate))
