from __future__ import annotations

import errno
from pathlib import Path

import pytest

from engineeringagent.loop_runtime.feature_state import (
    _archive_completed_feature,
    _restore_archived_feature,
)
from engineeringagent.specs import load_yaml


def _write_done_feature(feature_path: Path) -> None:
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


def test_archive_completed_feature_marks_subtasks_done(tmp_path: Path) -> None:
    feature_path = tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml"
    _write_done_feature(feature_path)

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


def test_archive_completed_feature_falls_back_on_exdev(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature_path = tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml"
    archive_path = tmp_path / "docs" / "spec" / "features_done" / "FEAT-001.yaml"
    _write_done_feature(feature_path)

    original_rename = Path.rename

    def _raise_exdev_for_archive(self: Path, target: str | Path) -> Path:
        normalized_target = Path(target)
        if self == feature_path and normalized_target == archive_path:
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", _raise_exdev_for_archive)

    ok, archived_path, message = _archive_completed_feature(tmp_path, feature_path)

    assert ok is True
    assert message == ""
    assert archived_path == archive_path
    assert archived_path is not None
    assert archived_path.exists()
    assert feature_path.exists() is False


def test_restore_archived_feature_falls_back_on_exdev(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archived_path = tmp_path / "docs" / "spec" / "features_done" / "FEAT-001.yaml"
    original_path = tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml"
    _write_done_feature(archived_path)

    original_rename = Path.rename

    def _raise_exdev_for_restore(self: Path, target: str | Path) -> Path:
        normalized_target = Path(target)
        if self == archived_path and normalized_target == original_path:
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", _raise_exdev_for_restore)

    ok, message = _restore_archived_feature(archived_path, original_path)

    assert ok is True
    assert message == ""
    assert original_path.exists()
    assert archived_path.exists() is False
