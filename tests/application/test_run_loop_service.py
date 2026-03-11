from __future__ import annotations

from pathlib import Path
from typing import Any

from engineeringagent.application import (
    RunLoopRequest,
    RunLoopResult,
    RunLoopRuntime,
    RunLoopService,
)
from engineeringagent.domain.quality import HarnessChecksDocument
from engineeringagent.ports import ValidationFailure


def _build_request(**overrides: object) -> RunLoopRequest:
    fields: dict[str, object] = {
        "project_root": Path("/tmp/project"),
        "feature_paths": ("docs/spec/features/FEAT-001/spec.yaml",),
        "run_all": False,
        "dry_run": False,
        "max_iterations": 5,
        "allow_dirty": False,
        "verbose_output": False,
    }
    fields.update(overrides)
    return RunLoopRequest.model_validate(fields)


class _FakeChecksCatalogRepository:
    def __init__(self, *, error: str | None = None) -> None:
        self._error = error
        self.project_roots: list[Path] = []

    def load(self, project_root: Path) -> HarnessChecksDocument:
        self.project_roots.append(project_root)
        if self._error is not None:
            raise ValidationFailure("ChecksCatalogRepository", self._error)
        return HarnessChecksDocument(contract_version="1.0", checks={})


class _FakeRunConfigOptions:
    def __init__(
        self,
        dry_run: bool,
        run_all: bool,
        max_iterations: int,
        allow_dirty: bool,
        verbose_output: bool,
    ) -> None:
        self.dry_run = dry_run
        self.run_all = run_all
        self.max_iterations = max_iterations
        self.allow_dirty = allow_dirty
        self.verbose_output = verbose_output


class _FakeRunLoopRuntime:
    def __init__(self, *, exit_code: int = 0) -> None:
        self.exit_code = exit_code
        self.config_calls: list[_FakeRunConfigOptions] = []
        self.run_config_calls: list[tuple[Path, tuple[str | Path, ...], object]] = []
        self.loop_runs: list[object] = []

    @property
    def runtime(self) -> RunLoopRuntime:
        return RunLoopRuntime(
            config_options=_FakeRunConfigOptions,
            build_run_config=self.build_run_config,
            build_loop_run=self.build_loop_run,
            run_loop_controller=self.run_loop_controller,
        )

    def build_run_config(
        self,
        *,
        project_root: Path,
        feature_paths: tuple[str | Path, ...],
        options: Any,
    ) -> tuple[Path, tuple[str | Path, ...], Any]:
        self.run_config_calls.append((project_root, feature_paths, options))
        return (project_root, feature_paths, options)

    def build_loop_run(self, config: tuple[Path, tuple[str | Path, ...], Any]) -> Any:
        loop_run = {"config": config}
        self.loop_runs.append(loop_run)
        return loop_run

    def run_loop_controller(self, loop_run: Any) -> int:
        self.config_calls.append(loop_run["config"][2])
        return self.exit_code


def test_run_loop_service_rejects_feature_paths_with_run_all() -> None:
    """The service should reject mixed `--all` plus positional feature input."""
    repository = _FakeChecksCatalogRepository()
    runtime = _FakeRunLoopRuntime()
    service = RunLoopService(
        checks_catalog_repository=repository,
        runtime=runtime.runtime,
    )

    result = service.run(_build_request(run_all=True))

    assert result == RunLoopResult(
        exit_code=1,
        message="run input error: positional feature paths cannot be used with --all",
    )
    assert repository.project_roots == []
    assert runtime.run_config_calls == []


def test_run_loop_service_requires_paths_when_run_all_is_disabled() -> None:
    """The service should require explicit feature paths without `--all`."""
    repository = _FakeChecksCatalogRepository()
    runtime = _FakeRunLoopRuntime()
    service = RunLoopService(
        checks_catalog_repository=repository,
        runtime=runtime.runtime,
    )

    result = service.run(_build_request(feature_paths=(), run_all=False))

    assert result == RunLoopResult(
        exit_code=1,
        message="run input error: provide one or more feature paths, or use --all",
    )
    assert repository.project_roots == []
    assert runtime.run_config_calls == []


def test_run_loop_service_preflights_checks_for_run_all_requests() -> None:
    """The service should stop before execution when run-all preflight fails."""
    repository = _FakeChecksCatalogRepository(
        error="run config error: missing harness/checks.yaml"
    )
    runtime = _FakeRunLoopRuntime()
    service = RunLoopService(
        checks_catalog_repository=repository,
        runtime=runtime.runtime,
    )

    result = service.run(_build_request(feature_paths=(), run_all=True))

    assert result == RunLoopResult(
        exit_code=1,
        message="run config error: missing harness/checks.yaml",
    )
    assert repository.project_roots == [Path("/tmp/project")]
    assert runtime.run_config_calls == []


def test_run_loop_service_executes_loop_after_preflight() -> None:
    """The service should execute the runtime loop through bootstrap-owned wiring."""
    repository = _FakeChecksCatalogRepository()
    runtime = _FakeRunLoopRuntime(exit_code=7)
    service = RunLoopService(
        checks_catalog_repository=repository,
        runtime=runtime.runtime,
    )

    request = _build_request(feature_paths=(), run_all=True, dry_run=True)
    result = service.run(request)

    assert result == RunLoopResult(exit_code=7, message=None)
    assert repository.project_roots == [Path("/tmp/project")]
    assert runtime.run_config_calls == [
        (
            request.project_root,
            request.feature_paths,
            runtime.config_calls[0],
        )
    ]
    assert isinstance(runtime.config_calls[0], _FakeRunConfigOptions)
    assert runtime.config_calls[0].dry_run is True
    assert runtime.config_calls[0].run_all is True
    assert runtime.config_calls[0].max_iterations == 5
    assert runtime.config_calls[0].allow_dirty is False
    assert runtime.config_calls[0].verbose_output is False
