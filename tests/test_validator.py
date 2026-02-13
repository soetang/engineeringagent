from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from engineeringagent.validator import validate


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SOURCE = REPO_ROOT / "docs" / "spec" / "schemas" / "feature.schema.json"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "specs" / "invalid"


def _make_invalid_project(tmp_path: Path, fixture_name: str) -> Path:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"
    schema_target = project_root / "docs" / "spec" / "schemas" / "feature.schema.json"

    features_dir.mkdir(parents=True, exist_ok=True)
    schema_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCHEMA_SOURCE, schema_target)
    shutil.copy2(FIXTURES_DIR / fixture_name, features_dir / f"{fixture_name}")

    return project_root


@pytest.mark.parametrize(
    ("fixture_name", "expected"),
    [
        ("missing-objective.yaml", "'objective' is a required property"),
        ("bad-status.yaml", "'doing' is not one of"),
        ("illegal-transition.yaml", "feature status done requires all subtasks done"),
    ],
)
def test_invalid_spec_fixtures_report_clear_errors(
    tmp_path: Path,
    fixture_name: str,
    expected: str,
) -> None:
    project_root = _make_invalid_project(tmp_path, fixture_name)

    messages = validate(project_root=project_root)

    assert messages
    assert any(expected in message for message in messages)


def test_validate_reports_done_feature_left_in_active_directory(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"
    schema_target = project_root / "docs" / "spec" / "schemas" / "feature.schema.json"

    features_dir.mkdir(parents=True, exist_ok=True)
    schema_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCHEMA_SOURCE, schema_target)

    feature_path = features_dir / "FEAT-901-preexisting-done.yaml"
    feature_path.write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-901",
                "title": "Done spec in active directory",
                "status": "done",
                "priority": "high",
                "objective": "Validate done specs are archived.",
                "acceptance": ["Done specs are archived under features_done."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "Already complete",
                        "status": "done",
                        "order": 1,
                        "verification": ["true"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert messages
    assert any(
        "completed feature specs must be archived" in message for message in messages
    )
    assert any(
        "docs/spec/features_done/FEAT-901-preexisting-done.yaml" in message
        for message in messages
    )


def test_validate_transitional_policy_for_preexisting_done_features(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"
    schema_target = project_root / "docs" / "spec" / "schemas" / "feature.schema.json"

    features_dir.mkdir(parents=True, exist_ok=True)
    schema_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCHEMA_SOURCE, schema_target)

    feature_name = "FEAT-902-transition-done.yaml"
    feature_path = features_dir / feature_name
    feature_path.write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-902",
                "title": "Transition exception",
                "status": "done",
                "priority": "high",
                "objective": "Allow temporary transition policy.",
                "acceptance": ["Validator supports explicit transition exception."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "Already complete",
                        "status": "done",
                        "order": 1,
                        "verification": ["true"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    (features_dir / ".allow-done-active.txt").write_text(
        f"# temporary exceptions\n{feature_name}\n",
        encoding="utf-8",
    )

    messages = validate(project_root=project_root)

    assert messages == []
