from __future__ import annotations

from pathlib import Path

from engineeringagent.changed_paths import ChangedPathsResult
from engineeringagent.checks.reviewers.engine import (
    PARSER_FAILURE_SUMMARY_PREFIX,
    REVIEWER_RESPONSEFORMAT_PLACEHOLDER,
    ReviewerDecisionEnvelope,
    build_reviewer_sandbox,
    run_reviewer,
)


RESPONSEFORMAT_PROMPT_SENTENCE = (
    "Return exactly one strict JSON object and no other text."
)


def _responseformat_prompt(body: str) -> str:
    return f"{REVIEWER_RESPONSEFORMAT_PLACEHOLDER}\n\n{body}"


def test_empty_folder_sandbox_copies_only_prompt_and_configured_assets_only(
    tmp_path: Path,
) -> None:
    prompt_path = (
        tmp_path / "harness" / "reviewers" / "prompts" / "onboarding_review.md"
    )
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("Review onboarding assets.", encoding="utf-8")

    (tmp_path / "README.md").write_text("Original README\n", encoding="utf-8")
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs" / "index.md").write_text("Docs index\n", encoding="utf-8")
    (tmp_path / ".opencode" / "agents").mkdir(parents=True)
    (tmp_path / ".opencode" / "agents" / "engineeringagent.md").write_text(
        "# agent\n",
        encoding="utf-8",
    )

    # These exist in the repo root but are not included as assets.
    (tmp_path / "src" / "engineeringagent").mkdir(parents=True)
    (tmp_path / "src" / "engineeringagent" / "cli.py").write_text(
        "print('ignored')\n",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir(parents=True)
    (tmp_path / "tests" / "test_ignored.py").write_text("pass\n", encoding="utf-8")
    (tmp_path / ".git").mkdir(parents=True)
    (tmp_path / ".git" / "config").write_text("[core]\n", encoding="utf-8")

    sandbox = build_reviewer_sandbox(
        tmp_path,
        "onboarding_review",
        {
            "prompt_file": "harness/reviewers/prompts/onboarding_review.md",
            "sandbox": {
                "mode": "empty_folder",
                "assets": ["README.md", "docs", ".opencode/agents"],
            },
        },
    )

    assert sandbox is not None
    try:
        files = sorted(
            str(path.relative_to(sandbox.execution_root))
            for path in sandbox.execution_root.rglob("*")
            if path.is_file()
        )
        assert files == [
            ".opencode/agents/engineeringagent.md",
            "README.md",
            "docs/index.md",
            "harness/reviewers/prompts/onboarding_review.md",
        ]
        assert not (sandbox.execution_root / "src").exists()
        assert not (sandbox.execution_root / "tests").exists()
        assert not (sandbox.execution_root / ".git").exists()
        assert not (sandbox.execution_root / ".engineeringagent").exists()
    finally:
        sandbox.cleanup()

    assert not sandbox.execution_root.exists()


def test_repo_empty_folder_sandbox_can_include_docs_and_opencode_agents(
    repo_root: Path,
) -> None:
    # This repository no longer ships a dedicated onboarding reviewer, but the
    # sandbox mode remains usable when a repo config opts into it.
    reviewer = {
        "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
        "sandbox": {
            "mode": "empty_folder",
            "assets": ["docs", ".opencode/agents"],
        },
    }

    assert (repo_root / "docs").is_dir()

    sandbox = build_reviewer_sandbox(repo_root, "code_simplifier", reviewer)
    assert sandbox is not None
    try:
        assert (sandbox.execution_root / "docs").is_dir()
        assert (sandbox.execution_root / ".opencode" / "agents").is_dir()
        assert not (sandbox.execution_root / "README.md").exists()
    finally:
        sandbox.cleanup()


def test_empty_folder_sandbox_does_not_copy_opencode_node_modules(
    tmp_path: Path,
) -> None:
    prompt_path = (
        tmp_path / "harness" / "reviewers" / "prompts" / "onboarding_review.md"
    )
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("Review onboarding assets.", encoding="utf-8")

    (tmp_path / ".opencode" / "agents").mkdir(parents=True)
    (tmp_path / ".opencode" / "agents" / "engineeringagent.md").write_text(
        "# agent\n",
        encoding="utf-8",
    )
    (tmp_path / ".opencode" / "node_modules").mkdir(parents=True)
    (tmp_path / ".opencode" / "node_modules" / "ignored.txt").write_text(
        "ignore me\n",
        encoding="utf-8",
    )

    sandbox = build_reviewer_sandbox(
        tmp_path,
        "onboarding_review",
        {
            "prompt_file": "harness/reviewers/prompts/onboarding_review.md",
            "sandbox": {"mode": "empty_folder", "assets": [".opencode"]},
        },
    )

    assert sandbox is not None
    try:
        assert (
            sandbox.execution_root / ".opencode" / "agents" / "engineeringagent.md"
        ).exists()
        assert not (
            sandbox.execution_root / ".opencode" / "node_modules" / "ignored.txt"
        ).exists()
    finally:
        sandbox.cleanup()


def test_run_reviewer_uses_empty_folder_sandbox_when_configured(
    tmp_path: Path,
) -> None:
    prompt_path = (
        tmp_path / "harness" / "reviewers" / "prompts" / "onboarding_review.md"
    )
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text(
        _responseformat_prompt("Review included onboarding assets."),
        encoding="utf-8",
    )

    readme_path = tmp_path / "README.md"
    readme_path.write_text("Original README\n", encoding="utf-8")
    (tmp_path / "src" / "engineeringagent").mkdir(parents=True)
    (tmp_path / "src" / "engineeringagent" / "cli.py").write_text(
        "print('ignored')\n",
        encoding="utf-8",
    )

    captured: dict[str, str | bool] = {}

    def _run_agent(project_root, prompt, *, output_type, max_validation_retries=2):
        del max_validation_retries
        sandbox_root = Path(project_root)
        captured["project_root"] = str(sandbox_root)
        captured["output_type"] = str(output_type)
        captured["prompt"] = prompt
        captured["sandbox_readme_before"] = (sandbox_root / "README.md").read_text(
            encoding="utf-8"
        )
        captured["sandbox_prompt_exists"] = (
            sandbox_root / "harness" / "reviewers" / "prompts" / "onboarding_review.md"
        ).exists()
        captured["sandbox_src_exists"] = (sandbox_root / "src").exists()
        return ReviewerDecisionEnvelope(
            decision="approve",
            summary="Looks good.",
            required_actions=[],
        )

    decision = run_reviewer(
        tmp_path,
        "onboarding_review",
        {
            "prompt_file": "harness/reviewers/prompts/onboarding_review.md",
            "trigger": {
                "phase": "feature_done",
                "on_change": ["README.md"],
            },
            "sandbox": {"mode": "empty_folder", "assets": ["README.md"]},
        },
        feature_id="FEAT-050",
        feature_path=tmp_path / "docs/spec/features/FEAT-050.yaml",
        changed_paths=ChangedPathsResult(
            paths=("README.md",),
            run_all=False,
            reason=None,
        ),
        prior_feedback=None,
        run_agent_fn=_run_agent,
    )

    assert decision["decision"] == "approve"
    assert captured["project_root"] != str(tmp_path)
    assert captured["sandbox_readme_before"] == "Original README\n"
    assert captured["sandbox_prompt_exists"] is True
    assert captured["sandbox_src_exists"] is False
    assert "$responseformat" not in str(captured["prompt"])
    assert RESPONSEFORMAT_PROMPT_SENTENCE in str(captured["prompt"])
    assert readme_path.read_text(encoding="utf-8") == "Original README\n"


def test_run_reviewer_uses_temp_worktree_snapshot_sandbox_when_configured(
    tmp_path: Path,
) -> None:
    prompt_path = (
        tmp_path / "harness" / "reviewers" / "prompts" / "onboarding_review.md"
    )
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text(
        _responseformat_prompt(
            "Read README.md and run the documented bootstrap flow.\n"
            "Create a new temporary directory and run the documented setup there.\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Getting started\n", encoding="utf-8")

    captured: dict[str, str] = {}

    def _run_agent(project_root, prompt, *, output_type, max_validation_retries=2):
        del max_validation_retries
        captured["project_root"] = str(project_root)
        captured["prompt"] = prompt
        captured["output_type"] = str(output_type)
        return ReviewerDecisionEnvelope(
            decision="approve",
            summary="Bootstrap succeeded.",
            required_actions=[],
        )

    decision = run_reviewer(
        tmp_path,
        "onboarding_review",
        {
            "prompt_file": "harness/reviewers/prompts/onboarding_review.md",
            "trigger": {
                "phase": "feature_done",
                "on_change": ["README.md"],
            },
            "sandbox": {"mode": "temp_worktree_snapshot"},
        },
        feature_id="FEAT-052",
        feature_path=tmp_path / "docs/spec/features/FEAT-052.yaml",
        changed_paths=ChangedPathsResult(
            paths=("README.md",),
            run_all=False,
            reason=None,
        ),
        prior_feedback=None,
        run_agent_fn=_run_agent,
    )

    assert decision["decision"] == "approve"
    assert captured["project_root"] != str(tmp_path)
    assert "$responseformat" not in captured["prompt"]
    assert RESPONSEFORMAT_PROMPT_SENTENCE in captured["prompt"]
    assert (
        "Create a new temporary directory and run the documented setup there."
        in captured["prompt"]
    )


def test_run_reviewer_returns_request_changes_when_snapshot_setup_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    prompt_path = (
        tmp_path / "harness" / "reviewers" / "prompts" / "onboarding_review.md"
    )
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("Review onboarding assets.", encoding="utf-8")

    def _raise_copytree(*_args, **_kwargs):
        raise OSError("copy failure")

    monkeypatch.setattr(
        "engineeringagent.checks.reviewers.engine.shutil.copytree",
        _raise_copytree,
    )

    decision = run_reviewer(
        tmp_path,
        "onboarding_review",
        {
            "prompt_file": "harness/reviewers/prompts/onboarding_review.md",
            "trigger": {
                "phase": "feature_done",
                "on_change": ["README.md"],
            },
            "sandbox": {"mode": "temp_worktree_snapshot"},
        },
        feature_id="FEAT-050",
        feature_path=tmp_path / "docs/spec/features/FEAT-050.yaml",
        changed_paths=ChangedPathsResult(
            paths=("README.md",),
            run_all=False,
            reason=None,
        ),
        prior_feedback=None,
        run_agent_fn=lambda *_args, **_kwargs: None,
    )

    assert decision["decision"] == "request_changes"
    assert decision["summary"].startswith(PARSER_FAILURE_SUMMARY_PREFIX)
    assert "sandbox setup failed" in decision["summary"]
