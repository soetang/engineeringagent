from __future__ import annotations

from pathlib import Path

from engineeringagent.specs import reviewer_contract_issues


def test_reviewer_contract_accepts_minimal_v1_document() -> None:
    document = {
        "contract_version": "1.0",
        "profiles": {"loop_fast": ["code_simplifier"]},
        "reviewers": {
            "code_simplifier": {
                "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
                "trigger": {"phase": "iteration_end"},
            }
        },
    }

    issues = reviewer_contract_issues(document, Path("harness/reviewers.yaml"))

    assert issues == []


def test_reviewer_contract_accepts_optional_approval_and_sandbox_fields() -> None:
    document = {
        "contract_version": "1.0",
        "profiles": {"loop_fast": ["readme_process"]},
        "reviewers": {
            "readme_process": {
                "prompt_file": "harness/reviewers/prompts/readme_process.md",
                "trigger": {
                    "phase": "feature_done",
                    "on_change": ["README.md"],
                },
                "approval": {
                    "mode": "blocking",
                    "first_feature_approval": True,
                    "max_retries": 2,
                    "continue_on_exhausted": True,
                },
                "sandbox": {"mode": "temp_worktree_snapshot"},
            }
        },
    }

    issues = reviewer_contract_issues(document, Path("harness/reviewers.yaml"))

    assert issues == []


def test_reviewer_contract_rejects_invalid_trigger_phase() -> None:
    document = {
        "contract_version": "1.0",
        "profiles": {"loop_fast": ["code_simplifier"]},
        "reviewers": {
            "code_simplifier": {
                "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
                "trigger": {"phase": "after_loop"},
            }
        },
    }

    issues = reviewer_contract_issues(document, Path("harness/reviewers.yaml"))

    assert any(
        issue.path == "harness/reviewers.yaml:reviewers.code_simplifier.trigger.phase"
        and "Input should be 'iteration_end' or 'feature_done'" in issue.message
        for issue in issues
    )


def test_reviewer_contract_rejects_prompt_outside_harness_prompt_directory() -> None:
    document = {
        "contract_version": "1.0",
        "profiles": {"loop_fast": ["code_simplifier"]},
        "reviewers": {
            "code_simplifier": {
                "prompt_file": "docs/prompts/code_simplifier.md",
                "trigger": {"phase": "iteration_end"},
            }
        },
    }

    issues = reviewer_contract_issues(document, Path("harness/reviewers.yaml"))

    assert any(
        issue.path == "harness/reviewers.yaml:reviewers.code_simplifier"
        and "harness/reviewers/prompts/" in issue.message
        for issue in issues
    )


def test_reviewer_contract_rejects_unknown_fields() -> None:
    document = {
        "contract_version": "1.0",
        "profiles": {"loop_fast": ["code_simplifier"]},
        "reviewers": {
            "code_simplifier": {
                "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
                "trigger": {"phase": "iteration_end"},
                "approval": {"unknown": True},
            }
        },
        "unknown": True,
    }

    issues = reviewer_contract_issues(document, Path("harness/reviewers.yaml"))

    assert any(
        issue.path == "harness/reviewers.yaml:unknown"
        and "Extra inputs are not permitted" in issue.message
        for issue in issues
    )
    assert any(
        issue.path
        == "harness/reviewers.yaml:reviewers.code_simplifier.approval.unknown"
        and "Extra inputs are not permitted" in issue.message
        for issue in issues
    )
