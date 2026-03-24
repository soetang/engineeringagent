"""Tests for workspace domain models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from engineeringagent.workspaces.models import (
    ExecutionTarget,
    RunHandle,
    RunStatus,
    WorkspaceSession,
    WorkspaceStatus,
)


def test_workspace_session_requires_known_execution_target_kind() -> None:
    """Workspace session validation should reject unknown execution target kinds."""
    with pytest.raises(ValidationError):
        WorkspaceSession(
            id="workspace-1",
            provider="git_worktree",
            status=WorkspaceStatus.READY,
            created_at=datetime.now(UTC),
            execution_target={"kind": "remote", "location": "/tmp/workspace"},
        )


def test_run_handle_allows_optional_status_fields() -> None:
    """Run handles should validate with the minimal pending payload."""
    run = RunHandle(
        id="run-1",
        workspace_id="workspace-1",
        status=RunStatus.PENDING,
        agent_kind="implementation",
    )

    assert run.started_at is None
    assert run.finished_at is None
    assert run.result_summary is None


def test_execution_target_forbids_extra_fields() -> None:
    """Execution targets should reject undeclared fields."""
    with pytest.raises(ValidationError):
        ExecutionTarget(
            kind="local_path",
            location="/tmp/workspace",
            unexpected=True,
        )
