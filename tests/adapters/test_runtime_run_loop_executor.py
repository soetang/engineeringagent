from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from engineeringagent.adapters.loop import RuntimeRunLoopExecutor
from engineeringagent.ports import RunLoopExecutionRequest


def test_runtime_run_loop_executor_builds_and_runs_controller(
    monkeypatch,
) -> None:
    """The adapter should translate the port request into runtime calls."""
    observed: dict[str, object] = {}

    def _fake_build_run_config(
        *,
        project_root: Path,
        feature_paths: tuple[str | Path, ...],
        options: object,
    ) -> str:
        observed["project_root"] = project_root
        observed["feature_paths"] = feature_paths
        observed["options"] = options
        return "runtime-config"

    def _fake_build_loop_run(config: str) -> str:
        observed["build_loop_run_config"] = config
        return "loop-run"

    def _fake_run_loop_controller(loop_run: str) -> int:
        observed["loop_run"] = loop_run
        return 23

    class _FakeRunConfigOptions:
        def __init__(
            self,
            dry_run: bool,
            run_all: bool,
            max_iterations: int,
            allow_dirty: bool,
            verbose_output: bool,
        ) -> None:
            observed["run_config_options_args"] = (
                dry_run,
                run_all,
                max_iterations,
                allow_dirty,
                verbose_output,
            )

    def _fake_import_module(name: str) -> SimpleNamespace:
        if name == "engineeringagent.loop":
            return SimpleNamespace(
                build_run_config=_fake_build_run_config,
                build_loop_run=_fake_build_loop_run,
                RunConfigOptions=_FakeRunConfigOptions,
            )
        if name == "engineeringagent.loop_runtime.controller":
            return SimpleNamespace(run_loop_controller=_fake_run_loop_controller)
        raise AssertionError(f"unexpected module import: {name}")

    monkeypatch.setattr(
        "engineeringagent.adapters.loop.runtime_run_loop_executor.import_module",
        _fake_import_module,
    )

    request = RunLoopExecutionRequest(
        project_root=Path("/tmp/project"),
        feature_paths=("docs/specifications/features/FEAT-001/spec.md",),
        run_all=False,
        dry_run=True,
        max_iterations=4,
        allow_dirty=False,
        verbose_output=True,
    )

    result = RuntimeRunLoopExecutor().run(request)

    assert result == 23
    assert observed["project_root"] == Path("/tmp/project")
    assert observed["feature_paths"] == (
        "docs/specifications/features/FEAT-001/spec.md",
    )
    assert observed["run_config_options_args"] == (True, False, 4, False, True)
    assert observed["build_loop_run_config"] == "runtime-config"
    assert observed["loop_run"] == "loop-run"
