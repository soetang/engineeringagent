from __future__ import annotations

import shutil
from pathlib import Path

import yaml


def invalid_spec_fixtures_dir(repo_root: Path) -> Path:
    return repo_root / "tests" / "fixtures" / "specs" / "invalid"


def make_invalid_project(repo_root: Path, tmp_path: Path, fixture_name: str) -> Path:
    project_root = tmp_path
    features_dir = project_root / "docs" / "spec" / "features"

    features_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        invalid_spec_fixtures_dir(repo_root) / fixture_name,
        features_dir / fixture_name,
    )
    return project_root


def write_bundled_feature_spec(
    feature_root: Path,
    *,
    feature_id: str = "FEAT-181",
    planning_tier: str = "planned",
    include_plan_artifact: bool = True,
    include_research_artifact: bool = False,
    extra_fields: dict[str, object] | None = None,
) -> Path:
    spec_path = feature_root / "spec.yaml"
    feature_root.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "id": feature_id,
        "title": "Bundled feature",
        "type": "spec",
        "expected_commit_subject": "spec: bundled feature contract",
        "planning_tier": planning_tier,
        "status": "backlog",
        "priority": "high",
        "objective": "Validate bundled feature packages.",
        "acceptance": ["Validator enforces bundled feature contracts."],
        "artifacts": {},
    }
    artifacts = payload["artifacts"]
    assert isinstance(artifacts, dict)
    if include_plan_artifact:
        artifacts["plan"] = "plan.md"
    if include_research_artifact:
        artifacts["research"] = "research.md"
    if extra_fields:
        payload.update(extra_fields)
    spec_path.write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )
    return spec_path


def write_plan_artifact(
    feature_root: Path,
    *,
    feature_id: str = "FEAT-181",
    planning_tier: str = "planned",
) -> Path:
    plan_path = feature_root / "plan.md"
    plan_path.write_text(
        "\n".join(
            [
                "---",
                f"plan_id: {feature_id}",
                f"feature_id: {feature_id}",
                "status: pending",
                "source_spec: spec.yaml",
                f"planning_tier: {planning_tier}",
                "phases:",
                "  - id: P1",
                "    title: First phase",
                "    status: pending",
                "    verification:",
                "      - 'true'",
                "---",
                "",
                "# Plan",
                "",
                "Implementation plan body.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return plan_path


def write_legacy_feature_wrapper(
    feature_path: Path,
    *,
    feature_id: str = "FEAT-181",
) -> Path:
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    feature_path.write_text(
        yaml.safe_dump(
            {
                "id": feature_id,
                "title": "Legacy wrapper",
                "type": "spec",
                "expected_commit_subject": "spec: legacy wrapper",
                "status": "in_progress",
                "priority": "high",
                "objective": "Compatibility wrapper for bundled feature.",
                "acceptance": ["Legacy wrapper remains selectable."],
                "subtasks": [
                    {
                        "id": "ST-001",
                        "title": "Compatibility task",
                        "status": "backlog",
                        "verification": ["true"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return feature_path
