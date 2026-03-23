"""Application-facing command and result models."""

from pydantic import BaseModel, ConfigDict

from developer.scaffolding.models import FileWriteResult, InitRequest, InitResult


class ImplementationRunResult(BaseModel):
    """Command-facing result for an implementation run."""

    model_config = ConfigDict(extra="forbid")

    exit_code: int
    message: str
