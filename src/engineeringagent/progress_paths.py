"""Centralized construction for loop progress and state artifact paths.

This module is the canonical source for resolving repository-local paths under the
`progress/` directory that are used by loop telemetry and reviewer state.
"""

from __future__ import annotations

from pathlib import Path

PROGRESS_DIRNAME = "progress"

RUNS_JSONL_FILENAME = "runs.jsonl"
REVIEWERS_STATE_FILENAME = "reviewers-state.json"


def progress_dir(project_root: Path) -> Path:
    """Return the absolute progress directory for a repo root."""
    return project_root / PROGRESS_DIRNAME


def runs_jsonl_path(project_root: Path) -> Path:
    """Return absolute path to the loop telemetry JSONL sink."""
    return progress_dir(project_root) / RUNS_JSONL_FILENAME


def runs_jsonl_reference(project_root: Path) -> str:
    """Return repository-relative reference for the JSONL run telemetry sink."""

    path = runs_jsonl_path(project_root)
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def reviewers_state_path(project_root: Path) -> Path:
    """Return absolute path to the reviewers state JSON file."""
    return progress_dir(project_root) / REVIEWERS_STATE_FILENAME


def sanitize_feature_id_for_log(feature_id: str) -> str:
    """Return a filename-safe feature identifier for progress logs.

    The output is stable and restricted to ASCII alphanumerics plus '-' and '_'.
    Any other character is replaced with '_' and leading/trailing '_' are removed.
    When the result is empty, this function returns 'unknown-feature'.
    """

    sanitized = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_" for char in feature_id
    ).strip("_")
    return sanitized or "unknown-feature"


def run_feature_log_filename(feature_id: str) -> str:
    """Return the per-feature progress log filename."""
    safe_feature_id = sanitize_feature_id_for_log(feature_id)
    return f"run-feature-{safe_feature_id}.txt"


def run_feature_log_path(project_root: Path, feature_id: str) -> Path:
    """Return absolute path to the per-feature progress log."""
    return progress_dir(project_root) / run_feature_log_filename(feature_id)


def run_feature_log_reference(project_root: Path, feature_id: str) -> str:
    """Return repository-relative reference for a feature progress log path."""

    path = run_feature_log_path(project_root, feature_id)
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def run_feature_log_template_reference(project_root: Path) -> str:
    """Return a repository-relative reference for the per-feature log template."""

    path = progress_dir(project_root) / "run-feature-<FEATURE_ID>.txt"
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)
