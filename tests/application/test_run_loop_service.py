from __future__ import annotations

from pathlib import Path

from engineeringagent.application import (
    RunLoopRequest,
    RunLoopResult,
    RunLoopService,
)
from engineeringagent.ports import ChecksCatalogLoadResult


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


def _increment_and_return_zero(observed: dict[str, int], key: str) -> int:
    observed[key] += 1
    return 0


def _increment_mixed_counter(
    observed: dict[str, Path | int | None],
    key: str,
) -> int:
    current_value = observed[key]
    assert isinstance(current_value, int)
    observed[key] = current_value + 1
    return 0


def test_run_loop_service_rejects_feature_paths_with_run_all() -> None:
    """The service should reject mixed `--all` plus positional feature input."""
    observed: dict[str, int] = {
        "execute_calls": 0,
    }
    repository = _FakeChecksCatalogRepository(
        ChecksCatalogLoadResult(document=None, error=None)
    )

    service = RunLoopService(
        checks_catalog_repository=repository,
        execute_run_loop=lambda _request: _increment_and_return_zero(
            observed, "execute_calls"
        ),
    )

    result = service.run(_build_request(run_all=True))

    assert result == RunLoopResult(
        exit_code=1,
        message="run input error: positional feature paths cannot be used with --all",
    )
    assert observed == {"execute_calls": 0}
    assert repository.project_roots == []


def test_run_loop_service_requires_paths_when_run_all_is_disabled() -> None:
    """The service should require explicit feature paths without `--all`."""
    observed: dict[str, int] = {
        "execute_calls": 0,
    }
    repository = _FakeChecksCatalogRepository(
        ChecksCatalogLoadResult(document=None, error=None)
    )

    service = RunLoopService(
        checks_catalog_repository=repository,
        execute_run_loop=lambda _request: _increment_and_return_zero(
            observed, "execute_calls"
        ),
    )

    result = service.run(_build_request(feature_paths=(), run_all=False))

    assert result == RunLoopResult(
        exit_code=1,
        message="run input error: provide one or more feature paths, or use --all",
    )
    assert observed == {"execute_calls": 0}
    assert repository.project_roots == []


def test_run_loop_service_preflights_checks_for_run_all_requests() -> None:
    """The service should stop before execution when run-all preflight fails."""
    observed: dict[str, Path | int | None] = {"execute_calls": 0}
    repository = _FakeChecksCatalogRepository(
        ChecksCatalogLoadResult(
            document=None,
            error="run config error: missing harness/checks.yaml",
        )
    )

    service = RunLoopService(
        checks_catalog_repository=repository,
        execute_run_loop=lambda _request: _increment_mixed_counter(
            observed, "execute_calls"
        ),
    )

    result = service.run(_build_request(feature_paths=(), run_all=True))

    assert result == RunLoopResult(
        exit_code=1,
        message="run config error: missing harness/checks.yaml",
    )
    assert observed == {"execute_calls": 0}
    assert repository.project_roots == [Path("/tmp/project")]


def test_run_loop_service_executes_loop_after_preflight() -> None:
    """The service should execute the loop after a successful run-all preflight."""
    observed: dict[str, Path | RunLoopRequest | None] = {
        "executed_request": None,
    }
    repository = _FakeChecksCatalogRepository(
        ChecksCatalogLoadResult(document=None, error=None)
    )

    service = RunLoopService(
        checks_catalog_repository=repository,
        execute_run_loop=lambda request: (
            observed.__setitem__("executed_request", request),
            7,
        )[1],
    )

    request = _build_request(feature_paths=(), run_all=True, dry_run=True)
    result = service.run(request)

    assert result == RunLoopResult(exit_code=7, message=None)
    assert observed == {"executed_request": request}
    assert repository.project_roots == [Path("/tmp/project")]
