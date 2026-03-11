from __future__ import annotations

from pathlib import Path

from engineeringagent.application import (
    RunLoopRequest,
    RunLoopResult,
    RunLoopService,
)
from engineeringagent.ports import ChecksCatalogLoadResult, RunLoopExecutionRequest


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
    def __init__(self, result: ChecksCatalogLoadResult) -> None:
        self._result = result
        self.project_roots: list[Path] = []

    def load(self, project_root: Path) -> ChecksCatalogLoadResult:
        self.project_roots.append(project_root)
        return self._result


class _FakeRunLoopExecutor:
    def __init__(self, exit_code: int = 0) -> None:
        self._exit_code = exit_code
        self.requests: list[RunLoopExecutionRequest] = []

    def run(self, request: RunLoopExecutionRequest) -> int:
        self.requests.append(request)
        return self._exit_code


def test_run_loop_service_rejects_feature_paths_with_run_all() -> None:
    """The service should reject mixed `--all` plus positional feature input."""
    observed: dict[str, int] = {
        "execute_calls": 0,
    }
    repository = _FakeChecksCatalogRepository(
        ChecksCatalogLoadResult(document=None, error=None)
    )
    executor = _FakeRunLoopExecutor()

    service = RunLoopService(
        checks_catalog_repository=repository,
        run_loop_executor=executor,
    )

    result = service.run(_build_request(run_all=True))

    assert result == RunLoopResult(
        exit_code=1,
        message="run input error: positional feature paths cannot be used with --all",
    )
    assert observed == {"execute_calls": 0}
    assert executor.requests == []
    assert repository.project_roots == []


def test_run_loop_service_requires_paths_when_run_all_is_disabled() -> None:
    """The service should require explicit feature paths without `--all`."""
    observed: dict[str, int] = {
        "execute_calls": 0,
    }
    repository = _FakeChecksCatalogRepository(
        ChecksCatalogLoadResult(document=None, error=None)
    )
    executor = _FakeRunLoopExecutor()

    service = RunLoopService(
        checks_catalog_repository=repository,
        run_loop_executor=executor,
    )

    result = service.run(_build_request(feature_paths=(), run_all=False))

    assert result == RunLoopResult(
        exit_code=1,
        message="run input error: provide one or more feature paths, or use --all",
    )
    assert observed == {"execute_calls": 0}
    assert executor.requests == []
    assert repository.project_roots == []


def test_run_loop_service_preflights_checks_for_run_all_requests() -> None:
    """The service should stop before execution when run-all preflight fails."""
    repository = _FakeChecksCatalogRepository(
        ChecksCatalogLoadResult(
            document=None,
            error="run config error: missing harness/checks.yaml",
        )
    )
    executor = _FakeRunLoopExecutor()

    service = RunLoopService(
        checks_catalog_repository=repository,
        run_loop_executor=executor,
    )

    result = service.run(_build_request(feature_paths=(), run_all=True))

    assert result == RunLoopResult(
        exit_code=1,
        message="run config error: missing harness/checks.yaml",
    )
    assert executor.requests == []
    assert repository.project_roots == [Path("/tmp/project")]


def test_run_loop_service_executes_loop_after_preflight() -> None:
    """The service should execute the loop after a successful run-all preflight."""
    repository = _FakeChecksCatalogRepository(
        ChecksCatalogLoadResult(document=None, error=None)
    )
    executor = _FakeRunLoopExecutor(exit_code=7)

    service = RunLoopService(
        checks_catalog_repository=repository,
        run_loop_executor=executor,
    )

    request = _build_request(feature_paths=(), run_all=True, dry_run=True)
    result = service.run(request)

    assert result == RunLoopResult(exit_code=7, message=None)
    assert executor.requests == [
        RunLoopExecutionRequest(
            project_root=request.project_root,
            feature_paths=request.feature_paths,
            run_all=request.run_all,
            dry_run=request.dry_run,
            max_iterations=request.max_iterations,
            allow_dirty=request.allow_dirty,
            verbose_output=request.verbose_output,
        )
    ]
    assert repository.project_roots == [Path("/tmp/project")]
