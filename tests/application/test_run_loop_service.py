from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from engineeringagent.application import (
    RunLoopRequest,
    RunLoopResult,
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


def test_run_loop_service_rejects_feature_paths_with_run_all() -> None:
    """The service should reject mixed `--all` plus positional feature input."""
    repository = _FakeChecksCatalogRepository()
    service = RunLoopService(checks_catalog_repository=repository)

    result = service.run(_build_request(run_all=True))

    assert result == RunLoopResult(
        exit_code=1,
        message="run input error: positional feature paths cannot be used with --all",
    )
    assert repository.project_roots == []


def test_run_loop_service_requires_paths_when_run_all_is_disabled() -> None:
    """The service should require explicit feature paths without `--all`."""
    repository = _FakeChecksCatalogRepository()
    service = RunLoopService(checks_catalog_repository=repository)

    result = service.run(_build_request(feature_paths=(), run_all=False))

    assert result == RunLoopResult(
        exit_code=1,
        message="run input error: provide one or more feature paths, or use --all",
    )
    assert repository.project_roots == []


def test_run_loop_service_preflights_checks_for_run_all_requests() -> None:
    """The service should stop before execution when run-all preflight fails."""
    repository = _FakeChecksCatalogRepository(
        error="run config error: missing harness/checks.yaml"
    )
    service = RunLoopService(checks_catalog_repository=repository)

    result = service.run(_build_request(feature_paths=(), run_all=True))

    assert result == RunLoopResult(
        exit_code=1,
        message="run config error: missing harness/checks.yaml",
    )
    assert repository.project_roots == [Path("/tmp/project")]


def test_run_loop_service_executes_loop_after_preflight(monkeypatch) -> None:
    """The service should execute the runtime loop after a successful preflight."""
    repository = _FakeChecksCatalogRepository()
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
        return 7

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
                run_loop_controller=_fake_run_loop_controller,
            )
        raise AssertionError(f"unexpected module import: {name}")

    monkeypatch.setattr(
        "engineeringagent.application.run_loop_service.import_module",
        _fake_import_module,
    )

    service = RunLoopService(checks_catalog_repository=repository)

    request = _build_request(feature_paths=(), run_all=True, dry_run=True)
    result = service.run(request)

    assert result == RunLoopResult(exit_code=7, message=None)
    assert repository.project_roots == [Path("/tmp/project")]
    assert observed["project_root"] == request.project_root
    assert observed["feature_paths"] == request.feature_paths
    assert observed["run_config_options_args"] == (True, True, 5, False, False)
    assert observed["build_loop_run_config"] == "runtime-config"
    assert observed["loop_run"] == "loop-run"
