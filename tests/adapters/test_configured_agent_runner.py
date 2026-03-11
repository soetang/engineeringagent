from __future__ import annotations

from pathlib import Path

from engineeringagent.adapters.agents import ConfiguredAgentRunner
from engineeringagent.ports import AgentRunRequest


def test_configured_agent_runner_delegates_to_canonical_agent_api(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """The adapter forwards the stable request envelope to `run_agent`."""
    recorded: list[tuple[Path, str, object, int]] = []

    def _fake_run_agent(
        project_root: Path,
        prompt: str,
        *,
        output_type: object,
        max_validation_retries: int,
    ) -> str:
        recorded.append(
            (project_root, prompt, output_type, max_validation_retries)
        )
        return "ok"

    monkeypatch.setattr(
        "engineeringagent.adapters.agents.run_agent",
        _fake_run_agent,
    )

    result = ConfiguredAgentRunner().run(
        AgentRunRequest(
            project_root=tmp_path,
            prompt="implement",
            output_type=str,
            max_validation_retries=4,
        )
    )

    assert result == "ok"
    assert recorded == [(tmp_path, "implement", str, 4)]
