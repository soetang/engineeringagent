from typing import Optional, Protocol, Type, TypeVar

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
        output_format: Optional[Type[TModel]] = None,
        path: Optional[str] = None,
    ) -> TModel | str:
        """Execute agent with prompt, return structured output or string."""
        ...
