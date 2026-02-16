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
        "profiles": {"loop_fast": ["onboarding_review"]},
        "reviewers": {
            "onboarding_review": {
                "prompt_file": "harness/reviewers/prompts/onboarding_review.md",
                "trigger": {
                    "phase": "feature_done",
                    "on_change": ["README.md"],
                },
                "approval": {
                    "first_feature_approval": True,
                },
                "sandbox": {
                    "mode": "empty_folder",
                    "assets": ["README.md", "docs"],
                },
            }
        },
    }

    issues = reviewer_contract_issues(document, Path("harness/reviewers.yaml"))

    assert issues == []


def test_reviewer_contract_rejects_removed_approval_mode() -> None:
    document = {
        "contract_version": "1.0",
        "profiles": {"loop_fast": ["onboarding_review"]},
        "reviewers": {
            "onboarding_review": {
                "prompt_file": "harness/reviewers/prompts/onboarding_review.md",
                "trigger": {
                    "phase": "feature_done",
                    "on_change": ["README.md"],
                },
                "approval": {
                    "mode": "blocking",
                    "first_feature_approval": True,
                },
            }
        },
    }

    issues = reviewer_contract_issues(document, Path("harness/reviewers.yaml"))

    assert any(
        ".approval." in issue.path
        and issue.path.endswith(".mode")
        and "Extra inputs are not permitted" in issue.message
        for issue in issues
    )


def test_reviewer_contract_accepts_feedback_context_string() -> None:
    document = {
        "contract_version": "1.0",
        "profiles": {"loop_fast": ["onboarding_review"]},
        "reviewers": {
            "onboarding_review": {
                "prompt_file": "harness/reviewers/prompts/onboarding_review.md",
                "feedback_context": "This reviewer may run with constrained context.",
                "trigger": {
                    "phase": "feature_done",
                    "on_change": ["README.md"],
                },
            }
        },
    }

    issues = reviewer_contract_issues(document, Path("harness/reviewers.yaml"))

    assert issues == []


def test_reviewer_contract_accepts_temp_worktree_snapshot_sandbox_mode() -> None:
    document = {
        "contract_version": "1.0",
        "profiles": {"loop_fast": ["onboarding_review"]},
        "reviewers": {
            "onboarding_review": {
                "prompt_file": "harness/reviewers/prompts/onboarding_review.md",
                "trigger": {
                    "phase": "feature_done",
                    "on_change": ["README.md"],
                },
                "sandbox": {"mode": "temp_worktree_snapshot"},
            }
        },
    }

    issues = reviewer_contract_issues(document, Path("harness/reviewers.yaml"))

    assert issues == []


def test_reviewer_contract_rejects_assets_when_mode_is_not_empty_folder() -> None:
    document = {
        "contract_version": "1.0",
        "profiles": {"loop_fast": ["onboarding_review"]},
        "reviewers": {
            "onboarding_review": {
                "prompt_file": "harness/reviewers/prompts/onboarding_review.md",
                "trigger": {
                    "phase": "feature_done",
                    "on_change": ["README.md"],
                },
                "sandbox": {
                    "mode": "temp_worktree_snapshot",
                    "assets": ["README.md"],
                },
            }
        },
    }

    issues = reviewer_contract_issues(document, Path("harness/reviewers.yaml"))

    assert any(
        issue.path.endswith("reviewers.onboarding_review.sandbox")
        and "sandbox.assets" in issue.message
        for issue in issues
    )


def test_reviewer_contract_rejects_removed_sandbox_mode_name() -> None:
    removed_mode = "_".join(["clean", "room", "readme", "cli"])
    document = {
        "contract_version": "1.0",
        "profiles": {"loop_fast": ["onboarding_review"]},
        "reviewers": {
            "onboarding_review": {
                "prompt_file": "harness/reviewers/prompts/onboarding_review.md",
                "trigger": {
                    "phase": "feature_done",
                    "on_change": ["README.md"],
                },
                "sandbox": {"mode": removed_mode},
            }
        },
    }

    issues = reviewer_contract_issues(document, Path("harness/reviewers.yaml"))

    assert any(
        issue.path.endswith("reviewers.onboarding_review.sandbox.mode")
        and "Input should be" in issue.message
        for issue in issues
    )


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
