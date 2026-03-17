from pydantic import BaseModel, Field
from pydantic import ConfigDict


class AgentSettings(BaseModel):
    """Agent configuration settings."""

    backend: str = Field(
        default="codex", description="Agent backend to use (codex, vibe, etc.)"
    )

    profile: str = Field(default="default", description="Agent profile to use")

    model: str = Field(default="gpt-4", description="LLM model to use")

    model_config = ConfigDict(extra="forbid")
