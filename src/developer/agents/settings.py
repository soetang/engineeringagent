from pydantic import BaseModel, ConfigDict, Field


class AgentSettings(BaseModel):
    """Agent configuration settings."""

    backend: str = Field(
        default="codex", description="Agent backend to use (codex, vibe, etc.)"
    )

    profile: str | None = Field(
        default=None,
        description="Optional agent profile to use",
    )

    model: str | None = Field(
        default=None,
        description="Optional LLM model to use",
    )

    model_config = ConfigDict(extra="forbid")
