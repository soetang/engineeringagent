from typing import Optional, Protocol, Type, TypeVar, Union

from pydantic import BaseModel

T = TypeVar("T", bound=Union[BaseModel, str])


class AgentProtocol(Protocol):
    """Agent protocol interface."""

    def run_agent(
        self,
        prompt: str,
        output_format: Type[T] = str,  # type: ignore[type-arg]
        model: Optional[str] = None,
        profile: Optional[str] = None,
        path: Optional[str] = None,
    ) -> T:
        """Execute agent with prompt, return structured output or string."""
        ...
