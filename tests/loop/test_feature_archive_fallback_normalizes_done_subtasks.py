from __future__ import annotations

from pathlib import Path

from engineeringagent.loop_runtime.feature_state import (
    _load_selected_feature_with_archive_fallback,
)
from engineeringagent.specs import load_yaml


def test_archive_fallback_marks_done_feature_subtasks_done(tmp_path: Path) -> None:
    active_path = tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml"
    archive_path = tmp_path / "docs" / "spec" / "features_done" / "FEAT-001.yaml"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_text(
        "\n".join(
            [
                "id: FEAT-001",
                "title: hello",
                "type: feature",
                "expected_commit_subject: 'feat: hello'",
                "status: done",
                "priority: high",
                "objective: hello",
                "acceptance: ['ok']",
                "subtasks:",
                "  - id: ST-001",
                "    title: sub",
                "    status: backlog",
                "    verification: ['true']",
                "",
            ]
        ),
        encoding="utf-8",
    )

    feature, loaded_from_archive, error = _load_selected_feature_with_archive_fallback(
        tmp_path,
        active_path,
    )
    assert error is None
    assert loaded_from_archive is True
    assert feature is not None

    archived = load_yaml(archive_path)
    subtasks = archived.get("subtasks")
    assert isinstance(subtasks, list)
    assert subtasks[0]["status"] == "done"
