from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tests.helpers.feature_iteration_feedback_support import (
    advance_bundled_plan_prompt_state,
)
from tests.helpers.feature_iteration_support import (
    base_feature,
    make_bundled_project_root,
)


def test_advance_bundled_plan_prompt_state_tracks_next_phase_then_finishes(
    tmp_path: Path,
) -> None:
    feature_data = {
        **base_feature(status="in_progress"),
        "planning_tier": "planned",
        "artifacts": {"plan": "plan.md"},
    }
    feature_data.pop("subtasks", None)
    _, feature_path, plan_path = make_bundled_project_root(
        tmp_path,
        feature_data=feature_data,
        plan_frontmatter={
            "plan_id": "FEAT-900",
            "feature_id": "FEAT-900",
            "status": "in_progress",
            "source_spec": "spec.yaml",
            "planning_tier": "planned",
            "phases": [
                {"id": "P1", "title": "First", "status": "pending"},
                {"id": "P2", "title": "Second", "status": "pending"},
            ],
        },
    )

    advance_bundled_plan_prompt_state(feature_path, plan_path, prompt_count=1)
    first_feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    first_plan = _load_plan_frontmatter(plan_path)
    first_phases = _load_plan_phases(first_plan)
    assert first_feature["status"] == "in_progress"
    assert first_plan["status"] == "in_progress"
    assert first_phases[0]["status"] == "done"
    assert first_phases[1]["status"] == "pending"

    advance_bundled_plan_prompt_state(feature_path, plan_path, prompt_count=3)
    final_feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    final_plan = _load_plan_frontmatter(plan_path)
    assert final_feature["status"] == "done"
    assert final_plan["status"] == "done"


def _load_plan_frontmatter(plan_path: Path) -> dict[str, object]:
    document = plan_path.read_text(encoding="utf-8")
    frontmatter_end = document.find("\n---", 4)
    payload = yaml.safe_load(document[4:frontmatter_end])
    assert isinstance(payload, dict)
    return payload


def _load_plan_phases(frontmatter: dict[str, object]) -> list[dict[str, Any]]:
    phases = frontmatter.get("phases")
    assert isinstance(phases, list)
    assert all(isinstance(phase, dict) for phase in phases)
    return phases
