from __future__ import annotations

from pathlib import Path

from engineeringagent.application import (
    RunLoopRequest,
    RunLoopResult,
    RunLoopService,
)


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


def _increment(observed: dict[str, int], key: str) -> tuple[None, None]:
    observed[key] += 1
    return (None, None)


def _increment_and_return_zero(observed: dict[str, int], key: str) -> int:
    observed[key] += 1
    return 0


def _set_project_root(
    observed: dict[str, Path | int | None],
    project_root: Path,
) -> tuple[None, str]:
    observed["project_root"] = project_root
    return (None, "run config error: missing harness/checks.yaml")


def _increment_mixed_counter(
    observed: dict[str, Path | int | None],
    key: str,
) -> int:
    current_value = observed[key]
    assert isinstance(current_value, int)
    observed[key] = current_value + 1
    return 0


def test_run_loop_service_rejects_feature_paths_with_run_all() -> None:
    observed: dict[str, int] = {
        "checks_calls": 0,
        "execute_calls": 0,
    }

    service = RunLoopService(
        load_harness_checks_document=lambda _project_root: _increment(
            observed, "checks_calls"
        ),
        execute_run_loop=lambda _request: _increment_and_return_zero(
            observed, "execute_calls"
        ),
    )

    result = service.run(_build_request(run_all=True))

    assert result == RunLoopResult(
        exit_code=1,
        message="run input error: positional feature paths cannot be used with --all",
    )
    assert observed == {"checks_calls": 0, "execute_calls": 0}


def test_run_loop_service_requires_paths_when_run_all_is_disabled() -> None:
    observed: dict[str, int] = {
        "checks_calls": 0,
        "execute_calls": 0,
    }

    service = RunLoopService(
        load_harness_checks_document=lambda _project_root: _increment(
            observed, "checks_calls"
        ),
        execute_run_loop=lambda _request: _increment_and_return_zero(
            observed, "execute_calls"
        ),
    )

    result = service.run(_build_request(feature_paths=(), run_all=False))

    assert result == RunLoopResult(
        exit_code=1,
        message="run input error: provide one or more feature paths, or use --all",
    )
    assert observed == {"checks_calls": 0, "execute_calls": 0}


def test_run_loop_service_preflights_checks_for_run_all_requests() -> None:
    observed: dict[str, Path | int | None] = {
        "project_root": None,
        "execute_calls": 0,
    }

    service = RunLoopService(
        load_harness_checks_document=lambda project_root: _set_project_root(
            observed, project_root
        ),
        execute_run_loop=lambda _request: _increment_mixed_counter(
            observed, "execute_calls"
        ),
    )

    result = service.run(_build_request(feature_paths=(), run_all=True))

    assert result == RunLoopResult(
        exit_code=1,
        message="run config error: missing harness/checks.yaml",
    )
    assert observed == {
        "project_root": Path("/tmp/project"),
        "execute_calls": 0,
    }


def test_run_loop_service_executes_loop_after_preflight() -> None:
    observed: dict[str, Path | RunLoopRequest | None] = {
        "checks_project_root": None,
        "executed_request": None,
    }

    service = RunLoopService(
        load_harness_checks_document=lambda project_root: (
            observed.__setitem__("checks_project_root", project_root),
            None,
        ),
        execute_run_loop=lambda request: (
            observed.__setitem__("executed_request", request),
            7,
        )[1],
    )

    request = _build_request(feature_paths=(), run_all=True, dry_run=True)
    result = service.run(request)

    assert result == RunLoopResult(exit_code=7, message=None)
    assert observed == {
        "checks_project_root": Path("/tmp/project"),
        "executed_request": request,
    }
