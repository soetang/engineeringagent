---
schema_version: 1
task_id: move-publication-orchestration-out-of-version-control
title: Move commit, push, and pull request workflow into publication orchestrators
status: draft
branch: feat/publication-orchestration-boundary
base_branch: master
phases:
  - id: publication-domain
    title: Define publication orchestration models and protocols under orchestrators
    status: todo
  - id: content-generation
    title: Move commit and pull request content generation behind orchestrator-owned protocols
    status: todo
  - id: infrastructure-adapters
    title: Reduce version control and forge packages to infrastructure adapters only
    status: todo
  - id: runtime-composition
    title: Compose publication orchestration from application without reintroducing workflow policy
    status: todo
  - id: fitness-rules
    title: Enforce dependency direction with import-boundary rules
    status: todo
  - id: tests
    title: Add orchestrator-first coverage and trim obsolete adapter/content tests
    status: todo
---

# Publication Orchestration Boundary Plan

## Goal

Move commit, push, and pull request workflow ownership out of `developer.version_control` and out of `developer.application`, and place it in an orchestrator-owned publication boundary.

After this refactor:

- `developer.orchestrators` owns publication workflow policy;
- `developer.version_control` owns only repository-local git operations;
- `developer.forge` owns only forge-hosting operations such as pull request lookup and creation;
- `developer.agent_backends` remains an execution mechanism, not an architectural dependency of version control; and
- `developer.application` stays a composition root that wires concrete implementations into orchestrator-owned ports.

## Decision

Treat publication as its own orchestration concern, separate from both:

- loop orchestration (`developer.orchestrators.loop`); and
- implementation-run planning (`developer.orchestrators.runs`).

Recommended ownership split:

- `developer.orchestrators.publication` owns commit/push/PR policy and the content-generation ports it needs.
- `developer.version_control` implements git command adapters and shared git request/result models.
- `developer.forge` implements forge command adapters and shared forge request/result models.
- `developer.agent_backends` may implement an orchestrator-owned publication content generation port, but version control must not import agent backend protocols directly.

## Problem In The Current Design

Today the main architectural leak is:

- `developer.version_control.content_service.VersionControlContentService` imports `developer.agent_backends.protocol.AgentBackendProtocol`; and
- `WorkspaceVersionControlObserver` coordinates commit, push, and PR flow even though it is application-owned.

That creates two distinct problems.

### 1. `developer.version_control` owns workflow-adjacent policy

`version_control` currently contains:

- raw git operations;
- prompt rendering for commit and PR generation; and
- an implicit dependency on agent-backed content generation.

That package now mixes infrastructure with orchestration policy.

### 2. `developer.application` owns more than composition

`WorkspaceVersionControlObserver` currently decides:

- when to commit;
- when to push;
- when to create or reuse a PR; and
- how commit and PR content is generated and recorded.

That is orchestration logic, not application composition.

## Target Architecture

## Package Ownership

### `developer.orchestrators.loop`

Keeps owning the inner implementation loop only.

It may publish lifecycle events, but it should not decide git or PR workflow directly.

### `developer.orchestrators.runs`

Keeps owning implementation-run planning only.

It may prepare run context for publication, but it should not own commit/push/PR workflow.

### `developer.orchestrators.publication`

New package.

Owns publication policy:

- whether an iteration should create a commit;
- how commit content is generated;
- whether a successful run should push a branch;
- whether a PR should be created or reused;
- how PR content is generated; and
- how publication metadata is returned to the loop/runtime.

This package defines the ports and typed models needed for publication orchestration.

### `developer.version_control`

Owns only git mechanics.

Examples:

- validate repository;
- detect changes;
- stage changes;
- resolve identity;
- create commit with a provided message;
- inspect branches;
- push a branch; and
- return diffs or recent commits when asked by an orchestrator-owned content port.

This package must not decide message policy and must not import `developer.agent_backends`.

### `developer.forge`

Owns only forge mechanics.

Examples:

- validate `gh` availability;
- find an open pull request; and
- create a pull request from a provided title/body.

This package must not render prompts or decide whether a PR should exist.

### `developer.application`

Owns composition only.

Examples:

- choose concrete publication orchestrator dependencies;
- wire version control, forge, registry, and content-generation implementations into orchestrator-owned ports; and
- attach a publication observer to the implementation loop.

Application should not decide publication sequencing or content policy.

## Dependency Direction

Desired direction:

- `developer.orchestrators.publication` defines ports
- `developer.version_control` implements git-facing ports
- `developer.forge` implements forge-facing ports
- `developer.agent_backends` may implement content-generation ports
- `developer.application` wires concrete implementations into orchestrators

Avoid these directions:

- `developer.version_control -> developer.agent_backends`
- `developer.forge -> developer.agent_backends`
- `developer.orchestrators.publication -> developer.version_control.adapters`
- `developer.orchestrators.publication -> developer.forge.adapters`
- `developer.application -> publication workflow helpers or policy logic`

## Proposed Modules

Recommended additions:

- `src/developer/orchestrators/publication/__init__.py`
- `src/developer/orchestrators/publication/models.py`
- `src/developer/orchestrators/publication/protocols.py`
- `src/developer/orchestrators/publication/publication_observer.py`
- `src/developer/orchestrators/publication/content_generation.py` or `services.py`

Recommended removals or moves:

- remove `src/developer/version_control/content_service.py`
- move `src/developer/version_control/content_models.py` into `developer.orchestrators.publication.models` or split them into publication-owned models
- replace `src/developer/application/observers/workspace_version_control_observer.py` with an orchestrator-owned publication observer

## Concrete Protocols

The exact names can change, but the ownership should stay the same.

### Publication Orchestrator Ports

Recommended protocol module:

- `src/developer/orchestrators/publication/protocols.py`

Recommended shapes:

```python
from __future__ import annotations

from typing import Protocol

from developer.orchestrators.publication.models import (
    CommitMessage,
    CommitMessageContext,
    PullRequestContent,
    PullRequestContentContext,
)
from developer.version_control.models import (
    CommitRequest,
    CommitResult,
    GitIdentity,
    PushResult,
    WorkingTreeStatus,
)
from developer.forge.models import PullRequestRequest, PullRequestResult


class PublicationVersionControlPort(Protocol):
    def validate_repository(self, repo_path: str) -> None:
        ...

    def get_status(self, repo_path: str) -> WorkingTreeStatus:
        ...

    def has_changes(self, repo_path: str) -> bool:
        ...

    def stage_all(self, repo_path: str) -> None:
        ...

    def resolve_identity(self, repo_path: str) -> GitIdentity:
        ...

    def create_commit(self, repo_path: str, request: CommitRequest) -> CommitResult:
        ...

    def push_branch(
        self,
        repo_path: str,
        branch_name: str,
        remote_name: str,
        source_ref: str = "HEAD",
    ) -> PushResult:
        ...

    def get_diff(self, repo_path: str, staged: bool = False) -> str:
        ...

    def get_recent_commits(self, repo_path: str, limit: int = 5) -> str:
        ...


class PublicationForgePort(Protocol):
    def validate_available(self, repo_path: str) -> None:
        ...

    def find_open_pull_request(
        self,
        repo_path: str,
        branch_name: str,
        base_branch: str,
    ) -> PullRequestResult | None:
        ...

    def create_pull_request(
        self,
        repo_path: str,
        request: PullRequestRequest,
    ) -> PullRequestResult:
        ...


class CommitMessageGenerator(Protocol):
    def build_commit_message(
        self,
        context: CommitMessageContext,
    ) -> CommitMessage:
        ...


class PullRequestContentGenerator(Protocol):
    def build_pull_request_content(
        self,
        context: PullRequestContentContext,
    ) -> PullRequestContent:
        ...
```

### Why These Ports

- `PublicationVersionControlPort` is infrastructure-facing and command-oriented.
- `PublicationForgePort` is infrastructure-facing and command-oriented.
- `CommitMessageGenerator` and `PullRequestContentGenerator` express policy inputs and outputs, not backend details.

This keeps `run_agent(...)` out of the publication orchestration boundary. If the concrete implementation uses an agent backend, that remains an implementation detail of the generator adapter.

## Concrete Models

Recommended model module:

- `src/developer/orchestrators/publication/models.py`

Suggested shapes:

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CommitMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    body: str = ""


class PullRequestContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    summary: list[str] = Field(default_factory=list)
    body: str


class CommitMessageContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo_path: str
    task_name: str
    task_path: str | None = None
    task_branch_name: str
    base_branch: str
    latest_change_summary: str | None = None
    staged_diff: str = ""
    recent_commits: str = ""


class PullRequestContentContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo_path: str
    task_name: str
    task_path: str | None = None
    task_branch_name: str
    base_branch: str
    latest_change_summary: str | None = None
    diff: str = ""
    recent_commits: str = ""


class PublicationIterationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    commit_sha: str | None = None
    commit_subject: str | None = None


class PublicationRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_name: str | None = None
    pr_url: str | None = None
    message: str | None = None
    status: str
```
```

Notes:

- move prompt-context ownership from `developer.version_control.content_models` into publication models;
- keep `CommitRequest`, `CommitResult`, `PushResult`, and `GitIdentity` in `developer.version_control.models`, because those are still git-domain transport models; and
- keep `PullRequestRequest` and `PullRequestResult` in `developer.forge.models`, because those are still forge-domain transport models.

## Publication Observer Shape

Recommended orchestrator-owned observer:

- `src/developer/orchestrators/publication/publication_observer.py`

This object should implement `developer.orchestrators.loop.protocols.ImplementationLifecycleObserver`.

Its dependencies should be only protocol-typed:

- `PublicationVersionControlPort`
- `CommitMessageGenerator`
- optional `PublicationForgePort`
- optional `PullRequestContentGenerator`
- existing `WorkspaceProvider` and `WorkspaceRunRegistry`, or smaller publication-state ports extracted later if desired

It should own the workflow currently in `WorkspaceVersionControlObserver`:

- validate publication tooling before the loop starts;
- on passing iteration, commit only when the worktree changed;
- on successful run, push the branch;
- on successful run with forge enabled, reuse an open PR or create one; and
- update run metadata and cleanup workspace.

That sequencing is orchestration, so it belongs here.

## Content Generation Adapters

The generator implementations should live outside `developer.version_control`.

Recommended implementations:

- `AgentBackedCommitMessageGenerator`
- `AgentBackedPullRequestContentGenerator`
- `DeterministicCommitMessageGenerator`
- `DeterministicPullRequestContentGenerator`
- optional `FallbackPublicationContentGenerator` wrapper that composes an agent-backed generator plus deterministic fallback

Recommended package placement:

- either `developer.application.publication_content` if treated as composition-time adapters; or
- `developer.publication_content` if you want a dedicated infrastructure package later.

For this slice, the simplest clean choice is application-owned adapter implementations composed into orchestrator ports, because the underlying backend selection already lives in application composition.

What should not happen:

- do not put these generators back under `developer.version_control`;
- do not make `developer.orchestrators.publication` import `developer.agent_backends` directly.

## Prompt Ownership

Prompt rendering for commit and PR generation should move with the content generator adapters, not stay in `developer.version_control`.

Recommended rule:

- prompt templates are content-generation implementation details;
- prompt paths may still come from `developer.config` and `developer.prompts`; and
- publication orchestrators should see only typed generator ports.

## Import Restrictions

Update `harness/policy/import_rules.yaml` to make the dependency direction enforceable.

### Recommended New Rules

#### `orchestrators-publication-boundary`

`developer.orchestrators.publication` should depend only on itself and orchestrator-shared models/protocols.

Recommended shape under the current policy system:

```yaml
- name: "orchestrators-publication-boundary"
  description: "Publication orchestration owns workflow policy and stays isolated from infrastructure packages."
  targets:
    - "developer.orchestrators.publication"
  mode: "allow_only"
  allow:
    - "developer.orchestrators.publication"
    - "developer.orchestrators.loop.models"
    - "developer.orchestrators.loop.protocols"
    - "developer.workspaces.protocols"
```
```

If publication models need shared transport models from `developer.version_control.models` or `developer.forge.models`, prefer moving those few transport types into publication-owned request/response models instead of allowing broad imports from infrastructure packages.

#### `version-control-boundary`

Replace the current `developer.agent_backends.protocol` allowance.

Recommended direction:

```yaml
- name: "version-control-boundary"
  description: "Version control stays a git adapter package and does not depend on agent backends or publication policy."
  targets:
    - "developer.version_control"
  mode: "allow_only"
  allow:
    - "developer.version_control"
    - "developer.config"
```
```

If prompt-backed content generation is fully removed from this package, `developer.prompts` should be removed from the allowlist too.

#### `forge-boundary`

Tighten forge similarly:

```yaml
- name: "forge-boundary"
  description: "Forge adapters stay infrastructure-only and do not own publication policy."
  targets:
    - "developer.forge"
  mode: "allow_only"
  allow:
    - "developer.forge"
    - "developer.config"
```
```

#### `agent-backend-boundary`

If you add publication content generator adapters under application, no new rule is required immediately.

If you instead add a dedicated package for agent-backed publication content generation, allow it to import:

- that package itself
- `developer.agent_backends`
- `developer.config`
- `developer.prompts`
- `developer.orchestrators.publication.models`
- `developer.orchestrators.publication.protocols`

### Import Rules To Preserve

Keep these architectural constraints explicit:

- `developer.orchestrators.publication` must not import `developer.application`
- `developer.orchestrators.publication` must not import `developer.version_control`
- `developer.orchestrators.publication` must not import `developer.forge`
- `developer.orchestrators.publication` must not import `developer.agent_backends`
- `developer.version_control` must not import `developer.agent_backends`
- `developer.version_control` must not import `developer.orchestrators.publication`
- `developer.forge` must not import `developer.agent_backends`
- `developer.forge` must not import `developer.orchestrators.publication`
- `developer.application` may import all of the above only to compose them

## Recommended Runtime Shape

Application composition should become:

1. select version control adapter;
2. select forge adapter;
3. select agent backend if prompt-backed content generation is enabled;
4. build concrete commit-message and PR-content generators;
5. build a publication observer from protocol-typed dependencies; and
6. inject that observer into the implementation loop runtime.

Application should not contain any of the following decisions:

- whether to commit after a successful iteration;
- whether to push after run success;
- whether to reuse or create a PR; or
- how to fall back from failed agent generation.

## Migration Plan

## Phase 1: Define publication orchestration models and protocols under orchestrators

### Checklist

- [ ] Add `src/developer/orchestrators/publication/`
- [ ] Add `models.py` with publication content and result models
- [ ] Add `protocols.py` with publication-facing version control, forge, and content-generator ports
- [ ] Keep the publication package free of infrastructure imports
- [ ] Decide whether publication should return dedicated result models or reuse `IterationArtifact` and `RunPublicationResult`

### Notes

Prefer dedicated publication models if they keep loop models smaller and more generic.

## Phase 2: Move commit and pull request content generation behind orchestrator-owned protocols

### Checklist

- [ ] Remove `VersionControlContentService` from `developer.version_control`
- [ ] Move or replace `CommitPromptContext` and `PullRequestPromptContext` with publication-owned models
- [ ] Add concrete commit-message and PR-content generator adapters outside `developer.version_control`
- [ ] Preserve deterministic fallback behavior in generator adapters or a wrapper
- [ ] Keep prompt rendering out of orchestrators and out of git adapters

### Notes

This is the key inversion step for the `version_control -> agent_backends` dependency.

## Phase 3: Reduce version control and forge packages to infrastructure adapters only

### Checklist

- [ ] Make `GitVersionControlAdapter` satisfy `PublicationVersionControlPort`
- [ ] Make `GitHubForgeAdapter` satisfy `PublicationForgePort`
- [ ] Remove any lingering content-generation code from `developer.version_control`
- [ ] Remove any lingering workflow-policy code from `developer.forge`
- [ ] Keep commit and PR request/result transport models in their infrastructure packages only if they remain purely command payloads

### Notes

After this phase, these packages should read like command adapters, not mini orchestrators.

## Phase 4: Compose publication orchestration from application without reintroducing workflow policy

### Checklist

- [ ] Add an orchestrator-owned publication observer implementing `ImplementationLifecycleObserver`
- [ ] Replace `WorkspaceVersionControlObserver` with the orchestrator-owned observer
- [ ] Update `src/developer/application/workspace_runtime.py` to build and inject the publication observer
- [ ] Keep application limited to dependency selection and assembly
- [ ] Remove publication sequencing logic from application-owned modules

### Notes

It is acceptable for application to build the concrete observer. It is not acceptable for application to own the observer's workflow decisions.

## Phase 5: Enforce dependency direction with import-boundary rules

### Checklist

- [ ] Add `orchestrators-publication-boundary`
- [ ] Tighten `version-control-boundary` so it no longer allows `developer.agent_backends.protocol`
- [ ] Remove `developer.prompts` from `version-control-boundary` if content generation fully leaves that package
- [ ] Tighten `forge-boundary` so it does not import orchestration or agent packages
- [ ] Run the import-rule fitness check after each package-boundary change

### Notes

This refactor is not complete until the import rules make regression difficult.

## Phase 6: Add orchestrator-first coverage and trim obsolete adapter/content tests

### Checklist

- [ ] Add `tests/orchestrators/publication/test_publication_observer.py`
- [ ] Add tests for commit-skip when there are no changes
- [ ] Add tests for commit generation fallback behavior
- [ ] Add tests for push-only publication when forge is disabled
- [ ] Add tests for PR reuse versus PR creation
- [ ] Move content-generation tests out of `tests/version_control/` to the new generator package tests
- [ ] Remove or rewrite tests that assume version control owns prompt-backed content generation

### Notes

The most important tests after the refactor should live at the publication orchestrator boundary, not at the git adapter boundary.

## Risks And Mitigations

- if publication content generators stay under `developer.version_control`, the main dependency leak remains; mitigate by moving the content service first
- if the publication observer stays under `developer.application`, the workflow boundary remains blurry; mitigate by making the observer orchestrator-owned in the same slice
- if publication orchestrators start importing git or forge adapters directly, the domain boundary just moves sideways; mitigate with protocol-only orchestrator imports and import rules
- if publication models depend heavily on `developer.version_control.models` and `developer.forge.models`, infrastructure details may leak upward; mitigate by introducing publication-owned models where useful

## Recommended Execution Order

1. add `developer.orchestrators.publication` models and protocols;
2. move content-generation contracts out of `developer.version_control`;
3. add concrete generator adapters outside `developer.version_control`;
4. add an orchestrator-owned publication observer;
5. rewire `workspace_runtime.py` to compose the new observer;
6. delete `version_control.content_service` and the application-owned publication observer;
7. tighten import rules;
8. update tests around the new publication boundary.

## Recommended Default Decision

Implement this as:

- a new `developer.orchestrators.publication` package;
- orchestrator-owned ports for git commands, forge commands, and publication content generation;
- infrastructure adapters in `developer.version_control` and `developer.forge` that accept already-decided commit/PR text;
- agent-backed content generators outside `developer.version_control`; and
- import rules that explicitly forbid `developer.version_control` from importing `developer.agent_backends`.

That keeps version control and forge as adapters, keeps application as composition, and puts commit/push/PR workflow ownership where it belongs: in orchestrators.
