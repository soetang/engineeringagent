from typing import List, Union
from pydantic import BaseModel, Field, ConfigDict


class CheckList(BaseModel):
    """Represents a list of checks defined in an external file."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Name of the check list")
    filepath: str = Field(..., description="Path to the file containing the check list")


class CheckType(BaseModel):
    """Base class for specific check types."""

    model_config = ConfigDict(extra="forbid")

    check_type: str = Field(
        ..., description="Technical type of check (e.g., 'command', 'http')"
    )
    check_category: str = Field(
        default="",
        description="Semantic category of check (e.g., 'linting', 'fitness')",
    )


class QualitySpec(BaseModel):
    """Root model for the quality specification YAML file."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="root", description="Name of the check list")
    filepath: str = Field(
        default="", description="Path to the file containing the check list"
    )
    checks: List[Union[CheckList, CheckType]] = Field(
        ..., description="List of checks or check lists to run"
    )
