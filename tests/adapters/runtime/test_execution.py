from __future__ import annotations

from pathlib import Path
from typing import Any

from engineeringagent.adapters.runtime.execution import run_loop_controller
from engineeringagent.adapters.runtime.loop_run_context import (
    LoopRun,
    RunConfig,
    RunServices,
)


def test_run_loop_controller_forwards_looprun_with_resolved_snapshot(
    tmp_path: Path,
) -> None:
    """Forward resolved loop-run snapshots into the execution controller."""
    resolved_feature_path = (
        tmp_path / "docs" / "spec" / "features" / "FEAT-078-looprun.yaml"
    )
    captured: dict[str, LoopRun] = {}

    def _run_selected_feature_iterations(loop_run: LoopRun) -> int:
        captured["loop_run"] = loop_run
        return 0

    code = run_loop_controller(
        LoopRun(
            config=RunConfig(
                project_root=tmp_path,
                feature_paths=(resolved_feature_path,),
                dry_run=False,
            ),
            services=RunServices(
                resolve_run_targets=lambda *_args, **_kwargs: [resolved_feature_path],
                emit_run_all_snapshot_feedback=lambda *_args, **_kwargs: None,
                handle_dry_run=lambda *_args, **_kwargs: None,
                enforce_worktree_precondition=lambda *_args, **_kwargs: None,
                run_permission_precheck=lambda **_kwargs: True,
                run_selected_feature_iterations=_run_selected_feature_iterations,
            ),
        )
    )

    assert code == 0
    forwarded_loop_run = captured["loop_run"]
    assert forwarded_loop_run.state.resolved_feature_paths == (resolved_feature_path,)
    assert forwarded_loop_run.state.total_iterations == 0


def test_run_loop_controller_rejects_invalid_max_iterations(
    tmp_path: Path,
    capsys: Any,
) -> None:
    """Reject non-positive max-iteration values in the loop controller."""
    code = run_loop_controller(
        LoopRun(
            config=RunConfig(
                project_root=tmp_path,
                feature_paths=(
                    tmp_path / "docs" / "spec" / "features" / "FEAT-079-looprun.yaml",
                ),
                dry_run=False,
                max_iterations=0,
            ),
            services=RunServices(
                resolve_run_targets=lambda *_args, **_kwargs: [],
                emit_run_all_snapshot_feedback=lambda *_args, **_kwargs: None,
                handle_dry_run=lambda *_args, **_kwargs: None,
                enforce_worktree_precondition=lambda *_args, **_kwargs: None,
                run_permission_precheck=lambda **_kwargs: True,
                run_selected_feature_iterations=lambda *_args, **_kwargs: 0,
            ),
        )
    )

    assert code == 1
    assert "max_iterations must be >= 1" in capsys.readouterr().out
