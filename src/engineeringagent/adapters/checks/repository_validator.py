"""Checks-backed repository validation adapter."""

from __future__ import annotations

from pathlib import Path

from engineeringagent.checks import validate_repository


class ChecksRepositoryValidator:
    """Adapter that delegates repository validation to the checks package."""

    def validate(
        self,
        project_root: Path,
        *,
        schema_only: bool = False,
    ) -> list[str]:
        """Return repository validation messages."""
        return validate_repository(project_root, schema_only=schema_only)
