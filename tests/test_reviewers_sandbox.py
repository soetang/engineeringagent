from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from engineeringagent.gates import ChangedPathsResult
from engineeringagent.opencode.client import DEFAULT_OPENCODE_AGENT
from engineeringagent.reviewers import (
    PARSER_FAILURE_SUMMARY_PREFIX,
    build_reviewer_sandbox,
    run_reviewer,
)


def test_readme_process_clean_room_sandbox_contains_expected_assets_only(
    tmp_path: Path,
) -> None:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "readme_process.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("Review README process quality.", encoding="utf-8")
    (tmp_path / "README.md").write_text("Original README\n", encoding="utf-8")

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
        "readme_process",
        {
            "prompt_file": "harness/reviewers/prompts/readme_process.md",
            "sandbox": {"mode": "clean_room_readme_cli"},
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
            ".engineeringagent/bin/engineeringagent",
            "README.md",
            "harness/reviewers/prompts/readme_process.md",
        ]
        assert not (sandbox.execution_root / "src").exists()
        assert not (sandbox.execution_root / "tests").exists()
        assert not (sandbox.execution_root / ".git").exists()
    finally:
        sandbox.cleanup()

    assert not sandbox.execution_root.exists()


def test_readme_process_uses_harness_clean_room_sandbox(
    tmp_path: Path,
) -> None:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "readme_process.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("Review README process quality.", encoding="utf-8")
    readme_path = tmp_path / "README.md"
    readme_path.write_text("Original README\n", encoding="utf-8")
    (tmp_path / "src" / "engineeringagent").mkdir(parents=True)
    (tmp_path / "src" / "engineeringagent" / "cli.py").write_text(
        "print('ignored')\n",
        encoding="utf-8",
    )

    captured: dict[str, str | bool] = {}

    def _start_agent(project_root, _prompt, *, agent=DEFAULT_OPENCODE_AGENT):
        sandbox_root = Path(project_root)
        captured["project_root"] = str(sandbox_root)
        captured["agent"] = agent
        sandbox_readme = sandbox_root / "README.md"
        captured["sandbox_readme_before"] = sandbox_readme.read_text(encoding="utf-8")
        captured["sandbox_prompt_exists"] = (
            sandbox_root / "harness" / "reviewers" / "prompts" / "readme_process.md"
        ).exists()
        captured["sandbox_src_exists"] = (sandbox_root / "src").exists()
        sandbox_readme.write_text("Sandbox changed\n", encoding="utf-8")
        return SimpleNamespace(
            stdout='{"decision":"approve","summary":"README process looks good."}',
            stderr="",
            returncode=0,
        )

    decision = run_reviewer(
        tmp_path,
        "readme_process",
        {
            "prompt_file": "harness/reviewers/prompts/readme_process.md",
            "trigger": {
                "phase": "feature_done",
                "on_change": ["README.md"],
            },
            "sandbox": {"mode": "clean_room_readme_cli"},
        },
        feature_id="FEAT-050",
        feature_path=tmp_path / "docs/spec/features/FEAT-050.yaml",
        changed_paths=ChangedPathsResult(
            paths=("README.md",),
            run_all=False,
            reason=None,
        ),
        prior_feedback=None,
        start_agent_fn=_start_agent,
    )

    assert decision["decision"] == "approve"
    assert captured["agent"] == DEFAULT_OPENCODE_AGENT
    assert captured["project_root"] != str(tmp_path)
    assert captured["sandbox_readme_before"] == "Original README\n"
    assert captured["sandbox_prompt_exists"] is True
    assert captured["sandbox_src_exists"] is False
    assert readme_path.read_text(encoding="utf-8") == "Original README\n"


def test_readme_process_clean_room_can_execute_engineeringagent_cli(
    tmp_path: Path,
) -> None:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "readme_process.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("Review README process quality.", encoding="utf-8")
    (tmp_path / "README.md").write_text("Original README\n", encoding="utf-8")

    package_root = tmp_path / "src" / "engineeringagent"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "cli.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "import json\n"
        "import sys\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    print(json.dumps({'argv': sys.argv[1:]}, sort_keys=True))\n",
        encoding="utf-8",
    )

    sandbox = build_reviewer_sandbox(
        tmp_path,
        "readme_process",
        {
            "prompt_file": "harness/reviewers/prompts/readme_process.md",
            "sandbox": {"mode": "clean_room_readme_cli"},
        },
    )

    assert sandbox is not None
    try:
        helper = (
            sandbox.execution_root / ".engineeringagent" / "bin" / "engineeringagent"
        )
        assert helper.exists()

        proc = subprocess.run(
            [str(helper), "gates", "list"],
            cwd=sandbox.execution_root,
            capture_output=True,
            text=True,
            check=False,
        )

        assert proc.returncode == 0
        assert proc.stdout.strip() == '{"argv": ["gates", "list"]}'
    finally:
        sandbox.cleanup()


def test_readme_process_runs_readme_bootstrap_in_fresh_temp_directory(
    tmp_path: Path,
) -> None:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "readme_process.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text(
        "Read README.md and run the documented bootstrap flow.\n"
        "Create a new temporary directory and run the documented setup there.\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Getting started\n", encoding="utf-8")

    captured: dict[str, str] = {}

    def _start_agent(project_root, prompt, *, agent=DEFAULT_OPENCODE_AGENT):
        captured["project_root"] = str(project_root)
        captured["prompt"] = prompt
        captured["agent"] = agent
        return SimpleNamespace(
            stdout='{"decision":"approve","summary":"README bootstrap succeeded."}',
            stderr="",
            returncode=0,
        )

    decision = run_reviewer(
        tmp_path,
        "readme_process",
        {
            "prompt_file": "harness/reviewers/prompts/readme_process.md",
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
        start_agent_fn=_start_agent,
    )

    assert decision["decision"] == "approve"
    assert captured["agent"] == DEFAULT_OPENCODE_AGENT
    assert captured["project_root"] != str(tmp_path)
    assert (
        "Create a new temporary directory and run the documented setup there."
        in captured["prompt"]
    )


def test_run_reviewer_returns_request_changes_when_sandbox_setup_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "readme_process.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("Review README process quality.", encoding="utf-8")

    def _raise_copytree(*_args, **_kwargs):
        raise OSError("copy failure")

    monkeypatch.setattr("engineeringagent.reviewers.shutil.copytree", _raise_copytree)

    decision = run_reviewer(
        tmp_path,
        "readme_process",
        {
            "prompt_file": "harness/reviewers/prompts/readme_process.md",
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
        start_agent_fn=lambda *_args, **_kwargs: None,
    )

    assert decision["decision"] == "request_changes"
    assert decision["summary"].startswith(PARSER_FAILURE_SUMMARY_PREFIX)
    assert "sandbox setup failed" in decision["summary"]
