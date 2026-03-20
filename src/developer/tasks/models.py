"""Task domain models."""

from pydantic import BaseModel, ConfigDict


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
