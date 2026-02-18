from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from engineeringagent.prompts.retry_feedback import (
    build_command_failure_retry_feedback,
    build_fitness_failure_retry_feedback,
    build_reviewer_feedback_retry_feedback,
    parse_retry_feedback_envelope,
    serialize_retry_feedback_envelope,
)
from engineeringagent.prompts.renderer import inject_retry_feedback


def test_retry_feedback_contract_accepts_command_failure_envelope() -> None:
    payload = {
        "kind": "command_failure",
        "phase": "gates",
        "gate": "ruff_validate",
        "precommit": True,
        "command": "uv run ruff check src/engineeringagent harness",
        "rerun": {
            "cwd": "repo_root",
            "instructions": "Run the command exactly as shown from the repository root.",
        },
        "message": "Command check failed. Rerun the command to see full diagnostics.",
    }

    envelope = parse_retry_feedback_envelope(payload)

    assert envelope.kind == "command_failure"
    assert envelope.phase == "gates"
    assert envelope.command == payload["command"]
    assert envelope.rerun.cwd == "repo_root"


def test_retry_feedback_contract_rejects_unknown_fields() -> None:
    payload = {
        "kind": "command_failure",
        "phase": "verification",
        "command": "uv run pytest -q",
        "rerun": {
            "cwd": "repo_root",
            "instructions": "Run the command exactly as shown from the repository root.",
        },
        "message": "Command failed.",
        "unknown": True,
    }

    with pytest.raises(ValidationError):
        parse_retry_feedback_envelope(payload)


def test_retry_feedback_serialization_is_sorted_and_compact() -> None:
    payload = {
        "kind": "reviewer_feedback",
        "phase": "reviewers",
        "reviewer_id": "code_simplifier",
        "reviewer_phase": "feature_done",
        "decision": {
            "decision": "request_changes",
            "summary": "Refactor duplicated helper.",
            "required_actions": ["Extract helper ..."],
            "scope_notes": "Reviewed src and tests changes only.",
        },
        "message": "Reviewer requested changes. Apply required actions before completing.",
    }

    envelope = parse_retry_feedback_envelope(payload)

    serialized = serialize_retry_feedback_envelope(envelope)
    assert "\n" not in serialized
    assert serialized == serialize_retry_feedback_envelope(envelope)

    roundtrip = json.loads(serialized)
    assert roundtrip == payload


def test_retry_feedback_contract_enforces_failed_rules_cap() -> None:
    payload = {
        "kind": "fitness_failure",
        "phase": "gates",
        "gate": "fitness_validate",
        "command": "uv run engineeringagent checks run --checks fitness --phase iteration_end",
        "failed_rules": [
            {
                "rule_id": f"architecture.rule-{index}",
                "status": "fail",
                "remediation": "Fix it.",
                "violations": ["path/to/file.md:1 ..."],
                "details": None,
            }
            for index in range(999)
        ],
        "message": "Fitness rule(s) failed.",
    }

    with pytest.raises(ValidationError):
        parse_retry_feedback_envelope(payload)


def test_retry_feedback_injection_does_not_truncate_contract_json() -> None:
    payload = {
        "kind": "fitness_failure",
        "phase": "gates",
        "gate": "fitness_validate",
        "command": "uv run engineeringagent checks run --checks fitness --phase iteration_end",
        "failed_rules": [
            {
                "rule_id": "architecture.prompt-contract",
                "status": "fail",
                "remediation": "Fix prompt injection contract.",
                "violations": [("v" * 500) + f"-{index}" for index in range(17)]
                + [("t" * 500) + "-TAIL-MARKER"],
                "details": None,
            }
        ],
        "message": "Fitness rule(s) failed.",
    }

    envelope = parse_retry_feedback_envelope(payload)
    serialized = serialize_retry_feedback_envelope(envelope)
    assert len(serialized) > 8_000

    injected = inject_retry_feedback("BASE\n", serialized)

    assert "-TAIL-MARKER" in injected
    assert "...[truncated]" not in injected


def test_build_reviewer_feedback_retry_feedback_emits_warning_envelope() -> None:
    serialized = build_reviewer_feedback_retry_feedback(
        reviewer_id="code_simplifier",
        reviewer_phase="feature_done",
        decision={
            "decision": "warning",
            "summary": "Minor nits.",
            "required_actions": [],
        },
    )

    envelope = parse_retry_feedback_envelope(serialized)
    assert envelope.kind == "reviewer_feedback"
    assert envelope.phase == "reviewers"
    assert envelope.reviewer_phase == "feature_done"
    assert envelope.decision.decision == "warning"
    assert envelope.message.startswith("Reviewer provided warning feedback")


def test_build_reviewer_feedback_retry_feedback_normalizes_unknown_decision() -> None:
    serialized = build_reviewer_feedback_retry_feedback(
        reviewer_id="code_simplifier",
        reviewer_phase="iteration_end",
        decision={
            "decision": "not_a_real_decision",
            "summary": "Unexpected output.",
            "required_actions": [],
        },
    )

    envelope = parse_retry_feedback_envelope(serialized)
    assert envelope.kind == "reviewer_feedback"
    assert envelope.decision.decision == "request_changes"
    assert envelope.message.startswith("Reviewer requested changes")


def test_build_reviewer_feedback_retry_feedback_accepts_approve_decision() -> None:
    serialized = build_reviewer_feedback_retry_feedback(
        reviewer_id="code_simplifier",
        reviewer_phase="feature_done",
        decision={
            "decision": "approve",
            "summary": "Looks good.",
            "required_actions": [],
        },
    )

    envelope = parse_retry_feedback_envelope(serialized)
    assert envelope.kind == "reviewer_feedback"
    assert envelope.decision.decision == "approve"


def test_build_command_failure_retry_feedback_uses_custom_message() -> None:
    serialized = build_command_failure_retry_feedback(
        phase="gates",
        gate="ruff",
        command="uv run ruff check .",
        precommit=True,
        message="Custom header.",
    )

    envelope = parse_retry_feedback_envelope(serialized)
    assert envelope.kind == "command_failure"
    assert envelope.phase == "gates"
    assert envelope.message == "Custom header."
    assert envelope.gate == "ruff"
    assert envelope.precommit is True


def test_build_fitness_failure_retry_feedback_normalizes_rules_and_details() -> None:
    serialized = build_fitness_failure_retry_feedback(
        gate="fitness_validate",
        command="uv run engineeringagent checks run --checks fitness --phase iteration_end",
        failed_rules=[
            {
                "rule_id": "architecture.demo",
                "remediation": "Fix it.",
                "violations": ["path/to/file.md:1 broken"],
                "details": {"extra": "info"},
            },
            {
                "rule_id": 123,
                "remediation": "ignored",
            },
        ],
    )

    envelope = parse_retry_feedback_envelope(serialized)
    assert envelope.kind == "fitness_failure"
    assert [rule.rule_id for rule in envelope.failed_rules] == ["architecture.demo"]
    assert envelope.failed_rules[0].details == {"extra": "info"}


def test_build_fitness_failure_retry_feedback_caps_rules_and_violations() -> None:
    failed_rules: list[dict[str, object]] = []
    for idx in range(30):
        violations = [f"path/to/file.md:{line} broken" for line in range(100)]
        if idx != 0:
            violations = ["path/to/file.md:1 broken"]
        failed_rules.append(
            {
                "rule_id": f"architecture.rule-{idx}",
                "remediation": "Fix it.",
                "violations": violations,
            }
        )

    serialized = build_fitness_failure_retry_feedback(
        gate="fitness_validate",
        command="uv run engineeringagent checks run --checks fitness --phase iteration_end",
        failed_rules=failed_rules,
    )

    envelope = parse_retry_feedback_envelope(serialized)
    assert envelope.kind == "fitness_failure"
    assert len(envelope.failed_rules) == 25
    assert len(envelope.failed_rules[0].violations) == 50


def test_build_reviewer_feedback_retry_feedback_caps_required_actions() -> None:
    serialized = build_reviewer_feedback_retry_feedback(
        reviewer_id="code_simplifier",
        reviewer_phase="feature_done",
        decision={
            "decision": "request_changes",
            "summary": "Do these things.",
            "required_actions": [f"action-{idx}" for idx in range(99)],
        },
    )

    envelope = parse_retry_feedback_envelope(serialized)
    assert envelope.kind == "reviewer_feedback"
    assert 1 <= len(envelope.decision.required_actions) <= 20
    assert envelope.decision.required_actions[0] == "action-0"


def test_build_reviewer_feedback_retry_feedback_honors_message_and_scope_notes() -> (
    None
):
    serialized = build_reviewer_feedback_retry_feedback(
        reviewer_id="code_simplifier",
        reviewer_phase="feature_done",
        decision={
            "decision": "request_changes",
            "summary": "Do it.",
            "required_actions": [],
            "scope_notes": "Reviewed only retry feedback.",
        },
        message="Custom reviewer header.",
    )

    envelope = parse_retry_feedback_envelope(serialized)
    assert envelope.kind == "reviewer_feedback"
    assert envelope.message == "Custom reviewer header."
    assert envelope.decision.scope_notes == "Reviewed only retry feedback."
