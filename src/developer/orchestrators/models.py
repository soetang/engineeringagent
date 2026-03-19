"""Domain models for orchestrator control flow."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict


class AgentResult(BaseModel):
    """Represents agent execution output for an orchestrator attempt."""

    model_config = ConfigDict(extra="forbid")

    summary: str


class GateResult(BaseModel):
    """Represents the result of a quality gate check."""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    feedback: str | None = None


class GatePhase(str, Enum):
    """Phases used by the gate runner."""

    ITERATION_COMPLETE = "IterationComplete"
    IMPLEMENTATION_COMPLETE = "ImplementationComplete"


class CompletionResult(str, Enum):
    """Represents whether an iterative flow has reached completion."""

    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


class OrchestratorOutcome(BaseModel):
    """Public orchestrator result with overall status and attempt count."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "failed"]
    iterations: int
    feedback: str | None = None
