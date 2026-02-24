from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict
from typing_extensions import Unpack

from engineeringagent.checks.commands.runtime import (
    CommandInvocationRecord,
)
from engineeringagent.checks.config_selection import (
    load_selected_harness_checks_document,
)
from engineeringagent.checks.group_execution import (
    GroupRunResult as _GroupRunResult,
    GroupRunners as _GroupRunners,
    call_collect_changed_paths as _call_collect_changed_paths,
    execute_groups as _execute_groups_internal,
    resolve_changed_paths as _resolve_changed_paths,
    run_commands_group as _run_commands_group,
    run_fitness_group as _run_fitness_group,
    run_reviewers_group as _run_reviewers_group,
    run_validate_group as _run_validate_group,
)
from engineeringagent.checks.request_normalization import (
    RunChecksKwargs as _RunChecksKwargs,
    RunChecksRequest as _RunChecksRequest,
    build_run_checks_request,
)

__all__ = [
    "ChecksRunResult",
    "run_checks",
    "_GroupRunResult",
    "_RunChecksRequest",
    "_call_collect_changed_paths",
    "_resolve_changed_paths",
]


class ChecksRunResult(BaseModel):
    """Structured result for a checks run.

    This contract is intentionally small and will expand as the migration
    progresses. For now, it primarily signals success/failure and preserves
    deterministic human-readable output for CLI parity.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool
    failed_group: str | None = None
    failed_check_id: str | None = None
    failed_payload: dict[str, Any] | None = None
    output: str = ""
    command_invocations: tuple[CommandInvocationRecord, ...] = ()


def _failure_result(
    *,
    group: str,
    check_id: str | None,
    output: str,
    payload: dict[str, Any] | None,
) -> ChecksRunResult:
    return ChecksRunResult(
        ok=False,
        failed_group=group,
        failed_check_id=check_id,
        failed_payload=payload,
        output=output,
    )


def _execute_groups(
    *,
    project_root: Path,
    doc: Any | None,
    request: _RunChecksRequest,
) -> ChecksRunResult:
    aggregate = _execute_groups_internal(
        project_root=project_root,
        doc=doc,
        request=request,
        runners=_GroupRunners(
            run_validate_group=_run_validate_group,
            run_commands_group=_run_commands_group,
            run_fitness_group=_run_fitness_group,
            run_reviewers_group=_run_reviewers_group,
        ),
    )
    return ChecksRunResult(
        ok=aggregate.ok,
        failed_group=aggregate.failed_group,
        failed_check_id=aggregate.failed_check_id,
        failed_payload=aggregate.failed_payload,
        output=aggregate.output,
        command_invocations=aggregate.command_invocations,
    )


def run_checks(
    project_root: str | Path,
    *,
    phase: str,
    checks: list[str] | None = None,
    **kwargs: Unpack[_RunChecksKwargs],
) -> ChecksRunResult:
    """Plan and run deterministic checks.

    Args:
        project_root: Repository root for the run.
        phase: Execution phase identifier (used for deterministic policy decisions).
        checks: Optional list of enabled check groups.
        **kwargs: Keyword-only options.

            Supported keys:
            - check_id: Optional single-check selection.
            - feature_path: Feature spec path required for reviewer execution.
            - verbose_output: Whether to stream verbose command output.
            - base: Optional base revision for diff-based checks.
            - head: Optional head revision for diff-based checks.
            - run_agent_fn: Optional injected callable to execute reviewers.

    Returns:
        Structured result indicating overall success/failure.
    """
    root, request = build_run_checks_request(
        project_root,
        phase=phase,
        checks=checks,
        kwargs=cast(_RunChecksKwargs, kwargs),
    )

    doc, config_or_selection_error = load_selected_harness_checks_document(
        root,
        request=request,
    )
    if config_or_selection_error is not None:
        return _failure_result(
            group=config_or_selection_error.group,
            check_id=config_or_selection_error.check_id,
            output=config_or_selection_error.output,
            payload=config_or_selection_error.payload,
        )

    return _execute_groups(project_root=root, doc=doc, request=request)
