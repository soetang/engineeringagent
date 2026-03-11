from __future__ import annotations

from pathlib import Path

import pytest

from engineeringagent.adapters.checks import RuntimeChecksRunner
from engineeringagent.checks.contracts import HarnessCheckPhase
from engineeringagent.checks.results import ChecksRunResult
from engineeringagent.checks.strategy_contracts import CheckExecutionRecord
from engineeringagent.ports import ChecksRunRequest


def _build_result() -> ChecksRunResult:
    return ChecksRunResult(
        ok=True,
        dry_run=False,
        failed_check_id=None,
        failed_payload=None,
        output="ok",
        decisions=(),
        executions=(
            CheckExecutionRecord(
                check_id="smoke",
                check_type="command",
                ok=True,
                output="ok",
                payload={},
            ),
        ),
        prompt_feedback=None,
        command_invocations=(),
    )


def test_runtime_checks_runner_delegates_to_top_level_checks_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The adapter forwards the typed request to the stable checks facade."""
    captured: dict[str, object] = {}

    def _fake_run_checks(project_root: Path, *, phase: HarnessCheckPhase, checks: list[str] | None = None, **kwargs: object) -> ChecksRunResult:
        captured["project_root"] = project_root
        captured["phase"] = phase
        captured["checks"] = checks
        captured["kwargs"] = kwargs
        return _build_result()

    monkeypatch.setattr(
        "engineeringagent.adapters.checks.runtime_checks_runner.checks_domain.run_checks",
        _fake_run_checks,
    )

    result = RuntimeChecksRunner().run(
        ChecksRunRequest(
            project_root=Path("/tmp/project"),
            selected_checks=["commands"],
            check_id="smoke",
            feature_path="docs/spec.yaml",
            phase=HarnessCheckPhase.ITERATION_END,
            base="main",
            head="HEAD",
            verbose_output=True,
            dry_run=False,
        )
    )

    assert result == _build_result()
    assert captured == {
        "project_root": Path("/tmp/project"),
        "phase": HarnessCheckPhase.ITERATION_END,
        "checks": ["commands"],
        "kwargs": {
            "check_id": "smoke",
            "feature_path": "docs/spec.yaml",
            "verbose_output": True,
            "base": "main",
            "head": "HEAD",
            "dry_run": False,
        },
    }


def test_runtime_checks_runner_uses_checks_surface_for_reviewer_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reviewer-group detection stays inside the checks adapter boundary."""
    monkeypatch.setattr(
        "engineeringagent.adapters.checks.runtime_checks_runner.checks_domain.reviewers_group_selected",
        lambda selected_checks: selected_checks == ["reviewers"],
    )

    runner = RuntimeChecksRunner()

    assert runner.reviewers_group_selected(["reviewers"]) is True
    assert runner.reviewers_group_selected(["commands"]) is False
