"""Progress artifact helpers.

This subpackage groups together the shared helpers for constructing progress artifact
paths and for appending to progress artifacts. It is intentionally independent of
loop runtime internals so it can be imported by both loop telemetry and reviewers.
"""

from __future__ import annotations

from . import handoff, logging, paths
from .handoff import (
    ImplementProgressEnvelope,
    append_handoff_markdown_entry,
    fallback_implement_progress_envelope,
    parse_implement_progress_envelope,
    render_handoff_markdown_entry,
)
from .logging import append_jsonl_record, append_text_block
from .paths import (
    FEATURE_HANDOFF_FILENAME,
    FEATURE_RUN_LOG_FILENAME,
    PROGRESS_DIRNAME,
    PROGRESS_FEATURES_DIRNAME,
    PROGRESS_REVIEWERS_DIRNAME,
    PROGRESS_RUNS_DIRNAME,
    REVIEWERS_STATE_FILENAME,
    RUNS_JSONL_FILENAME,
    feature_dir_path,
    features_dir,
    handoff_markdown_path,
    handoff_markdown_reference,
    handoff_markdown_template_reference,
    progress_dir,
    reviewers_state_path,
    run_feature_log_filename,
    run_feature_log_path,
    run_feature_log_reference,
    run_feature_log_template_reference,
    runs_dir,
    runs_jsonl_path,
    runs_jsonl_reference,
    sanitize_feature_id_for_log,
)

__all__ = [
    "logging",
    "handoff",
    "paths",
    "ImplementProgressEnvelope",
    "parse_implement_progress_envelope",
    "fallback_implement_progress_envelope",
    "render_handoff_markdown_entry",
    "append_handoff_markdown_entry",
    "append_jsonl_record",
    "append_text_block",
    "PROGRESS_DIRNAME",
    "PROGRESS_RUNS_DIRNAME",
    "PROGRESS_FEATURES_DIRNAME",
    "PROGRESS_REVIEWERS_DIRNAME",
    "RUNS_JSONL_FILENAME",
    "FEATURE_RUN_LOG_FILENAME",
    "FEATURE_HANDOFF_FILENAME",
    "REVIEWERS_STATE_FILENAME",
    "progress_dir",
    "runs_dir",
    "features_dir",
    "feature_dir_path",
    "runs_jsonl_path",
    "runs_jsonl_reference",
    "reviewers_state_path",
    "sanitize_feature_id_for_log",
    "run_feature_log_filename",
    "run_feature_log_path",
    "run_feature_log_reference",
    "run_feature_log_template_reference",
    "handoff_markdown_path",
    "handoff_markdown_reference",
    "handoff_markdown_template_reference",
]
