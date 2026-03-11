"""Quality adapters for deterministic checks orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, cast

from typing_extensions import Unpack

from engineeringagent.checks import collect_changed_paths
from engineeringagent.checks.config_selection import (
    ChecksConfigSelectionError,
    load_selected_harness_checks_document,
)
from engineeringagent.checks.contracts import (
    CheckDecision,
    CheckExecutionRecord,
    CommandInvocationRecord,
)
from engineeringagent.checks.request_normalization import (
    CHECK_GROUP_COMMANDS,
    CHECK_GROUP_FITNESS,
    CHECK_GROUP_REVIEWERS,
    CHECK_GROUP_VALIDATE,
    RunChecksKwargs as _RunChecksKwargs,
    _NormalizedRunChecksRequest,
    build_run_checks_request,
)
from engineeringagent.checks.results import ChecksRunResult
from engineeringagent.checks.strategies import (
    CommandCheckStrategy,
    FitnessCheckStrategy,
    ReviewerCheckStrategy,
    ValidateCheckStrategy,
)
from engineeringagent.checks.strategy_contracts import (
    CheckContext,
    CheckStrategy,
    build_strategy_registry,
)
from engineeringagent.domain.quality import (
    ChangedPathsResult,
    ChecksRunResult as DomainChecksRunResult,
    HarnessChecksDocument,
    reviewers_group_selected,
)
from engineeringagent.ports import ChecksRunRequest, ChecksRunner

__all__ = [
    "ChecksRunResult",
    "RuntimeChecksRunner",
    "run_checks",
    "_call_collect_changed_paths",
    "_resolve_changed_paths",
]


class RuntimeChecksRunner(ChecksRunner):
    """Run checks through the packaged quality runtime."""

    def run(self, request: ChecksRunRequest) -> DomainChecksRunResult:
        """Execute one checks request through the concrete runtime module."""
        return run_checks(
            request.project_root,
            phase=request.phase,
            checks=request.selected_checks,
            check_id=request.check_id,
            feature_path=request.feature_path,
            verbose_output=request.verbose_output,
            base=request.base,
            head=request.head,
            dry_run=request.dry_run,
        )

    def reviewers_group_selected(self, selected_checks: list[str] | None) -> bool:
        """Return whether the selected groups require reviewer context."""
        return reviewers_group_selected(selected_checks)


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


ChangedPathsCollector = Callable[..., object]


def _normalize_checks_contract_prompt_feedback(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def _call_collect_changed_paths(
    fn: ChangedPathsCollector,
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
    return fn(project_root, **kwargs)


def _resolve_changed_paths(
    project_root: Path,
    request: _NormalizedRunChecksRequest,
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

    fields["prompt_feedback"] = _normalize_checks_contract_prompt_feedback(
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
    decisions: list[CheckDecision],
    outputs: list[str],
    *,
    dry_run: bool,
) -> str:
    decision_trace = _render_decision_trace(decisions)
    if dry_run:
        return decision_trace
    execution_outputs = "\n".join(part for part in outputs if part).strip()
    if not execution_outputs:
        return decision_trace
    return "\n".join(part for part in (decision_trace, execution_outputs) if part).strip()


_GROUP_TO_STRATEGY_TYPE = {
    CHECK_GROUP_VALIDATE: "validate",
    CHECK_GROUP_COMMANDS: "command",
    CHECK_GROUP_FITNESS: "fitness",
    CHECK_GROUP_REVIEWERS: "reviewer",
}


def _build_strategy_registry(
    doc: HarnessChecksDocument | None,
    request: _NormalizedRunChecksRequest,
) -> dict[str, CheckStrategy]:
    strategies: list[CheckStrategy] = [
        ValidateCheckStrategy(schema_only=request.schema_only),
    ]
    if CHECK_GROUP_COMMANDS in request.ordered_groups and doc is not None:
        strategies.append(
            CommandCheckStrategy(doc=doc, verbose_output=request.verbose_output)
        )
    if CHECK_GROUP_FITNESS in request.ordered_groups and doc is not None:
        strategies.append(FitnessCheckStrategy(doc=doc))
    if CHECK_GROUP_REVIEWERS in request.ordered_groups and doc is not None:
        strategies.append(ReviewerCheckStrategy(doc=doc))
    return build_strategy_registry(strategies)


def _append_strategy_result(
    strategy: CheckStrategy,
    request: _NormalizedRunChecksRequest,
    context: CheckContext,
    state: _OrchestrationState,
) -> tuple[CheckExecutionRecord | None, str | None]:
    strategy_decisions = strategy.plan(context=context)
    state.decisions.extend(strategy_decisions)
    if request.dry_run:
        return (None, None)
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
            strategy.render_prompt_feedback(failed_record=record),
        )
    return (None, None)


def _build_check_context(
    project_root: Path,
    request: _NormalizedRunChecksRequest,
) -> CheckContext:
    return CheckContext(
        project_root=project_root,
        phase=request.phase,
        changed_paths=_resolve_changed_paths(project_root, request),
        feature_path=request.feature_path,
        feedback=request.feedback,
        run_agent_fn=request.run_agent_fn,
        verbose_output=request.verbose_output,
        phase_only_policy=request.phase_only_policy,
    )


def _ordered_request_strategies(
    strategy_registry: dict[str, CheckStrategy],
    request: _NormalizedRunChecksRequest,
) -> tuple[CheckStrategy, ...]:
    return tuple(
        strategy_registry[_GROUP_TO_STRATEGY_TYPE[group]]
        for group in request.ordered_groups
    )


def _execute_with_strategy_orchestration(
    project_root: Path,
    request: _NormalizedRunChecksRequest,
    strategy_registry: dict[str, CheckStrategy],
) -> ChecksRunResult:
    state = _OrchestrationState()
    context = _build_check_context(project_root, request)
    for strategy in _ordered_request_strategies(strategy_registry, request):
        failed_record, prompt_feedback = _append_strategy_result(
            strategy,
            request,
            context,
            state,
        )
        if failed_record is not None:
            return _finalize_orchestration_result(
                state=state,
                ok=False,
                dry_run=request.dry_run,
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
    """Plan and run deterministic checks."""

    root, request = build_run_checks_request(
        project_root,
        phase=phase,
        checks=checks,
        kwargs=kwargs,
    )
    doc, config_error = load_selected_harness_checks_document(
        root,
        request=request,
    )
    if config_error is not None:
        error = cast(ChecksConfigSelectionError, config_error)
        return _finalize_checks_run_result(
            ok=False,
            dry_run=request.dry_run,
            result_fields={
                "failed_check_id": error.check_id,
                "failed_payload": error.payload,
                "output": error.output,
            },
        )
    strategy_registry = _build_strategy_registry(doc, request)
    return _execute_with_strategy_orchestration(
        root,
        request,
        strategy_registry,
    )
