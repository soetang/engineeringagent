import json


from engineeringagent.reviewers import (
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


def test_parse_reviewer_decision_code_fence_with_nested_objects_extracts_outer() -> (
    None
):
    payload = {
        "decision": "approve",
        "summary": "Nested objects should not break parsing.",
        "meta": {"nested": True},
    }
    output = "```json\n" + json.dumps(payload) + "\n```\n"

    assert parse_reviewer_decision(output) == {
        "decision": "approve",
        "summary": "Nested objects should not break parsing.",
        "required_actions": [],
    }


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
