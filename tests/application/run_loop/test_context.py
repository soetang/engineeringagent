from __future__ import annotations

from pathlib import Path

from engineeringagent.application.run_loop import LoopRun, RunConfig, RunServices, RunState


def test_run_state_updates_feedback_entries_copy_on_write() -> None:
    """Run-state updates should return copied models with stable feedback lookups."""
    feature_path = Path("docs/specifications/features/FEAT-001/specification.yaml")
    state = RunState()

    updated = state.with_feedback(feature_path, "fix the failing gate")

    assert state.feedback_for(feature_path) is None
    assert updated.feedback_for(feature_path) == "fix the failing gate"
    assert updated.with_feedback(feature_path, None).feedback_for(feature_path) is None


def test_loop_run_updates_state_copy_on_write() -> None:
    """Loop runs should replace state immutably when orchestration advances."""
    config = RunConfig(project_root=Path("/tmp/project"), feature_paths=(), dry_run=False)
    services = RunServices(
        resolve_run_targets=lambda *_args, **_kwargs: [],
        emit_run_all_snapshot_feedback=lambda *_args, **_kwargs: None,
        handle_dry_run=lambda *_args, **_kwargs: None,
        enforce_worktree_precondition=lambda *_args, **_kwargs: None,
        run_permission_precheck=lambda **_kwargs: True,
        run_selected_feature_iterations=lambda _loop_run: 0,
    )
    loop_run = LoopRun(config=config, services=services)
    next_state = RunState(total_iterations=1)

    updated = loop_run.with_state(next_state)

    assert loop_run.state.total_iterations == 0
    assert updated.state == next_state
