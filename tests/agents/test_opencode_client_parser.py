from __future__ import annotations
# pylint: disable=protected-access

from engineeringagent.agents.backends.opencode import client as client_module


def test_extract_json_session_and_last_text_payload_ignores_blank_and_nondict_events() -> (
    None
):
    stdout = '\n[]\n\n{"sessionID":"s1","type":"text","part":{"text":"hello"}}\n'

    session_id, payload = client_module._extract_json_session_and_last_text_payload(
        stdout
    )

    assert session_id == "s1"
    assert payload == "hello"


def test_extract_json_session_and_last_text_payload_returns_none_for_invalid_json() -> (
    None
):
    stdout = '{"sessionID":"s1"}\nnot-json\n'

    assert client_module._extract_json_session_and_last_text_payload(stdout) == (
        None,
        None,
    )


def test_extract_json_session_and_last_text_payload_requires_text_part_dict() -> None:
    stdout = '{"sessionID":"s1","type":"text","part":"not-a-dict"}\n'

    assert client_module._extract_json_session_and_last_text_payload(stdout) == (
        None,
        None,
    )
