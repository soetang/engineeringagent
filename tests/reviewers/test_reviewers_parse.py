import json


from engineeringagent.checks.reviewers.engine import (
    PARSER_FAILURE_SUMMARY_PREFIX,
    parse_reviewer_decision,
)


def test_parse_reviewer_decision_accepts_code_fenced_json() -> None:
    payload = {"decision": "approve", "summary": "Looks good."}
    output = "```json\n" + json.dumps(payload) + "\n```\n"

    assert parse_reviewer_decision(output) == {
        "decision": "approve",
        "summary": "Looks good.",
        "required_actions": [],
    }


def test_parse_reviewer_decision_rejects_extra_keys_in_code_fenced_json() -> None:
    payload = {
        "decision": "approve",
        "summary": "Nested objects should not break parsing.",
        "meta": {"nested": True},
    }
    output = "```json\n" + json.dumps(payload) + "\n```\n"

    decision = parse_reviewer_decision(output)

    assert decision["decision"] == "request_changes"
    assert decision["summary"].startswith(f"{PARSER_FAILURE_SUMMARY_PREFIX}:")
    assert "meta" in decision["summary"]


def test_parse_reviewer_decision_accepts_json_with_prefix_and_suffix_noise() -> None:
    payload = {
        "decision": "request_changes",
        "summary": "Missing step.",
        "required_actions": ["Update README.md to include the missing step."],
    }
    output = "assistant: here is the decision\n" + json.dumps(payload) + "\n(EOF)\n"

    assert parse_reviewer_decision(output) == payload


def test_parse_reviewer_decision_returns_request_changes_on_non_json_output() -> None:
    decision = parse_reviewer_decision("not json")

    assert decision["decision"] == "request_changes"
    assert decision["summary"].startswith(f"{PARSER_FAILURE_SUMMARY_PREFIX}:")
    assert isinstance(decision.get("required_actions"), list)


def test_parse_reviewer_decision_parse_failures_point_to_schema_contract() -> None:
    decision = parse_reviewer_decision("not json")

    required_actions = decision.get("required_actions")
    assert isinstance(required_actions, list)
    assert required_actions
    assert "schema" in str(required_actions[0]).lower()


def test_parse_reviewer_decision_rejects_confidence_field() -> None:
    payload = {"decision": "approve", "summary": "Looks good.", "confidence": 0.9}
    output = json.dumps(payload)

    decision = parse_reviewer_decision(output)

    assert decision["decision"] == "request_changes"
    assert decision["summary"].startswith(f"{PARSER_FAILURE_SUMMARY_PREFIX}:")
    assert "confidence" in decision["summary"]
