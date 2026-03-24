"""Prompt settings models."""

from pydantic import BaseModel, ConfigDict, Field

from developer.scaffolding.paths import (
    COMMIT_MESSAGE_PROMPT_NAME,
    DEFAULT_HARNESS_DIR,
    IMPLEMENTATION_PROMPT_NAME,
    PULL_REQUEST_PROMPT_NAME,
    build_prompt_path,
)


class PromptSettings(BaseModel):
    """Configuration for prompt templates."""

    implementation_prompt_path: str = Field(
        default=build_prompt_path(DEFAULT_HARNESS_DIR, IMPLEMENTATION_PROMPT_NAME)
    )
    commit_prompt_path: str = Field(
        default=build_prompt_path(DEFAULT_HARNESS_DIR, COMMIT_MESSAGE_PROMPT_NAME)
    )
    pull_request_prompt_path: str = Field(
        default=build_prompt_path(DEFAULT_HARNESS_DIR, PULL_REQUEST_PROMPT_NAME)
    )

    model_config = ConfigDict(extra="forbid")
