"""Application-facing result models."""

from pydantic import BaseModel, ConfigDict


class ImplementationRunResult(BaseModel):
    """Command-facing result for an implementation run."""

    model_config = ConfigDict(extra="forbid")

    exit_code: int
    message: str
