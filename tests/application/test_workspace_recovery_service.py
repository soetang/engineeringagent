from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from engineeringagent.application.workspace_recovery_service import (
    RecoverWorkspaceRequest,
    RecoverWorkspaceResult,
    WorkspaceRecoveryService,
)
from engineeringagent.domain.audit import ProgressEvent
from engineeringagent.ports import (
    WorkspaceResetRequest,
    WorkspaceResetResult,
)


class _FakeProgressJournal:
    def __init__(self, handoff_path: Path | None) -> None:
        self._handoff_path = handoff_path
        self.calls: list[tuple[Path, str]] = []

    def latest_handoff_path(
        self, *, project_root: Path, feature_id: str
    ) -> Path | None:
        self.calls.append((project_root, feature_id))
        return self._handoff_path

    def append(self, *, project_root: Path, event: ProgressEvent) -> None:
        raise AssertionError((project_root, event))

    def append_feature_log(
        self,
        *,
        project_root: Path,
        feature_id: str,
        lines: Sequence[str],
    ) -> None:
        raise AssertionError((project_root, feature_id, lines))

    def write_iteration_report(
        self,
        *,
        project_root: Path,
        feature_id: str,
        payload: dict[str, Any],
    ) -> None:
        raise AssertionError((project_root, feature_id, payload))

    def write_handoff(
        self,
        *,
        project_root: Path,
        feature_id: str,
        lines: Sequence[str],
    ) -> None:
        raise AssertionError((project_root, feature_id, lines))


class _FakeWorkspaceManager:
    def __init__(self, reset_result: WorkspaceResetResult) -> None:
        self._reset_result = reset_result
        self.requests: list[WorkspaceResetRequest] = []

    def reset_to_last_accepted(
        self,
        request: WorkspaceResetRequest,
    ) -> WorkspaceResetResult:
        self.requests.append(request)
        return self._reset_result


def test_workspace_recovery_requires_handoff_by_default() -> None:
    """Recovery blocks when no persisted handoff exists for the feature."""
    service = WorkspaceRecoveryService(
        _FakeWorkspaceManager(
            WorkspaceResetResult(
                reset_applied=True,
                head_commit="abc123",
                stdout="",
                stderr="",
            )
        ),
        _FakeProgressJournal(None),
    )

    result = service.run(
        RecoverWorkspaceRequest(
            project_root=Path("/tmp/project"),
            feature_id="FEAT-100",
            last_accepted_commit="abc123",
        )
    )

    assert result == RecoverWorkspaceResult(
        ok=False,
        head_commit=None,
        handoff_path=None,
        message="workspace recovery requires a persisted handoff artifact for FEAT-100",
    )


def test_workspace_recovery_resets_to_last_accepted_commit() -> None:
    """Recovery should pass the accepted commit through to the reset port."""
    handoff_path = Path(".engineeringagent/progress/FEAT-100/handoff.md")
    workspace_manager = _FakeWorkspaceManager(
        WorkspaceResetResult(
            reset_applied=True,
            head_commit="abc123",
            stdout="reset ok\n",
            stderr="",
        )
    )
    journal = _FakeProgressJournal(handoff_path)

    result = WorkspaceRecoveryService(workspace_manager, journal).run(
        RecoverWorkspaceRequest(
            project_root=Path("/tmp/project"),
            feature_id="FEAT-100",
            last_accepted_commit="abc123",
        )
    )

    assert journal.calls == [(Path("/tmp/project"), "FEAT-100")]
    assert workspace_manager.requests == [
        WorkspaceResetRequest(
            workspace_path=Path("/tmp/project"),
            target_ref="abc123",
            clean_untracked=True,
        )
    ]
    assert result == RecoverWorkspaceResult(
        ok=True,
        head_commit="abc123",
        handoff_path=handoff_path,
        message="workspace reset to last accepted commit abc123",
    )


def test_workspace_recovery_surfaces_reset_failure() -> None:
    """Gateway failures should become stable application feedback."""
    service = WorkspaceRecoveryService(
        _FakeWorkspaceManager(
            WorkspaceResetResult(
                reset_applied=False,
                head_commit=None,
                stdout="",
                stderr="fatal: bad revision",
                failure_stage="git_reset",
            )
        ),
        _FakeProgressJournal(
            Path(".engineeringagent/progress/FEAT-100/handoff.md")
        ),
    )

    result = service.run(
        RecoverWorkspaceRequest(
            project_root=Path("/tmp/project"),
            feature_id="FEAT-100",
            last_accepted_commit="abc123",
            require_handoff=False,
        )
    )

    assert result == RecoverWorkspaceResult(
        ok=False,
        head_commit=None,
        handoff_path=Path(".engineeringagent/progress/FEAT-100/handoff.md"),
        message="workspace recovery failed during git_reset: fatal: bad revision",
    )
