from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from engineeringagent.adapters.loop import RuntimeRunLoopExecutor
from engineeringagent.ports import RunLoopExecutionRequest


def test_runtime_run_loop_executor_delegates_to_loop_module() -> None:
    """The adapter should normalize one port request into the legacy loop calls."""

    observed: dict[str, object] = {}

    class _FakeLoopModule:
        @staticmethod
        def RunConfigOptions(
            dry_run: bool,
            run_all: bool,
            max_iterations: int,
            allow_dirty: bool,
            verbose_output: bool,
        ) -> object:
            observed["options"] = {
                "dry_run": dry_run,
                "run_all": run_all,
                "max_iterations": max_iterations,
                "allow_dirty": allow_dirty,
                "verbose_output": verbose_output,
            }
            return SimpleNamespace(**observed["options"])

        @staticmethod
        def build_run_config(
            *,
            project_root: Path,
            feature_paths: tuple[str | Path, ...],
            options: object,
        ) -> object:
            observed["config"] = (project_root, feature_paths, options)
            return observed["config"]

        @staticmethod
        def build_loop_run(config: object) -> object:
            observed["loop_run"] = {"config": config}
            return observed["loop_run"]

        @staticmethod
        def run_loop_controller(loop_run: object) -> int:
            observed["controller_input"] = loop_run
            return 7

    executor = cast(Any, RuntimeRunLoopExecutor.__new__(RuntimeRunLoopExecutor))
    executor._loop_module = _FakeLoopModule()

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
    assert observed["options"] == {
        "dry_run": True,
        "run_all": False,
        "max_iterations": 3,
        "allow_dirty": False,
        "verbose_output": True,
    }
    config = cast(tuple[Path, tuple[str | Path, ...], object], observed["config"])
    assert observed["config"] == (
        Path("/tmp/project"),
        ("docs/spec/features/FEAT-001/spec.yaml",),
        config[2],
    )
    assert observed["loop_run"] == {"config": observed["config"]}
    assert observed["controller_input"] == observed["loop_run"]
