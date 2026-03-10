from __future__ import annotations

import json
from pathlib import Path

from engineeringagent.adapters.progress import FilesystemProgressJournal


def test_filesystem_progress_journal_writes_all_progress_artifacts(
    tmp_path: Path,
) -> None:
    """Persist run, feature-log, and handoff artifacts through one adapter."""
    journal = FilesystemProgressJournal()

    journal.append_run_record(
        project_root=tmp_path,
        payload={"feature_id": "FEAT-200", "result": "passed"},
    )
    journal.append_feature_log(
        project_root=tmp_path,
        feature_id="FEAT-200",
        lines=["entry one", "entry two"],
    )
    journal.append_handoff_entry(
        project_root=tmp_path,
        feature_id="FEAT-200",
        entry_lines=["## Iteration 1 - 2026-03-10T00:00:00Z", "", "Summary: wired"],
    )

    runs_payload = json.loads(
        (
            tmp_path / ".engineeringagent" / "progress" / "runs" / "runs.jsonl"
        ).read_text(encoding="utf-8")
    )
    assert runs_payload == {"feature_id": "FEAT-200", "result": "passed"}

    feature_log = (
        tmp_path
        / ".engineeringagent"
        / "progress"
        / "features"
        / "FEAT-200"
        / "run.txt"
    ).read_text(encoding="utf-8")
    assert "entry one\nentry two" in feature_log

    handoff_path = (
        tmp_path
        / ".engineeringagent"
        / "progress"
        / "features"
        / "FEAT-200"
        / "handoff.md"
    )
    assert handoff_path.read_text(encoding="utf-8").startswith("## Iteration 1")
    assert journal.latest_handoff_path(
        project_root=tmp_path,
        feature_id="FEAT-200",
    ) == handoff_path


def test_filesystem_progress_journal_returns_none_without_handoff(
    tmp_path: Path,
) -> None:
    """Return no handoff path when nothing has been persisted yet."""
    journal = FilesystemProgressJournal()

    assert (
        journal.latest_handoff_path(project_root=tmp_path, feature_id="FEAT-404")
        is None
    )
