"""Application services for JSON Schema export."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from developer.quality.services import get_schema_service


class PlanPhaseSchema(BaseModel):
    """JSON-schema model for one plan phase entry."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    status: Literal["todo", "in_progress", "blocked", "done"]


class PlanFrontmatterSchema(BaseModel):
    """JSON-schema model for markdown task-plan frontmatter."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    task_id: str = Field(..., pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=1)
    title: str = Field(..., min_length=1)
    status: Literal["draft", "ready", "in_progress", "blocked", "done"]
    branch: str | None = Field(default=None, min_length=1)
    base_branch: str | None = Field(default=None, min_length=1)
    phases: list[PlanPhaseSchema] = Field(..., min_length=1)


def get_plan_schema() -> dict[str, object]:
    """Return the JSON Schema for markdown plan frontmatter."""
    return PlanFrontmatterSchema.model_json_schema()


def get_quality_schema() -> dict[str, object]:
    """Return the JSON Schema for the quality-spec YAML structure."""
    return get_schema_service()["quality_spec_schema"]
