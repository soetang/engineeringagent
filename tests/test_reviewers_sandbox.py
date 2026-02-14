from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from engineeringagent.gates import ChangedPathsResult
from engineeringagent.reviewers import PARSER_FAILURE_SUMMARY_PREFIX, run_reviewer


def test_run_reviewer_uses_temp_snapshot_sandbox_for_readme_process(
    tmp_path: Path,
) -> None:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "readme_process.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("Review README process quality.", encoding="utf-8")
    readme_path = tmp_path / "README.md"
    readme_path.write_text("Original README\n", encoding="utf-8")

    captured: dict[str, str] = {}

    def _start_agent(project_root, _prompt, *, agent="build"):
        captured["project_root"] = str(project_root)
        captured["agent"] = agent
        snapshot_readme = Path(project_root) / "README.md"
        captured["snapshot_readme_before"] = snapshot_readme.read_text(encoding="utf-8")
        snapshot_readme.write_text("Snapshot changed\n", encoding="utf-8")
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
        start_agent_fn=_start_agent,
    )

    assert decision["decision"] == "approve"
    assert captured["agent"] == "build"
    assert captured["project_root"] != str(tmp_path)
    assert captured["snapshot_readme_before"] == "Original README\n"
    assert readme_path.read_text(encoding="utf-8") == "Original README\n"


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
