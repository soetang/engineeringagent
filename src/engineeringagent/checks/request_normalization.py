from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, TypedDict

from pydantic import BaseModel, ConfigDict

from engineeringagent.specs import HarnessCheckPhase


CHECK_GROUP_VALIDATE = "validate"
CHECK_GROUP_COMMANDS = "commands"
CHECK_GROUP_FITNESS = "fitness"
CHECK_GROUP_REVIEWERS = "reviewers"

ALLOWED_GROUPS = {
    CHECK_GROUP_VALIDATE,
    CHECK_GROUP_COMMANDS,
    CHECK_GROUP_FITNESS,
    CHECK_GROUP_REVIEWERS,
}
GROUP_ORDER = (
    CHECK_GROUP_VALIDATE,
    CHECK_GROUP_COMMANDS,
    CHECK_GROUP_FITNESS,
    CHECK_GROUP_REVIEWERS,
)
DEFAULT_GROUPS = (
    CHECK_GROUP_COMMANDS,
    CHECK_GROUP_FITNESS,
)
HARNESS_GROUPS = {
    CHECK_GROUP_COMMANDS,
    CHECK_GROUP_FITNESS,
    CHECK_GROUP_REVIEWERS,
}


class RunChecksRequest(BaseModel):
    """Normalized request consumed by checks orchestration internals."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        arbitrary_types_allowed=True,
    )

    phase: HarnessCheckPhase
    ordered_groups: tuple[str, ...]
    check_id: str | None
    feature_path: Path | None
    verbose_output: bool
    base: str | None
    head: str | None
    run_agent_fn: Callable[..., object] | None
    prior_feedback: str | None
    schema_only: bool
    dry_run: bool
    collect_changed_paths_fn: Callable[..., object] | None


class RunChecksKwargs(TypedDict, total=False):
    """Typed kwargs accepted by the public run_checks API."""

    check_id: str | None
    feature_path: str | Path | None
    verbose_output: bool
    base: str | None
    head: str | None
    run_agent_fn: Callable[..., object] | None
    prior_feedback: str | None
    schema_only: bool
    dry_run: bool
    collect_changed_paths: Callable[..., object] | None


RUN_CHECKS_ALLOWED_KWARGS = frozenset(
    {
        "check_id",
        "feature_path",
        "verbose_output",
        "base",
        "head",
        "run_agent_fn",
        "prior_feedback",
        "schema_only",
        "dry_run",
        "collect_changed_paths",
    }
)


def normalize_groups(checks: list[str] | None) -> tuple[str, ...]:
    """Normalize requested check groups into deterministic execution order."""
    requested = list(checks) if checks is not None else list(DEFAULT_GROUPS)
    normalized: list[str] = []
    for group in requested:
        value = str(group or "").strip()
        if value:
            normalized.append(value)

    invalid = sorted({group for group in normalized if group not in ALLOWED_GROUPS})
    if invalid:
        raise ValueError(
            f"unknown checks groups: {invalid}. Supported: {sorted(ALLOWED_GROUPS)}"
        )

    deduped: list[str] = []
    seen: set[str] = set()
    for group in normalized:
        if group in seen:
            continue
        seen.add(group)
        deduped.append(group)

    return tuple(group for group in GROUP_ORDER if group in deduped)


def coerce_project_root(project_root: str | Path) -> Path:
    """Resolve the project root path for check execution."""
    return Path(project_root).resolve()


def coerce_phase(phase: Any) -> HarnessCheckPhase:
    """Coerce phase input to a supported harness check phase."""
    if isinstance(phase, HarnessCheckPhase):
        return phase
    raw = str(phase or "").strip()
    try:
        return HarnessCheckPhase(raw)
    except ValueError as exc:
        raise ValueError(
            "unknown phase; expected one of: iteration_end|feature_done|manual"
        ) from exc


def build_run_checks_request(
    project_root: str | Path,
    *,
    phase: Any,
    checks: list[str] | None,
    kwargs: RunChecksKwargs,
) -> tuple[Path, RunChecksRequest]:
    """Build and validate a normalized run request for checks orchestration."""
    root = coerce_project_root(project_root)
    ordered_groups = normalize_groups(checks)

    unexpected = sorted(set(kwargs) - RUN_CHECKS_ALLOWED_KWARGS)
    if unexpected:
        raise TypeError(
            f"run_checks() got an unexpected keyword argument '{unexpected[0]}'"
        )

    check_id = kwargs.get("check_id")
    feature_path = kwargs.get("feature_path")
    verbose_output = bool(kwargs.get("verbose_output", False))
    base = kwargs.get("base")
    head = kwargs.get("head")
    run_agent_fn = kwargs.get("run_agent_fn")
    prior_feedback = kwargs.get("prior_feedback")
    schema_only = bool(kwargs.get("schema_only", False))
    dry_run = bool(kwargs.get("dry_run", False))
    collect_changed_paths_fn = kwargs.get("collect_changed_paths")

    if schema_only and CHECK_GROUP_VALIDATE not in ordered_groups:
        raise ValueError("schema_only requires the validate checks group")

    if CHECK_GROUP_REVIEWERS in ordered_groups and feature_path is None:
        raise ValueError("feature_path is required when reviewers checks are selected")

    request = RunChecksRequest(
        phase=coerce_phase(phase),
        ordered_groups=ordered_groups,
        check_id=check_id,
        feature_path=Path(feature_path).resolve() if feature_path is not None else None,
        verbose_output=verbose_output,
        base=base,
        head=head,
        run_agent_fn=run_agent_fn,
        prior_feedback=str(prior_feedback) if prior_feedback is not None else None,
        schema_only=schema_only,
        dry_run=dry_run,
        collect_changed_paths_fn=collect_changed_paths_fn,
    )
    return root, request
