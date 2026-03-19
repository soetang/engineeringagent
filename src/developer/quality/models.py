from typing import List, Union, Type
from pydantic import BaseModel, Field, ConfigDict, create_model

from developer.orchestrators.models import GatePhase


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
    phase: GatePhase = Field(
        default=GatePhase.ITERATION_COMPLETE,
        description="Execution phase for the check.",
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


def create_dynamic_quality_spec() -> Type[BaseModel]:
    """Create a dynamic QualitySpec model based on available adapters.

    Returns:
        A dynamically created pydantic BaseModel class
    """
    # Import here to avoid circular imports
    from .adapters import get_adapters

    adapters = get_adapters()

    if not adapters:
        # Fallback to basic QualitySpec if no adapters available
        return QualitySpec

    # Collect all check type models from adapters
    check_type_models = []
    for adapter_dict in adapters:
        if isinstance(adapter_dict, dict) and "adapter" in adapter_dict:
            adapter = adapter_dict["adapter"]
            if hasattr(adapter, "get_check_type"):
                check_type = adapter.get_check_type()
                if check_type:
                    check_type_models.append(check_type)

    # Create union of all check types (including CheckList)
    if check_type_models:
        check_type_models.append(CheckList)
        DynamicCheckType = Union[tuple(check_type_models)]  # type: ignore[misc]
    else:
        # Fallback to basic QualitySpec if no adapters available
        return QualitySpec

    # Create dynamic QualitySpec model
    DynamicQualitySpec = create_model(
        "DynamicQualitySpec",
        name=(str, Field(default="root", description="Name of the check list")),
        filepath=(
            str,
            Field(default="", description="Path to the file containing the check list"),
        ),
        checks=(
            List[DynamicCheckType],
            Field(..., description="List of checks or check lists to run"),
        ),
        __base__=BaseModel,
        __config__=ConfigDict(extra="forbid"),
    )

    return DynamicQualitySpec
