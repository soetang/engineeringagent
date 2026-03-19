"""Tests for the implementation run application service."""

from developer.application.services.implementation_run_service import (
    run_implementation,
)
from developer.orchestrators.models import OrchestratorOutcome


class _FakeImplementationAgent:
    def __init__(self, outcome: OrchestratorOutcome) -> None:
        self._outcome = outcome

    def run(self) -> OrchestratorOutcome:
        return self._outcome


def test_run_implementation_returns_failure_feedback(monkeypatch) -> None:
    """Direct runs should surface the last failure feedback."""
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service._workspace_mode_enabled",
        lambda config_service: False,
    )
    monkeypatch.setattr(
        "developer.agent_backends.select_agent_backend_service.SelectAgentBackendService.select_agent",
        lambda self: object(),
    )
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service.build_implementation_agent",
        lambda agent_runner: _FakeImplementationAgent(
            OrchestratorOutcome(
                status="failed",
                iterations=3,
                feedback="ruff check failed",
            )
        ),
    )

    result = run_implementation()

    assert result.exit_code == 1
    assert result.message == "Implementation run failed: ruff check failed"
