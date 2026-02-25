from __future__ import annotations

from pathlib import Path

from engineeringagent.loop_runtime.feature_state import (
    _load_selected_feature,
)
from engineeringagent.specs import load_yaml


def test_selected_feature_load_does_not_fallback_to_archive(tmp_path: Path) -> None:
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

    feature, error = _load_selected_feature(active_path)
    assert feature is None
    assert error == f"selected feature path disappeared during loop iteration: {active_path}"

    archived = load_yaml(archive_path)
    subtasks = archived.get("subtasks")
    assert isinstance(subtasks, list)
    assert subtasks[0]["status"] == "backlog"
