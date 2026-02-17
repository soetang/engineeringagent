from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Iterable, NamedTuple

from pydantic import BaseModel, ConfigDict

from .changed_paths import ChangedPathsResult, FALLBACK_CHANGE_DISCOVERY_REASON
from .on_change_matcher import path_matches_any_glob
from .specs import (
    HarnessCheckCommandDefinition,
    HarnessCheckFitnessDefinition,
    HarnessCheckPhase,
    HarnessCheckReviewerDefinition,
    HarnessChecksDocument,
    load_yaml,
)
from .fitness.adapters import execute_rule_definition
from .fitness.contracts import RuleStatus
from .fitness.registry import build_rule_catalog
from .loop_runtime.models import CommandTiming
from .loop_runtime.time_format import utc_iso_from_epoch_sec


ALWAYS_RUN_NO_ON_CHANGE_REASON = "always_run_no_on_change"
MATCHED_ON_CHANGE_REASON = "matched_on_change"
NO_ON_CHANGE_MATCH_REASON = "no_on_change_match"


class PlannedCheck(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    decision: str
    reason: str


def load_checks_document(checks_path: Path) -> HarnessChecksDocument:
    """Load and validate `harness/checks.yaml` into a typed contract model."""
    payload = load_yaml(checks_path)
    return HarnessChecksDocument.model_validate(payload)


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


def plan_command_checks(
    doc: HarnessChecksDocument,
    *,
    phase: HarnessCheckPhase,
    changed_paths: ChangedPathsResult,
) -> list[PlannedCheck]:
    """Plan deterministic run/skip decisions for command checks."""
    planned: list[PlannedCheck] = []
    fallback_reason = changed_paths.reason or FALLBACK_CHANGE_DISCOVERY_REASON
    for check_id, check in doc.checks.items():
        if not isinstance(check, HarnessCheckCommandDefinition):
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
                    check_id=check_id, decision="run", reason=MATCHED_ON_CHANGE_REASON
                )
            )
            continue

        planned.append(
            PlannedCheck(
                check_id=check_id, decision="skip", reason=NO_ON_CHANGE_MATCH_REASON
            )
        )

    return planned


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
                check_id=check_id, decision="skip", reason=NO_ON_CHANGE_MATCH_REASON
            )
        )

    return planned


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
                check_id=check_id, decision="skip", reason=NO_ON_CHANGE_MATCH_REASON
            )
        )

    return planned


def iter_planned_reviewer_checks(
    doc: HarnessChecksDocument,
    planned: Iterable[PlannedCheck],
) -> Iterable[tuple[str, HarnessCheckReviewerDefinition]]:
    """Yield reviewer check definitions marked to run."""
    by_id = doc.checks
    for entry in planned:
        check = by_id.get(entry.check_id)
        if not isinstance(check, HarnessCheckReviewerDefinition):
            continue
        yield entry.check_id, check


def iter_planned_command_check_commands(
    doc: HarnessChecksDocument,
    planned: Iterable[PlannedCheck],
) -> Iterable[tuple[str, str]]:
    """Yield (check_id, command) pairs for planned command checks."""
    by_id = doc.checks
    for entry in planned:
        if entry.decision != "run":
            continue
        check = by_id.get(entry.check_id)
        if not isinstance(check, HarnessCheckCommandDefinition):
            continue
        yield entry.check_id, check.command


class PlannedCommandChecksInputs(NamedTuple):
    project_root: Path
    doc: HarnessChecksDocument
    phase: HarnessCheckPhase
    changed_paths: ChangedPathsResult
    verbose_output: bool
    run_shell_command: Callable[[Path, str], Any]


def run_planned_command_checks(
    inputs: PlannedCommandChecksInputs,
) -> tuple[bool, str | None, str, list[CommandTiming]]:
    """Execute planned command checks and return deterministic outcome."""
    planned = plan_command_checks(
        inputs.doc,
        phase=inputs.phase,
        changed_paths=inputs.changed_paths,
    )
    combined_output_parts: list[str] = []
    timings: list[CommandTiming] = []

    for check_id, command in iter_planned_command_check_commands(inputs.doc, planned):
        started_epoch_sec = int(time.time())
        proc = inputs.run_shell_command(inputs.project_root, command)
        ended_epoch_sec = max(started_epoch_sec, int(time.time()))
        output = (getattr(proc, "stdout", "") or "") + (
            getattr(proc, "stderr", "") or ""
        )
        timings.append(
            CommandTiming(
                phase="gates",
                gate=check_id,
                command=command,
                started_at=utc_iso_from_epoch_sec(started_epoch_sec),
                ended_at=utc_iso_from_epoch_sec(ended_epoch_sec),
                duration_sec=max(0, ended_epoch_sec - started_epoch_sec),
            )
        )

        if inputs.verbose_output:
            if getattr(proc, "stdout", None):
                print(proc.stdout, end="")
            if getattr(proc, "stderr", None):
                print(proc.stderr, end="")

        combined_output_parts.append(f"[check:{check_id}] command={command}")
        combined_output_parts.append(
            f"[check:{check_id}] returncode={getattr(proc, 'returncode', 'unknown')}"
        )
        if output:
            combined_output_parts.append(output.rstrip("\n"))

        if getattr(proc, "returncode", 1) != 0:
            return False, check_id, "\n".join(combined_output_parts).strip(), timings

    return True, None, "\n".join(combined_output_parts).strip(), timings


def run_planned_fitness_checks(
    *,
    project_root: Path,
    doc: HarnessChecksDocument,
    phase: HarnessCheckPhase,
    changed_paths: ChangedPathsResult,
) -> tuple[bool, str | None, str, list[CommandTiming]]:
    """Execute planned fitness checks and return deterministic outcome."""
    ok, failed, output, timings, _failed_rules = _run_planned_fitness_checks_impl(
        project_root=project_root,
        doc=doc,
        phase=phase,
        changed_paths=changed_paths,
    )
    return ok, failed, output, timings


def run_planned_fitness_checks_with_failures(
    *,
    project_root: Path,
    doc: HarnessChecksDocument,
    phase: HarnessCheckPhase,
    changed_paths: ChangedPathsResult,
) -> tuple[bool, str | None, str, list[CommandTiming], list[dict[str, Any]]]:
    """Execute planned fitness checks and return failures-only payload.

    This exists for prompt-injection surfaces that need deterministic structured
    failure details (rule_id, remediation, violations, details) without scraping
    the human-oriented output string.
    """
    return _run_planned_fitness_checks_impl(
        project_root=project_root,
        doc=doc,
        phase=phase,
        changed_paths=changed_paths,
    )


def _run_planned_fitness_checks_impl(
    *,
    project_root: Path,
    doc: HarnessChecksDocument,
    phase: HarnessCheckPhase,
    changed_paths: ChangedPathsResult,
) -> tuple[bool, str | None, str, list[CommandTiming], list[dict[str, Any]]]:
    planned = plan_fitness_checks(doc, phase=phase, changed_paths=changed_paths)
    combined_output_parts: list[str] = []
    timings: list[CommandTiming] = []

    for entry in planned:
        if entry.decision != "run":
            continue
        check = doc.checks.get(entry.check_id)
        if not isinstance(check, HarnessCheckFitnessDefinition):  # pragma: no cover
            continue

        selection = "scope=all" if check.scope == "all" else "rule_ids"
        started_epoch_sec = int(time.time())

        catalog = build_rule_catalog(project_root)
        requested_rule_ids = set(check.rule_ids or ())
        if check.scope != "all":
            present = {definition.metadata.rule_id for definition in catalog}
            missing = sorted(requested_rule_ids - present)
            if missing:
                combined_output_parts.append(
                    f"[check:{entry.check_id}] type=fitness {selection} missing_rule_ids={missing}"
                )
                ended_epoch_sec = max(started_epoch_sec, int(time.time()))
                timings.append(
                    CommandTiming(
                        phase="gates",
                        gate=entry.check_id,
                        command=f"fitness {selection}",
                        started_at=utc_iso_from_epoch_sec(started_epoch_sec),
                        ended_at=utc_iso_from_epoch_sec(ended_epoch_sec),
                        duration_sec=max(0, ended_epoch_sec - started_epoch_sec),
                    )
                )
                return (
                    False,
                    entry.check_id,
                    "\n".join(combined_output_parts).strip(),
                    timings,
                    [],
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
        failed_rules: list[dict[str, Any]] = []
        for definition in definitions:
            result = execute_rule_definition(definition, project_root)
            combined_output_parts.append(
                f"[fitness:{result.rule_id}] status={result.status.value} summary={result.summary}"
            )
            if result.status in {RuleStatus.FAIL, RuleStatus.ERROR}:
                has_failures = True
                failed_rules.append(
                    {
                        "rule_id": result.rule_id,
                        "remediation": definition.metadata.remediation,
                        "violations": list(result.violations),
                        "details": result.details,
                    }
                )

        ended_epoch_sec = max(started_epoch_sec, int(time.time()))
        timings.append(
            CommandTiming(
                phase="gates",
                gate=entry.check_id,
                command=f"fitness {selection}",
                started_at=utc_iso_from_epoch_sec(started_epoch_sec),
                ended_at=utc_iso_from_epoch_sec(ended_epoch_sec),
                duration_sec=max(0, ended_epoch_sec - started_epoch_sec),
            )
        )

        if has_failures:
            return (
                False,
                entry.check_id,
                "\n".join(combined_output_parts).strip(),
                timings,
                failed_rules,
            )

    return True, None, "\n".join(combined_output_parts).strip(), timings, []
