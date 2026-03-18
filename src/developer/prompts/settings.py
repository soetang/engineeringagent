from pydantic import BaseModel, Field, ConfigDict


class OrchestratorPromptSettings(BaseModel):
    """Configuration for orchestrator prompt templates."""

    implementation_prompt_path: str = Field(
        default="prompts/implementation_prompt.md",
        description="Path to the implementation prompt template",
    )

    model_config = ConfigDict(extra="forbid")
