from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from engineeringagent.changed_paths import ChangedPathsResult
from engineeringagent.checks.reviewers.engine import (
    MATCHED_ON_CHANGE_REASON,
    NO_ON_CHANGE_MATCH_REASON,
    PARSER_FAILURE_SUMMARY_PREFIX,
    PHASE_MISMATCH_REASON,
    ReviewerDecisionEnvelope,
    plan_reviewers,
    run_reviewer,
)
from engineeringagent.agents import AgentOutputValidationError


def test_plan_reviewers_maps_iteration_end_config_to_feature_done() -> None:
    config = {
        "profiles": {"loop_fast": ["code_simplifier", "onboarding_review"]},
        "reviewers": {
            "code_simplifier": {
                "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
                "trigger": {
                    "phase": "iteration_end",
                    "on_change": ["src/**/*.py", "tests/**/*.py"],
                },
            },
            "onboarding_review": {
                "prompt_file": "harness/reviewers/prompts/onboarding_review.md",
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
            paths=("src/engineeringagent/checks/reviewers/engine.py",),
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
            "reviewer": "onboarding_review",
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
            paths=("src/engineeringagent/checks/reviewers/engine.py",),
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
        "profiles": {"loop_fast": ["code_simplifier", "onboarding_review"]},
        "reviewers": {
            "code_simplifier": {
                "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
                "trigger": {
                    "phase": "iteration_end",
                    "on_change": ["src/**/*.py"],
                },
            },
            "onboarding_review": {
                "prompt_file": "harness/reviewers/prompts/onboarding_review.md",
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
            "reviewer": "onboarding_review",
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
            paths=(r"src\engineeringagent\checks\reviewers\engine.py",),
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
        "profiles": {"loop_fast": ["onboarding_review"]},
        "reviewers": {
            "onboarding_review": {
                "prompt_file": "harness/reviewers/prompts/onboarding_review.md",
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
            "reviewer": "onboarding_review",
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


def test_onboarding_review_plans_only_for_readme_change_on_feature_done() -> None:
    config = {
        "profiles": {"loop_fast": ["onboarding_review"]},
        "reviewers": {
            "onboarding_review": {
                "prompt_file": "harness/reviewers/prompts/onboarding_review.md",
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
            "reviewer": "onboarding_review",
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
            "reviewer": "onboarding_review",
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
            "reviewer": "onboarding_review",
            "decision": "skip",
            "reason": NO_ON_CHANGE_MATCH_REASON,
        }
    ]


def test_run_reviewer_loads_harness_prompt_and_parses_decision(tmp_path) -> None:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text(
        "$responseformat\n\nTEST_SENTINEL_PROMPT_INCLUDED\n",
        encoding="utf-8",
    )

    captured: dict[str, str] = {}
    captured_max_validation_retries: list[int] = []

    def _run_agent(
        project_root, prompt, *, output_type, backend=None, max_validation_retries=2
    ):
        captured["project_root"] = str(project_root)
        captured["prompt"] = prompt
        captured["output_type"] = str(output_type)
        captured["backend"] = str(backend)
        captured_max_validation_retries.append(max_validation_retries)
        return ReviewerDecisionEnvelope(
            decision="approve",
            summary="No blocking issues.",
            required_actions=[],
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
            paths=("src/engineeringagent/checks/reviewers/engine.py",),
            run_all=False,
            reason=None,
        ),
        prior_feedback="tighten error handling",
        run_agent_fn=_run_agent,
    )

    assert decision == {
        "decision": "approve",
        "summary": "No blocking issues.",
        "required_actions": [],
    }
    assert captured["project_root"] == str(tmp_path)
    assert "$responseformat" not in captured["prompt"]
    assert (
        "Return exactly one strict JSON object and no other text." in captured["prompt"]
    )
    assert "JSON Schema:" not in captured["prompt"]
    assert "TEST_SENTINEL_PROMPT_INCLUDED" in captured["prompt"]
    assert captured_max_validation_retries == [2]


def test_run_reviewer_parse_failure_returns_request_changes(tmp_path) -> None:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("$responseformat\n\nReturn JSON only.", encoding="utf-8")

    def _run_agent(*_args, **_kwargs):
        raise AgentOutputValidationError(
            backend="fake",
            attempts=3,
            last_text="this is not json",
            error_summary="json parse error: Expecting value",
            backend_metadata=None,
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
        changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
        prior_feedback=None,
        run_agent_fn=_run_agent,
    )

    assert decision["decision"] == "request_changes"
    assert decision["summary"].startswith(PARSER_FAILURE_SUMMARY_PREFIX)


def test_run_reviewer_passes_max_validation_retries_to_canonical_runner(
    tmp_path,
) -> None:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("$responseformat\n\nReturn JSON only.", encoding="utf-8")

    captured: dict[str, str] = {}
    captured_max_validation_retries: list[int] = []

    def _run_agent(
        _project_root, _prompt, *, output_type, backend=None, max_validation_retries=2
    ):
        captured["output_type"] = str(output_type)
        captured["backend"] = str(backend)
        captured_max_validation_retries.append(max_validation_retries)
        return ReviewerDecisionEnvelope(
            decision="approve",
            summary="Recovered on retry.",
            required_actions=[],
        )

    decision = run_reviewer(
        tmp_path,
        "code_simplifier",
        {
            "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
            "trigger": {"phase": "iteration_end"},
        },
        feature_id="FEAT-070",
        feature_path=tmp_path / "docs/spec/features/FEAT-070.yaml",
        changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
        prior_feedback=None,
        run_agent_fn=_run_agent,
    )

    assert decision == {
        "decision": "approve",
        "summary": "Recovered on retry.",
        "required_actions": [],
    }
    assert captured_max_validation_retries == [2]


def test_run_reviewer_requires_responseformat_placeholder(tmp_path) -> None:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("Focus on code readability.", encoding="utf-8")

    def _run_agent(*_args, **_kwargs):
        raise AssertionError("run_agent_fn should not run when $responseformat missing")

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
        run_agent_fn=_run_agent,
    )

    assert decision["decision"] == "request_changes"
    assert decision["summary"] == (
        f"{PARSER_FAILURE_SUMMARY_PREFIX}: "
        "reviewer prompt must include the $responseformat placeholder"
    )


def test_repository_code_simplifier_prompt_uses_responseformat_contract(
    repo_root: Path,
) -> None:
    prompt_path = repo_root / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    prompt_text = prompt_path.read_text(encoding="utf-8")

    assert "$responseformat" in prompt_text
    assert "Return exactly one strict JSON object and no other text" not in prompt_text
