"""Settings for forge publication integration."""

from pydantic import BaseModel, ConfigDict, Field


class ForgeSettings(BaseModel):
    """Configuration for forge publication."""

    enabled: bool = Field(default=False)
    provider: str = Field(default="github")

    model_config = ConfigDict(extra="forbid")
