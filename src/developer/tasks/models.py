"""Task domain models."""

from pydantic import BaseModel, ConfigDict


class TaskPhaseDefinition(BaseModel):
    """Parsed phase metadata from one task plan."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    status: str


class TaskPlanDefinition(BaseModel):
    """Validated task plan definition loaded from markdown frontmatter."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int
    task_id: str
    title: str
    status: str
    branch: str | None = None
    base_branch: str | None = None
    phases: list[TaskPhaseDefinition]
    path: str


class PlanValidationError(BaseModel):
    """One semantic validation error for a task plan."""

    model_config = ConfigDict(extra="forbid")

    location: str
    message: str


class PlanValidationResult(BaseModel):
    """Structured task plan validation result."""

    model_config = ConfigDict(extra="forbid")

    valid: bool
    errors: list[PlanValidationError]


class TaskPublicationState(BaseModel):
    """Persisted publication state for a task."""

    model_config = ConfigDict(extra="forbid")

    task_name: str
    task_path: str | None = None
    branch_name: str
    base_branch: str
    pr_url: str | None = None
    pr_number: str | None = None
    status: str
