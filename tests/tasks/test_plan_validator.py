"""Tests for markdown plan validation."""

from developer.tasks.services.plan_validator import PlanValidator


def test_plan_validator_accepts_valid_plan() -> None:
    """Validator should accept a valid frontmatter payload."""
    result = PlanValidator().validate(
        {
            "schema_version": 1,
            "task_id": "ship-it",
            "title": "Ship it",
            "status": "ready",
            "phases": [{"id": "build", "title": "Build", "status": "todo"}],
        }
    )

    assert result.valid is True
    assert result.errors == []


def test_plan_validator_rejects_duplicate_phase_ids() -> None:
    """Validator should reject duplicate phase ids."""
    result = PlanValidator().validate(
        {
            "schema_version": 1,
            "task_id": "ship-it",
            "title": "Ship it",
            "status": "ready",
            "phases": [
                {"id": "build", "title": "Build", "status": "todo"},
                {"id": "build", "title": "Verify", "status": "todo"},
            ],
        }
    )

    assert result.valid is False
    assert any("duplicate phase id" in error.message for error in result.errors)


def test_plan_validator_rejects_done_task_with_incomplete_phases() -> None:
    """Done tasks should require every phase to be done."""
    result = PlanValidator().validate(
        {
            "schema_version": 1,
            "task_id": "ship-it",
            "title": "Ship it",
            "status": "done",
            "phases": [{"id": "build", "title": "Build", "status": "todo"}],
        }
    )

    assert result.valid is False
    assert any("all phases are 'done'" in error.message for error in result.errors)
