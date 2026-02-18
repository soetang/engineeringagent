from __future__ import annotations

from pathlib import Path

from engineeringagent.specs import checks_contract_issues


def test_checks_contract_accepts_minimal_command_check() -> None:
    payload = {
        "contract_version": "1.0",
        "checks": {
            "ruff": {
                "type": "command",
                "command": "uv run ruff check src/engineeringagent",
            }
        },
    }

    issues = checks_contract_issues(payload, Path("harness/checks.yaml"))

    assert not issues


def test_checks_contract_rejects_unknown_fields_in_check_definition() -> None:
    payload = {
        "contract_version": "1.0",
        "checks": {
            "ruff": {
                "type": "command",
                "command": "uv run ruff check src/engineeringagent",
                "blocking": True,
            }
        },
    }

    issues = checks_contract_issues(payload, Path("harness/checks.yaml"))

    assert issues
    rendered = "\n".join(f"{issue.path}: {issue.message}" for issue in issues)
    assert "harness/checks.yaml:checks.ruff" in rendered
    assert ".blocking" in rendered


def test_checks_contract_rejects_reviewer_check_with_iteration_end_effective_phase() -> (
    None
):
    payload = {
        "contract_version": "1.0",
        "checks": {
            "doc_review": {
                "type": "reviewer",
                "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
            }
        },
    }

    issues = checks_contract_issues(payload, Path("harness/checks.yaml"))

    assert issues
    rendered = "\n".join(f"{issue.path}: {issue.message}" for issue in issues)
    assert "harness/checks.yaml:checks.doc_review.when.phase" in rendered
    assert "feature_done" in rendered


def test_checks_contract_accepts_reviewer_check_when_phase_feature_done() -> None:
    payload = {
        "contract_version": "1.0",
        "checks": {
            "doc_review": {
                "type": "reviewer",
                "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
                "when": {"phase": "feature_done"},
            }
        },
    }

    issues = checks_contract_issues(payload, Path("harness/checks.yaml"))

    assert not issues


def test_checks_contract_rejects_reviewer_prompt_outside_prompts_dir() -> None:
    payload = {
        "contract_version": "1.0",
        "checks": {
            "doc_review": {
                "type": "reviewer",
                "prompt_file": "docs/reviewers/not_allowed.md",
                "when": {"phase": "feature_done"},
            }
        },
    }

    issues = checks_contract_issues(payload, Path("harness/checks.yaml"))

    assert issues
    rendered = "\n".join(f"{issue.path}: {issue.message}" for issue in issues)
    assert "harness/checks.yaml:checks.doc_review" in rendered
    assert "harness/reviewers/prompts" in rendered


def test_checks_contract_rejects_fitness_check_with_both_scope_and_rule_ids() -> None:
    payload = {
        "contract_version": "1.0",
        "checks": {
            "fitness": {
                "type": "fitness",
                "scope": "all",
                "rule_ids": ["architecture.dep-directionality"],
            }
        },
    }

    issues = checks_contract_issues(payload, Path("harness/checks.yaml"))

    assert issues
    rendered = "\n".join(f"{issue.path}: {issue.message}" for issue in issues)
    assert "harness/checks.yaml:checks.fitness" in rendered
    assert ".scope" in rendered
    assert ".rule_ids" in rendered
