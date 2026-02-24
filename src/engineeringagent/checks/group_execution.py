from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, cast

import yaml

from pydantic import BaseModel, ConfigDict

from engineeringagent.changed_paths import ChangedPathsResult, collect_changed_paths
from engineeringagent.checks.commands.runtime import (
    CommandInvocationRecord,
    RunPlannedCommandChecksRequest,
    run_planned_command_checks,
)
from engineeringagent.checks.fitness.runtime import (
    RunPlannedFitnessChecksRequest,
    run_planned_fitness_checks,
)
from engineeringagent.checks.request_normalization import (
    CHECK_GROUP_COMMANDS,
    CHECK_GROUP_FITNESS,
    CHECK_GROUP_REVIEWERS,
    CHECK_GROUP_VALIDATE,
    RunChecksRequest,
)
from engineeringagent.checks.reviewers.runtime import (
    RunPlannedReviewerChecksRequest,
    run_planned_reviewer_checks,
)
from engineeringagent.checks.validate import runtime as validate_runtime
from engineeringagent.specs import HarnessCheckCommandDefinition, load_yaml


class GroupRunResult(BaseModel):
    """Result payload returned by a single checks group execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool
    failed_check_id: str | None
    output: str
    failed_payload: dict[str, Any] | None = None
    command_invocations: tuple[CommandInvocationRecord, ...] = ()


class ExecuteGroupsResult(BaseModel):
    """Aggregated output across ordered checks groups."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool
    failed_group: str | None = None
    failed_check_id: str | None = None
    failed_payload: dict[str, Any] | None = None
    output: str = ""
    command_invocations: tuple[CommandInvocationRecord, ...] = ()


def _command_for_check_id(doc: Any, check_id: str | None) -> str:
    if not check_id:
        return "<unknown>"

    check = getattr(doc, "checks", {}).get(check_id)
    if isinstance(check, HarnessCheckCommandDefinition):
        command = check.command
        if isinstance(command, str) and command.strip():
            return command
    return "<unknown>"


def call_collect_changed_paths(
    fn: Callable[..., object],
    project_root: Path,
    *,
    base: str | None,
    head: str | None,
) -> object:
    """Call collect_changed_paths with optional base/head compatibility."""
    kwargs: dict[str, str] = {}
    if base is not None:
        kwargs["base"] = base
    if head is not None:
        kwargs["head"] = head
    if not kwargs:
        return fn(project_root)
    try:
        return fn(project_root, **kwargs)
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        return fn(project_root)


def resolve_changed_paths(
    project_root: Path, request: RunChecksRequest
) -> ChangedPathsResult:
    """Resolve changed paths using injected collector when provided."""
    collect_changed_paths_fn = request.collect_changed_paths_fn or collect_changed_paths
    return cast(
        ChangedPathsResult,
        call_collect_changed_paths(
            collect_changed_paths_fn,
            project_root,
            base=request.base,
            head=request.head,
        ),
    )


def run_validate_group(project_root: Path, *, schema_only: bool) -> GroupRunResult:
    """Execute validate checks group."""
    messages = validate_runtime.run_validate(project_root, schema_only=schema_only)
    if not messages:
        return GroupRunResult(ok=True, failed_check_id=None, output="")
    return GroupRunResult(
        ok=False,
        failed_check_id=None,
        output="\n".join(messages).strip(),
        failed_payload={
            "kind": "validate_failure",
            "messages": list(messages),
        },
    )


def run_commands_group(
    project_root: Path, doc: Any, request: RunChecksRequest
) -> GroupRunResult:
    """Execute commands checks group."""
    changed_paths = resolve_changed_paths(project_root, request)
    run_request = RunPlannedCommandChecksRequest(
        project_root=project_root,
        doc=doc,
        phase=request.phase,
        changed_paths=changed_paths,
        verbose_output=request.verbose_output,
    )
    run_result = run_planned_command_checks(run_request)
    failed_payload = None
    if not run_result.ok:
        command = _command_for_check_id(doc, run_result.failed_check_id)
        failed_payload = {
            "kind": "command_failure",
            "check_id": run_result.failed_check_id,
            "command": command,
        }

    return GroupRunResult(
        ok=run_result.ok,
        failed_check_id=run_result.failed_check_id,
        output=run_result.output,
        failed_payload=failed_payload,
        command_invocations=run_result.command_invocations,
    )


def run_fitness_group(
    project_root: Path, doc: Any, request: RunChecksRequest
) -> GroupRunResult:
    """Execute fitness checks group."""
    changed_paths = resolve_changed_paths(project_root, request)

    run_request = RunPlannedFitnessChecksRequest(
        project_root=project_root,
        doc=doc,
        phase=request.phase,
        changed_paths=changed_paths,
    )
    ok, failed_id, output, failed_payload = run_planned_fitness_checks(run_request)
    return GroupRunResult(
        ok=ok,
        failed_check_id=failed_id,
        output=output,
        failed_payload=failed_payload,
    )


def run_reviewers_group(
    project_root: Path, doc: Any, request: RunChecksRequest
) -> GroupRunResult:
    """Execute reviewers checks group."""
    if request.feature_path is None:
        return GroupRunResult(
            ok=False,
            failed_check_id=None,
            output="reviewers config error: feature_path is required",
        )
    if not request.feature_path.exists():
        return GroupRunResult(
            ok=False,
            failed_check_id=None,
            output=(
                "reviewers config error: feature spec not found: "
                f"{request.feature_path}"
            ),
        )

    try:
        feature_payload = load_yaml(request.feature_path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return GroupRunResult(
            ok=False,
            failed_check_id=None,
            output=f"reviewers config error: failed to load feature spec: {exc}",
        )
    feature_id = ""
    if isinstance(feature_payload, dict):
        feature_id = str(feature_payload.get("id", "")).strip()
    if not feature_id:
        return GroupRunResult(
            ok=False,
            failed_check_id=None,
            output="reviewers config error: feature spec is missing required id",
        )

    changed_paths = resolve_changed_paths(project_root, request)
    run_request = RunPlannedReviewerChecksRequest(
        project_root=project_root,
        doc=doc,
        phase=request.phase,
        changed_paths=changed_paths,
        feature_id=feature_id,
        feature_path=request.feature_path,
        run_agent_fn=request.run_agent_fn,
        prior_feedback=request.prior_feedback,
    )
    ok, failed_id, output, failed_payload = run_planned_reviewer_checks(run_request)
    return GroupRunResult(
        ok=ok,
        failed_check_id=failed_id,
        output=output,
        failed_payload=failed_payload,
    )


class GroupRunners(BaseModel):
    """Injectable checks group executors used by orchestration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_validate_group: Callable[..., GroupRunResult] = run_validate_group
    run_commands_group: Callable[..., GroupRunResult] = run_commands_group
    run_fitness_group: Callable[..., GroupRunResult] = run_fitness_group
    run_reviewers_group: Callable[..., GroupRunResult] = run_reviewers_group


def execute_groups(
    *,
    project_root: Path,
    doc: Any | None,
    request: RunChecksRequest,
    runners: GroupRunners | None = None,
) -> ExecuteGroupsResult:
    """Execute requested groups in deterministic order and aggregate result."""
    group_runners = runners or GroupRunners()
    outputs: list[str] = []
    command_invocations: list[CommandInvocationRecord] = []
    for group in request.ordered_groups:
        if group == CHECK_GROUP_VALIDATE:
            group_result = group_runners.run_validate_group(
                project_root,
                schema_only=request.schema_only,
            )
        elif group == CHECK_GROUP_COMMANDS:
            group_result = group_runners.run_commands_group(project_root, doc, request)
        elif group == CHECK_GROUP_FITNESS:
            group_result = group_runners.run_fitness_group(project_root, doc, request)
        elif group == CHECK_GROUP_REVIEWERS:
            group_result = group_runners.run_reviewers_group(project_root, doc, request)
        else:  # pragma: no cover
            raise RuntimeError(f"unreachable checks group: {group}")

        if group_result.output:
            outputs.append(group_result.output)
        command_invocations.extend(group_result.command_invocations)
        if not group_result.ok:
            return ExecuteGroupsResult(
                ok=False,
                failed_group=group,
                failed_check_id=group_result.failed_check_id,
                failed_payload=group_result.failed_payload,
                output="\n".join(outputs).strip(),
                command_invocations=tuple(command_invocations),
            )

    return ExecuteGroupsResult(
        ok=True,
        output="\n".join(outputs).strip(),
        command_invocations=tuple(command_invocations),
    )
