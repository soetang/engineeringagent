"""Quality-domain contracts for deterministic checks-group selection."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from .checks import HarnessCheckPhase

CHECK_GROUP_VALIDATE = "validate"
CHECK_GROUP_COMMANDS = "commands"
CHECK_GROUP_FITNESS = "fitness"
CHECK_GROUP_REVIEWERS = "reviewers"

ALLOWED_CHECK_GROUPS = frozenset(
    {
        CHECK_GROUP_VALIDATE,
        CHECK_GROUP_COMMANDS,
        CHECK_GROUP_FITNESS,
        CHECK_GROUP_REVIEWERS,
    }
)
CHECK_GROUP_ORDER = (
    CHECK_GROUP_VALIDATE,
    CHECK_GROUP_COMMANDS,
    CHECK_GROUP_FITNESS,
    CHECK_GROUP_REVIEWERS,
)
DEFAULT_CHECK_GROUPS = (
    CHECK_GROUP_VALIDATE,
    CHECK_GROUP_COMMANDS,
    CHECK_GROUP_FITNESS,
)
HARNESS_CHECK_GROUPS = frozenset(
    {
        CHECK_GROUP_COMMANDS,
        CHECK_GROUP_FITNESS,
        CHECK_GROUP_REVIEWERS,
    }
)

SelectionProfile = Literal["default", "loop_gate", "loop_reviewer", "loop_runtime"]

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


def list_check_groups() -> tuple[str, ...]:
    """Return supported checks groups in deterministic order."""
    return CHECK_GROUP_ORDER


def _groups_for_loop_gate_phase(phase: HarnessCheckPhase) -> tuple[str, ...]:
    groups = _LOOP_GATE_GROUPS_BY_PHASE.get(phase)
    if groups is None:
        raise ValueError("loop_gate selection_profile requires iteration_end|feature_done")
    return groups


def _groups_for_loop_reviewer_phase(phase: HarnessCheckPhase) -> tuple[str, ...]:
    if phase != HarnessCheckPhase.FEATURE_DONE:
        raise ValueError("loop_reviewer selection_profile requires feature_done")
    return (CHECK_GROUP_REVIEWERS,)


def _groups_for_loop_runtime_phase(
    phase: HarnessCheckPhase,
    feature_path: str | Path | None,
) -> tuple[str, ...]:
    if phase == HarnessCheckPhase.FEATURE_DONE and feature_path is not None:
        return (CHECK_GROUP_REVIEWERS,)
    if phase not in _LOOP_GATE_GROUPS_BY_PHASE:
        raise ValueError(
            "loop_runtime selection_profile requires iteration_end|feature_done"
        )
    return _LOOP_GATE_GROUPS_BY_PHASE[phase]


def default_groups_for_selection_profile(
    *,
    phase: HarnessCheckPhase,
    selection_profile: SelectionProfile,
    feature_path: str | Path | None = None,
) -> tuple[str, ...]:
    """Return the default checks groups for one supported selection profile."""
    if selection_profile == "default":
        return DEFAULT_CHECK_GROUPS
    if selection_profile == "loop_gate":
        return _groups_for_loop_gate_phase(phase)
    if selection_profile == "loop_reviewer":
        return _groups_for_loop_reviewer_phase(phase)
    if selection_profile == "loop_runtime":
        return _groups_for_loop_runtime_phase(phase, feature_path)
    raise ValueError(_SELECTION_PROFILE_ERROR)


def normalize_check_groups(
    checks: list[str] | tuple[str, ...] | None,
    *,
    phase: HarnessCheckPhase = HarnessCheckPhase.MANUAL,
    selection_profile: SelectionProfile = "default",
    feature_path: str | Path | None = None,
) -> tuple[str, ...]:
    """Normalize requested check groups into deterministic execution order."""
    requested = (
        list(checks)
        if checks is not None
        else list(
            default_groups_for_selection_profile(
                phase=phase,
                selection_profile=selection_profile,
                feature_path=feature_path,
            )
        )
    )
    normalized = [str(group or "").strip() for group in requested]
    normalized = [group for group in normalized if group]

    invalid = sorted({group for group in normalized if group not in ALLOWED_CHECK_GROUPS})
    if invalid:
        raise ValueError(
            "unknown checks groups: "
            f"{invalid}. Supported: {sorted(ALLOWED_CHECK_GROUPS)}"
        )

    deduped: list[str] = []
    seen: set[str] = set()
    for group in normalized:
        if group in seen:
            continue
        seen.add(group)
        deduped.append(group)

    return tuple(group for group in CHECK_GROUP_ORDER if group in deduped)


def reviewers_group_selected(groups: list[str] | tuple[str, ...] | None) -> bool:
    """Return whether the normalized selection includes reviewer checks."""
    if not groups:
        return False
    return any(str(group).strip() == CHECK_GROUP_REVIEWERS for group in groups)
