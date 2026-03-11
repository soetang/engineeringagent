"""Presentation-layer helpers and presenters."""

from .json_schema import JSON_SCHEMA_DRAFT_URL
from .prompt_feedback import (
    CHECKS_FAILURE_FALLBACK,
    format_command_failure_output_excerpt,
    format_command_return_code,
    format_failed_command_feedback_lines,
    normalize_checks_contract_prompt_feedback,
    normalize_checks_prompt_feedback,
    normalize_prompt_feedback,
    resolve_checks_prompt_feedback,
    resolve_prompt_feedback,
)
from .terminal import RunOutputPresenter, stdout_is_tty, tty_supports_ansi

__all__ = [
    "CHECKS_FAILURE_FALLBACK",
    "JSON_SCHEMA_DRAFT_URL",
    "RunOutputPresenter",
    "format_command_failure_output_excerpt",
    "format_command_return_code",
    "format_failed_command_feedback_lines",
    "normalize_checks_contract_prompt_feedback",
    "normalize_checks_prompt_feedback",
    "normalize_prompt_feedback",
    "resolve_checks_prompt_feedback",
    "resolve_prompt_feedback",
    "stdout_is_tty",
    "tty_supports_ansi",
]
