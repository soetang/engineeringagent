from __future__ import annotations

from engineeringagent.domain.audit import ProgressEvent


def test_progress_event_requires_typed_append_only_fields() -> None:
    """Keep audit events explicit while preserving flat JSONL telemetry records."""

    event = ProgressEvent(
        timestamp="2026-03-11T00:00:00Z",
        event_kind="iteration.telemetry",
        feature_id="FEAT-200",
        payload={"attempt": 1, "result": "passed"},
    )

    assert event.to_log_record() == {
        "attempt": 1,
        "result": "passed",
        "timestamp": "2026-03-11T00:00:00Z",
        "event_kind": "iteration.telemetry",
        "feature_id": "FEAT-200",
    }
