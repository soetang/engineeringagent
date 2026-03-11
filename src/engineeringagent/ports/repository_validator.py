"""Repository validation port used by the application layer."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class RepositoryValidator(Protocol):
    """Run repository validation without exposing checks implementation details."""

    def validate(
        self,
        project_root: Path,
        *,
        schema_only: bool = False,
    ) -> list[str]:
        """Return validation messages for one repository request."""
        raise NotImplementedError
