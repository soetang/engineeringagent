from __future__ import annotations

from pathlib import Path
from typing import (
    Any,
    Callable,
    Iterable,
    Mapping,
    NamedTuple,
    Protocol,
    Sequence,
    TypeVar,
)
from typing_extensions import Literal, TypedDict

from engineeringagent.changed_paths import ChangedPathsResult
from engineeringagent.specs import HarnessCheckPhase, HarnessChecksDocument

CheckDecisionAction = Literal["run", "skip"]
_MappedDecisionT = TypeVar("_MappedDecisionT")


class CheckContext(NamedTuple):
    """Shared planning/execution context passed to checks strategies."""

    project_root: Path
    phase: HarnessCheckPhase
    changed_paths: ChangedPathsResult
    feature_path: Path | None = None
    prior_feedback: str | None = None
    run_agent_fn: Any | None = None
    verbose_output: bool = False


class CheckDecision(TypedDict):
    """Deterministic check planning record."""

    check_id: str
    check_type: str
    phase: str
    decision: CheckDecisionAction
    reason: str


class PlannedCheckRecord(Protocol):
    """Minimal planner output required to build check decisions."""

    @property
    def check_id(self) -> str:
        """Deterministic check identifier."""
        raise NotImplementedError

    @property
    def decision(self) -> CheckDecisionAction:
        """Planner-selected run/skip action."""
        raise NotImplementedError

    @property
    def reason(self) -> str:
        """Planner reason label for explainability."""
        raise NotImplementedError


class ChecksPlanner(Protocol):
    """Minimal planner callable contract for doc-backed strategies."""

    def __call__(
        self,
        doc: HarnessChecksDocument,
        *,
        phase: HarnessCheckPhase,
        changed_paths: ChangedPathsResult,
    ) -> Sequence[PlannedCheckRecord]:
        raise NotImplementedError


def make_check_decision(
    *,
    check_id: str,
    check_type: str,
    phase: HarnessCheckPhase | str,
    decision: CheckDecisionAction,
    reason: str,
) -> CheckDecision:
    """Build one normalized deterministic check-decision record."""

    phase_value = phase.value if isinstance(phase, HarnessCheckPhase) else str(phase)
    return CheckDecision(
        check_id=check_id,
        check_type=check_type,
        phase=phase_value,
        decision=decision,
        reason=reason,
    )


def map_planned_checks_to_decisions(
    *,
    entries: Iterable[PlannedCheckRecord],
    check_type: str,
    phase: HarnessCheckPhase | str,
) -> tuple[CheckDecision, ...]:
    """Convert planner entries into normalized deterministic decisions."""

    return tuple(
        make_check_decision(
            check_id=entry.check_id,
            check_type=check_type,
            phase=phase,
            decision=entry.decision,
            reason=entry.reason,
        )
        for entry in entries
    )


def plan_strategy_decisions(
    *,
    context: CheckContext,
    check_type: str,
    entries: Iterable[PlannedCheckRecord],
) -> tuple[CheckDecision, ...]:
    """Map planner records to strategy-owned check decisions."""

    return map_planned_checks_to_decisions(
        entries=entries,
        check_type=check_type,
        phase=context.phase,
    )


def plan_doc_strategy_decisions(
    *,
    context: CheckContext,
    check_type: str,
    doc: HarnessChecksDocument,
    planner: ChecksPlanner,
) -> tuple[CheckDecision, ...]:
    """Plan deterministic strategy decisions via a doc-backed planner."""

    return plan_strategy_decisions(
        context=context,
        entries=planner(
            doc,
            phase=context.phase,
            changed_paths=context.changed_paths,
        ),
        check_type=check_type,
    )


def plan_single_strategy_decision(
    *,
    context: CheckContext,
    check_id: str,
    check_type: str,
    decision: CheckDecisionAction,
    reason: str,
) -> tuple[CheckDecision, ...]:
    """Build one strategy decision via the shared mapping path."""

    class _SinglePlannedCheckRecord(NamedTuple):
        check_id: str
        decision: CheckDecisionAction
        reason: str

    return map_planned_checks_to_decisions(
        entries=(
            _SinglePlannedCheckRecord(
                check_id=check_id,
                decision=decision,
                reason=reason,
            ),
        ),
        check_type=check_type,
        phase=context.phase,
    )


def map_strategy_decisions(
    decisions: Iterable[CheckDecision],
    *,
    check_type: str,
    mapper: Callable[[CheckDecision], _MappedDecisionT],
) -> tuple[_MappedDecisionT, ...]:
    """Map one strategy's decisions into another deterministic representation."""

    return tuple(
        mapper(decision)
        for decision in decisions
        if decision["check_type"] == check_type
    )


def strategy_run_decisions(
    decisions: Iterable[CheckDecision],
    *,
    check_type: str,
) -> tuple[CheckDecision, ...]:
    """Return deterministic run decisions for one strategy type."""

    return tuple(
        decision
        for decision in map_strategy_decisions(
            decisions,
            check_type=check_type,
            mapper=lambda decision: decision,
        )
        if decision["decision"] == "run"
    )


class CheckExecutionRecord(NamedTuple):
    """One side-effecting execution result emitted by a strategy."""

    check_id: str
    check_type: str
    ok: bool
    output: str
    payload: dict[str, Any] | None = None
    timing: Mapping[str, Any] | None = None


class CheckStrategy(Protocol):
    """Strategy contract keyed by check type in the orchestrator registry."""

    check_type: str

    def plan(
        self,
        *,
        context: CheckContext,
    ) -> tuple[CheckDecision, ...]:
        """Return deterministic run/skip decisions owned by the strategy."""
        raise NotImplementedError

    def execute(
        self,
        *,
        context: CheckContext,
        decisions: tuple[CheckDecision, ...],
    ) -> tuple[CheckExecutionRecord, ...]:
        """Execute planned run decisions in deterministic order."""
        raise NotImplementedError

    def render_prompt_feedback(
        self,
        *,
        failed_record: CheckExecutionRecord,
    ) -> str | None:
        """Render prompt-ready feedback for a failing execution."""
        raise NotImplementedError


def build_strategy_registry(
    strategies: Iterable[CheckStrategy],
) -> dict[str, CheckStrategy]:
    """Build a deterministic check-type registry from strategy instances."""

    registry: dict[str, CheckStrategy] = {}
    for strategy in strategies:
        check_type = strategy.check_type.strip()
        if not check_type:
            raise ValueError("check strategy check_type must be non-empty")
        if check_type in registry:
            raise ValueError(f"duplicate check strategy registration: {check_type}")
        registry[check_type] = strategy
    return registry
