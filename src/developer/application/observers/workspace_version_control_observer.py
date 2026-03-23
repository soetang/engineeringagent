"""Workspace lifecycle observer for version control and publication."""

from developer.forge.models import PullRequestRequest
from developer.forge.protocol import ForgeProtocol
from developer.orchestrators.loop.models import (
    AgentResult,
    ImplementationContext,
    IterationArtifact,
    RunPublicationResult,
)
from developer.tasks.models import TaskPublicationState
from developer.version_control.content_models import (
    CommitPromptContext,
    PullRequestPromptContext,
)
from developer.version_control.content_service import VersionControlContentService
from developer.version_control.models import CommitRequest
from developer.version_control.protocol import VersionControlProtocol
from developer.workspaces.protocols import WorkspaceProvider, WorkspaceRunRegistry


class WorkspaceVersionControlObserver:
    """Commit, push, and publish successful workspace runs."""

    def __init__(
        self,
        registry: WorkspaceRunRegistry,
        workspace_provider: WorkspaceProvider,
        version_control: VersionControlProtocol,
        content_service: VersionControlContentService,
        forge: ForgeProtocol | None = None,
    ) -> None:
        """Store dependencies and validate required tooling early."""
        self._registry = registry
        self._workspace_provider = workspace_provider
        self._version_control = version_control
        self._content_service = content_service
        self._forge = forge

    def validate(self, context: ImplementationContext) -> None:
        """Run preflight validation for repository and publication tooling."""
        workspace_path = _require_context_value(
            context.workspace_path, "workspace_path"
        )
        self._version_control.validate_repository(workspace_path)
        if self._forge is not None:
            self._forge.validate_available(workspace_path)

    def on_iteration_passed(
        self,
        attempt: int,
        context: ImplementationContext,
        agent_result: AgentResult,
    ) -> IterationArtifact | None:
        """Commit a passing iteration when the workspace tree changed."""
        workspace_path = _require_context_value(
            context.workspace_path, "workspace_path"
        )
        task_branch_name = _require_context_value(
            context.task_branch_name, "task_branch_name"
        )
        base_branch = _require_context_value(context.base_branch, "base_branch")
        run_id = _require_context_value(context.run_id, "run_id")
        if not self._version_control.has_changes(workspace_path):
            return None
        self._version_control.stage_all(workspace_path)
        identity = self._version_control.resolve_identity(workspace_path)
        commit_message = self._content_service.build_commit_message(
            CommitPromptContext(
                task_name=context.task_name,
                task_path=context.task_path,
                task_branch_name=task_branch_name,
                base_branch=base_branch,
            )
        )
        commit_result = self._version_control.create_commit(
            workspace_path,
            CommitRequest(
                subject=commit_message.subject,
                body=commit_message.body,
                author_name=identity.name,
                author_email=identity.email,
            ),
        )
        self._append_run_metadata_item(run_id, "commit_shas", commit_result.sha)
        self._append_run_metadata_item(
            run_id,
            "commit_message_subjects",
            commit_message.subject,
        )
        return IterationArtifact(
            commit_sha=commit_result.sha,
            commit_subject=commit_message.subject,
        )

    def on_run_succeeded(
        self,
        context: ImplementationContext,
    ) -> RunPublicationResult | None:
        """Push the publication branch and optionally create or reuse a PR."""
        workspace_path = _require_context_value(
            context.workspace_path, "workspace_path"
        )
        branch_name = _require_context_value(
            context.task_branch_name, "task_branch_name"
        )
        base_branch = _require_context_value(context.base_branch, "base_branch")
        run_id = _require_context_value(context.run_id, "run_id")
        remote_name = context.remote_name or "origin"
        push_result = self._version_control.push_branch(
            workspace_path,
            branch_name=branch_name,
            remote_name=remote_name,
            source_ref="HEAD",
        )
        publication = TaskPublicationState(
            task_name=context.task_name,
            task_path=context.task_path,
            branch_name=branch_name,
            base_branch=base_branch,
            status="pushed",
        )
        self._registry.save_task_publication(publication)
        metadata_updates: dict[str, object] = {
            "pushed_branch": push_result.branch_name,
            "publication_status": "pushed",
            "task_name": context.task_name,
            "task_path": context.task_path,
            "task_branch_name": branch_name,
            "version_control_enabled": True,
            "forge_enabled": self._forge is not None,
        }

        if self._forge is None:
            self._update_run_metadata(run_id, **metadata_updates)
            return RunPublicationResult(
                branch_name=branch_name,
                message=f"branch={branch_name}",
            )

        existing_pr = self._forge.find_open_pull_request(
            workspace_path,
            branch_name=branch_name,
            base_branch=base_branch,
        )
        if existing_pr is None:
            content = self._content_service.build_pull_request_content(
                PullRequestPromptContext(
                    task_name=context.task_name,
                    task_path=context.task_path,
                    task_branch_name=branch_name,
                    base_branch=base_branch,
                )
            )
            pr = self._forge.create_pull_request(
                workspace_path,
                PullRequestRequest(
                    title=content.title,
                    body=content.body,
                    head_branch=branch_name,
                    base_branch=base_branch,
                ),
            )
            publication_status = "created"
            message = f"Pull request: {pr.url}"
            metadata_updates["pull_request_title"] = content.title
        else:
            pr = existing_pr
            publication_status = "updated"
            message = f"Pull request updated: {pr.url}"

        self._registry.save_task_publication(
            publication.model_copy(
                update={
                    "pr_url": pr.url,
                    "pr_number": pr.number,
                    "status": publication_status,
                }
            )
        )
        metadata_updates.update(
            {
                "publication_status": publication_status,
                "pr_url": pr.url,
                "pull_request_number": pr.number,
            }
        )
        self._update_run_metadata(
            run_id,
            **metadata_updates,
        )
        self._cleanup_workspace(context)
        return RunPublicationResult(
            branch_name=branch_name,
            pr_url=pr.url,
            message=message,
        )

    def on_run_failed(
        self,
        context: ImplementationContext,
        feedback: str | None,
    ) -> None:
        """Record a failed publication state on the run handle."""
        run_id = context.run_id
        if run_id is None:
            return
        self._update_run_metadata(
            run_id, publication_status="failed", failure_feedback=feedback
        )

    def _cleanup_workspace(self, context: ImplementationContext) -> None:
        """Destroy the workspace after successful publication when possible."""
        workspace_id = context.workspace_id
        if workspace_id is None:
            return
        try:
            self._workspace_provider.destroy(workspace_id)
        except Exception:
            self._update_run_metadata(
                _require_context_value(context.run_id, "run_id"),
                cleanup_warning="Workspace cleanup failed after publication",
            )

    def _update_run_metadata(self, run_id: str, **updates: object) -> None:
        """Persist metadata updates onto the run handle."""
        run = self._registry.get_run(run_id)
        metadata = dict(run.metadata)
        for key, value in updates.items():
            metadata[key] = value
        self._registry.save_run(run.model_copy(update={"metadata": metadata}))

    def _append_run_metadata_item(self, run_id: str, key: str, value: object) -> None:
        """Append one value to a list stored on run metadata."""
        run = self._registry.get_run(run_id)
        metadata = dict(run.metadata)
        existing = metadata.get(key, [])
        metadata[key] = [*existing, value] if isinstance(existing, list) else [value]
        self._registry.save_run(run.model_copy(update={"metadata": metadata}))


def _require_context_value(value: str | None, name: str) -> str:
    """Require that a context field is populated."""
    if value is None or value == "":
        raise ValueError(f"Implementation context is missing {name}")
    return value
