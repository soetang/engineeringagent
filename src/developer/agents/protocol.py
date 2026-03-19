from typing import Optional, Protocol, Type, TypeVar

from developer.orchestrators.protocols import AgentRunner

from pydantic import BaseModel

TModel = TypeVar("TModel", bound=BaseModel)


class AgentProtocol(AgentRunner):
    """Full agent protocol including construction-time inputs.

    This protocol is a superset of :class:`AgentRunner`.
    Use ``AgentRunner`` when only execution methods are needed (orchestrator).
    """

    def __init__(
        self,
        profile: Optional[str] = None,
        model: Optional[str] = None,
        path: Optional[str] = None,
    ):
        """Initialize agent with profile and model configuration."""
        ...
