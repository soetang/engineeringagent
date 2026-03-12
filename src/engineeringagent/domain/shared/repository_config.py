"""Typed repository configuration values shared across bootstrap and adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_repo_relative_path(value: str, *, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} cannot be empty")

    candidate = Path(stripped)
    if candidate.is_absolute():
        raise ValueError(f"{field_name} must be relative")
    if any(part == ".." for part in candidate.parts):
        raise ValueError(f"{field_name} cannot contain '..'")

    normalized_parts = [part for part in candidate.parts if part not in {"", "."}]
    if not normalized_parts:
        raise ValueError(f"{field_name} cannot be '.'")
    return Path(*normalized_parts).as_posix()


class RepositoryPaths(BaseModel):
    """Effective repository-local paths resolved from config and defaults."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    docs_root: str = "docs"
    harness_root: str = "harness"
    progress_root: str = ".engineeringagent/progress"
    specifications_root: str = "docs/spec"
    harness_checks_path: str = "harness/checks.yaml"

    @field_validator(
        "docs_root",
        "harness_root",
        "progress_root",
        "specifications_root",
        "harness_checks_path",
        mode="before",
    )
    @classmethod
    def _validate_path_field(cls, value: Any, info: Any) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{info.field_name} must be a string")
        return _normalize_repo_relative_path(value, field_name=info.field_name)


class CodexRepositoryConfig(BaseModel):
    """Codex-specific repository defaults."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile: str | None = None
    model: str | None = None

    @field_validator("profile", "model", mode="before")
    @classmethod
    def _validate_optional_string(cls, value: Any, info: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"agents.codex.{info.field_name} must be a string")
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"agents.codex.{info.field_name} cannot be empty")
        return normalized


class ImplementationAgentConfig(BaseModel):
    """Implementation-agent defaults owned by repository configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt_definition: str = "implementation_default"

    @field_validator("prompt_definition", mode="before")
    @classmethod
    def _validate_prompt_definition(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("agents.implementation.prompt_definition must be a string")
        normalized = value.strip()
        if not normalized:
            raise ValueError("agents.implementation.prompt_definition cannot be empty")
        return normalized


class RepositoryAgentsConfig(BaseModel):
    """Effective agent-related repository defaults."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    backend: str | None = None
    codex: CodexRepositoryConfig = Field(default_factory=CodexRepositoryConfig)
    implementation: ImplementationAgentConfig = Field(
        default_factory=ImplementationAgentConfig
    )

    @field_validator("backend", mode="before")
    @classmethod
    def _validate_backend(cls, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("backend must be a string")
        normalized = value.strip()
        if not normalized:
            raise ValueError("backend cannot be empty")
        return normalized


class RepositoryConfig(BaseModel):
    """Effective repository configuration after precedence resolution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    paths: RepositoryPaths = Field(default_factory=RepositoryPaths)
    agents: RepositoryAgentsConfig = Field(default_factory=RepositoryAgentsConfig)
