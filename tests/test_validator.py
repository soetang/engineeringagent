from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from agent_harness.validator import validate


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
