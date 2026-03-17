from typing import Optional, Protocol, Type, TypeVar, Union

from pydantic import BaseModel

TModel = TypeVar("TModel", bound=BaseModel)


class AgentProtocol(Protocol):
    """Agent protocol interface."""

    def __init__(self, profile: Optional[str] = None, model: Optional[str] = None):
        """Initialize agent with profile and model configuration."""
        ...

    def run_agent(
        self,
        prompt: str,
        output_format: Union[Type[TModel], None] = None,
        path: Optional[str] = None,
    ) -> Union[TModel, str]:
        """Execute agent with prompt, return structured output or string."""
        ...
