"""Prompt settings models."""

from pydantic import BaseModel, ConfigDict, Field


class PromptSettings(BaseModel):
    """Configuration for prompt templates."""

    implementation_prompt_path: str = Field(default="harness/implementation_prompt.md")
    commit_prompt_path: str = Field(default="harness/prompts/commit_message_prompt.md")
    pull_request_prompt_path: str = Field(
        default="harness/prompts/pull_request_prompt.md"
    )

    model_config = ConfigDict(extra="forbid")
