"""Tests for the implementation CLI command."""

from pathlib import Path
from shutil import copytree

import pytest
from typer.testing import CliRunner

from developer.agents.adapters.codex_adapter import CodexAdapter
from developer.application.models import ImplementationRunResult
from developer.orchestrators.models import AgentResult, OrchestratorOutcome
from developer.presentation.cli import app


def test_implementation_command_uses_real_selectors(monkeypatch) -> None:
    """The command should compose the agent via the selector service."""
    selected_agents: list[object] = []

    def fake_select_agent(self, **kwargs):
        del kwargs
        selected_agents.append(self)

        class FakeRunner:
            def run_agent(self, prompt: str, output_format=None) -> AgentResult:
                del prompt, output_format
                return AgentResult(summary="done")

        return FakeRunner()

    class FakeImplementationAgent:
        def run(self) -> OrchestratorOutcome:
            return OrchestratorOutcome(status="success", iterations=1)

    def fake_build_implementation_agent(agent_runner):
        del agent_runner
        return FakeImplementationAgent()

    monkeypatch.setattr(
        "developer.agents.select_agent_service.SelectAgentService.select_agent",
        fake_select_agent,
    )
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service.build_implementation_agent",
        fake_build_implementation_agent,
    )
    monkeypatch.setattr(
        "developer.application.services.implementation_run_service._workspace_mode_enabled",
        lambda config_service: False,
    )

    runner = CliRunner()
    result = runner.invoke(app, ["implementation", "run"])

    assert result.exit_code == 0
    assert len(selected_agents) == 1
    assert "Implementation run succeeded" in result.output


@pytest.mark.integration
def test_cli_implementation_run_succeeds(monkeypatch) -> None:
    """The implementation command should succeed with test-local runtime files."""
    runner = CliRunner()
    fixture_dir = Path(__file__).resolve().parent / "stub_data" / "implementation_run"

    def fake_run_agent(
        self,
        prompt: str,
        output_format=None,
    ) -> AgentResult:
        del self, prompt, output_format
        return AgentResult(summary="done")

    monkeypatch.setattr(CodexAdapter, "run_agent", fake_run_agent)

    with runner.isolated_filesystem():
        copytree(fixture_dir, Path("."), dirs_exist_ok=True)
        result = runner.invoke(app, ["implementation", "run"])

    assert result.exit_code == 0
    assert "Implementation run succeeded" in result.output


def test_implementation_command_uses_workspace_flow_when_configured(
    monkeypatch,
) -> None:
    """The command should use workspace orchestration when configured."""
    runner = CliRunner()

    monkeypatch.setattr(
        "developer.presentation.commands.implementation.run_implementation",
        lambda: ImplementationRunResult(
            exit_code=0,
            message="workspace=workspace-1 run=run-1 status=succeeded",
        ),
    )

    with runner.isolated_filesystem():
        Path("engineeringagent.toml").write_text(
            """
[workspaces]
default_provider = "git_worktree"
state_dir = ".developer/state"
git_worktree_root_dir = ".developer/workspaces"
""".strip(),
            encoding="utf-8",
        )
        result = runner.invoke(app, ["implementation", "run"])

    assert result.exit_code == 0
    assert "workspace=workspace-1 run=run-1 status=succeeded" in result.output
