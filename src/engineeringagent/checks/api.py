from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, TypedDict, cast

import yaml

from pydantic import BaseModel, ConfigDict, ValidationError
from typing_extensions import Unpack

from engineeringagent.changed_paths import ChangedPathsResult, collect_changed_paths
from engineeringagent.checks.commands.runtime import (
    RunPlannedCommandChecksRequest,
    run_planned_command_checks,
)
from engineeringagent.checks.fitness.runtime import (
    RunPlannedFitnessChecksRequest,
    run_planned_fitness_checks,
)
from engineeringagent.checks.reviewers.runtime import (
    RunPlannedReviewerChecksRequest,
    run_planned_reviewer_checks,
)
from engineeringagent.checks.validate import runtime as validate_runtime
from engineeringagent.specs import (
    HarnessCheckCommandDefinition,
    HarnessCheckFitnessDefinition,
    HarnessCheckPhase,
    HarnessCheckReviewerDefinition,
    HarnessChecksDocument,
    checks_contract_issues,
    load_yaml,
)

from engineeringagent.process import run_shell_command


_CHECK_GROUP_VALIDATE = "validate"
_CHECK_GROUP_COMMANDS = "commands"
_CHECK_GROUP_FITNESS = "fitness"
_CHECK_GROUP_REVIEWERS = "reviewers"

_ALLOWED_GROUPS = {
    _CHECK_GROUP_VALIDATE,
    _CHECK_GROUP_COMMANDS,
    _CHECK_GROUP_FITNESS,
    _CHECK_GROUP_REVIEWERS,
}
_GROUP_ORDER = (
    _CHECK_GROUP_VALIDATE,
    _CHECK_GROUP_COMMANDS,
    _CHECK_GROUP_FITNESS,
    _CHECK_GROUP_REVIEWERS,
)
_DEFAULT_GROUPS = (
    _CHECK_GROUP_COMMANDS,
    _CHECK_GROUP_FITNESS,
)


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


def _command_for_check_id(doc: Any, check_id: str | None) -> str:
    if not check_id:
        return "<unknown>"

    check = getattr(doc, "checks", {}).get(check_id)
    if isinstance(check, HarnessCheckCommandDefinition):
        command = check.command
        if isinstance(command, str) and command.strip():
            return command
    return "<unknown>"


class _RunChecksRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        arbitrary_types_allowed=True,
    )

    phase: Any
    ordered_groups: tuple[str, ...]
    check_id: str | None
    feature_path: Path | None
    verbose_output: bool
    base: str | None
    head: str | None
    run_agent_fn: Callable[..., object] | None
    prior_feedback: str | None
    schema_only: bool
    collect_changed_paths_fn: Callable[..., object] | None
    run_shell_command_fn: Callable[..., object] | None


class _RunChecksKwargs(TypedDict, total=False):
    check_id: str | None
    feature_path: str | Path | None
    verbose_output: bool
    base: str | None
    head: str | None
    run_agent_fn: Callable[..., object] | None
    prior_feedback: str | None
    schema_only: bool
    collect_changed_paths: Callable[..., object] | None
    run_shell_command: Callable[..., object] | None


class _GroupRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool
    failed_check_id: str | None
    output: str
    failed_payload: dict[str, Any] | None = None


def _normalize_groups(checks: list[str] | None) -> tuple[str, ...]:
    requested = list(checks) if checks is not None else list(_DEFAULT_GROUPS)
    normalized: list[str] = []
    for group in requested:
        value = str(group or "").strip()
        if value:
            normalized.append(value)

    invalid = sorted({group for group in normalized if group not in _ALLOWED_GROUPS})
    if invalid:
        raise ValueError(
            f"unknown checks groups: {invalid}. Supported: {sorted(_ALLOWED_GROUPS)}"
        )

    deduped: list[str] = []
    seen: set[str] = set()
    for group in normalized:
        if group in seen:
            continue
        seen.add(group)
        deduped.append(group)

    return tuple(group for group in _GROUP_ORDER if group in deduped)


def _coerce_project_root(project_root: str | Path) -> Path:
    return Path(project_root).resolve()


def _coerce_phase(phase: Any) -> Any:
    if isinstance(phase, HarnessCheckPhase):
        return phase
    raw = str(phase or "").strip()
    try:
        return HarnessCheckPhase(raw)
    except ValueError as exc:
        raise ValueError(
            "unknown phase; expected one of: iteration_end|feature_done|manual"
        ) from exc


def _call_collect_changed_paths(
    fn: Callable[..., object],
    project_root: Path,
    *,
    base: str | None,
    head: str | None,
) -> object:
    """Call collect_changed_paths with optional base/head.

    The loop runtime wires a memoized collector that only accepts a single
    positional argument; checks must tolerate that narrower callable.
    """

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
        # Only fallback for the known compatibility case where callers inject
        # base/head but the collector only accepts a single positional argument.
        if "unexpected keyword argument" not in str(exc):
            raise
        return fn(project_root)


def _load_harness_checks_doc(project_root: Path) -> tuple[Any | None, str | None]:
    checks_path = project_root / "harness" / "checks.yaml"
    if not checks_path.exists():
        return (
            None,
            "checks config error: missing harness/checks.yaml. "
            "Remediation: run `engineeringagent init`.",
        )

    try:
        payload = load_yaml(checks_path)
        issues = checks_contract_issues(payload, checks_path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return None, f"checks config error: failed to load harness/checks.yaml: {exc}"
    if issues:
        rendered = "\n".join(f"- {issue.path}: {issue.message}" for issue in issues)
        return (
            None,
            f"checks config error: invalid harness/checks.yaml\n{rendered}",
        )

    try:
        doc = HarnessChecksDocument.model_validate(payload)
    except ValidationError as exc:
        return (
            None,
            f"checks config error: failed to validate harness/checks.yaml: {exc}",
        )

    return doc, None


def _resolve_check_group_for_id(doc: Any, check_id: str) -> str | None:
    check = getattr(doc, "checks", {}).get(check_id)
    if isinstance(check, HarnessCheckCommandDefinition):
        return _CHECK_GROUP_COMMANDS
    if isinstance(check, HarnessCheckFitnessDefinition):
        return _CHECK_GROUP_FITNESS
    if isinstance(check, HarnessCheckReviewerDefinition):
        return _CHECK_GROUP_REVIEWERS
    return None


def _filter_doc_to_check_id(doc: Any, check_id: str) -> Any:
    check = getattr(doc, "checks", {}).get(check_id)
    if check is None:
        return doc
    return doc.model_copy(update={"checks": {check_id: check}})


def _requires_harness_doc(ordered_groups: tuple[str, ...]) -> bool:
    harness_groups = {
        _CHECK_GROUP_COMMANDS,
        _CHECK_GROUP_FITNESS,
        _CHECK_GROUP_REVIEWERS,
    }
    return any(group in harness_groups for group in ordered_groups)


def _apply_check_id_selection(
    *,
    doc: Any | None,
    request: _RunChecksRequest,
) -> tuple[Any | None, ChecksRunResult | None]:
    if request.check_id is None:
        return doc, None
    if doc is None:
        output = "unknown check_id: no harness checks document loaded"
        return (
            None,
            _failure_result(
                group="selection",
                check_id=request.check_id,
                output=output,
                payload={
                    "kind": "selection_error",
                    "message": output,
                    "check_id": request.check_id,
                },
            ),
        )

    harness_groups = {
        _CHECK_GROUP_COMMANDS,
        _CHECK_GROUP_FITNESS,
        _CHECK_GROUP_REVIEWERS,
    }
    resolved_group = _resolve_check_group_for_id(doc, request.check_id)
    if resolved_group is None or resolved_group not in request.ordered_groups:
        enabled = [group for group in request.ordered_groups if group in harness_groups]
        output = (
            "unknown check_id for enabled groups: "
            f"check_id={request.check_id} enabled_groups={enabled}"
        )
        return (
            None,
            _failure_result(
                group="selection",
                check_id=request.check_id,
                output=output,
                payload={
                    "kind": "selection_error",
                    "message": output,
                    "check_id": request.check_id,
                },
            ),
        )

    return _filter_doc_to_check_id(doc, request.check_id), None


def _run_validate_group(project_root: Path, *, schema_only: bool) -> _GroupRunResult:
    messages = validate_runtime.run_validate(project_root, schema_only=schema_only)
    if not messages:
        return _GroupRunResult(ok=True, failed_check_id=None, output="")
    return _GroupRunResult(
        ok=False,
        failed_check_id=None,
        output="\n".join(messages).strip(),
        failed_payload={
            "kind": "validate_failure",
            "messages": list(messages),
        },
    )


def _run_commands_group(
    project_root: Path,
    doc: Any,
    request: _RunChecksRequest,
) -> _GroupRunResult:

    collect_changed_paths_fn = request.collect_changed_paths_fn or collect_changed_paths
    changed_paths = cast(
        ChangedPathsResult,
        _call_collect_changed_paths(
            collect_changed_paths_fn,
            project_root,
            base=request.base,
            head=request.head,
        ),
    )
    run_request = RunPlannedCommandChecksRequest(
        project_root=project_root,
        doc=doc,
        phase=request.phase,
        changed_paths=changed_paths,
        verbose_output=request.verbose_output,
    )
    run_shell_command_fn = request.run_shell_command_fn or run_shell_command
    ok, failed_id, output = run_planned_command_checks(
        run_request,
        run_shell_command=run_shell_command_fn,
    )
    failed_payload = None
    if not ok:
        command = _command_for_check_id(doc, failed_id)
        failed_payload = {
            "kind": "command_failure",
            "check_id": failed_id,
            "command": command,
        }

    return _GroupRunResult(
        ok=ok,
        failed_check_id=failed_id,
        output=output,
        failed_payload=failed_payload,
    )


def _run_fitness_group(
    project_root: Path,
    doc: Any,
    request: _RunChecksRequest,
) -> _GroupRunResult:

    collect_changed_paths_fn = request.collect_changed_paths_fn or collect_changed_paths
    changed_paths = cast(
        ChangedPathsResult,
        _call_collect_changed_paths(
            collect_changed_paths_fn,
            project_root,
            base=request.base,
            head=request.head,
        ),
    )

    run_request = RunPlannedFitnessChecksRequest(
        project_root=project_root,
        doc=doc,
        phase=request.phase,
        changed_paths=changed_paths,
    )
    ok, failed_id, output, failed_payload = run_planned_fitness_checks(run_request)
    return _GroupRunResult(
        ok=ok,
        failed_check_id=failed_id,
        output=output,
        failed_payload=failed_payload,
    )


def _run_reviewers_group(
    project_root: Path,
    doc: Any,
    request: _RunChecksRequest,
) -> _GroupRunResult:

    if request.feature_path is None:
        return _GroupRunResult(
            ok=False,
            failed_check_id=None,
            output="reviewers config error: feature_path is required",
        )
    if not request.feature_path.exists():
        return _GroupRunResult(
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
        return _GroupRunResult(
            ok=False,
            failed_check_id=None,
            output=f"reviewers config error: failed to load feature spec: {exc}",
        )
    feature_id = ""
    if isinstance(feature_payload, dict):
        feature_id = str(feature_payload.get("id", "")).strip()
    if not feature_id:
        return _GroupRunResult(
            ok=False,
            failed_check_id=None,
            output="reviewers config error: feature spec is missing required id",
        )

    collect_changed_paths_fn = request.collect_changed_paths_fn or collect_changed_paths
    changed_paths = cast(
        ChangedPathsResult,
        _call_collect_changed_paths(
            collect_changed_paths_fn,
            project_root,
            base=request.base,
            head=request.head,
        ),
    )
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
    return _GroupRunResult(
        ok=ok,
        failed_check_id=failed_id,
        output=output,
        failed_payload=failed_payload,
    )


def _execute_groups(
    *,
    project_root: Path,
    doc: Any | None,
    request: _RunChecksRequest,
) -> ChecksRunResult:
    outputs: list[str] = []
    for group in request.ordered_groups:
        if group == _CHECK_GROUP_VALIDATE:
            group_result = _run_validate_group(
                project_root,
                schema_only=request.schema_only,
            )
        elif group == _CHECK_GROUP_COMMANDS:
            group_result = _run_commands_group(project_root, doc, request)
        elif group == _CHECK_GROUP_FITNESS:
            group_result = _run_fitness_group(project_root, doc, request)
        elif group == _CHECK_GROUP_REVIEWERS:
            group_result = _run_reviewers_group(project_root, doc, request)
        else:  # pragma: no cover
            raise RuntimeError(f"unreachable checks group: {group}")

        if group_result.output:
            outputs.append(group_result.output)
        if not group_result.ok:
            return ChecksRunResult(
                ok=False,
                failed_group=group,
                failed_check_id=group_result.failed_check_id,
                failed_payload=group_result.failed_payload,
                output="\n".join(outputs).strip(),
            )

    return ChecksRunResult(ok=True, output="\n".join(outputs).strip())


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
    root = _coerce_project_root(project_root)
    ordered_groups = _normalize_groups(checks)

    allowed_kwargs = {
        "check_id",
        "feature_path",
        "verbose_output",
        "base",
        "head",
        "run_agent_fn",
        "prior_feedback",
        "schema_only",
        "collect_changed_paths",
        "run_shell_command",
    }
    unexpected = sorted(set(kwargs) - allowed_kwargs)
    if unexpected:
        # Mirror Python's typical error shape for unexpected keyword args.
        raise TypeError(
            f"run_checks() got an unexpected keyword argument '{unexpected[0]}'"
        )

    check_id = kwargs.get("check_id")
    feature_path = kwargs.get("feature_path")
    verbose_output = bool(kwargs.get("verbose_output", False))
    base = kwargs.get("base")
    head = kwargs.get("head")
    run_agent_fn = kwargs.get("run_agent_fn")
    prior_feedback = kwargs.get("prior_feedback")
    schema_only = bool(kwargs.get("schema_only", False))
    collect_changed_paths_fn = kwargs.get("collect_changed_paths")
    run_shell_command_fn = kwargs.get("run_shell_command")

    if schema_only and _CHECK_GROUP_VALIDATE not in ordered_groups:
        raise ValueError("schema_only requires the validate checks group")

    if _CHECK_GROUP_REVIEWERS in ordered_groups and feature_path is None:
        raise ValueError("feature_path is required when reviewers checks are selected")

    request = _RunChecksRequest(
        phase=_coerce_phase(phase),
        ordered_groups=ordered_groups,
        check_id=check_id,
        feature_path=Path(feature_path).resolve() if feature_path is not None else None,
        verbose_output=verbose_output,
        base=base,
        head=head,
        run_agent_fn=run_agent_fn,
        prior_feedback=str(prior_feedback) if prior_feedback is not None else None,
        schema_only=schema_only,
        collect_changed_paths_fn=collect_changed_paths_fn,
        run_shell_command_fn=run_shell_command_fn,
    )

    doc = None
    if _requires_harness_doc(request.ordered_groups):
        doc, doc_error = _load_harness_checks_doc(root)
        if doc_error is not None:
            return _failure_result(
                group="config",
                check_id=request.check_id,
                output=doc_error,
                payload={
                    "kind": "config_error",
                    "message": doc_error,
                },
            )

    doc, selection_result = _apply_check_id_selection(doc=doc, request=request)
    if selection_result is not None:
        return selection_result

    return _execute_groups(project_root=root, doc=doc, request=request)
