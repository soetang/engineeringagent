from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict

from engineeringagent.changed_paths import (
    ChangedPathsResult,
    FALLBACK_CHANGE_DISCOVERY_REASON,
)
from engineeringagent.on_change_matcher import path_matches_any_glob

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


ALWAYS_RUN_NO_ON_CHANGE_REASON = "always_run_no_on_change"
MATCHED_ON_CHANGE_REASON = "matched_on_change"
NO_ON_CHANGE_MATCH_REASON = "no_on_change_match"


class PlannedCheck(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    decision: str
    reason: str


class RunPlannedReviewerChecksRequest(BaseModel):
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
    start_agent_fn: Callable[..., Any]
    prior_feedback: str | None = None


def _effective_default_phase(doc: HarnessChecksDocument) -> HarnessCheckPhase:
    defaults = doc.defaults
    if defaults is None or defaults.when is None or defaults.when.phase is None:
        return HarnessCheckPhase.ITERATION_END
    return defaults.when.phase


def _effective_check_phase(
    *, doc: HarnessChecksDocument, check_when: Any
) -> HarnessCheckPhase:
    default_phase = _effective_default_phase(doc)
    if check_when is None or getattr(check_when, "phase", None) is None:
        return default_phase
    return check_when.phase


def plan_reviewer_checks(
    doc: HarnessChecksDocument,
    *,
    phase: HarnessCheckPhase,
    changed_paths: ChangedPathsResult,
) -> list[PlannedCheck]:
    """Plan deterministic run/skip decisions for reviewer checks."""

    planned: list[PlannedCheck] = []
    fallback_reason = changed_paths.reason or FALLBACK_CHANGE_DISCOVERY_REASON
    for check_id, check in doc.checks.items():
        if not isinstance(check, HarnessCheckReviewerDefinition):
            continue
        if _effective_check_phase(doc=doc, check_when=check.when) != phase:
            continue

        on_change = None
        if check.when is not None:
            on_change = check.when.on_change

        if phase == HarnessCheckPhase.MANUAL:
            planned.append(
                PlannedCheck(check_id=check_id, decision="skip", reason="manual")
            )
            continue

        if on_change is None:
            planned.append(
                PlannedCheck(
                    check_id=check_id,
                    decision="run",
                    reason=ALWAYS_RUN_NO_ON_CHANGE_REASON,
                )
            )
            continue

        if changed_paths.run_all:
            planned.append(
                PlannedCheck(check_id=check_id, decision="run", reason=fallback_reason)
            )
            continue

        if any(path_matches_any_glob(path, on_change) for path in changed_paths.paths):
            planned.append(
                PlannedCheck(
                    check_id=check_id,
                    decision="run",
                    reason=MATCHED_ON_CHANGE_REASON,
                )
            )
            continue

        planned.append(
            PlannedCheck(
                check_id=check_id,
                decision="skip",
                reason=NO_ON_CHANGE_MATCH_REASON,
            )
        )

    return planned


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
            start_agent_fn=request.start_agent_fn,
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
            payload = decision if isinstance(decision, dict) else None
            return False, reviewer_id, "\n".join(output_parts).strip(), payload

    save_reviewers_state(request.project_root, state)
    return True, None, "\n".join(output_parts).strip(), None
