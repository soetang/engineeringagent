from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Callable, cast

from pydantic import BaseModel, ConfigDict
from typing_extensions import Unpack

from engineeringagent.changed_paths import ChangedPathsResult, collect_changed_paths
from engineeringagent.checks.commands.runtime import (
    CommandInvocationRecord,
)
from engineeringagent.checks.config_selection import (
    load_selected_harness_checks_document,
)
from engineeringagent.checks.request_normalization import (
    CHECK_GROUP_COMMANDS,
    CHECK_GROUP_FITNESS,
    CHECK_GROUP_REVIEWERS,
    CHECK_GROUP_VALIDATE,
    RunChecksKwargs as _RunChecksKwargs,
    RunChecksRequest as _RunChecksRequest,
    build_run_checks_request,
)
from engineeringagent.checks.strategies import (
    CommandCheckStrategy,
    FitnessCheckStrategy,
    ReviewerCheckStrategy,
    ValidateCheckStrategy,
)
from engineeringagent.checks.strategy_contracts import (
    CheckContext,
    CheckDecision,
    CheckExecutionRecord,
    CheckStrategy,
    build_strategy_registry,
)
from engineeringagent.prompt_feedback import normalize_checks_contract_prompt_feedback

__all__ = [
    "ChecksRunResult",
    "run_checks",
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
    dry_run: bool = False
    failed_check_id: str | None = None
    failed_payload: dict[str, Any] | None = None
    output: str = ""
    decisions: tuple[CheckDecision, ...] = ()
    executions: tuple[CheckExecutionRecord, ...] = ()
    prompt_feedback: str | None = None
    command_invocations: tuple[CommandInvocationRecord, ...] = ()


class _OrchestrationState:
    outputs: list[str]
    decisions: list[CheckDecision]
    executions: list[CheckExecutionRecord]
    command_invocations: list[CommandInvocationRecord]

    def __init__(self) -> None:
        self.outputs = []
        self.decisions = []
        self.executions = []
        self.command_invocations = []


def _supports_collect_changed_paths_kwargs(
    fn: Callable[..., object],
    *,
    keyword_names: tuple[str, ...],
) -> bool:
    """Return whether ``fn`` accepts all provided keyword names."""

    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        return False

    parameters = signature.parameters
    if any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    ):
        return True

    supported_kinds = {
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    }
    for keyword_name in keyword_names:
        parameter = parameters.get(keyword_name)
        if parameter is None or parameter.kind not in supported_kinds:
            return False
    return True


def _call_collect_changed_paths(
    fn: Callable[..., object],
    project_root: Path,
    *,
    base: str | None,
    head: str | None,
) -> object:
    kwargs: dict[str, str] = {}
    if base is not None:
        kwargs["base"] = base
    if head is not None:
        kwargs["head"] = head
    if not kwargs:
        return fn(project_root)

    if _supports_collect_changed_paths_kwargs(
        fn,
        keyword_names=tuple(kwargs),
    ):
        return fn(project_root, **kwargs)

    return fn(project_root)


def _resolve_changed_paths(
    project_root: Path,
    request: _RunChecksRequest,
) -> ChangedPathsResult:
    collect_changed_paths_fn = request.collect_changed_paths_fn or collect_changed_paths
    return cast(
        ChangedPathsResult,
        _call_collect_changed_paths(
            collect_changed_paths_fn,
            project_root,
            base=request.base,
            head=request.head,
        ),
    )


def _finalize_checks_run_result(
    *,
    ok: bool,
    dry_run: bool,
    result_fields: dict[str, Any] | None = None,
) -> ChecksRunResult:
    """Build one normalized checks-run result contract record."""

    fields: dict[str, Any] = {
        "failed_check_id": None,
        "failed_payload": None,
        "output": "",
        "decisions": (),
        "executions": (),
        "prompt_feedback": None,
        "command_invocations": (),
    }
    if result_fields is not None:
        fields.update(result_fields)

    fields["prompt_feedback"] = normalize_checks_contract_prompt_feedback(
        cast(str | None, fields.get("prompt_feedback")),
    )
    return ChecksRunResult(
        ok=ok,
        dry_run=dry_run,
        **fields,
    )


def _extract_command_invocation(
    record: CheckExecutionRecord,
) -> CommandInvocationRecord | None:
    timing = record.timing
    if not isinstance(timing, dict):
        return None
    raw = timing.get("command_invocation")
    if not isinstance(raw, dict):
        return None
    try:
        return CommandInvocationRecord(**raw)
    except (TypeError, ValueError):
        return None


def _append_execution_record(
    *,
    state: _OrchestrationState,
    record: CheckExecutionRecord,
) -> None:
    """Record execution output and command timing metadata."""

    state.executions.append(record)
    if record.output:
        state.outputs.append(record.output)
    invocation = _extract_command_invocation(record)
    if invocation is not None:
        state.command_invocations.append(invocation)


def _finalize_orchestration_result(
    *,
    state: _OrchestrationState,
    ok: bool,
    dry_run: bool,
    failed_record: CheckExecutionRecord | None = None,
    prompt_feedback: str | None = None,
) -> ChecksRunResult:
    return _finalize_checks_run_result(
        ok=ok,
        dry_run=dry_run,
        result_fields=_result_fields_from_orchestration_state(
            state=state,
            dry_run=dry_run,
            failed_record=failed_record,
            prompt_feedback=prompt_feedback,
        ),
    )


def _result_fields_from_orchestration_state(
    *,
    state: _OrchestrationState,
    dry_run: bool,
    failed_record: CheckExecutionRecord | None,
    prompt_feedback: str | None,
) -> dict[str, Any]:
    """Build deterministic result fields from strategy orchestration state."""

    output = _compose_output(
        decisions=state.decisions,
        outputs=state.outputs,
        dry_run=dry_run,
    )

    return {
        "output": output,
        "decisions": tuple(state.decisions),
        "executions": tuple(state.executions),
        "command_invocations": tuple(state.command_invocations),
        "failed_check_id": failed_record.check_id
        if failed_record is not None
        else None,
        "failed_payload": failed_record.payload if failed_record is not None else None,
        "prompt_feedback": prompt_feedback,
    }


def _render_decision_trace(decisions: list[CheckDecision]) -> str:
    lines: list[str] = []
    for decision in decisions:
        lines.append(
            " ".join(
                (
                    f"[decision:{decision['check_id']}]",
                    f"type={decision['check_type']}",
                    f"phase={decision['phase']}",
                    f"decision={decision['decision']}",
                    f"reason={decision['reason']}",
                )
            )
        )
    return "\n".join(lines).strip()


def _compose_output(
    *,
    decisions: list[CheckDecision],
    outputs: list[str],
    dry_run: bool,
) -> str:
    decision_trace = _render_decision_trace(decisions)
    if dry_run:
        return decision_trace
    execution_output = "\n".join(outputs).strip()
    if not execution_output:
        return decision_trace
    return "\n".join(
        part for part in (execution_output, decision_trace) if part
    ).strip()


_GROUP_TO_STRATEGY_TYPE = {
    CHECK_GROUP_VALIDATE: "validate",
    CHECK_GROUP_COMMANDS: "command",
    CHECK_GROUP_FITNESS: "fitness",
    CHECK_GROUP_REVIEWERS: "reviewer",
}


def _build_strategy_registry(
    *,
    doc: Any | None,
    request: _RunChecksRequest,
) -> dict[str, CheckStrategy]:
    strategies: list[CheckStrategy] = [
        ValidateCheckStrategy(schema_only=request.schema_only),
    ]
    if doc is not None:
        strategies.extend(
            [
                CommandCheckStrategy(
                    doc=doc,
                    verbose_output=request.verbose_output,
                ),
                FitnessCheckStrategy(doc=doc),
                ReviewerCheckStrategy(doc=doc),
            ]
        )
    return build_strategy_registry(strategies)


def _append_strategy_result(
    *,
    strategy: CheckStrategy,
    context: CheckContext,
    request: _RunChecksRequest,
    state: _OrchestrationState,
) -> tuple[CheckExecutionRecord | None, str | None]:
    strategy_decisions = strategy.plan(context=context)
    state.decisions.extend(strategy_decisions)

    if request.dry_run:
        return None, None

    strategy_executions = strategy.execute(
        context=context,
        decisions=strategy_decisions,
    )
    for record in strategy_executions:
        _append_execution_record(state=state, record=record)
        if record.ok:
            continue
        return (
            record,
            strategy.render_prompt_feedback(
                failed_record=record,
            ),
        )
    return None, None


def _build_check_context(
    *,
    project_root: Path,
    request: _RunChecksRequest,
) -> CheckContext:
    """Build shared checks context from normalized request fields."""

    return CheckContext(
        project_root=project_root,
        phase=request.phase,
        changed_paths=_resolve_changed_paths(project_root, request),
        feature_path=request.feature_path,
        feedback=request.feedback,
        run_agent_fn=request.run_agent_fn,
        verbose_output=request.verbose_output,
    )


def _ordered_request_strategies(
    *,
    request: _RunChecksRequest,
    strategy_registry: dict[str, CheckStrategy],
) -> tuple[CheckStrategy, ...]:
    """Return deterministic strategy order for the selected checks groups."""

    return tuple(
        strategy_registry[_GROUP_TO_STRATEGY_TYPE[group]]
        for group in request.ordered_groups
    )


def _execute_with_strategy_orchestration(
    *,
    project_root: Path,
    doc: Any | None,
    request: _RunChecksRequest,
) -> ChecksRunResult:
    state = _OrchestrationState()

    strategy_registry = _build_strategy_registry(doc=doc, request=request)
    context = _build_check_context(project_root=project_root, request=request)

    for strategy in _ordered_request_strategies(
        request=request,
        strategy_registry=strategy_registry,
    ):
        failed_record, prompt_feedback = _append_strategy_result(
            strategy=strategy,
            context=context,
            request=request,
            state=state,
        )
        if failed_record is not None:
            return _finalize_orchestration_result(
                state=state,
                ok=False,
                dry_run=False,
                failed_record=failed_record,
                prompt_feedback=prompt_feedback,
            )

    return _finalize_orchestration_result(
        state=state,
        ok=True,
        dry_run=request.dry_run,
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
            - feedback: Optional feedback supplied to reviewer checks.
            - schema_only: Validate-only mode for schema checks.
            - dry_run: Plan checks without executing commands or reviewers.
            - collect_changed_paths: Optional changed-paths collector override.

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
        return _finalize_checks_run_result(
            ok=False,
            dry_run=request.dry_run,
            result_fields={
                "output": config_or_selection_error.output,
                "failed_check_id": config_or_selection_error.check_id,
                "failed_payload": config_or_selection_error.payload,
            },
        )

    return _execute_with_strategy_orchestration(
        project_root=root,
        doc=doc,
        request=request,
    )
