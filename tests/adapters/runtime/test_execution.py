from __future__ import annotations

from pathlib import Path
from typing import Any
from typing import cast

import engineeringagent.adapters.runtime.execution as runtime_executor_adapter_module
from engineeringagent.adapters.runtime import RuntimeRunLoopExecutor
from engineeringagent.adapters.runtime.execution import run_loop_controller
from engineeringagent.adapters.runtime.loop_run_context import (
    LoopRun,
    RunConfig,
    RunServices,
)
from engineeringagent.application import FeatureIterationService
from engineeringagent.ports import RunLoopExecutionRequest
from engineeringagent.ports.version_control import VersionControlGateway


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


def test_runtime_run_loop_executor_uses_runtime_run_builder(
    monkeypatch,
) -> None:
    """Runtime execution adapter should build run context through adapter-owned helpers."""

    observed: dict[str, object] = {}

    def _build_run_config(
        *,
        project_root: Path,
        feature_paths: tuple[str | Path, ...],
        options: object,
    ) -> object:
        observed["config_args"] = (project_root, feature_paths, options)
        return {"config": "value"}

    def _build_loop_run(
        config: object,
        *,
        enforce_worktree_precondition_fn: object,
        run_selected_feature_iterations_fn: object,
        print_summary_fn: object,
    ) -> object:
        observed["loop_run_args"] = (
            config,
            enforce_worktree_precondition_fn,
            run_selected_feature_iterations_fn,
            print_summary_fn,
        )
        return {"loop_run": config}

    def _run_loop_controller(loop_run: object) -> int:
        observed["controller_input"] = loop_run
        return 7

    monkeypatch.setattr(
        runtime_executor_adapter_module, "build_run_config", _build_run_config
    )
    monkeypatch.setattr(
        runtime_executor_adapter_module, "build_loop_run", _build_loop_run
    )
    monkeypatch.setattr(
        runtime_executor_adapter_module,
        "run_loop_controller",
        _run_loop_controller,
    )

    executor = RuntimeRunLoopExecutor(
        build_feature_iteration_service=lambda _project_root: cast(
            FeatureIterationService, None
        ),
        build_version_control_gateway=lambda _project_root: cast(
            VersionControlGateway, None
        ),
    )
    result = executor.run(
        RunLoopExecutionRequest(
            project_root=Path("/tmp/project"),
            feature_paths=("docs/specifications/features/FEAT-001/spec.yaml",),
            run_all=False,
            dry_run=True,
            max_iterations=3,
            allow_dirty=False,
            verbose_output=True,
        )
    )

    assert result == 7
    config_args = observed["config_args"]
    assert isinstance(config_args, tuple)
    assert config_args[0] == Path("/tmp/project")
    assert config_args[1] == ("docs/specifications/features/FEAT-001/spec.yaml",)
    options = config_args[2]
    assert isinstance(options, runtime_executor_adapter_module.RunConfigOptions)
    assert options == runtime_executor_adapter_module.RunConfigOptions(
        dry_run=True,
        run_all=False,
        max_iterations=3,
        allow_dirty=False,
        verbose_output=True,
    )
    loop_run_args = observed["loop_run_args"]
    assert isinstance(loop_run_args, tuple)
    assert loop_run_args[0] == {"config": "value"}
    assert callable(loop_run_args[3])
    assert observed["controller_input"] == {"loop_run": {"config": "value"}}
