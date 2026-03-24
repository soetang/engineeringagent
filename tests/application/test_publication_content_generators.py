"""Tests for application-composed publication prompt generation helpers."""

from engineeringagent.config.service import ConfigService
from engineeringagent.orchestrators.publication import (
    CommitMessageContext,
    PullRequestContentContext,
)
from engineeringagent.prompts import ConfiguredPublicationPromptRenderer


def test_publication_prompt_renderer_renders_commit_prompt(tmp_path) -> None:
    """Commit prompt rendering should use the configured publication template."""
    commit_prompt = tmp_path / "commit.md"
    commit_prompt.write_text("Task {{ task_name }}", encoding="utf-8")
    pr_prompt = tmp_path / "pr.md"
    pr_prompt.write_text("PR {{ task_name }}", encoding="utf-8")
    config = tmp_path / "engineeringagent.toml"
    config.write_text(
        f'[prompts]\nimplementation_prompt_path = "impl.md"\ncommit_prompt_path = "{commit_prompt}"\npull_request_prompt_path = "{pr_prompt}"\n',
        encoding="utf-8",
    )

    renderer = ConfiguredPublicationPromptRenderer(
        ConfigService(config_file=str(config))
    )

    prompt = renderer.render_commit_prompt(
        CommitMessageContext(
            repo_path="/repo",
            task_name="ship-it",
            task_branch_name="ship-it",
            base_branch="main",
        )
    )

    assert prompt == "Task ship-it"


def test_publication_prompt_renderer_renders_pull_request_prompt(tmp_path) -> None:
    """PR prompt rendering should use the configured publication template."""
    commit_prompt = tmp_path / "commit.md"
    commit_prompt.write_text("Commit {{ task_name }}", encoding="utf-8")
    pr_prompt = tmp_path / "pr.md"
    pr_prompt.write_text("PR {{ task_name }}", encoding="utf-8")
    config = tmp_path / "engineeringagent.toml"
    config.write_text(
        f'[prompts]\nimplementation_prompt_path = "impl.md"\ncommit_prompt_path = "{commit_prompt}"\npull_request_prompt_path = "{pr_prompt}"\n',
        encoding="utf-8",
    )

    renderer = ConfiguredPublicationPromptRenderer(
        ConfigService(config_file=str(config))
    )

    prompt = renderer.render_pull_request_prompt(
        PullRequestContentContext(
            repo_path="/repo",
            task_name="ship-it",
            task_branch_name="ship-it",
            base_branch="main",
        )
    )

    assert prompt == "PR ship-it"
