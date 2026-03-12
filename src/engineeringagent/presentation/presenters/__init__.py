"""Presentation-layer result renderers and helpers."""

from .json_schema import (
    JSON_SCHEMA_DRAFT_URL,
    UnknownSchemaIdError,
    list_schema_ids,
    schema_from_registry,
)
from .markdown import HandoffRenderMetadata, render_handoff_markdown_entry
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
    "HandoffRenderMetadata",
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
    "render_handoff_markdown_entry",
    "UnknownSchemaIdError",
    "list_schema_ids",
    "schema_from_registry",
    "stdout_is_tty",
    "tty_supports_ansi",
]
