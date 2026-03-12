from __future__ import annotations

# pyright: reportAbstractUsage=false, reportArgumentType=false

from pathlib import Path

import pytest

from engineeringagent.domain.audit import ProgressEvent
from engineeringagent.domain.quality import HarnessCheckPhase
from engineeringagent.domain.specification import FeatureArtifacts, FeatureSpecification
from engineeringagent.ports.agent_runner import AgentRunRequest, AgentRunner
from engineeringagent.ports.checks_catalog_repository import ChecksCatalogRepository
from engineeringagent.ports.checks_runner import ChecksRunRequest, ChecksRunner
from engineeringagent.ports.feature_specification_repository import (
    FeatureSpecificationRepository,
)
from engineeringagent.ports.feature_workspace_manager import (
    FeatureWorkspaceFailure,
    FeatureWorkspaceManager,
    WorkspaceResetRequest,
)
from engineeringagent.ports.progress_journal import ProgressJournal
from engineeringagent.ports.prompt_definition_repository import PromptDefinitionRepository
from engineeringagent.ports.repository_validator import (
    RepositoryValidationRequest,
    RepositoryValidator,
)
from engineeringagent.ports.run_loop_executor import (
    RunLoopExecutionRequest,
    RunLoopExecutor,
)
from engineeringagent.ports.shell_runner import ShellRunner
from engineeringagent.ports.version_control import CommitRequest, VersionControlGateway


def test_port_protocol_methods_raise_not_implemented() -> None:
    """Protocol stub methods should fail loudly until adapters implement them."""
    project_root = Path("/tmp/project")

    with pytest.raises(NotImplementedError):
        AgentRunner.run(
            object(),
            AgentRunRequest(project_root=project_root, prompt="implement"),
        )
    with pytest.raises(NotImplementedError):
        ChecksCatalogRepository.load(object(), project_root)
    with pytest.raises(NotImplementedError):
        ChecksRunner.run(
            object(),
            ChecksRunRequest(
                project_root=project_root,
                selected_checks=None,
                check_id=None,
                feature_path=None,
                phase=HarnessCheckPhase.ITERATION_END,
                base=None,
                head=None,
                verbose_output=False,
                dry_run=False,
            ),
        )
    with pytest.raises(NotImplementedError):
        ChecksRunner.reviewers_group_selected(object(), None)
    with pytest.raises(NotImplementedError):
        FeatureSpecificationRepository.list_selection_candidates(object(), project_root)
    with pytest.raises(NotImplementedError):
        FeatureSpecificationRepository.load(object(), project_root, "FEAT-001")
    with pytest.raises(NotImplementedError):
        FeatureSpecificationRepository.save(
            object(),
            project_root,
            "FEAT-001",
            FeatureSpecification(
                feature_id="FEAT-001",
                title="Title",
                feature_type="feature",
                expected_commit_subject="feat: complete FEAT-001",
                planning_tier="direct",
                artifacts=FeatureArtifacts(),
                updated_at="2026-03-11T00:00:00Z",
                objective="Objective",
                status="backlog",
                priority="high",
                acceptance=("done",),
            ),
        )
    with pytest.raises(NotImplementedError):
        FeatureSpecificationRepository.archive(object(), project_root, "FEAT-001")
    with pytest.raises(NotImplementedError):
        FeatureWorkspaceManager.reset_to_last_accepted(
            object(),
            WorkspaceResetRequest(workspace_path=project_root, target_ref="HEAD"),
        )
    with pytest.raises(NotImplementedError):
        ProgressJournal.append(
            object(),
            project_root=project_root,
            event=ProgressEvent(
                feature_id="FEAT-001",
                timestamp="2026-03-11T00:00:00Z",
                event_kind="iteration_started",
            ),
        )
    with pytest.raises(NotImplementedError):
        ProgressJournal.append_feature_log(
            object(),
            project_root=project_root,
            feature_id="FEAT-001",
            lines=("line",),
        )
    with pytest.raises(NotImplementedError):
        ProgressJournal.write_iteration_report(
            object(),
            project_root=project_root,
            feature_id="FEAT-001",
            payload={"result": "passed"},
        )
    with pytest.raises(NotImplementedError):
        ProgressJournal.write_handoff(
            object(),
            project_root=project_root,
            feature_id="FEAT-001",
            lines=("handoff",),
        )
    with pytest.raises(NotImplementedError):
        ProgressJournal.latest_handoff_path(
            object(),
            project_root=project_root,
            feature_id="FEAT-001",
        )
    with pytest.raises(NotImplementedError):
        PromptDefinitionRepository.get(object(), "implementation_default")
    with pytest.raises(NotImplementedError):
        PromptDefinitionRepository.list_ids(object())
    with pytest.raises(NotImplementedError):
        RepositoryValidator.validate(
            object(),
            RepositoryValidationRequest(project_root=project_root),
        )
    with pytest.raises(NotImplementedError):
        RunLoopExecutor.run(
            object(),
            RunLoopExecutionRequest(
                project_root=project_root,
                feature_paths=(),
                run_all=True,
                dry_run=False,
                max_iterations=1,
                allow_dirty=False,
                verbose_output=False,
            ),
        )
    with pytest.raises(NotImplementedError):
        ShellRunner.run(object(), project_root, "uv run pytest")
    with pytest.raises(NotImplementedError):
        VersionControlGateway.diff_against_base(object(), project_root)
    with pytest.raises(NotImplementedError):
        VersionControlGateway.head_commit(object(), project_root)
    with pytest.raises(NotImplementedError):
        VersionControlGateway.worktree_status(object(), project_root)
    with pytest.raises(NotImplementedError):
        VersionControlGateway.commit(
            object(),
            CommitRequest(
                workspace_path=project_root,
                message="feat: complete FEAT-001",
            ),
        )


def test_feature_workspace_failure_uses_stable_port_name() -> None:
    """Workspace failures should keep the canonical port name."""
    error = FeatureWorkspaceFailure("boom")

    assert error.port_name == "FeatureWorkspaceManager"
    assert error.message == "boom"
