"""Publication lifecycle observer owned by the publication orchestrator."""

from engineeringagent.orchestrators.loop.models import (
    AgentResult,
    ImplementationContext,
    IterationArtifact,
    RunPublicationResult,
)
from engineeringagent.orchestrators.loop.protocols import (
    AgentRunner,
    ImplementationLifecycleObserver,
)

from .models import (
    CommitMessage,
    CommitMessageContext,
    CommitRequest,
    PublicationState,
    PullRequestContent,
    PullRequestContentContext,
    PullRequestRequest,
)
from .protocols import (
    PublicationForgePort,
    PublicationPromptRenderer,
    PublicationStateStore,
    PublicationVersionControlPort,
    RunMetadataStore,
    WorkspaceLifecyclePort,
)


class PublicationObserver(ImplementationLifecycleObserver):
    """Commit, push, and publish successful workspace runs."""

    def __init__(
        self,
        publication_state_store: PublicationStateStore,
        run_metadata_store: RunMetadataStore,
        workspace_lifecycle: WorkspaceLifecyclePort,
        version_control: PublicationVersionControlPort,
        prompt_renderer: PublicationPromptRenderer | None = None,
        agent_runner: AgentRunner | None = None,
        forge: PublicationForgePort | None = None,
    ) -> None:
        """Store publication dependencies and validate tooling early."""
        self._publication_state_store = publication_state_store
        self._run_metadata_store = run_metadata_store
        self._workspace_lifecycle = workspace_lifecycle
        self._version_control = version_control
        self._prompt_renderer = prompt_renderer
        self._agent_runner = agent_runner
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
        del attempt, agent_result
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
        commit_message = self._build_commit_message(
            CommitMessageContext(
                repo_path=workspace_path,
                task_name=context.task_name,
                task_path=context.task_path,
                task_branch_name=task_branch_name,
                base_branch=base_branch,
                latest_change_summary=context.latest_change_summary,
                staged_diff=self._version_control.get_diff(workspace_path, staged=True),
                recent_commits=self._version_control.get_recent_commits(workspace_path),
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
        self._run_metadata_store.append_run_metadata_item(
            run_id, "commit_shas", commit_result.sha
        )
        self._run_metadata_store.append_run_metadata_item(
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
        publication = PublicationState(
            task_name=context.task_name,
            task_path=context.task_path,
            branch_name=branch_name,
            base_branch=base_branch,
            status="pushed",
        )
        self._publication_state_store.save_publication(publication)
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
            self._run_metadata_store.update_run_metadata(run_id, metadata_updates)
            self._cleanup_workspace(context)
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
            content = self._build_pull_request_content(
                PullRequestContentContext(
                    repo_path=workspace_path,
                    task_name=context.task_name,
                    task_path=context.task_path,
                    task_branch_name=branch_name,
                    base_branch=base_branch,
                    latest_change_summary=context.latest_change_summary,
                    diff=self._version_control.get_diff(workspace_path),
                    recent_commits=self._version_control.get_recent_commits(
                        workspace_path
                    ),
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

        self._publication_state_store.save_publication(
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
        self._run_metadata_store.update_run_metadata(run_id, metadata_updates)
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
        self._run_metadata_store.update_run_metadata(
            run_id,
            {
                "publication_status": "failed",
                "failure_feedback": feedback,
            },
        )

    def _cleanup_workspace(self, context: ImplementationContext) -> None:
        """Destroy the workspace after successful publication when possible."""
        workspace_id = context.workspace_id
        if workspace_id is None:
            return
        try:
            self._workspace_lifecycle.destroy_workspace(workspace_id)
        except Exception:
            self._run_metadata_store.update_run_metadata(
                _require_context_value(context.run_id, "run_id"),
                {"cleanup_warning": "Workspace cleanup failed after publication"},
            )

    def _build_commit_message(self, context: CommitMessageContext) -> CommitMessage:
        """Generate a commit message using the configured strategy."""
        if self._prompt_renderer is None or self._agent_runner is None:
            return _build_deterministic_commit_message(context)
        try:
            prompt = self._prompt_renderer.render_commit_prompt(context)
            result = self._agent_runner.run_agent(prompt, output_format=CommitMessage)
            return CommitMessage.model_validate(result)
        except Exception:
            return _build_deterministic_commit_message(context)

    def _build_pull_request_content(
        self, context: PullRequestContentContext
    ) -> PullRequestContent:
        """Generate pull-request content using the configured strategy."""
        if self._prompt_renderer is None or self._agent_runner is None:
            return _build_deterministic_pull_request_content(context)
        try:
            prompt = self._prompt_renderer.render_pull_request_prompt(context)
            result = self._agent_runner.run_agent(
                prompt, output_format=PullRequestContent
            )
            return PullRequestContent.model_validate(result)
        except Exception:
            return _build_deterministic_pull_request_content(context)


def _require_context_value(value: str | None, name: str) -> str:
    """Require that a context field is populated."""
    if value is None or value == "":
        raise ValueError(f"Implementation context is missing {name}")
    return value


def _build_deterministic_commit_message(context: CommitMessageContext) -> CommitMessage:
    """Return a stable commit message when agent-backed generation is unavailable."""
    return CommitMessage(subject=f"chore: implement {context.task_name}"[:72], body="")


def _build_deterministic_pull_request_content(
    context: PullRequestContentContext,
) -> PullRequestContent:
    """Return stable pull-request content when agent-backed generation fails."""
    summary = f"Complete task {context.task_name}."
    body = "## Summary\n- " + summary + "\n\n## Testing\n- Not run"
    return PullRequestContent(
        title=f"Complete {context.task_name}",
        summary=[summary],
        body=body,
    )
