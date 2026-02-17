from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from engineeringagent.changed_paths import (
    ChangedPathsResult,
    FALLBACK_CHANGE_DISCOVERY_REASON,
)
from engineeringagent.fitness.adapters import execute_rule_definition
from engineeringagent.fitness.contracts import RuleStatus
from engineeringagent.fitness.registry import build_rule_catalog
from engineeringagent.on_change_matcher import path_matches_any_glob
from engineeringagent.specs import (
    HarnessCheckFitnessDefinition,
    HarnessCheckPhase,
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


class RunPlannedFitnessChecksRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    doc: HarnessChecksDocument
    phase: HarnessCheckPhase
    changed_paths: ChangedPathsResult


def _effective_default_phase(doc: HarnessChecksDocument) -> HarnessCheckPhase:
    defaults = doc.defaults
    if defaults is None or defaults.when is None or defaults.when.phase is None:
        return HarnessCheckPhase.ITERATION_END
    return defaults.when.phase


def _effective_check_phase(
    *,
    doc: HarnessChecksDocument,
    check_when: Any,
) -> HarnessCheckPhase:
    default_phase = _effective_default_phase(doc)
    if check_when is None or getattr(check_when, "phase", None) is None:
        return default_phase
    return check_when.phase


def plan_fitness_checks(
    doc: HarnessChecksDocument,
    *,
    phase: HarnessCheckPhase,
    changed_paths: ChangedPathsResult,
) -> list[PlannedCheck]:
    """Plan deterministic run/skip decisions for fitness checks."""
    planned: list[PlannedCheck] = []
    fallback_reason = changed_paths.reason or FALLBACK_CHANGE_DISCOVERY_REASON

    for check_id, check in doc.checks.items():
        if not isinstance(check, HarnessCheckFitnessDefinition):
            continue
        if _effective_check_phase(doc=doc, check_when=check.when) != phase:
            continue

        on_change = None
        if check.when is not None:
            on_change = check.when.on_change

        if phase == HarnessCheckPhase.MANUAL:
            planned.append(
                PlannedCheck(
                    check_id=check_id,
                    decision="skip",
                    reason="manual",
                )
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
                PlannedCheck(
                    check_id=check_id,
                    decision="run",
                    reason=fallback_reason,
                )
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


def run_planned_fitness_checks(
    request: RunPlannedFitnessChecksRequest,
) -> tuple[bool, str | None, str]:
    """Execute planned fitness checks and return deterministic outcome."""
    planned = plan_fitness_checks(
        request.doc,
        phase=request.phase,
        changed_paths=request.changed_paths,
    )
    combined_output_parts: list[str] = []

    for entry in planned:
        if entry.decision != "run":
            continue
        check = request.doc.checks.get(entry.check_id)
        if not isinstance(check, HarnessCheckFitnessDefinition):  # pragma: no cover
            continue

        selection = "scope=all" if check.scope == "all" else "rule_ids"

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
                return False, entry.check_id, "\n".join(combined_output_parts).strip()

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

        if has_failures:
            return (
                False,
                entry.check_id,
                "\n".join(combined_output_parts).strip(),
            )

    return True, None, "\n".join(combined_output_parts).strip()
