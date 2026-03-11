"""Progress journal port for repository-local operational artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, Sequence


class ProgressJournal(Protocol):
    """Persist loop progress records behind an application-facing seam."""

    def append_run_record(
        self,
        *,
        project_root: Path,
        payload: dict[str, Any],
    ) -> None:
        """Append one JSONL run record."""
        raise NotImplementedError

    def append_feature_log(
        self,
        *,
        project_root: Path,
        feature_id: str,
        lines: Sequence[str],
    ) -> None:
        """Append one newline-terminated text block to the feature log."""
        raise NotImplementedError

    def write_iteration_report(
        self,
        *,
        project_root: Path,
        feature_id: str,
        payload: dict[str, Any],
    ) -> None:
        """Write the latest machine-readable iteration report for a feature."""
        raise NotImplementedError

    def write_handoff(
        self,
        *,
        project_root: Path,
        feature_id: str,
        lines: Sequence[str],
    ) -> None:
        """Write the latest rendered handoff artifact for a feature."""
        raise NotImplementedError

    def latest_handoff_path(self, *, project_root: Path, feature_id: str) -> Path | None:
        """Return the latest persisted handoff path when present."""
        raise NotImplementedError
