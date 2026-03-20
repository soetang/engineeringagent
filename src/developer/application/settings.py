"""Application-layer settings models."""

from pydantic import BaseModel, ConfigDict, Field


class ImplementationSettings(BaseModel):
    """Configuration for implementation run behavior."""

    model_config = ConfigDict(extra="forbid")

    max_iterations: int | str = Field(default=40)
