from __future__ import annotations

import json
from pathlib import Path

from engineeringagent.adapters.progress import FilesystemProgressJournal
from engineeringagent.domain.audit import ProgressEvent


def test_filesystem_progress_journal_writes_all_progress_artifacts(
    tmp_path: Path,
) -> None:
    """Persist run, feature-log, report, and handoff artifacts through one adapter."""
    journal = FilesystemProgressJournal()

    journal.append(
        project_root=tmp_path,
        event=ProgressEvent(
            timestamp="2026-03-11T00:00:00Z",
            event_kind="iteration.telemetry",
            feature_id="FEAT-200",
            payload={"result": "passed"},
        ),
    )
    journal.append_feature_log(
        project_root=tmp_path,
        feature_id="FEAT-200",
        lines=["entry one", "entry two"],
    )
    journal.write_iteration_report(
        project_root=tmp_path,
        feature_id="FEAT-200",
        payload={"feature_id": "FEAT-200", "attempt": 1, "result": "passed"},
    )
    journal.write_handoff(
        project_root=tmp_path,
        feature_id="FEAT-200",
        lines=["# Handoff", "", "- Feature: `FEAT-200`", "- Carryover summary: wired"],
    )

    runs_payload = json.loads(
        (
            tmp_path / ".engineeringagent" / "progress" / "runs" / "runs.jsonl"
        ).read_text(encoding="utf-8")
    )
    assert runs_payload == {
        "result": "passed",
        "timestamp": "2026-03-11T00:00:00Z",
        "event_kind": "iteration.telemetry",
        "feature_id": "FEAT-200",
    }

    feature_log = (
        tmp_path
        / ".engineeringagent"
        / "progress"
        / "features"
        / "FEAT-200"
        / "run.txt"
    ).read_text(encoding="utf-8")
    assert "entry one\nentry two" in feature_log

    report_payload = json.loads(
        (
            tmp_path
            / ".engineeringagent"
            / "progress"
            / "features"
            / "FEAT-200"
            / "iteration-report.json"
        ).read_text(encoding="utf-8")
    )
    assert report_payload == {
        "feature_id": "FEAT-200",
        "attempt": 1,
        "result": "passed",
    }

    handoff_path = (
        tmp_path
        / ".engineeringagent"
        / "progress"
        / "features"
        / "FEAT-200"
        / "handoff.md"
    )
    assert handoff_path.read_text(encoding="utf-8").startswith("# Handoff")
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
