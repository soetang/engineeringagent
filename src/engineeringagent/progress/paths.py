"""Centralized construction for loop progress and state artifact paths.

This module is the canonical source for resolving repository-local paths under the
`.engineeringagent/progress/` namespace that are used by loop telemetry and reviewer state.
"""

from __future__ import annotations

from pathlib import Path

from engineeringagent.config import resolve_progress_root

PROGRESS_DIRNAME = Path(".engineeringagent") / "progress"
PROGRESS_RUNS_DIRNAME = "runs"
PROGRESS_FEATURES_DIRNAME = "features"
PROGRESS_REVIEWERS_DIRNAME = "reviewers"

RUNS_JSONL_FILENAME = "runs.jsonl"
FEATURE_RUN_LOG_FILENAME = "run.txt"
FEATURE_HANDOFF_FILENAME = "handoff.md"
REVIEWERS_STATE_FILENAME = "state.json"


def progress_dir(project_root: Path) -> Path:
    """Return the absolute progress directory for a repo root."""

    resolved_project_root = project_root.resolve()
    return resolve_progress_root(resolved_project_root)


def runs_dir(project_root: Path) -> Path:
    """Return absolute path to the runs telemetry directory."""

    return progress_dir(project_root) / PROGRESS_RUNS_DIRNAME


def features_dir(project_root: Path) -> Path:
    """Return absolute path to the feature-scoped progress directory."""

    return progress_dir(project_root) / PROGRESS_FEATURES_DIRNAME


def runs_jsonl_path(project_root: Path) -> Path:
    """Return absolute path to the loop telemetry JSONL sink."""

    return runs_dir(project_root) / RUNS_JSONL_FILENAME


def runs_jsonl_reference(project_root: Path) -> str:
    """Return repository-relative reference for the JSONL run telemetry sink."""

    return _to_reference(project_root, runs_jsonl_path(project_root))


def _to_reference(project_root: Path, path: Path) -> str:
    """Return a repo-relative path string when possible."""

    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def reviewers_state_path(project_root: Path) -> Path:
    """Return absolute path to the reviewers state JSON file."""

    return (
        progress_dir(project_root)
        / PROGRESS_REVIEWERS_DIRNAME
        / REVIEWERS_STATE_FILENAME
    )


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


def run_feature_log_filename() -> str:
    """Return the per-feature progress log filename."""

    return FEATURE_RUN_LOG_FILENAME


def feature_dir_path(project_root: Path, feature_id: str) -> Path:
    """Return absolute path to the feature-scoped progress directory."""

    safe_feature_id = sanitize_feature_id_for_log(feature_id)
    return features_dir(project_root) / safe_feature_id


def run_feature_log_path(project_root: Path, feature_id: str) -> Path:
    """Return absolute path to the per-feature progress log."""

    return feature_dir_path(project_root, feature_id) / run_feature_log_filename()


def run_feature_log_reference(project_root: Path, feature_id: str) -> str:
    """Return repository-relative reference for a feature progress log path."""

    return _to_reference(project_root, run_feature_log_path(project_root, feature_id))


def run_feature_log_template_reference(project_root: Path) -> str:
    """Return a repository-relative reference for the per-feature log template."""

    return _to_reference(
        project_root,
        features_dir(project_root) / "<FEATURE_ID>" / FEATURE_RUN_LOG_FILENAME,
    )


def handoff_markdown_path(project_root: Path, feature_id: str) -> Path:
    """Return absolute path to the per-feature handoff markdown log."""

    return feature_dir_path(project_root, feature_id) / FEATURE_HANDOFF_FILENAME


def handoff_markdown_reference(project_root: Path, feature_id: str) -> str:
    """Return repository-relative reference for a feature handoff markdown path."""

    return _to_reference(project_root, handoff_markdown_path(project_root, feature_id))


def handoff_markdown_template_reference(project_root: Path) -> str:
    """Return a repository-relative reference for the per-feature handoff template."""

    return _to_reference(
        project_root,
        features_dir(project_root) / "<FEATURE_ID>" / FEATURE_HANDOFF_FILENAME,
    )
