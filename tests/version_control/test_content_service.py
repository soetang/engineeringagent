"""Tests for prompt-backed version control content generation."""

from engineeringagent.config.service import ConfigService
from engineeringagent.version_control.content_models import (
    CommitMessageOutput,
    CommitPromptContext,
    PullRequestContentOutput,
    PullRequestPromptContext,
)
from engineeringagent.version_control.content_service import (
    VersionControlContentService,
)


class _FakeAgentRunner:
    def __init__(self, response) -> None:
        self.response = response
        self.prompts: list[str] = []

    def run_agent(self, prompt: str, output_format=None):
        del output_format
        self.prompts.append(prompt)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_content_service_renders_commit_prompt_and_parses_output(tmp_path) -> None:
    """Commit generation should render the configured prompt and parse output."""
    commit_prompt = tmp_path / "commit.md"
    commit_prompt.write_text("Task {{ task_name }}", encoding="utf-8")
    pr_prompt = tmp_path / "pr.md"
    pr_prompt.write_text("PR {{ task_name }}", encoding="utf-8")
    config = tmp_path / "engineeringagent.toml"
    config.write_text(
        f'[prompts]\nimplementation_prompt_path = "impl.md"\ncommit_prompt_path = "{commit_prompt}"\npull_request_prompt_path = "{pr_prompt}"\n',
        encoding="utf-8",
    )
    agent = _FakeAgentRunner(CommitMessageOutput(subject="Ship it", body=""))
    service = VersionControlContentService(
        agent_runner=agent,
        config_service=ConfigService(config_file=str(config)),
    )

    result = service.build_commit_message(
        CommitPromptContext(
            task_name="ship-it",
            task_branch_name="ship-it",
            base_branch="main",
        )
    )

    assert result.subject == "Ship it"
    assert "Task ship-it" in agent.prompts[0]


def test_content_service_uses_pr_fallback_on_agent_failure(tmp_path) -> None:
    """PR generation should fall back deterministically when the agent fails."""
    commit_prompt = tmp_path / "commit.md"
    commit_prompt.write_text("Commit {{ task_name }}", encoding="utf-8")
    pr_prompt = tmp_path / "pr.md"
    pr_prompt.write_text("PR {{ task_name }}", encoding="utf-8")
    config = tmp_path / "engineeringagent.toml"
    config.write_text(
        f'[prompts]\nimplementation_prompt_path = "impl.md"\ncommit_prompt_path = "{commit_prompt}"\npull_request_prompt_path = "{pr_prompt}"\n',
        encoding="utf-8",
    )
    service = VersionControlContentService(
        agent_runner=_FakeAgentRunner(RuntimeError("boom")),
        config_service=ConfigService(config_file=str(config)),
    )

    result = service.build_pull_request_content(
        PullRequestPromptContext(
            task_name="ship-it",
            task_branch_name="ship-it",
            base_branch="main",
        )
    )

    assert result.title == "Complete ship-it"
    assert result.summary == ["Complete task ship-it."]
    assert "## Summary" in result.body
