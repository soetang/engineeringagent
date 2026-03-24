from pydantic import BaseModel, ConfigDict, Field


class AgentBackendSettings(BaseModel):
    """Shared configuration for selecting an agent backend."""

    backend: str = Field(
        default="codex",
        description="Backend family to use, such as codex or vibe.",
    )

    profile: str | None = Field(
        default=None,
        description=(
            "Optional backend preset or profile. This may bundle model choice, "
            "prompts, tools, or permissions."
        ),
    )

    model: str | None = Field(
        default=None,
        description="Optional underlying LLM override when the backend supports it.",
    )

    model_config = ConfigDict(extra="forbid")
