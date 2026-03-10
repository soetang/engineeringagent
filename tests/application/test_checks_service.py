from __future__ import annotations

from pathlib import Path

import pytest

from engineeringagent.application import DefaultChecksService, RunChecksRequest
from engineeringagent.checks.results import ChecksRunResult
from engineeringagent.checks.contracts import HarnessCheckPhase
from engineeringagent.checks.strategy_contracts import CheckExecutionRecord


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


def test_default_checks_service_runs_single_requested_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The service should execute only the requested phase by default."""
    calls: list[HarnessCheckPhase] = []

    def _fake_run_checks(project_root: Path, *, phase: HarnessCheckPhase, **_: object) -> ChecksRunResult:
        calls.append(phase)
        assert project_root == Path("/tmp/project")
        return _build_result(ok=True, output=f"{phase.value}:ok")

    monkeypatch.setattr("engineeringagent.application.checks_service.checks_domain.run_checks", _fake_run_checks)

    result = DefaultChecksService().run(_build_request())

    assert calls == [HarnessCheckPhase.ITERATION_END]
    assert result.result.ok is True
    assert result.failed_phase is None
    assert result.phase_results == (
        (HarnessCheckPhase.ITERATION_END, result.result),
    )


def test_default_checks_service_stops_at_first_failed_phase_in_all_phases_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All-phase execution should stop once one phase fails."""
    calls: list[HarnessCheckPhase] = []

    def _fake_run_checks(project_root: Path, *, phase: HarnessCheckPhase, **_: object) -> ChecksRunResult:
        calls.append(phase)
        assert project_root == Path("/tmp/project")
        if phase is HarnessCheckPhase.FEATURE_DONE:
            return _build_result(ok=False, output="feature_done:failed")
        return _build_result(ok=True, output=f"{phase.value}:ok")

    monkeypatch.setattr("engineeringagent.application.checks_service.checks_domain.run_checks", _fake_run_checks)

    result = DefaultChecksService().run(_build_request(all_phases=True))

    assert calls == [
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
        DefaultChecksService().run(
            _build_request(selected_checks=["reviewers"])
        )
