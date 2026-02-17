from __future__ import annotations

from pathlib import Path


def run_validate(project_root: Path, *, schema_only: bool = False) -> list[str]:
    """Run spec/setup validation for a repository.

    This is the canonical validation execution entrypoint for checks orchestration.
    """

    from engineeringagent.checks.validate.validator import validate

    return validate(project_root=project_root, schema_only=schema_only)
