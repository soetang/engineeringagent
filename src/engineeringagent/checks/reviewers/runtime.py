from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable

from pydantic import BaseModel, ConfigDict

from engineeringagent.changed_paths import (
    ChangedPathsResult,
)

from engineeringagent.checks.reviewers.engine import (
    DECISION_APPROVE,
    DECISION_REQUEST_CHANGES,
    evaluate_cached_reviewer_approval,
    load_reviewers_state,
    record_reviewer_approval,
    run_reviewer,
    save_reviewers_state,
)
from engineeringagent.specs import (
    HarnessCheckPhase,
    HarnessCheckReviewerDefinition,
    HarnessChecksDocument,
)

from ..planning_policy import (
    ALWAYS_RUN_NO_ON_CHANGE_REASON as _ALWAYS_RUN_NO_ON_CHANGE_REASON,
    MATCHED_ON_CHANGE_REASON as _MATCHED_ON_CHANGE_REASON,
    NO_ON_CHANGE_MATCH_REASON as _NO_ON_CHANGE_MATCH_REASON,
    plan_check_when_decision,
)


ALWAYS_RUN_NO_ON_CHANGE_REASON = _ALWAYS_RUN_NO_ON_CHANGE_REASON
MATCHED_ON_CHANGE_REASON = _MATCHED_ON_CHANGE_REASON
NO_ON_CHANGE_MATCH_REASON = _NO_ON_CHANGE_MATCH_REASON


class PlannedCheck(BaseModel):
    """Deterministic plan entry for a reviewer check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    decision: str
    reason: str


class RunPlannedReviewerChecksRequest(BaseModel):
    """Request payload for running planned reviewer checks."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    project_root: Path
    doc: HarnessChecksDocument
    phase: HarnessCheckPhase
    changed_paths: ChangedPathsResult
    feature_id: str
    feature_path: Path
    run_agent_fn: Callable[..., Any] | None = None
    prior_feedback: str | None = None


def plan_reviewer_checks(
    doc: HarnessChecksDocument,
    *,
    phase: HarnessCheckPhase,
    changed_paths: ChangedPathsResult,
) -> list[PlannedCheck]:
    """Plan deterministic run/skip decisions for reviewer checks."""

    planned: list[PlannedCheck] = []
    for check_id, check in doc.checks.items():
        if not isinstance(check, HarnessCheckReviewerDefinition):
            continue
        decision = plan_check_when_decision(
            doc=doc,
            phase=phase,
            check_when=check.when,
            changed_paths=changed_paths,
        )
        if decision is None:
            continue
        decision_value, reason = decision
        planned.append(
            PlannedCheck(check_id=check_id, decision=decision_value, reason=reason)
        )

    return planned


def iter_planned_reviewer_checks(
    doc: HarnessChecksDocument,
    planned: Iterable[PlannedCheck],
) -> Iterable[tuple[str, HarnessCheckReviewerDefinition]]:
    """Yield reviewer check definitions referenced by planned entries.

    This helper exists for unit tests and mirrors the legacy harness runtime
    behavior (it does not filter on the planned decision).
    """

    by_id = doc.checks
    for entry in planned:
        check = by_id.get(entry.check_id)
        if not isinstance(check, HarnessCheckReviewerDefinition):
            continue
        yield entry.check_id, check


def run_planned_reviewer_checks(
    request: RunPlannedReviewerChecksRequest,
) -> tuple[bool, str | None, str, dict[str, Any] | None]:
    """Execute planned reviewer checks and return deterministic outcome."""

    planned = plan_reviewer_checks(
        request.doc,
        phase=request.phase,
        changed_paths=request.changed_paths,
    )
    if not planned:
        return True, None, "", None

    state = load_reviewers_state(request.project_root)
    output_parts: list[str] = []

    for entry in planned:
        reviewer_def = request.doc.checks.get(entry.check_id)
        if not isinstance(reviewer_def, HarnessCheckReviewerDefinition):
            continue

        if entry.decision != "run":
            output_parts.append(
                f"[reviewer:{entry.check_id}] skip reason={entry.reason}"
            )
            continue

        reviewer_id = entry.check_id
        reviewer = reviewer_def.model_dump(mode="python")
        on_change = None
        if reviewer_def.when is not None:
            on_change = reviewer_def.when.on_change
        reviewer["trigger"] = {"on_change": on_change} if on_change else {}

        reuse, reuse_reason = evaluate_cached_reviewer_approval(
            state,
            feature_id=request.feature_id,
            reviewer_id=reviewer_id,
            reviewer=reviewer,
            changed_paths=request.changed_paths,
        )
        if reuse:
            output_parts.append(
                f"[reviewer:{reviewer_id}] decision=approve reused={reuse_reason}"
            )
            continue

        decision = run_reviewer(
            request.project_root,
            reviewer_id,
            reviewer,
            feature_id=request.feature_id,
            feature_path=request.feature_path,
            changed_paths=request.changed_paths,
            prior_feedback=request.prior_feedback,
            run_agent_fn=request.run_agent_fn,
        )
        if isinstance(decision, dict):
            record_reviewer_approval(
                state,
                feature_id=request.feature_id,
                reviewer_id=reviewer_id,
                decision=str(decision.get("decision", "")),
            )

        raw_decision = (
            str(decision.get("decision", DECISION_REQUEST_CHANGES))
            if isinstance(decision, dict)
            else DECISION_REQUEST_CHANGES
        )
        decision_name = (
            DECISION_APPROVE
            if raw_decision == DECISION_APPROVE
            else DECISION_REQUEST_CHANGES
        )
        summary = (
            str(decision.get("summary", ""))
            if isinstance(decision, dict)
            else "(reviewer payload missing)"
        )
        output_parts.append(
            f"[reviewer:{reviewer_id}] decision={decision_name} summary={summary}"
        )

        if decision_name != DECISION_APPROVE:
            save_reviewers_state(request.project_root, state)
            decision_payload = decision if isinstance(decision, dict) else None
            reviewer_phase = (
                "feature_done"
                if request.phase == HarnessCheckPhase.FEATURE_DONE
                else "iteration_end"
            )
            payload = {
                "kind": "reviewer_feedback",
                "reviewer_id": reviewer_id,
                "reviewer_phase": reviewer_phase,
                "decision": decision_payload,
            }
            return False, reviewer_id, "\n".join(output_parts).strip(), payload

    save_reviewers_state(request.project_root, state)
    return True, None, "\n".join(output_parts).strip(), None
