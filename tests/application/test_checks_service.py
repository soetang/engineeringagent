from __future__ import annotations

from pathlib import Path

from engineeringagent.application import DefaultChecksService, RunChecksRequest
from engineeringagent.checks.results import ChecksRunResult
from engineeringagent.checks.contracts import HarnessCheckPhase
from engineeringagent.checks.strategy_contracts import CheckExecutionRecord
from engineeringagent.ports import ChecksRunRequest
import pytest


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


def test_default_checks_service_runs_single_requested_phase() -> None:
    """The service should execute only the requested phase by default."""
    runner = _FakeChecksRunner(
        result_by_phase={
            HarnessCheckPhase.ITERATION_END: _build_result(
                ok=True,
                output="iteration_end:ok",
            )
        }
    )

    result = DefaultChecksService(runner).run(_build_request())

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
    """All-phase execution should stop once one phase fails."""
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

    result = DefaultChecksService(runner).run(_build_request(all_phases=True))

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
    """Reviewer runs require an explicit feature path before execution starts."""
    with pytest.raises(
        ValueError,
        match="feature_path is required when reviewers checks are selected",
    ):
        DefaultChecksService(
            _FakeChecksRunner(
                result_by_phase={
                    HarnessCheckPhase.ITERATION_END: _build_result(ok=True)
                },
                reviewers_selected=True,
            )
        ).run(
            _build_request(selected_checks=["reviewers"])
        )
