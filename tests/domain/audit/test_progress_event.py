from __future__ import annotations

import pytest

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


def test_progress_event_rejects_blank_feature_id() -> None:
    """Shared-kernel FeatureId validation should reject blank audit event ids."""
    with pytest.raises(ValueError, match="String should have at least 1 character"):
        ProgressEvent(
            timestamp="2026-03-11T00:00:00Z",
            event_kind="iteration.telemetry",
            feature_id="",
            payload={},
        )
