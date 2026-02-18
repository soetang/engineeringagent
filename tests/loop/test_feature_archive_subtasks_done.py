from __future__ import annotations

from pathlib import Path

from engineeringagent.loop_runtime.feature_state import _archive_completed_feature
from engineeringagent.specs import load_yaml


def test_archive_completed_feature_marks_subtasks_done(tmp_path: Path) -> None:
    feature_path = tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml"
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    feature_path.write_text(
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

    ok, archived_path, message = _archive_completed_feature(
        tmp_path,
        feature_path,
    )

    assert ok is True
    assert message == ""
    assert archived_path is not None
    archived = load_yaml(archived_path)
    subtasks = archived.get("subtasks")
    assert isinstance(subtasks, list)
    assert subtasks[0]["status"] == "done"
