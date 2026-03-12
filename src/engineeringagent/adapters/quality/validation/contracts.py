from __future__ import annotations

from pathlib import Path
from typing import Mapping, NamedTuple, Protocol

from typing_extensions import Literal


class ValidationContext(NamedTuple):
    """Shared deterministic context passed to validate validators."""

    project_root: Path
    docs_root: Path
    schema_only: bool
    selected_groups: tuple[str, ...] | None = None
    docs_map_config: Mapping[str, str] | None = None


class ValidationIssue(NamedTuple):
    """Canonical validation issue model produced by repo/strategy validators."""

    validator_id: str
    scope: Literal["repo", "strategy"]
    path: str
    message: str
    code: str


class RepoValidator(Protocol):
    """Protocol for deterministic repository-level validate validators."""

    validator_id: str

    def validate(
        self,
        *,
        context: ValidationContext,
    ) -> tuple[ValidationIssue, ...]:
        """Return deterministic repository-level validation issues for a context."""
        raise NotImplementedError


class StrategyValidator(Protocol):
    """Optional protocol for strategy-owned static validate validators."""

    strategy_type: str
    validator_id: str

    def validate(
        self,
        *,
        context: ValidationContext,
    ) -> tuple[ValidationIssue, ...]:
        """Return deterministic strategy-level validation issues for a context."""
        raise NotImplementedError
