from __future__ import annotations

import errno
from pathlib import Path

import pytest
import yaml

from engineeringagent.application.feature_state import (
    archive_completed_feature,
    refresh_feature_after_implement,
    restore_archived_feature,
)
def _write_done_bundled_feature(feature_root: Path) -> tuple[Path, Path]:
    spec_path = feature_root / "spec.yaml"
    plan_path = feature_root / "plan.md"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        "\n".join(
            [
                "id: FEAT-001",
                "title: hello",
                "type: feature",
                "expected_commit_subject: 'feat: hello'",
                "status: done",
                "planning_tier: planned",
                "priority: high",
                "objective: hello",
                "acceptance: ['ok']",
                "artifacts:",
                "  plan: plan.md",
                "",
            ]
        ),
        encoding="utf-8",
    )
    plan_path.write_text(
        "---\n"
        + yaml.safe_dump(
            {
                "plan_id": "FEAT-001",
                "feature_id": "FEAT-001",
                "status": "in_progress",
                "source_spec": "spec.yaml",
                "planning_tier": "planned",
                "phases": [
                    {
                        "id": "P1",
                        "title": "Wrap archive bookkeeping",
                        "status": "done",
                    },
                    {
                        "id": "P2",
                        "title": "Normalize remaining plan metadata",
                        "status": "in_progress",
                    },
                ],
            },
            sort_keys=False,
        )
        + "---\n\n# Plan\n",
        encoding="utf-8",
    )
    return spec_path, plan_path


def _load_plan_frontmatter(plan_path: Path) -> dict[str, object]:
    document = plan_path.read_text(encoding="utf-8")
    frontmatter_end = document.find("\n---", 4)
    assert frontmatter_end >= 0
    frontmatter = yaml.safe_load(document[4:frontmatter_end])
    assert isinstance(frontmatter, dict)
    return frontmatter


def test_archive_completed_feature_returns_bundled_done_entrypoint(
    tmp_path: Path,
) -> None:
    """Archive returns the bundled spec entrypoint under features_done."""
    feature_path, _plan_path = _write_done_bundled_feature(
        tmp_path / "docs" / "spec" / "features" / "FEAT-001"
    )

    ok, archived_path, message = archive_completed_feature(
        tmp_path,
        feature_path,
    )

    assert ok is True
    assert message == ""
    assert archived_path == tmp_path / "docs" / "spec" / "features_done" / "FEAT-001" / "spec.yaml"
    assert archived_path is not None
    assert feature_path.exists() is False


def test_archive_completed_feature_marks_bundled_plan_done(tmp_path: Path) -> None:
    """Archive normalizes bundled plan frontmatter to done."""
    feature_path, _plan_path = _write_done_bundled_feature(
        tmp_path / "docs" / "spec" / "features" / "FEAT-001"
    )

    ok, archived_path, message = archive_completed_feature(
        tmp_path,
        feature_path,
    )

    assert ok is True
    assert message == ""
    assert archived_path is not None
    frontmatter = _load_plan_frontmatter(archived_path.parent / "plan.md")
    assert frontmatter["status"] == "done"
    phases = frontmatter.get("phases")
    assert isinstance(phases, list)
    assert [phase["status"] for phase in phases] == ["done", "done"]


def test_refresh_archived_bundled_feature_marks_plan_done(tmp_path: Path) -> None:
    """Post-implement refresh loads an archived bundled feature as done."""
    active_spec_path = tmp_path / "docs" / "spec" / "features" / "FEAT-001" / "spec.yaml"
    archived_spec_path, _plan_path = _write_done_bundled_feature(
        tmp_path / "docs" / "spec" / "features_done" / "FEAT-001"
    )

    post_outcome = refresh_feature_after_implement(
        tmp_path,
        active_spec_path,
    )

    assert post_outcome.result == "passed"
    assert post_outcome.archived_in_iteration is True
    assert post_outcome.archived_path == archived_spec_path
    frontmatter = _load_plan_frontmatter(archived_spec_path.parent / "plan.md")
    assert frontmatter["status"] == "done"
    phases = frontmatter.get("phases")
    assert isinstance(phases, list)
    assert [phase["status"] for phase in phases] == ["done", "done"]


def test_archive_completed_feature_falls_back_on_exdev(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Archive falls back to a cross-device-safe move when rename cannot work."""
    feature_path, _plan_path = _write_done_bundled_feature(
        tmp_path / "docs" / "spec" / "features" / "FEAT-001"
    )
    archive_path = (
        tmp_path / "docs" / "spec" / "features_done" / "FEAT-001" / "spec.yaml"
    )

    original_rename = Path.rename

    def _raise_exdev_for_archive(self: Path, target: str | Path) -> Path:
        normalized_target = Path(target)
        if self == feature_path.parent and normalized_target == archive_path.parent:
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", _raise_exdev_for_archive)

    ok, archived_path, message = archive_completed_feature(tmp_path, feature_path)

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
    """Restore falls back to a cross-device-safe move when rename cannot work."""
    archived_path, _plan_path = _write_done_bundled_feature(
        tmp_path / "docs" / "spec" / "features_done" / "FEAT-001"
    )
    original_path = tmp_path / "docs" / "spec" / "features" / "FEAT-001" / "spec.yaml"

    original_rename = Path.rename

    def _raise_exdev_for_restore(self: Path, target: str | Path) -> Path:
        normalized_target = Path(target)
        if self == archived_path.parent and normalized_target == original_path.parent:
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", _raise_exdev_for_restore)

    ok, message = restore_archived_feature(archived_path, original_path)

    assert ok is True
    assert message == ""
    assert original_path.exists()
    assert archived_path.exists() is False
