"""Bootstrap-owned support helpers for the legacy loop runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import engineeringagent.adapters.agents as agent_runtime
from engineeringagent.adapters.agents import (
    ConfiguredAgentRunner,
    classify_backend_exception,
    describe_action,
    format_failed_backend_output,
    should_handle_backend_exception,
)
from engineeringagent.adapters.progress import paths as progress_paths
from engineeringagent.adapters.progress import FilesystemProgressJournal
from engineeringagent.adapters.prompts import FilesystemPromptDefinitionRepository
from engineeringagent.adapters.vcs import GitCliVersionControlGateway
from engineeringagent.application.feature_iteration import (
    ImplementStepFailureDependencies,
    ImplementStepInputs,
    ImplementStepResult,
    ImplementStepOutputDependencies,
    ImplementStepRuntimeDependencies,
    IterationSummaryInputs,
    run_implement_step_from_inputs,
)
from engineeringagent.application import PromptBuilder
from engineeringagent.adapters.config import (
    load_repository_config,
    repo_relative_label,
    resolve_harness_root,
)
from engineeringagent.presentation.presenters.terminal import RunOutputPresenter
from engineeringagent.specs import progress_kind_label

__all__ = ["agent_runtime"]


def git_head_short(project_root: Path) -> str | None:
    """Return the short git HEAD hash for a repository."""
    version_control_gateway = _build_version_control_gateway(project_root)
    head_commit = version_control_gateway.head_commit(project_root)
    return head_commit


def build_implement_step_runtime_dependencies() -> ImplementStepRuntimeDependencies:
    """Build runtime-owned helpers for application implement-step orchestration."""

    return ImplementStepRuntimeDependencies(
        describe_action=describe_action,
        failure_dependencies=ImplementStepFailureDependencies(
            classify_backend_exception=classify_backend_exception,
            should_handle_backend_exception=should_handle_backend_exception,
            format_failed_backend_output=format_failed_backend_output,
        ),
        ensure_progress_artifacts=_ensure_progress_artifacts,
        repo_relative_label=repo_relative_label,
        output_dependencies=ImplementStepOutputDependencies(
            emit_step_start=_emit_implement_step_start,
            emit_output=_emit_implement_output,
        ),
    )


def run_implement_step(
    project_root: Path,
    feature: dict[str, Any],
    feature_path: Path,
    feedback: str | None,
    verbose_output: bool,
) -> ImplementStepResult:
    """Run the implement phase for one loop iteration."""
    implement_inputs = ImplementStepInputs(
        project_root=project_root,
        feature=feature,
        feature_path=feature_path,
        feedback=feedback,
        verbose_output=verbose_output,
    )
    return run_implement_step_from_inputs(
        implement_inputs,
        agent_runner=_build_agent_runner(project_root),
        prompt_builder=_build_prompt_builder(project_root),
        progress_journal=_build_progress_journal(project_root),
        runtime_dependencies=build_implement_step_runtime_dependencies(),
    )


def _build_version_control_gateway(_project_root: Path) -> GitCliVersionControlGateway:
    return GitCliVersionControlGateway()


def _build_agent_runner(_project_root: Path) -> ConfiguredAgentRunner:
    return ConfiguredAgentRunner(run_agent_fn=agent_runtime.run_agent)


def _build_prompt_builder(project_root: Path) -> PromptBuilder:
    config = load_repository_config(project_root)
    prompt_repository = FilesystemPromptDefinitionRepository(
        resolve_harness_root(project_root) / "prompts"
    )
    return PromptBuilder(
        prompt_repository,
        implementation_prompt_id=config.agents.implementation.prompt_definition,
    )


def _build_progress_journal(_project_root: Path) -> FilesystemProgressJournal:
    return FilesystemProgressJournal()


def _ensure_progress_artifacts(implement_inputs: ImplementStepInputs) -> None:
    project_root = implement_inputs.project_root
    feature_id = implement_inputs.feature.get("id")
    if not isinstance(feature_id, str) or not feature_id.strip():
        feature_id = "unknown-feature"

    progress_paths.runs_dir(project_root).mkdir(parents=True, exist_ok=True)
    progress_paths.runs_jsonl_path(project_root).touch(exist_ok=True)


def _emit_implement_step_start(command: str) -> None:
    print(f"Implement step: {command}", flush=True)


def _emit_implement_output(output: str) -> None:
    print(output, end="" if output.endswith("\n") else "\n")


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
