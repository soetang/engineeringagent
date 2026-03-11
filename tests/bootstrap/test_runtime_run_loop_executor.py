from __future__ import annotations

from pathlib import Path
from typing import cast

import engineeringagent.adapters.runtime.execution as runtime_executor_adapter_module
from engineeringagent.adapters.runtime import RuntimeRunLoopExecutor
from engineeringagent.application.feature_iteration_service import (
    FeatureIterationService,
)
from engineeringagent.ports import RunLoopExecutionRequest
from engineeringagent.ports.version_control import VersionControlGateway


def test_runtime_run_loop_executor_uses_runtime_run_builder(
    monkeypatch,
) -> None:
    """Bootstrap runtime execution should build run context through adapter-owned runtime helpers."""

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
            feature_paths=("docs/spec/features/FEAT-001/spec.yaml",),
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
    assert config_args[1] == ("docs/spec/features/FEAT-001/spec.yaml",)
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
