"""Application service for deterministic blocked-work recovery."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from engineeringagent.ports import (
    FeatureWorkspaceManager,
    ProgressJournal,
    WorkspaceResetRequest,
)


class RecoverWorkspaceRequest(BaseModel):
    """Typed input for one workspace recovery request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    feature_id: str
    last_accepted_commit: str
    require_handoff: bool = True


class RecoverWorkspaceResult(BaseModel):
    """Stable application result for one workspace recovery request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ok: bool
    head_commit: str | None
    handoff_path: Path | None
    message: str


class WorkspaceRecoveryService:
    """Own deterministic reset back to the last accepted iteration commit."""

    def __init__(
        self,
        workspace_manager: FeatureWorkspaceManager,
        progress_journal: ProgressJournal,
    ) -> None:
        self._workspace_manager = workspace_manager
        self._progress_journal = progress_journal

    def run(self, request: RecoverWorkspaceRequest) -> RecoverWorkspaceResult:
        """Reset the workspace when recovery preconditions are satisfied."""
        handoff_path = self._progress_journal.latest_handoff_path(
            project_root=request.project_root,
            feature_id=request.feature_id,
        )
        if request.require_handoff and handoff_path is None:
            return RecoverWorkspaceResult(
                ok=False,
                head_commit=None,
                handoff_path=None,
                message=(
                    "workspace recovery requires a persisted handoff artifact for "
                    f"{request.feature_id}"
                ),
            )

        reset_result = self._workspace_manager.reset_to_last_accepted(
            WorkspaceResetRequest(
                workspace_path=request.project_root,
                target_ref=request.last_accepted_commit,
            )
        )
        if not reset_result.reset_applied:
            failure_stage = reset_result.failure_stage or "unknown"
            detail = reset_result.stderr.strip() or reset_result.stdout.strip()
            message = f"workspace recovery failed during {failure_stage}"
            if detail:
                message = f"{message}: {detail}"
            return RecoverWorkspaceResult(
                ok=False,
                head_commit=None,
                handoff_path=handoff_path,
                message=message,
            )

        return RecoverWorkspaceResult(
            ok=True,
            head_commit=reset_result.head_commit,
            handoff_path=handoff_path,
            message=(
                "workspace reset to last accepted commit "
                f"{request.last_accepted_commit}"
            ),
        )
