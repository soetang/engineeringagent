# Version Control In Implement Flow

## Goal

Add version control to the workspace-backed `implementation run` flow so that:

- each iteration that passes checks is committed;
- the successful branch is pushed on completion; and
- a pull request is created when publication is enabled.

Initial scope covers:

- one version control adapter family for repository operations;
- one forge adapter family for platform operations;
- `git` as the only version control adapter; and
- `github` as the only forge adapter.

## Recommended Scope Boundaries

Build this only for workspace-backed runs in v1.

Reasons:

- the current implementation flow already isolates changes in a git worktree;
- committing inside the caller's live checkout is riskier and harder to reason about;
- workspaces already carry branch and repository metadata; and
- pull request publication only makes sense when the run owns the branch lifecycle.

Direct-mode `implementation run` should continue to work unchanged and should not create commits or pull requests in v1.

## Current State

- `run_implementation()` switches between direct execution and workspace execution in `src/developer/application/services/implementation_run_service.py`.
- workspace mode creates a branch-backed worktree through `GitWorktreeWorkspaceProvider` in `src/developer/workspaces/adapters/git_worktree_provider.py`.
- `ImplementationAgent` in `src/developer/orchestrators/implementation_agent.py` owns the iteration loop and has no lifecycle hooks for post-iteration side effects.
- successful workspace runs currently return only run status and a short message.
- git support stops at branch discovery and `git worktree add/remove`.
- there is no commit, push, remote inspection, or PR creation service today.
- `ImplementationJudge` is still a stub, so "completion" currently means "first iteration that clears the gates."

## Design Overview

Introduce two new integration layers.

Prompt generation for commit and PR text is not a third adapter family; it is an agent-backed service layer built on the existing agent infrastructure.

### Code Sketch

High-level shape:

```python
class ImplementationAgent:
    def run(self, context: ImplementationContext | None = None) -> OrchestratorOutcome:
        ...
        agent_result = self._agent_runner.run_agent(prompt, output_format=AgentResult)
        ...
        iteration_artifact = observer.on_iteration_passed(attempt, context, agent_result)
        ...
        publication = observer.on_run_succeeded(attempt, context)
```

```python
class WorkspaceVersionControlObserver(ImplementationLifecycleObserver):
    def on_iteration_passed(...):
        commit_message = self._content_service.build_commit_message(...)
        return self._git.commit_iteration(...)

    def on_run_succeeded(...):
        pushed = self._git.push_branch(...)
        pr = self._forge.find_open_pull_request(...) or self._forge.create_pull_request(...)
        self._workspace_provider.destroy(workspace_id)
        return RunPublicationResult(pr_url=pr.url, branch_name=pushed.branch_name)
```

```python
class VersionControlContentService:
    def build_commit_message(self, context: CommitPromptContext) -> CommitMessageOutput:
        prompt = self._prompt_builder.build_commit_prompt(context)
        return self._agent.run_agent(prompt, output_format=CommitMessageOutput)

    def build_pull_request_content(
        self, context: PullRequestPromptContext
    ) -> PullRequestContentOutput:
        prompt = self._prompt_builder.build_pull_request_prompt(context)
        return self._agent.run_agent(prompt, output_format=PullRequestContentOutput)
```

### 1. Version Control Layer

Purpose: repository-local operations such as status, staging, commit creation, branch push, and SHA inspection.

Recommended package shape:

- `src/developer/version_control/protocol.py`
- `src/developer/version_control/models.py`
- `src/developer/version_control/settings.py`
- `src/developer/version_control/select_service.py`
- `src/developer/version_control/adapters/git_adapter.py`

Recommended protocol surface:

- `get_status(repo_path) -> WorkingTreeStatus`
- `has_changes(repo_path) -> bool`
- `stage_all(repo_path) -> None`
- `create_commit(repo_path, request: CommitRequest) -> CommitResult`
- `get_head_sha(repo_path) -> str`
- `push_branch(repo_path, branch_name, remote_name) -> PushResult`

Notes:

- keep commit author identity out of repository config;
- pass `GIT_AUTHOR_*` and `GIT_COMMITTER_*` environment variables per command;
- if no explicit override is configured, resolve author name/email from the current git user identity; and
- `push_branch()` must be non-force by default and should fail on non-fast-forward push attempts.

### 2. Forge Layer

Purpose: hosting-platform operations such as pull request creation.

Recommended package shape:

- `src/developer/forge/protocol.py`
- `src/developer/forge/models.py`
- `src/developer/forge/settings.py`
- `src/developer/forge/select_service.py`
- `src/developer/forge/adapters/github_adapter.py`

Recommended protocol surface:

- `find_open_pull_request(repo_path, branch_name, base_branch) -> PullRequestResult | None`
- `create_pull_request(repo_path, request: PullRequestRequest) -> PullRequestResult`

Notes:

- use the `gh` CLI in v1 instead of talking to the GitHub API directly;
- require that `gh` is installed and authenticated when GitHub publication is enabled; and
- derive owner/repo from the local checkout or `gh repo view` instead of storing it eagerly unless a later use case requires overrides.

### Prompt-Driven Content Generation

Use the existing agent layer to generate commit messages and PR content via structured output.

Why this fits the current codebase:

- `AgentProtocol.run_agent(..., output_format=...)` already supports typed Pydantic output;
- both `CodexAdapter` and `VibeAdapter` already know how to enforce structured JSON responses; and
- this avoids hard-coding low-quality templates for commit and PR text.

Recommended package shape:

- `src/developer/version_control/content_models.py`
- `src/developer/version_control/content_service.py`

Recommended structured output models:

- `CommitMessageOutput` with `subject` and `body`
- `PullRequestContentOutput` with `title`, `summary`, and `body`

Recommended service behavior:

- gather repository context from the git adapter: branch name, base branch, staged or working diff, changed files, and recent commits;
- treat git diff data as supporting evidence, not the primary narrative source;
- prefer a high-level change summary from the implementation run when available;
- render a dedicated prompt for commit generation after a passing iteration with changes;
- render a dedicated prompt for PR generation after successful completion and before PR creation;
- call the selected agent with `output_format=<pydantic model>`;
- validate the returned fields and normalize them into git and GitHub payloads; and
- fall back to deterministic default text only if generation is disabled or the structured call fails and config allows fallback.

Recommended prompt files:

- `harness/prompts/commit_message_prompt.md`
- `harness/prompts/pull_request_prompt.md`

These paths should be defaults only. The actual prompt locations should come from a shared TOML-backed `[prompts]` section so implementation, commit, and pull request prompts are configured in one place.

Recommended prompt inputs:

- `task_id`
- `iteration`
- `branch_name`
- `base_branch`
- `change_summary`
- `diff_evidence`
- `recent_commits`
- `check_feedback` when relevant

`change_summary` should be the primary conceptual description of what the iteration or run accomplished.

`diff_evidence` should be secondary supporting context derived from git, used to ground the model and prevent hallucination rather than to drive file-by-file narration.

This keeps content generation separate from git and GitHub transport concerns while still using the same agent infrastructure already present in the repo.

### Draft Prompt: Commit Message

Initial draft for `commit_prompt_path`:

```md
You are generating a git commit message for an automated implementation workflow.

Write a concise, high-signal commit message based only on the repository context provided.

Rules:
- Return structured output only.
- The `subject` must be a single line.
- Keep the `subject` under 72 characters.
- Use imperative mood.
- Focus on intent, user value, or the reason for the change.
- Do not list files, implementation steps, or low-level technical edits.
- Do not restate the diff line-by-line.
- Treat diff evidence as verification context, not as the main thing to summarize.
- Do not mention tests unless they are the primary purpose of the change.
- Do not invent motivation that is not supported by the diff.
- The `body` should usually be empty.
- If a `body` is needed, keep it to 1-2 short sentences about why this change exists.

Context:
- Task ID: {{ task_id }}
- Iteration: {{ iteration }}
- Branch: {{ branch_name }}
- Base branch: {{ base_branch }}

Change summary:
{{ change_summary }}

Diff evidence:
{{ diff_evidence }}

Recent commits:
{{ recent_commits }}

Check feedback:
{{ check_feedback }}

Return JSON matching the provided schema.
```

### Draft Prompt: Pull Request

Initial draft for `pull_request_prompt_path`:

```md
You are generating pull request content for an automated implementation workflow.

Write a clear PR title and body based only on the repository context provided.

Rules:
- Return structured output only.
- The `title` must be specific and concise.
- The `summary` must be 1-3 short bullets focused on intent and outcome.
- The `body` should be valid GitHub markdown.
- Use these sections in the body: `## Summary` and `## Testing`.
- Under `## Summary`, explain why this change exists and what it achieves.
- Under `## Testing`, list only checks that actually ran or passed if that information is available.
- Focus on intent, behavior, and outcome.
- Do not enumerate files or low-level implementation details.
- Do not turn the PR body into a diff summary.
- Treat diff evidence as support for accuracy, not as the main narrative.
- Do not invent motivation, requirements, or testing that is not present in the context.
- Avoid filler text and generic phrases like "updates code".

Context:
- Task ID: {{ task_id }}
- Branch: {{ branch_name }}
- Base branch: {{ base_branch }}

Change summary:
{{ change_summary }}

Diff evidence:
{{ diff_evidence }}

Recent commits:
{{ recent_commits }}

Run summary:
{{ run_summary }}

Return JSON matching the provided schema.
```

Recommended structured output shapes for these prompts:

- `CommitMessageOutput(subject: str, body: str)`
- `PullRequestContentOutput(title: str, summary: list[str], body: str)`

## Change Summary Source

To avoid making git diff text the dominant input, preserve a higher-level summary from the implementation flow and pass that into content generation.

Recommended change:

- keep the returned `AgentResult.summary` from each iteration instead of discarding it in `ImplementationAgent`
- include the latest passing iteration summary in `ImplementationContext` or the iteration artifact returned to the observer
- build the final PR `change_summary` from the successful iteration summaries, final run message, and any completion/gate context

This gives commit and PR generation a conceptual "what/why" source, while git diff data remains grounding evidence only.

## Orchestrator Integration

The main architecture change should be a loop lifecycle hook instead of wiring git directly into `ImplementationAgent`.

Recommended new protocol:

- `ImplementationLifecycleObserver` in `src/developer/orchestrators/protocols.py`

Recommended callbacks:

- `on_iteration_passed(attempt: int, context: ImplementationContext) -> IterationArtifact | None`
- `on_run_succeeded(attempt: int, context: ImplementationContext) -> RunPublicationResult | None`
- `on_run_failed(attempt: int, context: ImplementationContext, feedback: str | None) -> None`

Recommended behavior:

- `ImplementationAgent` calls `on_iteration_passed()` after `GatePhase.ITERATION_COMPLETE` passes;
- if the completion judge says the task is complete, the agent still runs `GatePhase.IMPLEMENTATION_COMPLETE` before `on_run_succeeded()`;
- `on_run_succeeded()` handles final push and PR creation;
- observer callback failures should be caught inside `ImplementationAgent` and converted into `OrchestratorOutcome(status="failed", feedback=...)` instead of being re-raised; and
- when no observer is configured, current behavior stays unchanged.

This keeps the loop reusable and makes version control a composition concern rather than a core orchestrator concern.

### Callback Context Plumbing

Define a typed context model so lifecycle callbacks do not depend on ad hoc dictionaries.

Recommended model:

- `ImplementationContext` with `workspace_id`, `run_id`, `repo_path`, `workspace_path`, `branch_name`, `base_branch`, `remote_name`, and `task_id`

Recommended plumbing path:

1. `LocalProcessWorkspaceRunner.start_run()` creates the `RunHandle` first, as it does today;
2. before invoking the runnable agent, it enriches `RunRequest.context` with `run_id`;
3. `WorkspaceRunnableImplementationAgent.run()` builds `ImplementationContext` from `workspace.metadata`, `workspace.execution_target`, and `request.context`; and
4. that context is passed into `ImplementationAgent`, which forwards it to lifecycle callbacks.

This is the smallest change that gives the observer enough information to commit, push, and persist run artifacts.

## Commit Semantics

Recommended v1 behavior:

- after an iteration passes `ITERATION_COMPLETE`, inspect the workspace tree;
- if there are no file changes, skip commit creation for that iteration;
- if there are changes, stage all tracked and untracked changes and create one commit;
- do not create an extra commit after final implementation checks unless new changes exist; and
- use the already committed branch head when pushing and creating the PR.

Why this trigger point:

- it matches the user's request to commit each iteration that passes checks;
- it preserves progress even if a later iteration is needed; and
- it avoids coupling commit creation to the still-stubbed completion judge.

Recommended default commit message template:

- `chore: implementation iteration {{ iteration }} for {{ task_id }}`

Use this only as the fallback path.

Primary v1 behavior should be:

- generate commit text with `CommitMessageOutput` structured output;
- use `subject` as the commit subject line;
- use `body` as the optional multi-line commit body; and
- fall back to the template only when structured generation is disabled or explicitly allowed to degrade.

## Pull Request Semantics

Recommended v1 behavior:

- only attempt PR creation after the overall run succeeds;
- push the workspace branch to the configured remote first, without force;
- create the PR against the workspace base branch unless overridden by config; and
- return the PR URL in the final run message and persisted metadata.

### Follow-Up Work On An Existing PR

Further work should update the same PR when possible, not open a second PR for the same branch.

Recommended behavior:

- treat the published branch as a stable `publication_branch` separate from any temporary local execution branch;
- on a fresh run, `publication_branch` is the generated implementation branch;
- on a rerun started from a branch that already has an open PR, reuse that branch as `publication_branch`;
- provision a new workspace from that branch, but allow the workspace to use a temporary execution branch if needed for worktree safety;
- on success, push `HEAD` back to the same `publication_branch`; and
- before creating a PR, ask the forge adapter whether an open PR already exists for `publication_branch`.

If an open PR already exists:

- do not create a new PR;
- return the existing PR URL;
- report terminal output as an update, for example `Pull request updated: <url>`; and
- keep the existing PR title/body unchanged in v1, while new commits update the PR diff automatically.

If no open PR exists for `publication_branch`:

- create a new PR as normal.

This gives a clean follow-up workflow: the user checks out the branch locally, adds more instructions, runs again, and the system pushes more commits to the same PR branch.

### Publication Branch Naming

Use a stable publication branch and a disposable execution branch.

Recommended behavior:

- if the current branch already has an open PR, reuse that branch as `publication_branch`
- else if the current branch is not the base branch, reuse the current branch as `publication_branch`
- else create `developer/<task_slug>` as the `publication_branch`
- if that name already exists, append a short suffix such as `developer/<task_slug>-a1b2c3`
- keep the workspace branch disposable, for example `developer/<task_slug>/ws-<workspace_id>`

Code sketch:

```python
def resolve_publication_branch(
    current_branch: str,
    base_branch: str,
    task_slug: str,
    has_open_pr: Callable[[str], bool],
    branch_exists: Callable[[str], bool],
) -> str:
    if has_open_pr(current_branch):
        return current_branch
    if current_branch != base_branch:
        return current_branch

    candidate = f"developer/{task_slug}"
    if not branch_exists(candidate):
        return candidate
    return f"{candidate}-{short_uuid()}"
```

### Workspace Cleanup After Publication

Yes - once the branch is pushed and the PR is created, the worktree directory can be torn down.

Recommended behavior:

- after successful push and PR creation, call `WorkspaceProvider.destroy(workspace_id)` to remove the local worktree checkout;
- keep the persisted run record and publication metadata even after workspace cleanup;
- retain the branch remotely, since the PR depends on it;
- do not delete the local branch ref in v1 unless a later cleanup policy is added; and
- if cleanup fails after PR creation, keep the run successful and surface cleanup as a warning instead of failing the whole run.

This keeps local disk usage under control without treating successful publication as a failure just because cleanup was incomplete.

If publication is enabled and PR creation fails:

- keep the created commits and pushed branch intact;
- mark the run as failed; and
- surface a message that implementation succeeded but publication failed.

That makes the failure explicit without discarding recoverable artifacts.

## Configuration Plan

Keep TOML minimal in v1.

Only expose settings that are likely to vary by repo. Prefer built-in defaults for behavior flags until we have a clearer need for more knobs.

Recommended minimal config surface:

- `[prompts]` for implementation, commit, and pull request prompt paths
- `[version_control]` for enabling git integration and optional commit identity overrides
- `[forge]` for enabling platform publication

Everything else should default in code for v1.

### `[prompts]`

Recommended fields:

- `implementation_prompt_path = "harness/implementation_prompt.md"`
- `commit_prompt_path = "harness/prompts/commit_message_prompt.md"`
- `pull_request_prompt_path = "harness/prompts/pull_request_prompt.md"`

This should replace the current split where the implementation prompt lives under `[orchestrator]`.

Recommended rollout behavior:

- prefer `[prompts]` when present; and
- temporarily fall back to legacy `[orchestrator].implementation_prompt_path` for backward compatibility until configs are migrated.

Minimal TOML example:

```toml
[prompts]
implementation_prompt_path = "harness/implementation_prompt.md"
commit_prompt_path = "harness/prompts/commit_message_prompt.md"
pull_request_prompt_path = "harness/prompts/pull_request_prompt.md"

[version_control]
enabled = true

[forge]
enabled = true
```

### `[version_control]`

Recommended fields:

- `enabled = false`
- `author_name = "Your Name"` as an optional override
- `author_email = "you@example.com"` as an optional override

`provider` should default to `git` in code and should not need to be set in TOML for v1.

`author_name` and `author_email` should be optional overrides only. If absent, resolve the current git user identity from the repository or user git config and use that for automated commits.

Built-in defaults that should not be user-configurable yet:

- commit on each passing iteration
- push on successful completion
- remote name `origin`
- version control provider `git`
- structured commit generation enabled
- deterministic commit fallback enabled

### `[forge]`

Recommended fields:

- `enabled = false`

`provider` should default to `github` in code while GitHub is the only supported forge.

Built-in defaults that should not be user-configurable yet:

- forge provider `github`
- create a pull request on successful completion when forge is enabled

Built-in defaults that should not be user-configurable yet:

- non-draft pull requests
- use workspace base branch as PR base
- structured PR generation enabled
- deterministic PR fallback enabled

### `[workspaces]`

Do not add new workspace cleanup flags in v1.

Built-in default behavior:

- destroy the worktree automatically after successful PR creation
- keep the workspace when publication did not happen or failed

Prompt configuration should stay generic. The GitHub adapter should consume already-generated PR title/body rather than owning GitHub-specific prompt settings.

### Typed Model Sketch

```python
class CommitMessageOutput(BaseModel):
    subject: str
    body: str


class PullRequestContentOutput(BaseModel):
    title: str
    summary: list[str]
    body: str


class ImplementationContext(BaseModel):
    workspace_id: str
    run_id: str
    repo_path: str
    workspace_path: str
    branch_name: str
    publication_branch: str
    base_branch: str
    remote_name: str
    task_id: str
    task_slug: str
    latest_change_summary: str | None = None
```

Example terminal output:

```text
workspace=ws-123 | run=run-456 | status=succeeded | commits=2 | branch=developer/add-version-control | pr=https://github.com/org/repo/pull/42
Pull request: https://github.com/org/repo/pull/42
```

## Domain Model Changes

Extend workspace/run metadata instead of creating a separate persistence system.

Recommended additions:

- workspace metadata: `branch_name`, `base_branch`, `repo_path`, `remote_name`
- workspace metadata: `publication_branch`
- add `metadata: dict[str, Any] = Field(default_factory=dict)` to `RunHandle`
- store publication data in `RunHandle.metadata` with these keys:
  - created commit SHAs in order;
  - pushed branch name;
  - publication status;
  - PR URL when created

Recommended `RunHandle.metadata` keys:

- `commit_shas: list[str]`
- `pushed_branch: str`
- `publication_status: str`
- `pr_url: str`
- `version_control_enabled: bool`
- `forge_enabled: bool`
- `commit_message_subjects: list[str]`
- `pull_request_title: str`
- `pull_request_number: str`
- `publication_branch: str`

## Runtime Composition Changes

Update `src/developer/application/workspace_runtime.py` to assemble the new services.

Recommended composition flow:

1. build workspace provider as today;
2. resolve version control settings and create a git adapter when enabled;
3. resolve an agent-backed content generation service when commit or PR generation is enabled;
4. resolve forge settings and create a GitHub adapter when enabled;
5. wrap them in a workspace-aware lifecycle observer; and
6. inject that observer into `ImplementationAgent` for workspace runs only.

The content generation service should mirror the existing implementation prompt flow:

- load prompt paths from a shared TOML-backed prompt settings model;
- read prompt files at runtime;
- render prompt context from git/workspace metadata; and
- submit the rendered prompt through the selected agent with structured output.

Recommended new concrete service:

- `WorkspaceVersionControlObserver`

Responsibilities:

- read workspace metadata and repo paths;
- commit successful iterations;
- ask the content generation service for a structured commit message when needed;
- push the branch on final success;
- ask the content generation service for structured PR content before publication;
- create or reuse a PR when forge publication is enabled; and
- optionally destroy the workspace after successful publication; and
- produce human-readable status strings for the run result.

Preflight checks should run when the observer is created:

- if version control is enabled, validate that the workspace checkout is a git repository;
- if forge publication is enabled, validate that `gh` is installed and can inspect the repo context; and
- fail early with actionable errors before the implementation loop starts.

## CLI / UX Changes

Keep the CLI surface small in v1.

No new command is required to deliver this feature.

Update the final `implementation run` message to include publication details when available, for example:

- `workspace=<id> | run=<id> | status=succeeded | commits=2 | branch=developer/... | pr=https://github.com/...`

When a PR is created, print the PR URL plainly in terminal output so it is easy to click or copy.

Recommended terminal output shape:

- include the URL in the main status line; and
- also print a dedicated `Pull request: <url>` line immediately after the summary when created; and
- print `Pull request updated: <url>` when an existing PR was reused.

If publication fails, include the durable artifacts in the failure message, for example:

- `status=failed | branch=developer/... | commits=2 | publication=github pr create failed`

## Testing Plan

### Unit Tests

- `git_adapter` command construction and environment handling
- no-op commit behavior when the tree is clean
- branch push behavior and error surfacing
- `github_adapter` command construction and PR result parsing
- content generation service prompt inputs and structured-output parsing
- `ImplementationAgent` lifecycle hook order and failure propagation

### Service / Composition Tests

- config-driven adapter selection for version control and forge services
- config-driven content generation enablement and fallback behavior
- workspace runtime builds the observer only when the related sections are enabled
- final result messages include commit counts and PR URL when present
- observer failures are converted into failed outcomes instead of uncaught exceptions
- passing iteration with no diff records no commit and still allows the run to continue
- successful publication triggers workspace teardown when enabled
- cleanup failure is surfaced as a warning without flipping a successful publication to failed
- rerunning from a branch with an existing open PR reuses that PR instead of creating a new one

### Integration Tests

- temp repo + bare remote: passing iteration creates a commit on the workspace branch
- multi-iteration success creates one commit per passing iteration
- passing iteration with no file diff skips commit creation
- successful completion pushes the branch to the remote
- generated structured commit message is used in the created git commit
- GitHub publication path uses a stubbed adapter and records the PR URL
- generated structured PR content is passed to the GitHub adapter
- publication failure leaves commits and branch intact but marks the run failed
- successful PR creation removes the local worktree when cleanup is enabled
- cleanup failure after PR creation leaves the run successful and reports a warning
- missing `gh` when GitHub is enabled fails before the first iteration with a clear message
- rerunning from an already-published branch pushes new commits to the same branch and reports the existing PR URL

## Implementation Order

### Phase 1: Protocols, settings, and models

- add `version_control` and `forge` packages
- add settings models and config coverage
- add domain models for commits, pushes, and PR results
- add structured content models for commit and PR generation
- add TOML-backed prompt path settings for commit and PR generation

### Phase 2: Git adapter

- implement local git subprocess wrapper
- add status, stage, commit, head SHA, and push support
- add unit tests around author identity and clean-tree handling

### Phase 3: Loop lifecycle hooks

- add lifecycle observer protocol to the orchestrator layer
- update `ImplementationAgent` to notify the observer
- keep direct-mode behavior unchanged when no observer is present

### Phase 4: Workspace observer

- implement `WorkspaceVersionControlObserver`
- connect it in `workspace_runtime`
- plumb `run_id` and workspace metadata into `ImplementationContext`
- persist commit and publication metadata on runs

### Phase 5: Content generation service

- implement prompt-driven structured output generation for commit messages and PR content
- add dedicated prompt templates and prompt settings
- wire generated content into git commit creation and GitHub PR creation

### Phase 6: GitHub adapter and PR publication

- implement GitHub adapter over `gh`
- push branch on successful completion
- detect existing open PRs for the publication branch
- create or reuse PR and surface the returned URL
- destroy the workspace after successful publication when configured

### Phase 7: Presentation and docs

- update CLI output messages
- document new config in `engineeringagent.toml` examples or README when that documentation exists
- add end-to-end coverage for success and publication failure paths

## Risks And Mitigations

- stub completion judge means PR creation will happen as soon as the run reports success today; keep the design correct for a future real judge and document the current behavior clearly
- generated commit and PR content quality depends on the available diff and task context; keep deterministic fallbacks configurable and revisit once task input exists
- `gh` CLI availability/auth can fail outside controlled environments; validate early and return actionable errors
- automatic commits in a user checkout could be surprising; keep v1 scoped to workspace-backed runs only
- moving implementation prompt config from `[orchestrator]` to `[prompts]` can break existing configs if done abruptly; keep a temporary fallback during rollout

## Rollout And Rollback

- rollout is config-gated; behavior only changes when `[version_control] enabled = true`
- PR publication is independently config-gated through `[forge] enabled = true`
- rollback is simply disabling one or both sections; no data migration is required
- the only schema change is additive `RunHandle.metadata`, which is backward compatible for persisted run files

## Open Questions

- do you want PRs opened as draft by default until the completion judge becomes real?
- should fallback to deterministic commit/PR text remain enabled by default, or should structured generation failures fail the run?

## Recommended Default Decisions

Unless the user says otherwise, implement with these defaults:

- workspace-backed runs only
- git as the sole version control provider
- GitHub via `gh` as the sole forge provider
- version control provider defaults to `git`
- forge provider defaults to `github`
- commit author defaults to the current git user identity
- prompt-driven structured output for commit messages and PR content
- deterministic fallback text enabled by default
- PR creation enabled only after a successful workspace run
- non-draft PRs by default
