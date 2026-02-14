from __future__ import annotations

from types import SimpleNamespace

from engineeringagent.gates import ChangedPathsResult
from engineeringagent.reviewers import (
    MATCHED_ON_CHANGE_REASON,
    NO_ON_CHANGE_MATCH_REASON,
    PARSER_FAILURE_SUMMARY_PREFIX,
    PHASE_MISMATCH_REASON,
    plan_reviewers,
    run_reviewer,
)


def test_plan_reviewers_by_phase_and_change_selectors() -> None:
    config = {
        "profiles": {"loop_fast": ["code_simplifier", "readme_process"]},
        "reviewers": {
            "code_simplifier": {
                "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
                "trigger": {
                    "phase": "iteration_end",
                    "on_change": ["src/**/*.py", "tests/**/*.py"],
                },
            },
            "readme_process": {
                "prompt_file": "harness/reviewers/prompts/readme_process.md",
                "trigger": {
                    "phase": "feature_done",
                    "on_change": ["README.md"],
                },
            },
        },
    }

    decisions = plan_reviewers(
        config,
        "loop_fast",
        phase="iteration_end",
        changed_paths=ChangedPathsResult(
            paths=("src/engineeringagent/reviewers.py",),
            run_all=False,
            reason=None,
        ),
    )

    assert decisions == [
        {
            "reviewer": "code_simplifier",
            "decision": "run",
            "reason": MATCHED_ON_CHANGE_REASON,
        },
        {
            "reviewer": "readme_process",
            "decision": "skip",
            "reason": PHASE_MISMATCH_REASON,
        },
    ]


def test_plan_reviewers_reports_deterministic_skip_reasons() -> None:
    config = {
        "profiles": {"loop_fast": ["code_simplifier", "readme_process"]},
        "reviewers": {
            "code_simplifier": {
                "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
                "trigger": {
                    "phase": "iteration_end",
                    "on_change": ["src/**/*.py"],
                },
            },
            "readme_process": {
                "prompt_file": "harness/reviewers/prompts/readme_process.md",
                "trigger": {"phase": "feature_done"},
            },
        },
    }

    decisions = plan_reviewers(
        config,
        "loop_fast",
        phase="iteration_end",
        changed_paths=ChangedPathsResult(
            paths=("docs/spec/features/FEAT-050.yaml",),
            run_all=False,
            reason=None,
        ),
    )

    assert decisions == [
        {
            "reviewer": "code_simplifier",
            "decision": "skip",
            "reason": NO_ON_CHANGE_MATCH_REASON,
        },
        {
            "reviewer": "readme_process",
            "decision": "skip",
            "reason": PHASE_MISMATCH_REASON,
        },
    ]


def test_run_reviewer_loads_harness_prompt_and_parses_decision(tmp_path) -> None:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("Focus on code readability.", encoding="utf-8")

    captured: dict[str, str] = {}

    def _start_agent(project_root, prompt, *, agent="build"):
        captured["project_root"] = str(project_root)
        captured["prompt"] = prompt
        captured["agent"] = agent
        return SimpleNamespace(
            stdout='{"decision":"approve","summary":"No blocking issues."}',
            stderr="",
            returncode=0,
        )

    decision = run_reviewer(
        tmp_path,
        "code_simplifier",
        {
            "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
            "trigger": {"phase": "iteration_end"},
        },
        feature_id="FEAT-050",
        feature_path=tmp_path / "docs/spec/features/FEAT-050.yaml",
        changed_paths=ChangedPathsResult(
            paths=("src/engineeringagent/reviewers.py",),
            run_all=False,
            reason=None,
        ),
        prior_feedback="tighten error handling",
        start_agent_fn=_start_agent,
    )

    assert decision == {
        "decision": "approve",
        "summary": "No blocking issues.",
        "required_actions": [],
    }
    assert captured["project_root"] == str(tmp_path)
    assert captured["agent"] == "build"
    assert "Focus on code readability." in captured["prompt"]
    assert "Feature ID: FEAT-050" in captured["prompt"]


def test_run_reviewer_parse_failure_returns_request_changes(tmp_path) -> None:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("Return JSON only.", encoding="utf-8")

    def _start_agent(_project_root, _prompt, *, agent="build"):
        del agent
        return SimpleNamespace(stdout="this is not json", stderr="", returncode=0)

    decision = run_reviewer(
        tmp_path,
        "code_simplifier",
        {
            "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
            "trigger": {"phase": "iteration_end"},
        },
        feature_id="FEAT-050",
        feature_path=tmp_path / "docs/spec/features/FEAT-050.yaml",
        changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
        prior_feedback=None,
        start_agent_fn=_start_agent,
    )

    assert decision["decision"] == "request_changes"
    assert decision["summary"].startswith(PARSER_FAILURE_SUMMARY_PREFIX)
