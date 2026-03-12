from __future__ import annotations

from pathlib import Path

from engineeringagent.adapters.runtime.context import (
    LoopRun,
    RunConfig,
    RunServices,
    RunState,
)


def test_run_state_updates_feedback_and_resolved_paths() -> None:
    """Track runtime feedback and resolved feature paths in immutable state."""
    state = RunState()

    state = state.with_feedback(Path("/tmp/feature-a"), "retry feedback")
    state = state.with_resolved_feature_paths([Path("/tmp/feature-a")])

    assert state.feedback_for(Path("/tmp/feature-a")) == "retry feedback"
    assert state.resolved_feature_paths == (Path("/tmp/feature-a"),)


def test_loop_run_with_state_returns_updated_copy() -> None:
    """Return a copied loop context when runtime state changes."""
    config = RunConfig(project_root=Path("/tmp/project"), feature_paths=(), dry_run=False)
    services = RunServices(
        resolve_run_targets=lambda _root, _paths, _run_all: [],
        emit_run_all_snapshot_feedback=lambda _paths, _run_all: None,
        handle_dry_run=lambda _paths, _run_all, _dry_run: None,
        enforce_worktree_precondition=lambda _root, _allow_dirty: None,
        run_permission_precheck=lambda **_kwargs: True,
        run_selected_feature_iterations=lambda _loop_run: 0,
    )
    loop_run = LoopRun(config=config, services=services)
    next_state = RunState(total_iterations=1)

    updated = loop_run.with_state(next_state)

    assert updated is not loop_run
    assert updated.state == next_state
    assert loop_run.state == RunState()
