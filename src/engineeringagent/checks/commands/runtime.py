from __future__ import annotations

from pathlib import Path
import time
from time import monotonic_ns
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict

from engineeringagent.changed_paths import (
    ChangedPathsResult,
    FALLBACK_CHANGE_DISCOVERY_REASON,
)
from engineeringagent.specs import (
    HarnessCheckCommandDefinition,
    HarnessCheckPhase,
    HarnessChecksDocument,
)
from engineeringagent.process import run_shell_command

from ..on_change_matcher import path_matches_any_glob


ALWAYS_RUN_NO_ON_CHANGE_REASON = "always_run_no_on_change"
MATCHED_ON_CHANGE_REASON = "matched_on_change"
NO_ON_CHANGE_MATCH_REASON = "no_on_change_match"


class PlannedCheck(BaseModel):
    """Deterministic plan entry for a command check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    decision: str
    reason: str


class RunPlannedCommandChecksRequest(BaseModel):
    """Request payload for running planned command checks."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    doc: HarnessChecksDocument
    phase: HarnessCheckPhase
    changed_paths: ChangedPathsResult
    verbose_output: bool


class CommandInvocationRecord(BaseModel):
    """Structured metadata for one command-check invocation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    command: str
    returncode: int | None
    started_epoch_sec: int
    ended_epoch_sec: int
    started_monotonic_ns: int
    finished_monotonic_ns: int
    duration_ms: float


class RunPlannedCommandChecksResult(BaseModel):
    """Structured result for a command-check execution batch."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ok: bool
    failed_check_id: str | None
    output: str
    command_invocations: tuple[CommandInvocationRecord, ...] = ()


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


def run_planned_command_checks(
    request: RunPlannedCommandChecksRequest,
) -> RunPlannedCommandChecksResult:
    """Execute planned command checks and return deterministic outcome."""
    planned = plan_command_checks(
        request.doc,
        phase=request.phase,
        changed_paths=request.changed_paths,
    )
    combined_output_parts: list[str] = []
    command_invocations: list[CommandInvocationRecord] = []

    for check_id, command in iter_planned_command_check_commands(request.doc, planned):
        started_epoch_sec = int(time.time())
        started_monotonic_ns = monotonic_ns()
        proc = run_shell_command(request.project_root, command)
        finished_monotonic_ns = monotonic_ns()
        ended_epoch_sec = max(started_epoch_sec, int(time.time()))
        returncode_raw = getattr(proc, "returncode", None)
        returncode = returncode_raw if isinstance(returncode_raw, int) else None
        stdout = getattr(proc, "stdout", "") or ""
        stderr = getattr(proc, "stderr", "") or ""
        rendered_returncode = (
            returncode_raw if returncode_raw is not None else "unknown"
        )
        command_invocations.append(
            CommandInvocationRecord(
                check_id=check_id,
                command=command,
                returncode=returncode,
                started_epoch_sec=started_epoch_sec,
                ended_epoch_sec=ended_epoch_sec,
                started_monotonic_ns=started_monotonic_ns,
                finished_monotonic_ns=finished_monotonic_ns,
                duration_ms=(finished_monotonic_ns - started_monotonic_ns) / 1_000_000,
            )
        )
        output = f"{stdout}{stderr}"

        if request.verbose_output:
            if stdout:
                print(stdout, end="")
            if stderr:
                print(stderr, end="")

        combined_output_parts.append(f"[check:{check_id}] command={command}")
        combined_output_parts.append(
            f"[check:{check_id}] returncode={rendered_returncode}"
        )
        if output:
            combined_output_parts.append(output.rstrip("\n"))

        if returncode != 0:
            return RunPlannedCommandChecksResult(
                ok=False,
                failed_check_id=check_id,
                output="\n".join(combined_output_parts).strip(),
                command_invocations=tuple(command_invocations),
            )

    return RunPlannedCommandChecksResult(
        ok=True,
        failed_check_id=None,
        output="\n".join(combined_output_parts).strip(),
        command_invocations=tuple(command_invocations),
    )
