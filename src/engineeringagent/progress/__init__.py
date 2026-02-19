"""Progress artifact helpers.

This subpackage groups together the shared helpers for constructing progress artifact
paths and for appending to progress artifacts. It is intentionally independent of
loop runtime internals so it can be imported by both loop telemetry and reviewers.
"""

from __future__ import annotations

from . import logging, paths
from .logging import append_jsonl_record, append_text_block
from .paths import (
    PROGRESS_DIRNAME,
    REVIEWERS_STATE_FILENAME,
    RUNS_JSONL_FILENAME,
    progress_dir,
    reviewers_state_path,
    run_feature_log_filename,
    run_feature_log_path,
    run_feature_log_reference,
    run_feature_log_template_reference,
    runs_jsonl_path,
    runs_jsonl_reference,
    sanitize_feature_id_for_log,
)

__all__ = [
    "logging",
    "paths",
    "append_jsonl_record",
    "append_text_block",
    "PROGRESS_DIRNAME",
    "RUNS_JSONL_FILENAME",
    "REVIEWERS_STATE_FILENAME",
    "progress_dir",
    "runs_jsonl_path",
    "runs_jsonl_reference",
    "reviewers_state_path",
    "sanitize_feature_id_for_log",
    "run_feature_log_filename",
    "run_feature_log_path",
    "run_feature_log_reference",
    "run_feature_log_template_reference",
]
