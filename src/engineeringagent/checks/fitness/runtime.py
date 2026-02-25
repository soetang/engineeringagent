from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict

from engineeringagent.changed_paths import ChangedPathsResult
from engineeringagent.checks.fitness.adapters import execute_rule_definition
from engineeringagent.checks.fitness.contracts import RuleStatus
from engineeringagent.checks.fitness.registry import build_rule_catalog
from engineeringagent.specs import (
    HarnessCheckFitnessDefinition,
    HarnessCheckPhase,
    HarnessChecksDocument,
)
from engineeringagent.checks.strategy_contracts import CheckDecisionAction
from ..planning_policy import (
    ALWAYS_RUN_NO_ON_CHANGE_REASON as _ALWAYS_RUN_NO_ON_CHANGE_REASON,
    MATCHED_ON_CHANGE_REASON as _MATCHED_ON_CHANGE_REASON,
    NO_ON_CHANGE_MATCH_REASON as _NO_ON_CHANGE_MATCH_REASON,
    plan_checks_for_definition_type,
)


ALWAYS_RUN_NO_ON_CHANGE_REASON = _ALWAYS_RUN_NO_ON_CHANGE_REASON
MATCHED_ON_CHANGE_REASON = _MATCHED_ON_CHANGE_REASON
NO_ON_CHANGE_MATCH_REASON = _NO_ON_CHANGE_MATCH_REASON


class PlannedCheck(BaseModel):
    """A deterministic run/skip decision for a single fitness check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    decision: CheckDecisionAction
    reason: str


class RunPlannedFitnessChecksRequest(BaseModel):
    """Inputs required to plan and execute fitness checks."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    doc: HarnessChecksDocument
    phase: HarnessCheckPhase
    changed_paths: ChangedPathsResult


def plan_fitness_checks(
    doc: HarnessChecksDocument,
    *,
    phase: HarnessCheckPhase,
    changed_paths: ChangedPathsResult,
) -> list[PlannedCheck]:
    """Plan deterministic run/skip decisions for fitness checks."""
    return plan_checks_for_definition_type(
        doc,
        phase=phase,
        changed_paths=changed_paths,
        definition_type=HarnessCheckFitnessDefinition,
        make_record=lambda check_id, decision, reason: PlannedCheck(
            check_id=check_id,
            decision=cast(CheckDecisionAction, decision),
            reason=reason,
        ),
    )


def run_planned_fitness_checks(
    request: RunPlannedFitnessChecksRequest,
) -> tuple[bool, str | None, str, dict[str, Any] | None]:
    """Execute planned fitness checks and return deterministic outcome."""
    planned = plan_fitness_checks(
        request.doc,
        phase=request.phase,
        changed_paths=request.changed_paths,
    )
    combined_output_parts: list[str] = []

    catalog = None

    for entry in planned:
        if entry.decision != "run":
            continue
        check = request.doc.checks.get(entry.check_id)
        if not isinstance(check, HarnessCheckFitnessDefinition):  # pragma: no cover
            continue

        selection = "scope=all" if check.scope == "all" else "rule_ids"

        if catalog is None:
            catalog = build_rule_catalog(request.project_root)
        requested_rule_ids = set(check.rule_ids or ())
        if check.scope != "all":
            present = {definition.metadata.rule_id for definition in catalog}
            missing = sorted(requested_rule_ids - present)
            if missing:
                combined_output_parts.append(
                    (
                        f"[check:{entry.check_id}] type=fitness {selection} "
                        f"missing_rule_ids={missing}"
                    )
                )
                return (
                    False,
                    entry.check_id,
                    "\n".join(combined_output_parts).strip(),
                    {
                        "kind": "selection_error",
                        "message": f"missing fitness rule_ids: {missing}",
                        "check_id": entry.check_id,
                    },
                )

        combined_output_parts.append(
            f"[check:{entry.check_id}] type=fitness {selection}"
        )

        definitions = (
            catalog
            if check.scope == "all"
            else [
                definition
                for definition in catalog
                if definition.metadata.rule_id in requested_rule_ids
            ]
        )

        has_failures = False
        failed_rules: list[dict[str, object]] = []
        for definition in definitions:
            result = execute_rule_definition(definition, request.project_root)
            combined_output_parts.append(
                (
                    f"[fitness:{result.rule_id}] status={result.status.value} "
                    f"summary={result.summary}"
                )
            )
            if result.status in {RuleStatus.FAIL, RuleStatus.ERROR}:
                has_failures = True
                failed_rules.append(
                    {
                        "rule_id": str(result.rule_id),
                        "remediation": str(definition.metadata.remediation),
                        "violations": list(result.violations or ()),
                        "details": result.details,
                    }
                )

        if has_failures:
            return (
                False,
                entry.check_id,
                "\n".join(combined_output_parts).strip(),
                {
                    "kind": "fitness_failure",
                    "check_id": entry.check_id,
                    "failed_rules": failed_rules,
                },
            )

    return True, None, "\n".join(combined_output_parts).strip(), None
