"""Backward-compatible shim for progress artifact writers.

Canonical import path is now `engineeringagent.progress.logging`.
"""

from __future__ import annotations

from engineeringagent.progress.logging import (  # noqa: F401
    _FORMATTER,
    _get_or_create_file_logger,
    _logger_name_for_path,
    append_jsonl_record,
    append_text_block,
)

__all__ = [
    "_FORMATTER",
    "_get_or_create_file_logger",
    "_logger_name_for_path",
    "append_jsonl_record",
    "append_text_block",
]
