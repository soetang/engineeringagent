from __future__ import annotations

from pathlib import Path

import pytest

from engineeringagent.application import ChecksService, RunChecksRequest
from engineeringagent.domain.quality import (
    CheckExecutionRecord,
    ChecksRunResult,
    HarnessCheckPhase,
    HarnessChecksDocument,
)
from engineeringagent.ports import ChecksRunRequest, ValidationFailure


def _build_result(
    *,
    ok: bool,
    check_id: str = "smoke",
    check_type: str = "command",
    output: str = "",
) -> ChecksRunResult:
    execution = CheckExecutionRecord(
        check_id=check_id,
        check_type=check_type,
        ok=ok,
        output=output,
        payload={},
    )
    return ChecksRunResult(
        ok=ok,
        dry_run=False,
        failed_check_id=None if ok else check_id,
        failed_payload=None if ok else {},
        output=output,
        decisions=(),
        executions=(execution,),
        prompt_feedback=None,
        command_invocations=(),
    )


def _build_request(**overrides: object) -> RunChecksRequest:
    fields: dict[str, object] = {
        "project_root": Path("/tmp/project"),
        "selected_checks": None,
        "check_id": None,
        "feature_path": None,
        "phase": HarnessCheckPhase.ITERATION_END,
        "all_phases": False,
        "base": None,
        "head": None,
        "verbose_output": False,
        "dry_run": False,
    }
    fields.update(overrides)
    return RunChecksRequest.model_validate(fields)


class _FakeChecksRunner:
    def __init__(
        self,
        *,
        result_by_phase: dict[HarnessCheckPhase, ChecksRunResult],
        reviewers_selected: bool = False,
    ) -> None:
        self._result_by_phase = result_by_phase
        self._reviewers_selected = reviewers_selected
        self.requests: list[ChecksRunRequest] = []

    def run(self, request: ChecksRunRequest) -> ChecksRunResult:
        self.requests.append(request)
        return self._result_by_phase[request.phase]

    def reviewers_group_selected(self, selected_checks: list[str] | None) -> bool:
        assert selected_checks is None or isinstance(selected_checks, list)
        return self._reviewers_selected


class _FakeChecksCatalogRepository:
    def __init__(self, *, error: str | None = None) -> None:
        self._error = error
        self.project_roots: list[Path] = []

    def load(self, project_root: Path) -> HarnessChecksDocument:
        self.project_roots.append(project_root)
        if self._error is not None:
            raise ValidationFailure("ChecksCatalogRepository", self._error)
        return HarnessChecksDocument(contract_version="1.0", checks={})


def test_default_checks_service_runs_single_requested_phase() -> None:
    runner = _FakeChecksRunner(
        result_by_phase={
            HarnessCheckPhase.ITERATION_END: _build_result(
                ok=True,
                output="iteration_end:ok",
            )
        }
    )

    result = ChecksService(
        runner,
        _FakeChecksCatalogRepository(),
    ).run(_build_request())

    assert [request.phase for request in runner.requests] == [
        HarnessCheckPhase.ITERATION_END
    ]
    assert runner.requests[0].project_root == Path("/tmp/project")
    assert result.result.ok is True
    assert result.failed_phase is None
    assert result.phase_results == (
        (HarnessCheckPhase.ITERATION_END, result.result),
    )


def test_default_checks_service_stops_at_first_failed_phase_in_all_phases_mode() -> None:
    runner = _FakeChecksRunner(
        result_by_phase={
            HarnessCheckPhase.ITERATION_END: _build_result(
                ok=True,
                output="iteration_end:ok",
            ),
            HarnessCheckPhase.FEATURE_DONE: _build_result(
                ok=False,
                output="feature_done:failed",
            ),
        }
    )

    result = ChecksService(
        runner,
        _FakeChecksCatalogRepository(),
    ).run(_build_request(all_phases=True))

    assert [request.phase for request in runner.requests] == [
        HarnessCheckPhase.ITERATION_END,
        HarnessCheckPhase.FEATURE_DONE,
    ]
    assert result.result.ok is False
    assert result.failed_phase is HarnessCheckPhase.FEATURE_DONE
    assert result.failed_runtime_message == (
        "checks failed: phase=feature_done type=command check_id=smoke"
    )
    assert tuple(phase for phase, _ in result.phase_results) == (
        HarnessCheckPhase.ITERATION_END,
        HarnessCheckPhase.FEATURE_DONE,
    )


def test_default_checks_service_rejects_reviewers_without_feature_path() -> None:
    with pytest.raises(
        ValueError,
        match="feature_path is required when reviewers checks are selected",
    ):
        ChecksService(
            _FakeChecksRunner(
                result_by_phase={
                    HarnessCheckPhase.ITERATION_END: _build_result(ok=True)
                },
                reviewers_selected=True,
            ),
            _FakeChecksCatalogRepository(),
        ).run(_build_request(selected_checks=["reviewers"]))


def test_default_checks_service_preflights_catalog_for_harness_groups() -> None:
    runner = _FakeChecksRunner(
        result_by_phase={
            HarnessCheckPhase.ITERATION_END: _build_result(ok=True),
        }
    )
    repository = _FakeChecksCatalogRepository(
        error="checks config error: missing harness/checks.yaml",
    )

    result = ChecksService(runner, repository).run(
        _build_request(selected_checks=["commands"])
    )

    assert repository.project_roots == [Path("/tmp/project")]
    assert runner.requests == []
    assert result.result.ok is False
    assert result.result.output == "checks config error: missing harness/checks.yaml"
    assert result.phase_results == ()


def test_default_checks_service_skips_catalog_preflight_for_validate_only() -> None:
    runner = _FakeChecksRunner(
        result_by_phase={
            HarnessCheckPhase.ITERATION_END: _build_result(ok=True),
        }
    )
    repository = _FakeChecksCatalogRepository(
        error="checks config error: missing harness/checks.yaml",
    )

    result = ChecksService(runner, repository).run(
        _build_request(selected_checks=["validate"])
    )

    assert repository.project_roots == []
    assert [request.phase for request in runner.requests] == [
        HarnessCheckPhase.ITERATION_END
    ]
    assert result.result.ok is True
