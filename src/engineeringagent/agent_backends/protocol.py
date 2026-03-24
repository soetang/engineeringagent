from typing import TypeVar

from engineeringagent.orchestrators.loop.protocols import AgentRunner

from pydantic import BaseModel

TModel = TypeVar("TModel", bound=BaseModel)


class AgentBackendProtocol(AgentRunner):
    """Full agent backend protocol including construction-time inputs.

    This protocol is a superset of :class:`AgentRunner`.
    Use ``AgentRunner`` when only execution methods are needed (orchestrator).
    """

    def __init__(
        self,
        profile: str | None = None,
        model: str | None = None,
        path: str | None = None,
    ) -> None:
        """Initialize a backend instance.

        Args:
            profile: Optional backend preset or agent persona. This may bundle
                model selection with prompts, tools, or permissions.
            model: Optional underlying LLM override when the backend supports
                direct model selection.
            path: Optional execution-time working directory override.
        """
        ...
