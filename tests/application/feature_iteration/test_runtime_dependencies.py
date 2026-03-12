from __future__ import annotations

from pathlib import Path

from engineeringagent.application.feature_iteration import (
    build_feature_iteration_pipeline_dependencies,
)
from engineeringagent.ports import CommitRequest, CommitResult

from tests.application.test_feature_iteration_service import (
    _FakeCompletionPhaseDependencies,
    _FakeVersionControlGateway,
    _build_runtime_dependencies,
)


def test_build_feature_iteration_pipeline_dependencies_wires_completion_commit() -> None:
    """Pipeline dependency assembly should stay with runtime helper wiring."""
    observed: dict[str, object] = {}
    gateway = _FakeVersionControlGateway(
        observed,
        CommitResult(
            stdout="ok\n",
            stderr="",
            commit_created=True,
            commit_sha="abc1234",
            failure_stage=None,
        ),
    )

    pipeline_dependencies = build_feature_iteration_pipeline_dependencies(
        _build_runtime_dependencies(observed),
        gateway,
    )

    assert pipeline_dependencies.describe_action(Path("/tmp/project"), "implement", False)
    completion_dependencies = pipeline_dependencies.completion_phase_dependencies
    assert isinstance(completion_dependencies, _FakeCompletionPhaseDependencies)
    recorded_completion_dependencies = observed["completion_dependencies"]
    assert isinstance(recorded_completion_dependencies, dict)
    assert recorded_completion_dependencies["commit_feature_completion"](
        Path("/tmp/project"),
        {"expected_commit_subject": "feat: complete FEAT-001"},
    ) == (True, None, "ok\n")
    assert observed["commit_requests"] == [
        CommitRequest(
            workspace_path=Path("/tmp/project"),
            message="feat: complete FEAT-001",
            stage_all=True,
            allow_empty=False,
        )
    ]
