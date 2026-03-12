from __future__ import annotations

from pathlib import Path

from engineeringagent.application import (
    RunLoopService,
)
from engineeringagent.application.contracts.run_loop import (
    RunLoopRequest,
    RunLoopResult,
)
from engineeringagent.domain.quality import HarnessChecksDocument
from engineeringagent.ports import RunLoopExecutionRequest, ValidationFailure


def _build_request(**overrides: object) -> RunLoopRequest:
    fields: dict[str, object] = {
        "project_root": Path("/tmp/project"),
        "feature_paths": ("docs/specifications/features/FEAT-001/spec.yaml",),
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


class _FakeRunLoopExecutor:
    def __init__(self, *, exit_code: int = 0) -> None:
        self.exit_code = exit_code
        self.requests: list[RunLoopExecutionRequest] = []

    def run(self, request: RunLoopExecutionRequest) -> int:
        self.requests.append(request)
        return self.exit_code


def test_run_loop_service_rejects_feature_paths_with_run_all() -> None:
    """The service should reject mixed `--all` plus positional feature input."""
    repository = _FakeChecksCatalogRepository()
    executor = _FakeRunLoopExecutor()
    service = RunLoopService(
        checks_catalog_repository=repository,
        executor=executor,
    )

    result = service.run(_build_request(run_all=True))

    assert result == RunLoopResult(
        exit_code=1,
        message="run input error: positional feature paths cannot be used with --all",
    )
    assert repository.project_roots == []
    assert executor.requests == []


def test_run_loop_service_requires_paths_when_run_all_is_disabled() -> None:
    """The service should require explicit feature paths without `--all`."""
    repository = _FakeChecksCatalogRepository()
    executor = _FakeRunLoopExecutor()
    service = RunLoopService(
        checks_catalog_repository=repository,
        executor=executor,
    )

    result = service.run(_build_request(feature_paths=(), run_all=False))

    assert result == RunLoopResult(
        exit_code=1,
        message="run input error: provide one or more feature paths, or use --all",
    )
    assert repository.project_roots == []
    assert executor.requests == []


def test_run_loop_service_preflights_checks_for_run_all_requests() -> None:
    """The service should stop before execution when run-all preflight fails."""
    repository = _FakeChecksCatalogRepository(
        error="run config error: missing harness/checks.yaml"
    )
    executor = _FakeRunLoopExecutor()
    service = RunLoopService(
        checks_catalog_repository=repository,
        executor=executor,
    )

    result = service.run(_build_request(feature_paths=(), run_all=True))

    assert result == RunLoopResult(
        exit_code=1,
        message="run config error: missing harness/checks.yaml",
    )
    assert repository.project_roots == [Path("/tmp/project")]
    assert executor.requests == []


def test_run_loop_service_executes_loop_after_preflight() -> None:
    """The service should execute the runtime loop through bootstrap-owned wiring."""
    repository = _FakeChecksCatalogRepository()
    executor = _FakeRunLoopExecutor(exit_code=7)
    service = RunLoopService(
        checks_catalog_repository=repository,
        executor=executor,
    )

    request = _build_request(feature_paths=(), run_all=True, dry_run=True)
    result = service.run(request)

    assert result == RunLoopResult(exit_code=7, message=None)
    assert repository.project_roots == [Path("/tmp/project")]
    assert executor.requests == [
        RunLoopExecutionRequest(
            project_root=request.project_root,
            feature_paths=request.feature_paths,
            run_all=True,
            dry_run=True,
            max_iterations=5,
            allow_dirty=False,
            verbose_output=False,
        )
    ]
