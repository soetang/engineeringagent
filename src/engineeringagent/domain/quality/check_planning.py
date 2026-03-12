"""Quality-domain planner records for deterministic checks selection."""

from __future__ import annotations

from typing import Iterable, Protocol, cast

from pydantic import BaseModel, ConfigDict

from .changed_paths import ChangedPathsResult
from .checks import CheckDecision, CheckDecisionAction, HarnessCheckPhase
from .checks_catalog import HarnessChecksDocument


class PlannedCheck(BaseModel):
    """Canonical deterministic planner record shared by checks runtimes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    decision: CheckDecisionAction
    reason: str


def make_planned_check(check_id: str, decision: str, reason: str) -> PlannedCheck:
    """Construct one canonical planner output record."""

    return PlannedCheck(
        check_id=check_id,
        decision=cast(CheckDecisionAction, decision),
        reason=reason,
    )


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
        phase_only_policy: bool = False,
    ) -> Iterable[PlannedCheckRecord]:
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


__all__ = [
    "ChecksPlanner",
    "PlannedCheck",
    "PlannedCheckRecord",
    "make_check_decision",
    "make_planned_check",
    "map_planned_checks_to_decisions",
]
