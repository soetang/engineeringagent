from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Iterable

from pydantic import BaseModel, ConfigDict

from engineeringagent.changed_paths import (
    ChangedPathsResult,
)
from engineeringagent.checks.contracts import HarnessCheckPhase
from engineeringagent.checks.reviewers.engine import (
    DECISION_APPROVE,
    DECISION_REQUEST_CHANGES,
    ReviewerRunRequest,
    evaluate_cached_reviewer_approval,
    load_reviewers_state,
    record_reviewer_approval,
    run_reviewer,
    save_reviewers_state,
)
from engineeringagent.checks.strategy_contracts import (
    CheckDecision,
    PlannedCheck,
    make_planned_check,
)
from engineeringagent.specs import (
    HarnessCheckReviewerDefinition,
    HarnessChecksDocument,
)

from ..planning_policy import (
    PlanningPolicyContext,
    plan_checks_for_definition_type,
)

FALLBACK_REMEDIATION_GUIDANCE = (
    "reviewer did not provide required_actions; use summary and scope_notes to plan "
    "next edits and rerun checks."
)


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
    feedback: str | None = None
    verbose_output: bool = False


def plan_reviewer_checks(
    doc: HarnessChecksDocument,
    *,
    phase: HarnessCheckPhase,
    changed_paths: ChangedPathsResult,
    phase_only_policy: bool = False,
) -> list[PlannedCheck]:
    """Plan deterministic run/skip decisions for reviewer checks."""
    context = PlanningPolicyContext(
        phase=phase,
        changed_paths=changed_paths,
        phase_only_policy=phase_only_policy,
    )
    return plan_checks_for_definition_type(
        doc,
        context=context,
        definition_type=HarnessCheckReviewerDefinition,
        make_record=make_planned_check,
    )


def run_planned_reviewer_checks_from_plan(
    request: RunPlannedReviewerChecksRequest,
    planned: Iterable[CheckDecision],
) -> tuple[bool, str | None, str, dict[str, Any] | None]:
    """Execute reviewer checks from an existing deterministic plan."""

    planned_entries = tuple(planned)
    if not planned_entries:
        return True, None, "", None

    state = load_reviewers_state(request.project_root)
    output_parts: list[str] = []
    reviewer_run_request = ReviewerRunRequest(
        feature_id=request.feature_id,
        feature_path=request.feature_path,
        changed_paths=request.changed_paths,
        feedback=request.feedback,
        run_agent_fn=request.run_agent_fn,
    )

    for entry in planned_entries:
        check_id = str(entry["check_id"])
        reviewer_def = request.doc.checks.get(check_id)
        if not isinstance(reviewer_def, HarnessCheckReviewerDefinition):
            continue

        reviewer_id = check_id
        reviewer = reviewer_def.model_dump(mode="python")
        on_change = (
            reviewer_def.when.on_change if reviewer_def.when is not None else None
        )
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
            request=reviewer_run_request,
        )
        decision_name, summary, decision_payload = _normalize_reviewer_decision(
            decision
        )
        if decision_payload is not None:
            record_reviewer_approval(
                state,
                feature_id=request.feature_id,
                reviewer_id=reviewer_id,
                decision=str(decision_payload.get("decision", "")),
            )

        output_parts.append(
            f"[reviewer:{reviewer_id}] decision={decision_name} summary={summary}"
        )
        if request.verbose_output and decision_payload is not None:
            output_parts.append(
                f"[reviewer:{reviewer_id}] payload="
                f"{_serialize_reviewer_payload(decision_payload)}"
            )

        if decision_name != DECISION_APPROVE:
            if _is_missing_required_actions(decision_payload):
                output_parts.append(
                    f"[reviewer:{reviewer_id}] remediation={FALLBACK_REMEDIATION_GUIDANCE}"
                )
            save_reviewers_state(request.project_root, state)
            payload = {
                "kind": "reviewer_feedback",
                "reviewer_id": reviewer_id,
                "reviewer_phase": _reviewer_phase_for_payload(request.phase),
                "decision": decision_payload,
            }
            return False, reviewer_id, "\n".join(output_parts).strip(), payload

    save_reviewers_state(request.project_root, state)
    return True, None, "\n".join(output_parts).strip(), None


def _normalize_reviewer_decision(
    decision: Any,
) -> tuple[str, str, dict[str, Any] | None]:
    if not isinstance(decision, dict):
        return DECISION_REQUEST_CHANGES, "(reviewer payload missing)", None

    raw_decision = str(decision.get("decision", DECISION_REQUEST_CHANGES))
    decision_name = (
        DECISION_APPROVE
        if raw_decision == DECISION_APPROVE
        else DECISION_REQUEST_CHANGES
    )
    normalized_payload = {
        **decision,
        "decision": decision_name,
    }
    return decision_name, str(decision.get("summary", "")), normalized_payload


def _reviewer_phase_for_payload(phase: HarnessCheckPhase) -> str:
    if phase == HarnessCheckPhase.FEATURE_DONE:
        return "feature_done"
    return "iteration_end"


def _serialize_reviewer_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _is_missing_required_actions(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return True
    required_actions = payload.get("required_actions")
    if not isinstance(required_actions, list):
        return True
    return not any(isinstance(action, str) and action.strip() for action in required_actions)
