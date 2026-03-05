from __future__ import annotations

from engineeringagent.prompt_feedback import (
    format_command_failure_output_excerpt,
    format_command_return_code,
)


def test_format_command_failure_output_excerpt_uses_tail_when_over_max_lines() -> None:
    output = "\n".join(["line-1", "line-2", "line-3", "line-4"])
    assert format_command_failure_output_excerpt(output, max_lines=2) == "line-3\nline-4"


def test_format_command_return_code_none_returns_unknown() -> None:
    assert format_command_return_code(None) == "unknown"
