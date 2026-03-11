from __future__ import annotations

from pathlib import Path

import pytest

from engineeringagent import loop as loop_module
from engineeringagent.ports import CommitResult, WorktreeStatus


class StubVersionControlGateway:
    def __init__(self) -> None:
        self.head_calls: list[Path] = []
        self.status_calls: list[Path] = []
        self.commit_request: object | None = None
        self.head_result: str | None = None
        self.commit_result: object | None = None
        self.status_result = WorktreeStatus(dirty=False, stdout="", stderr="")

    def head_commit(self, project_root: Path) -> str | None:
        self.head_calls.append(project_root)
        return self.head_result

    def worktree_status(self, project_root: Path) -> WorktreeStatus:
        self.status_calls.append(project_root)
        return self.status_result

    def commit(self, request: object) -> object:
        self.commit_request = request
        assert self.commit_result is not None
        return self.commit_result


def _patch_gateway(
    monkeypatch: pytest.MonkeyPatch,
    gateway: StubVersionControlGateway,
) -> None:
    monkeypatch.setattr(loop_module, "_build_version_control_gateway", lambda _root: gateway)


def test_git_head_short_uses_version_control_gateway(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve the current short head commit through the gateway seam."""
    gateway = StubVersionControlGateway()
    gateway.head_result = "abc123"
    _patch_gateway(monkeypatch, gateway)

    result = loop_module.git_head_short(tmp_path)

    assert result == "abc123"
    assert gateway.head_calls == [tmp_path]


def test_commit_feature_completion_uses_version_control_gateway(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Route feature completion commits through the gateway seam."""
    gateway = StubVersionControlGateway()
    gateway.commit_result = CommitResult(
        commit_created=False,
        commit_sha=None,
        stdout="",
        stderr="commit failed",
        failure_stage="git_commit",
    )
    _patch_gateway(monkeypatch, gateway)

    ok, failed_gate, output = loop_module._commit_feature_completion(
        tmp_path,
        {"id": "FEAT-123", "title": "Example"},
    )

    request = gateway.commit_request
    assert isinstance(request, loop_module.CommitRequest)
    assert request.project_root == tmp_path
    assert request.stage_all is True
    assert request.allow_empty is False
    assert ok is False
    assert failed_gate == "git_commit"
    assert output == "commit failed"


def test_enforce_worktree_precondition_uses_version_control_gateway(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve worktree status through the version-control gateway seam."""
    gateway = StubVersionControlGateway()
    _patch_gateway(monkeypatch, gateway)

    result = loop_module._enforce_worktree_precondition(tmp_path, allow_dirty=False)

    assert result is None
    assert gateway.status_calls == [tmp_path]
