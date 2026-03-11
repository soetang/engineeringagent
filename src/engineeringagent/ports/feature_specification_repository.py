"""Feature specification repository port used by orchestration services."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from engineeringagent.domain.specification import (
    FeatureSelectionCandidate,
    FeatureSpecification,
)


class FeatureSpecificationRepository(Protocol):
    """Load and persist bundled feature specifications through a stable seam."""

    def list_selection_candidates(
        self,
        project_root: Path,
    ) -> tuple[FeatureSelectionCandidate, ...]:
        """Return typed candidates from the active feature specification catalog."""
        raise NotImplementedError

    def load(self, project_root: Path, feature_id: str) -> FeatureSpecification:
        """Load one feature specification from the active or archived catalog."""
        raise NotImplementedError

    def save(
        self,
        project_root: Path,
        feature_id: str,
        specification: FeatureSpecification,
    ) -> None:
        """Persist one feature specification back to its current storage location."""
        raise NotImplementedError

    def archive(self, project_root: Path, feature_id: str) -> None:
        """Move one active feature package into the completed catalog."""
        raise NotImplementedError
