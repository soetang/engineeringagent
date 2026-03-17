from pydantic import BaseModel, Field
from pydantic import ConfigDict


class QualitySettings(BaseModel):
    """Quality configuration settings."""

    checks_path: str = Field(
        default="checks.yaml",
        description="Path to the quality checks configuration file",
    )

    model_config = ConfigDict(extra="forbid")
