"""File-backed persistence for workspace sessions and runs."""

import json
from pathlib import Path

from developer.workspaces.models import RunHandle, WorkspaceSession


class FileWorkspaceRegistry:
    """Persist workspace and run metadata as JSON files."""

    def __init__(self, state_dir: Path) -> None:
        """Create registry directories beneath the configured state path."""
        self._state_dir = state_dir
        self._workspaces_dir = state_dir / "workspaces"
        self._runs_dir = state_dir / "runs"
        self._workspaces_dir.mkdir(parents=True, exist_ok=True)
        self._runs_dir.mkdir(parents=True, exist_ok=True)

    def save_workspace(self, workspace: WorkspaceSession) -> None:
        """Persist a workspace session."""
        self._write_json(
            self._workspaces_dir / f"{workspace.id}.json",
            workspace.model_dump(mode="json"),
        )

    def save_run(self, run: RunHandle) -> None:
        """Persist a run handle."""
        self._write_json(self._runs_dir / f"{run.id}.json", run.model_dump(mode="json"))

    def get_workspace(self, workspace_id: str) -> WorkspaceSession:
        """Load a workspace by identifier."""
        return WorkspaceSession.model_validate(
            self._read_json(self._workspaces_dir / f"{workspace_id}.json")
        )

    def list_workspaces(self) -> list[WorkspaceSession]:
        """Return all persisted workspaces sorted by file name."""
        return [
            WorkspaceSession.model_validate(self._read_json(path))
            for path in sorted(self._workspaces_dir.glob("*.json"))
        ]

    def get_run(self, run_id: str) -> RunHandle:
        """Load a run by identifier."""
        return RunHandle.model_validate(
            self._read_json(self._runs_dir / f"{run_id}.json")
        )

    def list_runs(self, workspace_id: str | None = None) -> list[RunHandle]:
        """Return all runs, optionally filtered by workspace id."""
        runs = [
            RunHandle.model_validate(self._read_json(path))
            for path in sorted(self._runs_dir.glob("*.json"))
        ]
        if workspace_id is None:
            return runs
        return [run for run in runs if run.workspace_id == workspace_id]

    def _write_json(self, path: Path, payload: dict[str, object]) -> None:
        """Write one JSON payload to disk."""
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _read_json(self, path: Path) -> dict[str, object]:
        """Read one JSON payload from disk."""
        return json.loads(path.read_text(encoding="utf-8"))
