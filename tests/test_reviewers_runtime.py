from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from engineeringagent.gates import ChangedPathsResult
from engineeringagent.opencode.client import DEFAULT_OPENCODE_AGENT
from engineeringagent.reviewers import (
    MATCHED_ON_CHANGE_REASON,
    NO_ON_CHANGE_MATCH_REASON,
    PARSER_FAILURE_SUMMARY_PREFIX,
    PHASE_MISMATCH_REASON,
    plan_reviewers,
    run_reviewer,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CODE_SIMPLIFIER_PROMPT = (
    REPO_ROOT / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
)


def test_plan_reviewers_maps_iteration_end_config_to_feature_done() -> None:
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
        phase="feature_done",
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
            "reason": NO_ON_CHANGE_MATCH_REASON,
        },
    ]


def test_code_simplifier_plans_only_for_code_scoped_changes() -> None:
    config = {
        "profiles": {"loop_fast": ["code_simplifier"]},
        "reviewers": {
            "code_simplifier": {
                "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
                "trigger": {
                    "phase": "iteration_end",
                    "on_change": ["src/**/*.py", "tests/**/*.py"],
                },
            }
        },
    }

    code_change_decisions = plan_reviewers(
        config,
        "loop_fast",
        phase="feature_done",
        changed_paths=ChangedPathsResult(
            paths=("src/engineeringagent/reviewers.py",),
            run_all=False,
            reason=None,
        ),
    )
    assert code_change_decisions == [
        {
            "reviewer": "code_simplifier",
            "decision": "run",
            "reason": MATCHED_ON_CHANGE_REASON,
        }
    ]

    docs_change_decisions = plan_reviewers(
        config,
        "loop_fast",
        phase="feature_done",
        changed_paths=ChangedPathsResult(
            paths=("docs/spec/features/FEAT-054.yaml",),
            run_all=False,
            reason=None,
        ),
    )
    assert docs_change_decisions == [
        {
            "reviewer": "code_simplifier",
            "decision": "skip",
            "reason": NO_ON_CHANGE_MATCH_REASON,
        }
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
            "reason": PHASE_MISMATCH_REASON,
        },
        {
            "reviewer": "readme_process",
            "decision": "skip",
            "reason": PHASE_MISMATCH_REASON,
        },
    ]


def test_plan_reviewers_matches_normalized_separator_paths() -> None:
    config = {
        "profiles": {"loop_fast": ["code_simplifier"]},
        "reviewers": {
            "code_simplifier": {
                "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
                "trigger": {
                    "phase": "iteration_end",
                    "on_change": ["src/**/*.py"],
                },
            }
        },
    }

    decisions = plan_reviewers(
        config,
        "loop_fast",
        phase="feature_done",
        changed_paths=ChangedPathsResult(
            paths=(r"src\engineeringagent\reviewers.py",),
            run_all=False,
            reason=None,
        ),
    )

    assert decisions == [
        {
            "reviewer": "code_simplifier",
            "decision": "run",
            "reason": MATCHED_ON_CHANGE_REASON,
        }
    ]


def test_plan_reviewers_runs_when_rename_paths_include_match() -> None:
    config = {
        "profiles": {"loop_fast": ["readme_process"]},
        "reviewers": {
            "readme_process": {
                "prompt_file": "harness/reviewers/prompts/readme_process.md",
                "trigger": {
                    "phase": "feature_done",
                    "on_change": ["docs/spec/features/old-name.yaml"],
                },
            }
        },
    }

    decisions = plan_reviewers(
        config,
        "loop_fast",
        phase="feature_done",
        changed_paths=ChangedPathsResult(
            paths=(
                "docs/spec/features/new-name.yaml",
                "docs/spec/features/old-name.yaml",
            ),
            run_all=False,
            reason=None,
        ),
    )

    assert decisions == [
        {
            "reviewer": "readme_process",
            "decision": "run",
            "reason": MATCHED_ON_CHANGE_REASON,
        }
    ]


def test_plan_reviewers_skip_when_changed_paths_are_empty() -> None:
    config = {
        "profiles": {"loop_fast": ["code_simplifier"]},
        "reviewers": {
            "code_simplifier": {
                "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
                "trigger": {
                    "phase": "iteration_end",
                    "on_change": ["src/**/*.py"],
                },
            }
        },
    }

    decisions = plan_reviewers(
        config,
        "loop_fast",
        phase="feature_done",
        changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
    )

    assert decisions == [
        {
            "reviewer": "code_simplifier",
            "decision": "skip",
            "reason": NO_ON_CHANGE_MATCH_REASON,
        }
    ]


def test_readme_process_plans_only_for_readme_change_on_feature_done() -> None:
    config = {
        "profiles": {"loop_fast": ["readme_process"]},
        "reviewers": {
            "readme_process": {
                "prompt_file": "harness/reviewers/prompts/readme_process.md",
                "trigger": {
                    "phase": "feature_done",
                    "on_change": ["README.md"],
                },
            }
        },
    }

    matching_decisions = plan_reviewers(
        config,
        "loop_fast",
        phase="feature_done",
        changed_paths=ChangedPathsResult(
            paths=("README.md",),
            run_all=False,
            reason=None,
        ),
    )
    assert matching_decisions == [
        {
            "reviewer": "readme_process",
            "decision": "run",
            "reason": MATCHED_ON_CHANGE_REASON,
        }
    ]

    phase_mismatch_decisions = plan_reviewers(
        config,
        "loop_fast",
        phase="iteration_end",
        changed_paths=ChangedPathsResult(
            paths=("README.md",),
            run_all=False,
            reason=None,
        ),
    )
    assert phase_mismatch_decisions == [
        {
            "reviewer": "readme_process",
            "decision": "skip",
            "reason": PHASE_MISMATCH_REASON,
        }
    ]

    no_match_decisions = plan_reviewers(
        config,
        "loop_fast",
        phase="feature_done",
        changed_paths=ChangedPathsResult(
            paths=("docs/spec/features/FEAT-052.yaml",),
            run_all=False,
            reason=None,
        ),
    )
    assert no_match_decisions == [
        {
            "reviewer": "readme_process",
            "decision": "skip",
            "reason": NO_ON_CHANGE_MATCH_REASON,
        }
    ]


def test_run_reviewer_loads_harness_prompt_and_parses_decision(tmp_path) -> None:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text(
        "$responseformat\n\nFocus on code readability.",
        encoding="utf-8",
    )

    captured: dict[str, str] = {}

    def _start_agent(project_root, prompt, *, agent=DEFAULT_OPENCODE_AGENT):
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
    assert captured["agent"] == DEFAULT_OPENCODE_AGENT
    assert "$responseformat" not in captured["prompt"]
    assert (
        "Return exactly one strict JSON object and no other text." in captured["prompt"]
    )
    assert "Focus on code readability." in captured["prompt"]
    assert "Feature ID: FEAT-050" in captured["prompt"]


def test_run_reviewer_parse_failure_returns_request_changes(tmp_path) -> None:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("$responseformat\n\nReturn JSON only.", encoding="utf-8")

    def _start_agent(_project_root, _prompt, *, agent=DEFAULT_OPENCODE_AGENT):
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


def test_run_reviewer_requires_responseformat_placeholder(tmp_path) -> None:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("Focus on code readability.", encoding="utf-8")

    def _start_agent(_project_root, _prompt, *, agent=DEFAULT_OPENCODE_AGENT):
        raise AssertionError(f"start_agent_fn should not run; received agent={agent}")

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
    assert decision["summary"] == (
        f"{PARSER_FAILURE_SUMMARY_PREFIX}: "
        "reviewer prompt must include the $responseformat placeholder"
    )


def test_repository_code_simplifier_prompt_uses_responseformat_contract() -> None:
    prompt_text = CODE_SIMPLIFIER_PROMPT.read_text(encoding="utf-8")

    assert "$responseformat" in prompt_text
    assert "Return exactly one strict JSON object and no other text" not in prompt_text
