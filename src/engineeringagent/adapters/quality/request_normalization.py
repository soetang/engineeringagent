from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, TypedDict

from pydantic import BaseModel, ConfigDict

from engineeringagent.domain.quality import (
    CHECK_GROUP_COMMANDS,
    CHECK_GROUP_FITNESS,
    CHECK_GROUP_REVIEWERS,
    CHECK_GROUP_VALIDATE,
    HARNESS_CHECK_GROUPS,
    HarnessCheckPhase,
    SelectionProfile,
    normalize_check_groups,
    reviewers_group_selected,
)


class _NormalizedRunChecksRequest(BaseModel):
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
    feedback: str | None
    schema_only: bool
    dry_run: bool
    collect_changed_paths_fn: Callable[..., object] | None
    phase_only_policy: bool


class RunChecksKwargs(TypedDict, total=False):
    """Typed kwargs accepted by the public run_checks API."""

    check_id: str | None
    feature_path: str | Path | None
    verbose_output: bool
    base: str | None
    head: str | None
    run_agent_fn: Callable[..., object] | None
    feedback: str | None
    schema_only: bool
    dry_run: bool
    collect_changed_paths: Callable[..., object] | None
    selection_profile: SelectionProfile


RUN_CHECKS_ALLOWED_KWARGS = frozenset(
    {
        "check_id",
        "feature_path",
        "verbose_output",
        "base",
        "head",
        "run_agent_fn",
        "feedback",
        "schema_only",
        "dry_run",
        "collect_changed_paths",
        "selection_profile",
    }
)


_LOOP_GATE_GROUPS_BY_PHASE: dict[HarnessCheckPhase, tuple[str, ...]] = {
    HarnessCheckPhase.ITERATION_END: (
        CHECK_GROUP_VALIDATE,
        CHECK_GROUP_COMMANDS,
        CHECK_GROUP_FITNESS,
    ),
    HarnessCheckPhase.FEATURE_DONE: (
        CHECK_GROUP_COMMANDS,
        CHECK_GROUP_FITNESS,
    ),
}

_SELECTION_PROFILE_ERROR = (
    "unknown selection profile; expected one of: "
    "default|loop_gate|loop_reviewer|loop_runtime"
)

HARNESS_GROUPS = HARNESS_CHECK_GROUPS


def normalize_groups(
    checks: list[str] | None,
    *,
    phase: HarnessCheckPhase = HarnessCheckPhase.MANUAL,
    selection_profile: SelectionProfile = "default",
    feature_path: str | Path | None = None,
) -> tuple[str, ...]:
    """Normalize requested check groups into deterministic execution order."""
    if checks is not None:
        return normalize_check_groups(
            checks,
            phase=phase,
            selection_profile=selection_profile,
            feature_path=feature_path,
        )

    if selection_profile == "default":
        requested = ("validate", "commands", "fitness")
    elif selection_profile == "loop_gate":
        groups = _LOOP_GATE_GROUPS_BY_PHASE.get(phase)
        if groups is None:
            raise ValueError("loop_gate selection_profile requires iteration_end|feature_done")
        requested = groups
    elif selection_profile == "loop_reviewer":
        if phase != HarnessCheckPhase.FEATURE_DONE:
            raise ValueError("loop_reviewer selection_profile requires feature_done")
        requested = (CHECK_GROUP_REVIEWERS,)
    elif selection_profile == "loop_runtime":
        if phase == HarnessCheckPhase.FEATURE_DONE and feature_path is not None:
            requested = (CHECK_GROUP_REVIEWERS,)
        else:
            groups = _LOOP_GATE_GROUPS_BY_PHASE.get(phase)
            if groups is None:
                raise ValueError(
                    "loop_runtime selection_profile requires iteration_end|feature_done"
                )
            requested = groups
    else:
        raise ValueError(_SELECTION_PROFILE_ERROR)

    return normalize_check_groups(requested)


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
) -> tuple[Path, _NormalizedRunChecksRequest]:
    """Build and validate a normalized run request for checks orchestration."""
    root = coerce_project_root(project_root)
    phase_value = coerce_phase(phase)

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
    feedback = kwargs.get("feedback")
    schema_only = bool(kwargs.get("schema_only", False))
    dry_run = bool(kwargs.get("dry_run", False))
    collect_changed_paths_fn = kwargs.get("collect_changed_paths")
    raw_selection_profile = kwargs.get("selection_profile")
    selection_profile = (
        "default"
        if checks is not None
        else _resolve_selection_profile(
            phase=phase_value,
            raw_selection_profile=raw_selection_profile,
            collect_changed_paths_fn=collect_changed_paths_fn,
        )
    )
    ordered_groups = normalize_groups(
        checks,
        phase=phase_value,
        selection_profile=selection_profile,
        feature_path=feature_path,
    )

    if schema_only and CHECK_GROUP_VALIDATE not in ordered_groups:
        raise ValueError("schema_only requires the validate checks group")

    if reviewers_group_selected(ordered_groups) and feature_path is None:
        raise ValueError("feature_path is required when reviewers checks are selected")

    request = _NormalizedRunChecksRequest(
        phase=phase_value,
        ordered_groups=ordered_groups,
        check_id=check_id,
        feature_path=Path(feature_path).resolve() if feature_path is not None else None,
        verbose_output=verbose_output,
        base=base,
        head=head,
        run_agent_fn=run_agent_fn,
        feedback=str(feedback) if feedback is not None else None,
        schema_only=schema_only,
        dry_run=dry_run,
        collect_changed_paths_fn=collect_changed_paths_fn,
        phase_only_policy=(selection_profile == "default"),
    )
    return root, request


def _coerce_selection_profile(raw_selection_profile: object) -> SelectionProfile:
    if raw_selection_profile == "default":
        return "default"
    if raw_selection_profile == "loop_gate":
        return "loop_gate"
    if raw_selection_profile == "loop_reviewer":
        return "loop_reviewer"
    if raw_selection_profile == "loop_runtime":
        return "loop_runtime"
    raise ValueError(_SELECTION_PROFILE_ERROR)


def _resolve_selection_profile(
    *,
    phase: HarnessCheckPhase,
    raw_selection_profile: object | None,
    collect_changed_paths_fn: Callable[..., object] | None,
) -> SelectionProfile:
    if raw_selection_profile is not None:
        return _coerce_selection_profile(raw_selection_profile)

    if phase != HarnessCheckPhase.MANUAL and collect_changed_paths_fn is not None:
        return "loop_runtime"

    return "default"
