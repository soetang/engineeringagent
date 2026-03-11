from __future__ import annotations

from engineeringagent.adapters.progress import FilesystemProgressJournal
from engineeringagent.progress import (
    handoff_markdown_path,
    progress_dir,
    reviewers_state_path,
    run_feature_log_path,
    runs_jsonl_path,
)


def test_progress_package_exports_common_helpers() -> None:
    """The progress package should keep exposing its public path helper surface."""

    assert callable(FilesystemProgressJournal)
    assert callable(progress_dir)
    assert callable(reviewers_state_path)
    assert callable(run_feature_log_path)
    assert callable(handoff_markdown_path)
    assert callable(runs_jsonl_path)
