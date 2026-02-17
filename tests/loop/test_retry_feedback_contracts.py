from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from engineeringagent.retry_feedback.contracts import (
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
        "command": "uv run python -m engineeringagent.cli fitness run --format json",
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
        "command": "uv run python -m engineeringagent.cli fitness run --format json",
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
