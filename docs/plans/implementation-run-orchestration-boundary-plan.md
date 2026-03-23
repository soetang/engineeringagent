---
schema_version: 1
task_id: move-implementation-run-orchestration-boundary
title: Move implementation run orchestration into orchestrators
status: ready
branch: feat/move-implementation-run-orchestration-boundary
base_branch: main
phases:
  - id: orchestrator-boundary
    title: Restructure orchestrators around loop and run ownership
    status: done
  - id: protocol-inversion
    title: Move orchestration-facing protocols into orchestrators
    status: done
  - id: workspace-run-flow
    title: Extract workspace implementation run flow from application
    status: done
  - id: application-composition
    title: Reduce application to composition and result mapping
    status: done
  - id: fitness-guards
    title: Tighten fitness rules around the new boundary
    status: done
  - id: tests
    title: Update tests to match the new ownership model
    status: done
  - id: task-owned-run-contract
    title: Push remaining task-owned run defaults out of application
    status: done
  - id: policy-simplification
    title: Simplify rule and contract scaffolding after extraction
    status: todo
---

# Goal

Move implementation-run orchestration out of `developer.application` and into `developer.orchestrators` while preserving the architectural rule that orchestrators are the domain layer.

After this change:

- `developer.orchestrators` owns implementation-run decisions and defines the protocols it needs;
- `developer.application` composes concrete implementations and translates results;
- `developer.workspaces` and `developer.version_control` implement orchestrator-owned protocols instead of owning orchestration policy; and
- `src/developer/application/services/implementation_run_service.py` stops accumulating branch planning, publication reuse, and workspace request assembly.

# Decision

Keep orchestration inside `developer.orchestrators`, but separate two different responsibilities inside that package.

Recommended split:

- `src/developer/orchestrators/loop/`
- `src/developer/orchestrators/runs/`

Recommended ownership:

- `developer.orchestrators.loop` owns the inner implementation loop;
- `developer.orchestrators.runs` owns higher-level implementation-run coordination; and
- both subpackages remain domain-owned and define the ports they need.

Do not move implementation-run orchestration into `developer.workspaces`.

Do not let `developer.orchestrators` import from `developer.application`, `developer.workspaces`, or `developer.version_control`.

# Current State

Today `src/developer/application/services/implementation_run_service.py` owns too much workflow coordination.

The workspace-backed path currently does all of the following inside application:

- clean-checkout preflight;
- task publication lookup;
- current base-branch lookup;
- task-branch reuse and collision handling;
- workspace start-point selection;
- workspace metadata assembly;
- run-request context assembly; and
- delegation into workspace runtime.

That is orchestration policy, not application composition.

The architectural issue is not simply that application imports too much. The deeper issue is that workflow decisions live in application instead of in the domain-owned orchestrator layer.

# Target Architecture

## `developer.orchestrators.loop`

Owns the inner implementation loop only.

Examples:

- `ImplementationAgent`
- prompt and gate sequencing
- completion checks inside the implementation loop
- loop-level observers and outcomes

This package should stay isolated from workspace and version-control concerns.

## `developer.orchestrators.runs`

Owns higher-level implementation-run coordination.

Examples:

- deciding how workspace-mode implementation runs are planned;
- selecting base branch, task branch, and workspace start point;
- deciding when publication state is reused;
- building typed workspace execution plans; and
- delegating to a workspace runner through orchestrator-owned protocols.

This package defines the protocols needed for that orchestration.

## `developer.application`

Owns composition and result translation.

Examples:

- resolve config;
- resolve task input;
- normalize `max_iterations`;
- build orchestrators with concrete implementations of orchestrator-owned ports; and
- map orchestrator outcomes into `ImplementationRunResult`.

Application should not decide branch policy, publication reuse policy, or workspace run planning.

## `developer.workspaces`

Owns generic workspace runtime behavior and concrete adapters.

Examples:

- `WorkspaceRunOrchestrator`
- workspace provider and runner
- workspace registry implementation details

This package may implement protocols defined by `developer.orchestrators.runs`, but it should not own implementation-run orchestration policy.

## `developer.version_control`

Owns concrete git operations and adapters.

Examples:

- current branch lookup
- branch existence checks
- clean-checkout validation

This package may implement protocols defined by `developer.orchestrators.runs`, but it should not own implementation-run orchestration policy.

# Dependency Direction

The dependency direction should be inverted so the orchestrator layer stays the owner.

Desired direction:

- `developer.orchestrators.runs` defines ports
- `developer.workspaces` implements workspace-related ports
- `developer.version_control` implements git-related ports
- `developer.application` wires those implementations into orchestrators

Avoid this direction:

- `developer.orchestrators.runs` importing concrete workspace or git adapters

That would make orchestrators depend on infrastructure and weaken the domain boundary.

# Proposed Files

Recommended additions and moves:

- `src/developer/orchestrators/loop/__init__.py`
- `src/developer/orchestrators/loop/implementation_agent.py`
- `src/developer/orchestrators/loop/models.py`
- `src/developer/orchestrators/loop/protocols.py`
- `src/developer/orchestrators/runs/__init__.py`
- `src/developer/orchestrators/runs/implementation_workspace_run_orchestrator.py`
- `src/developer/orchestrators/runs/models.py`
- `src/developer/orchestrators/runs/protocols.py`
- `src/developer/application/implementation_run_runtime.py`

This refactor should land directly in the final module layout.

Required outcome:

- update imports to the new module paths in the same change;
- remove old flat orchestrator module usage as part of the migration; and
- remove the old flat orchestrator modules as part of the migration; and
- finish with no support for the old flat module paths.

# Proposed Orchestrator-Owned Protocols

The exact names can change, but the ownership should stay the same.

Recommended run-orchestration ports:

- `ImplementationRunTask`
- `TaskPublicationStore`
- `BranchInspectionPort`
- `WorkspaceRunPort`

`developer.orchestrators.runs` should not import from `developer.tasks`.

That means:

- the task module may implement orchestrator-owned task protocols; and
- infrastructure implementations map persisted publication records into orchestrator-owned publication models before returning them through orchestrator ports.

Suggested shapes:

```python
class ImplementationRunTask(Protocol):
    @property
    def task_id(self) -> str:
        ...

    @property
    def task_name(self) -> str:
        ...

    @property
    def task_path(self) -> str | None:
        ...

    def get_branch_name(self) -> str:
        ...
```

```python
class TaskPublicationStore(Protocol):
    def get_task_publication(
        self,
        task_name: str,
        task_path: str | None,
    ) -> PublishedTaskBranch | None:
        ...
```

```python
class BranchInspectionPort(Protocol):
    def get_current_branch(self, repo_path: str) -> str:
        ...

    def branch_exists(
        self,
        repo_path: str,
        branch_name: str,
        remote_name: str = "origin",
    ) -> bool:
        ...
```

```python
class WorkspaceRunPort(Protocol):
    def run(self, command: WorkspaceRunCommand) -> WorkspaceRunResult:
        ...
```

Concrete implementations should live outside orchestrators:

- `FileWorkspaceRegistry` can satisfy `TaskPublicationStore`
- `GitVersionControlAdapter` can satisfy `BranchInspectionPort`
- `WorkspaceRunOrchestrator` can satisfy `WorkspaceRunPort`
- the resolved implementation-task type in `developer.tasks` can satisfy `ImplementationRunTask`

One additional ownership decision should stay explicit in the plan:

- `_normalize_workspace_task_input(...)` stays in application because it normalizes caller input before orchestration starts

Concrete protocol sketch for `src/developer/orchestrators/runs/protocols.py`:

```python
from __future__ import annotations

from typing import Protocol

from developer.orchestrators.runs.models import (
    PublishedTaskBranch,
    WorkspaceRunCommand,
    WorkspaceRunResult,
)


class ImplementationRunTask(Protocol):
    @property
    def task_id(self) -> str:
        ...

    @property
    def task_name(self) -> str:
        ...

    @property
    def task_path(self) -> str | None:
        ...

    def get_branch_name(self) -> str:
        ...


class TaskPublicationStore(Protocol):
    def get_task_publication(
        self,
        task_name: str,
        task_path: str | None,
    ) -> PublishedTaskBranch | None:
        ...


class BranchInspectionPort(Protocol):
    def get_current_branch(self, repo_path: str) -> str:
        ...

    def branch_exists(
        self,
        repo_path: str,
        branch_name: str,
        remote_name: str = "origin",
    ) -> bool:
        ...


class WorkspaceRunPort(Protocol):
    def run(self, command: WorkspaceRunCommand) -> WorkspaceRunResult:
        ...
```

Concrete task-side sketch showing the allowed dependency direction:

```python
from developer.orchestrators.runs.protocols import ImplementationRunTask


class MarkdownImplementationTask(ImplementationRunTask):
    ...
```

# Proposed Models

Recommended domain models inside `developer.orchestrators.runs.models`:

- `ImplementationWorkspaceRunRequest`
- `ImplementationWorkspacePlan`
- `ImplementationWorkspaceRunOutcome`

Suggested fields:

`ImplementationWorkspaceRunRequest`

- `repo_path: str`
- `task_input: str`
- `normalized_task_input: str`
- `task: ImplementationRunTask`
- `max_iterations: int | None`
- `remote_name: str = "origin"`

`PublishedTaskBranch`

- `branch_name: str`

`ImplementationWorkspacePlan`

- `base_branch: str`
- `task_branch_name: str`
- `workspace_start_point: str`
- `workspace_metadata: dict[str, object]`
- `run_context: dict[str, object]`

`ImplementationWorkspaceRunOutcome`

- `task_name: str`
- `workspace_id: str`
- `run_id: str`
- `status: str`
- `latest_message: str | None`
- `metadata: dict[str, object]`

`WorkspaceRunCommand`

- `repo_path: str`
- `base_branch: str`
- `task_id: str`
- `workspace_metadata: dict[str, object]`
- `agent_kind: str`
- `run_context: dict[str, object]`

`WorkspaceRunResult`

- `workspace_id: str`
- `run_id: str`
- `status: str`
- `latest_message: str | None`
- `metadata: dict[str, object]`

Ownership defaults:

- application resolves and normalizes task input before constructing the request;
- `developer.tasks` may implement `ImplementationRunTask`, which lets application pass the resolved task directly into the orchestrator-owned request model;
- `_normalize_workspace_task_input(...)` stays in application because it is caller-input normalization, not orchestration policy;
- `developer.orchestrators.runs` builds the plan and outcome;
- application maps the outcome to `ImplementationRunResult`; and
- clean-checkout preflight remains in application for this slice unless a better shared preflight abstraction already emerges during implementation.

Concrete model sketch for `src/developer/orchestrators/runs/models.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from developer.orchestrators.runs.protocols import ImplementationRunTask


class ImplementationWorkspaceRunRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    repo_path: str
    task_input: str
    normalized_task_input: str
    task: ImplementationRunTask
    max_iterations: int | None
    remote_name: str = "origin"


class PublishedTaskBranch(BaseModel):
    branch_name: str


class ImplementationWorkspacePlan(BaseModel):
    workspace_metadata: dict[str, object]
    run_context: dict[str, object]
    base_branch: str
    task_branch_name: str
    workspace_start_point: str


class ImplementationWorkspaceRunOutcome(BaseModel):
    task_name: str
    workspace_id: str
    run_id: str
    status: str
    latest_message: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class WorkspaceRunCommand(BaseModel):
    repo_path: str
    base_branch: str
    task_id: str
    workspace_metadata: dict[str, object]
    agent_kind: str
    run_context: dict[str, object]


class WorkspaceRunResult(BaseModel):
    workspace_id: str
    run_id: str
    status: str
    latest_message: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
```

This keeps `developer.orchestrators.runs` from depending on `developer.workspaces.models` directly.

# Proposed Runtime Shape

Application flow should become:

1. resolve config;
2. ensure clean checkout;
3. resolve task input into a task-module object;
4. resolve `max_iterations`;
5. if workspace mode is disabled, run direct mode as today;
6. otherwise normalize caller input, build `ImplementationWorkspaceRunRequest` with the resolved task object, and build `ImplementationWorkspaceRunOrchestrator` through application composition;
7. call `orchestrator.run(...)`; and
8. map the returned outcome into `ImplementationRunResult`.

Run-orchestration flow should become:

1. load task publication state through `TaskPublicationStore`;
2. get the current base branch through `BranchInspectionPort`;
3. resolve the task branch for this run;
4. resolve the workspace start point;
5. build the typed workspace plan;
6. build a `WorkspaceRunCommand`;
7. delegate to `WorkspaceRunPort`; and
8. return a typed `ImplementationWorkspaceRunOutcome`.

Concrete orchestrator sketch for `src/developer/orchestrators/runs/implementation_workspace_run_orchestrator.py`:

```python
from __future__ import annotations

from uuid import uuid4

from developer.orchestrators.runs.models import (
    ImplementationWorkspacePlan,
    ImplementationWorkspaceRunOutcome,
    ImplementationWorkspaceRunRequest,
    PublishedTaskBranch,
    WorkspaceRunCommand,
)
from developer.orchestrators.runs.protocols import (
    BranchInspectionPort,
    TaskPublicationStore,
    WorkspaceRunPort,
)
class ImplementationWorkspaceRunOrchestrator:
    def __init__(
        self,
        publication_store: TaskPublicationStore,
        branch_inspector: BranchInspectionPort,
        workspace_runner: WorkspaceRunPort,
    ) -> None:
        self._publication_store = publication_store
        self._branch_inspector = branch_inspector
        self._workspace_runner = workspace_runner

    def run(
        self,
        request: ImplementationWorkspaceRunRequest,
    ) -> ImplementationWorkspaceRunOutcome:
        publication = self._publication_store.get_task_publication(
            request.task.task_name,
            request.task.task_path,
        )
        plan = self._build_plan(request, publication)
        run_result = self._workspace_runner.run(
            WorkspaceRunCommand(
                repo_path=request.repo_path,
                base_branch=plan.base_branch,
                task_id=request.task.task_id,
                workspace_metadata=plan.workspace_metadata,
                agent_kind="implementation",
                run_context=plan.run_context,
            )
        )
        return ImplementationWorkspaceRunOutcome(
            task_name=request.task.task_name,
            workspace_id=run_result.workspace_id,
            run_id=run_result.run_id,
            status=run_result.status,
            latest_message=run_result.latest_message,
            metadata=run_result.metadata,
        )

    def _build_plan(
        self,
        request: ImplementationWorkspaceRunRequest,
        publication: PublishedTaskBranch | None,
    ) -> ImplementationWorkspacePlan:
        base_branch = self._branch_inspector.get_current_branch(request.repo_path)
        task_branch_name = self._resolve_task_branch(request, publication)
        workspace_start_point = self._resolve_workspace_start_point(
            publication,
            base_branch,
        )
        return ImplementationWorkspacePlan(
            base_branch=base_branch,
            task_branch_name=task_branch_name,
            workspace_start_point=workspace_start_point,
            workspace_metadata={
                "task_id": request.task.task_id,
                "task_name": request.task.task_name,
                "task_path": request.task.task_path,
                "task_branch_name": task_branch_name,
                "remote_name": request.remote_name,
                "start_point": workspace_start_point,
            },
            run_context={
                "task_input": request.normalized_task_input,
                "task_id": request.task.task_id,
                "task_name": request.task.task_name,
                "task_path": request.task.task_path,
                "task_branch_name": task_branch_name,
                "max_iterations": request.max_iterations,
            },
        )

    def _resolve_task_branch(
        self,
        request: ImplementationWorkspaceRunRequest,
        publication: PublishedTaskBranch | None,
    ) -> str:
        if publication is not None:
            return publication.branch_name
        candidate = request.task.get_branch_name()
        if not self._branch_inspector.branch_exists(
            request.repo_path,
            candidate,
            remote_name=request.remote_name,
        ):
            return candidate
        return f"{candidate}-{uuid4().hex[:8]}"

    def _resolve_workspace_start_point(
        self,
        publication: PublishedTaskBranch | None,
        base_branch: str,
    ) -> str:
        if publication is not None:
            return publication.branch_name
        return base_branch
```

Concrete application composition sketch for `src/developer/application/implementation_run_runtime.py`:

```python
from __future__ import annotations

from pathlib import Path

from developer.application.workspace_runtime import build_workspace_orchestrator
from developer.config.service import ConfigService
from developer.orchestrators.runs.implementation_workspace_run_orchestrator import (
    ImplementationWorkspaceRunOrchestrator,
)
from developer.orchestrators.runs.models import WorkspaceRunCommand, WorkspaceRunResult
from developer.orchestrators.runs.protocols import WorkspaceRunPort
from developer.version_control.adapters.git_adapter import GitVersionControlAdapter
from developer.workspaces.models import RunRequest, WorkspaceSpec
from developer.workspaces.services.file_registry import FileWorkspaceRegistry
from developer.workspaces.settings import WorkspaceSettings


class WorkspaceRunOrchestratorPortAdapter(WorkspaceRunPort):
    def __init__(self, workspace_runner) -> None:
        self._workspace_runner = workspace_runner

    def run(self, command: WorkspaceRunCommand) -> WorkspaceRunResult:
        workspace, run_handle = self._workspace_runner.run_in_workspace(
            WorkspaceSpec(
                provider="git_worktree",
                repo_path=command.repo_path,
                base_branch=command.base_branch,
                task_id=command.task_id,
                metadata=command.workspace_metadata,
            ),
            RunRequest(
                agent_kind=command.agent_kind,
                context=command.run_context,
            ),
        )
        return WorkspaceRunResult(
            workspace_id=workspace.id,
            run_id=run_handle.id,
            status=run_handle.status.value,
            latest_message=run_handle.latest_message,
            metadata=dict(run_handle.metadata),
        )


def build_implementation_workspace_run_orchestrator(
    config_service: ConfigService,
) -> ImplementationWorkspaceRunOrchestrator:
    workspace_settings = config_service.get_config("workspaces", WorkspaceSettings)
    publication_store = FileWorkspaceRegistry(
        Path(workspace_settings.state_dir).resolve()
    )
    return ImplementationWorkspaceRunOrchestrator(
        publication_store=publication_store,
        branch_inspector=GitVersionControlAdapter(),
        workspace_runner=WorkspaceRunOrchestratorPortAdapter(
            build_workspace_orchestrator(config_service)
        ),
    )
```

Concrete post-refactor service sketch for `src/developer/application/services/implementation_run_service.py`:

```python
from __future__ import annotations

from pathlib import Path

from developer.agent_backends.select_agent_backend_service import (
    SelectAgentBackendService,
)
from developer.application.implementation_run_runtime import (
    build_implementation_workspace_run_orchestrator,
)
from developer.application.models import ImplementationRunResult
from developer.application.settings import ImplementationSettings
from developer.application.workspace_bridges import build_implementation_agent
from developer.config.service import ConfigService
from developer.orchestrators.loop.models import OrchestratorOutcome
from developer.orchestrators.runs.models import (
    ImplementationWorkspaceRunOutcome,
    ImplementationWorkspaceRunRequest,
)
from developer.tasks.errors import TaskError
from developer.tasks.select_service import TaskSelectionService
from developer.version_control.adapters.git_adapter import GitVersionControlAdapter


def run_implementation(
    task_input: str,
    max_iterations: int | str | None = None,
    config_service: ConfigService | None = None,
) -> ImplementationRunResult:
    resolved_config_service = config_service or ConfigService()
    repo_path = Path.cwd()
    version_control = GitVersionControlAdapter()
    try:
        version_control.ensure_clean_checkout(str(repo_path))
        task = TaskSelectionService().resolve(task_input, base_path=repo_path)
        resolved_max_iterations = _resolve_max_iterations(
            resolved_config_service,
            cli_override=max_iterations,
        )
    except (ValueError, TaskError) as exc:
        return ImplementationRunResult(exit_code=1, message=str(exc))

    if _workspace_mode_enabled(resolved_config_service):
        normalized_task_input = _normalize_workspace_task_input(repo_path, task_input)
        outcome = build_implementation_workspace_run_orchestrator(
            resolved_config_service
        ).run(
            ImplementationWorkspaceRunRequest(
                repo_path=str(repo_path),
                task_input=task_input,
                normalized_task_input=normalized_task_input,
                task=task,
                max_iterations=resolved_max_iterations,
            )
        )
        return _build_workspace_run_result(outcome)

    outcome = build_implementation_agent(
        SelectAgentBackendService(resolved_config_service).select_agent(),
        task=task,
        max_iterations=resolved_max_iterations,
    ).run()
    return _build_direct_run_result(outcome)
```

Recommended workspace-result formatter shape in the same service:

```python
def _build_workspace_run_result(
    outcome: ImplementationWorkspaceRunOutcome,
) -> ImplementationRunResult:
    metadata = outcome.metadata
    parts = [
        f"workspace={outcome.workspace_id}",
        f"run={outcome.run_id}",
        f"task={outcome.task_name}",
        f"status={outcome.status}",
    ]
    commit_shas = metadata.get("commit_shas", [])
    if isinstance(commit_shas, list) and commit_shas:
        parts.append(f"commits={len(commit_shas)}")
    branch = metadata.get("pushed_branch") or metadata.get("task_branch_name")
    if isinstance(branch, str) and branch:
        parts.append(f"branch={branch}")
    pr_url = metadata.get("pr_url")
    if isinstance(pr_url, str) and pr_url:
        parts.append(f"pr={pr_url}")
    if outcome.latest_message:
        parts.append(outcome.latest_message)
    message = " | ".join(parts)
    if isinstance(pr_url, str) and pr_url:
        message = f"{message}\nPull request: {pr_url}"
    exit_code = 0 if outcome.status == "succeeded" else 1
    return ImplementationRunResult(exit_code=exit_code, message=message)
```

This keeps the CLI-formatting contract intact without requiring `implementation_run_service.py` to depend on `developer.workspaces.models`.

# Fitness Guard Recommendation

The primary fitness change should be an import-boundary update that reinforces domain ownership.

## Import-Boundary Updates

Update `harness/policy/import_rules.yaml` so it reflects the new orchestrator split and dependency direction.

Recommended rules:

- add a rule for `src/developer/orchestrators/loop/**/*.py`
- add a rule for `src/developer/orchestrators/runs/**/*.py`
- keep both orchestrator subpackages from importing `developer.application`
- keep both orchestrator subpackages from importing `developer.tasks`
- keep both orchestrator subpackages from importing concrete `developer.workspaces` and `developer.version_control` modules
- allow orchestrator subpackages to import only from orchestrator-local modules and shared domain-facing types they already own
- allow `developer.tasks` to import orchestrator-owned protocol modules when task types implement them
- keep `developer.workspaces` and `developer.version_control` free to import orchestrator-owned protocol modules so they can implement those ports

Recommended `import_rules.yaml` draft after the split:

```yaml
rules:
  - name: "orchestrator-loop-import-boundary"
    paths:
      - "src/developer/orchestrators/loop/**/*.py"
    allow:
      local_prefixes:
        - "developer.orchestrators.loop"
      relative_import_roots:
        - "."
    deny:
      local_prefixes:
        - "developer"

  - name: "orchestrator-runs-import-boundary"
    paths:
      - "src/developer/orchestrators/runs/**/*.py"
    allow:
      local_prefixes:
        - "developer.orchestrators.runs"
      relative_import_roots:
        - "."
    deny:
      local_prefixes:
        - "developer"

  - name: "workspaces-can-implement-orchestrator-ports"
    paths:
      - "src/developer/workspaces/**/*.py"
    allow:
      local_prefixes:
        - "developer.workspaces"
        - "developer.tasks.models"
        - "developer.orchestrators.runs.protocols"
      relative_import_roots:
        - "."
    deny:
      local_prefixes:
        - "developer.application"
        - "developer.orchestrators.loop"
        - "developer.orchestrators.runs"

  - name: "version-control-can-implement-orchestrator-ports"
    paths:
      - "src/developer/version_control/**/*.py"
    allow:
      local_prefixes:
        - "developer.version_control"
        - "developer.orchestrators.runs.protocols"
        - "developer.agent_backends.protocol"
        - "developer.config"
        - "developer.prompts"
      relative_import_roots:
        - "."
    deny:
      local_prefixes:
        - "developer"
```

Notes on this draft:

- the orchestrator rules deny all non-allowed `developer.*` imports, which preserves domain ownership;
- `developer.orchestrators.runs` is not allowed to depend on `developer.tasks`; task-module objects must satisfy orchestrator-owned protocols instead;
- `developer.workspaces` and `developer.version_control` are allowed to import only the orchestrator protocol module they need to implement; and
- the current broad orchestrator rule and flat orchestrator imports should be removed as part of this refactor.

Add a targeted rule for `src/developer/application/services/implementation_run_service.py`.

That rule should block the application service from importing concrete planning dependencies once the extraction is complete, especially:

- `developer.workspaces.services.file_registry`
- concrete workspace planning/runtime modules beyond the application composition helper
- direct branch-selection or publication-planning helpers

Keep an explicit allow for the clean-checkout preflight dependency only if it remains in application.

Recommended targeted rule draft for the application service after extraction:

```yaml
  - name: "implementation-run-service-stays-thin"
    paths:
      - "src/developer/application/services/implementation_run_service.py"
    allow:
      local_prefixes:
        - "developer.application"
        - "developer.agent_backends"
        - "developer.config"
        - "developer.orchestrators.loop"
        - "developer.orchestrators.runs"
        - "developer.tasks"
        - "developer.version_control.adapters.git_adapter"
      relative_import_roots:
        - "."
    deny:
      local_prefixes:
        - "developer.workspaces"
        - "developer.version_control"
```

Notes on this targeted rule:

- the explicit `developer.version_control.adapters.git_adapter` allow is only for the clean-checkout preflight kept in application for this slice;
- the broad `developer.version_control` deny stops application from reacquiring branch-planning behavior elsewhere;
- `developer.workspaces` is denied entirely so `implementation_run_service.py` cannot directly rebuild workspace requests or inspect registry state; and
- application should reach workspace execution only through `src/developer/application/implementation_run_runtime.py` plus the orchestrator-facing APIs.

## Dedicated Fitness Script

Do not add a new custom AST-based fitness script in this slice by default.

Reason:

- the import-boundary update is the clearest first enforcement;
- it aligns with the repository's existing fitness mechanism; and
- the main architectural concern is dependency ownership, which import rules can express well once the protocols move into orchestrators.

If the import rules later prove insufficient, a follow-up script can assert that `implementation_run_service.py` delegates rather than orchestrates, but that is not required for this first refactor.

## Phase 1: Restructure orchestrators around loop and run ownership

- [x] Update `harness/policy/import_rules.yaml` before moving code so the new orchestrator split is policy-compliant immediately
- [x] Add `src/developer/orchestrators/loop/`
- [x] Add `src/developer/orchestrators/loop/__init__.py`
- [x] Add `src/developer/orchestrators/runs/`
- [x] Add `src/developer/orchestrators/runs/__init__.py`
- [x] Move `ImplementationAgent` into `src/developer/orchestrators/loop/implementation_agent.py`
- [x] Move loop-specific models into `src/developer/orchestrators/loop/models.py`
- [x] Move loop-specific protocols into `src/developer/orchestrators/loop/protocols.py`
- [x] Add `src/developer/orchestrators/runs/models.py`
- [x] Add `src/developer/orchestrators/runs/protocols.py`
- [x] Update all existing imports to the new orchestrator module paths in the same change
- [x] Remove use of flat `developer.orchestrators.*` module paths
- [x] Remove the old flat orchestrator modules after imports are migrated

### Notes

The point of this phase is not just folder cleanup. It is to make the ownership split visible in code and enforceable in fitness rules.

This phase should end with only the new orchestrator module layout in use.

## Phase 2: Move orchestration-facing protocols into orchestrators

- [x] Define `ImplementationRunTask` in `src/developer/orchestrators/runs/protocols.py`
- [x] Define `TaskPublicationStore` in `src/developer/orchestrators/runs/protocols.py`
- [x] Define `BranchInspectionPort` in `src/developer/orchestrators/runs/protocols.py`
- [x] Define `WorkspaceRunPort` in `src/developer/orchestrators/runs/protocols.py`
- [x] Define `ImplementationWorkspaceRunRequest` in `src/developer/orchestrators/runs/models.py`
- [x] Define `PublishedTaskBranch` in `src/developer/orchestrators/runs/models.py`
- [x] Define `ImplementationWorkspacePlan` in `src/developer/orchestrators/runs/models.py`
- [x] Define `ImplementationWorkspaceRunOutcome` in `src/developer/orchestrators/runs/models.py`
- [x] Update the resolved implementation-task type to satisfy `ImplementationRunTask`
- [x] Update `developer.workspaces` implementations to satisfy the new orchestrator-owned ports
- [x] Update `developer.version_control` implementations to satisfy the new orchestrator-owned ports
- [x] Keep concrete implementations outside orchestrators

### Notes

This is the key inversion step. The protocols and task-facing run contracts should move toward the domain layer, not away from it.

## Phase 3: Extract workspace implementation run flow from application

- [x] Add `src/developer/orchestrators/runs/implementation_workspace_run_orchestrator.py`
- [x] Keep `_normalize_workspace_task_input(...)` in application as an input-normalization helper
- [x] Move publication reuse logic out of `src/developer/application/services/implementation_run_service.py`
- [x] Move base-branch selection out of `src/developer/application/services/implementation_run_service.py`
- [x] Move task-branch collision handling out of `src/developer/application/services/implementation_run_service.py`
- [x] Move workspace start-point selection out of `src/developer/application/services/implementation_run_service.py`
- [x] Move workspace metadata assembly into the new run orchestrator
- [x] Move run-context assembly into the new run orchestrator
- [x] Build `WorkspaceRunCommand` in the new run orchestrator
- [x] Delegate workspace execution through `WorkspaceRunPort`
- [x] Return `ImplementationWorkspaceRunOutcome` instead of formatting CLI-facing text inside orchestrators

### Notes

The helpers currently named `_load_task_publication(...)`, `_resolve_task_branch(...)`, and `_resolve_workspace_start_point(...)` should move into `developer.orchestrators.runs` as private methods or nearby collaborators.

## Phase 4: Reduce application to composition and result mapping

- [x] Add `src/developer/application/implementation_run_runtime.py`
- [x] Build `ImplementationWorkspaceRunOrchestrator` in that file from concrete implementations of orchestrator-owned protocols
- [x] Update `src/developer/application/services/implementation_run_service.py` to delegate workspace mode to `developer.orchestrators.runs`
- [x] Keep task resolution in application
- [x] Keep `max_iterations` normalization in application
- [x] Keep clean-checkout preflight in application for this refactor unless a small shared preflight abstraction is already obvious and low-risk
- [x] Keep CLI-facing message formatting in application
- [x] Keep direct-mode execution unchanged in the first slice
- [x] Remove workspace-planning helpers from `src/developer/application/services/implementation_run_service.py`

### Notes

Application remains important, but only as the composition root and CLI-facing use-case layer.

## Phase 5: Tighten fitness rules around the new boundary

- [x] Add a dedicated import rule for `src/developer/orchestrators/loop/**/*.py`
- [x] Add a dedicated import rule for `src/developer/orchestrators/runs/**/*.py`
- [x] Ensure orchestrator subpackages cannot import `developer.application`
- [x] Ensure orchestrator subpackages cannot import concrete `developer.workspaces` modules
- [x] Ensure orchestrator subpackages cannot import concrete `developer.version_control` modules
- [x] Allow infrastructure packages to import orchestrator-owned protocol modules they implement
- [x] Add a targeted import rule for `src/developer/application/services/implementation_run_service.py`
- [x] Keep the preflight exception explicit if it still exists in application
- [x] Run the import-boundary fitness command after the refactor

### Notes

The main fitness update is about enforcing dependency direction, not just package naming.

## Phase 6: Update tests to match the new ownership model

- [x] Add `tests/orchestrators/runs/test_implementation_workspace_run_orchestrator.py`
- [x] Cover publication reuse in run-orchestrator tests
- [x] Cover branch collision handling in run-orchestrator tests
- [x] Cover workspace start-point selection in run-orchestrator tests
- [x] Cover `WorkspaceRunCommand` content in run-orchestrator tests
- [x] Cover `WorkspaceRunCommand` to workspace runtime adaptation in `src/developer/application/implementation_run_runtime.py` tests
- [x] Cover `WorkspaceSpec` and `RunRequest` assembly in `src/developer/application/implementation_run_runtime.py` adapter tests
- [x] Cover `_normalize_workspace_task_input(...)` behavior in application-level tests
- [x] Update `tests/application/services/test_implementation_run_service.py` to assert delegation instead of internal workspace planning
- [x] Move helper-focused tests for branch resolution and start-point selection out of application tests and into run-orchestrator tests
- [x] Add or update composition tests for `src/developer/application/implementation_run_runtime.py`
- [x] Run `uv run pytest harness/fitness/tests`
- [x] Run `uv run python -m harness.fitness.scripts.import_rules --config harness/policy/import_rules.yaml`
- [x] Run `uv run pytest tests/application/services/test_implementation_run_service.py tests/orchestrators`
- [x] Run `uv run developer validate-plan docs/plans/implementation-run-orchestration-boundary-plan.md`

### Notes

After extraction, application tests should stop asserting workspace-planning helpers and instead assert delegation and result mapping.

## Phase 7: Push remaining task-owned run defaults out of application

- [x] Extend `ImplementationRunTask` with a base-branch accessor backed by task frontmatter instead of rediscovering it during workspace-run planning
- [x] Update the markdown-plan task implementation to expose `base_branch` directly from `TaskPlanDefinition`
- [x] Teach `ImplementationWorkspaceRunOrchestrator` to prefer the task-provided base branch and fall back to `BranchInspectionPort.get_current_branch(...)` only when the task does not specify one
- [x] Keep task-owned branch naming on `ImplementationRunTask` and avoid adding duplicate "default branch" fields to run-request models
- [x] Revisit whether both `task_input` and `normalized_task_input` need to survive after task resolution and collapse them to one workspace-safe task reference if possible
- [x] Make an explicit ownership decision for workspace execution defaults such as `agent_kind` and workspace provider
- [x] If those defaults vary by task, expose them through an orchestrator-owned task execution contract implemented by `developer.tasks`
- [x] If those defaults do not vary by task, move them out of per-run application assembly and centralize them inside runtime composition helpers
- [x] Keep `repo_path` runtime-owned because it comes from the caller's checkout rather than the task definition
- [x] Update runtime-adapter and application tests to assert the final ownership split for branch selection, base-branch selection, and workspace execution defaults

### Notes

This phase closes the review concern that task-owned execution intent should not leak back into application through ad hoc command assembly.

Recommended default:

- task owns stable identity, branch naming, and optional base-branch preference; and
- runtime composition owns environment defaults that do not vary by task, but those defaults should no longer be assembled ad hoc inside application request adapters.

## Phase 8: Simplify rule and contract scaffolding after extraction

- [x] Remove the legacy `orchestrators-only-import-orchestrators` rule once no flat orchestrator modules remain
- [x] Rewrite the new orchestrator, workspace, and version-control boundary rules to use the repository's standard "allow specific prefixes + deny `developer`" shape
- [x] Remove redundant deny entries where a broad `developer` deny already enforces the boundary
- [x] Narrow `developer.version_control` allows to only the exact orchestrator protocol modules still needed after the follow-through cleanup
- [ ] Re-evaluate whether `implementation-run-service-import-boundary` adds unique protection beyond the broader application import rules and remove it if it is duplicative
- [x] Audit `PublishedTaskBranch` and `PublishedTaskBranchView` and collapse them to the smallest useful contract, or remove them if task-owned branch data plus publication lookup already cover the reuse case
- [ ] Audit `ImplementationWorkspaceRunRequest` for fields that merely echo task-owned data and trim them once the task execution contract is settled
- [x] Keep a dedicated publication-store adapter only if publication lookup remains a distinct concern from the broader workspace registry after the simplification pass
- [ ] Re-run `uv run python -m harness.fitness.scripts.import_rules --config harness/policy/import_rules.yaml` and the targeted implementation-run tests after the simplification pass

### Notes

The goal here is to keep the final boundary small and obvious. The review feedback suggests some of the first-slice scaffolding may be transitional rather than permanent.

# Migration Sequence

1. update import rules first so the new subpackages and dependency direction are policy-compliant;
2. create `developer.orchestrators.loop` and `developer.orchestrators.runs` with final module paths;
3. move orchestration-facing protocols into `developer.orchestrators.runs`;
4. move workspace implementation-run planning into `developer.orchestrators.runs`;
5. update application composition to wire concrete implementations into the orchestrator;
6. migrate tests to the new ownership model;
7. push remaining task-owned branch and base-branch defaults into the task contract or runtime defaults that clearly own them;
8. simplify temporary import-rule and run-contract scaffolding added during the extraction; and
9. remove flat orchestrator imports and finish with tests and fitness checks green.

# Risks And Mitigations

- if `developer.orchestrators.runs` imports concrete infrastructure modules, the domain boundary will still be wrong; mitigate by moving the protocols into orchestrators and keeping implementations outside
- if application keeps a few planning helpers “for convenience,” orchestration will accumulate there again; mitigate by using a targeted import rule and delegation-focused tests
- if `developer.workspaces` or `developer.version_control` starts owning branch or publication policy, the orchestration split will blur; mitigate by keeping those packages focused on concrete operations and protocol implementations
- if the migration updates module paths incompletely, imports and fitness checks will fail; mitigate by migrating imports in the same change and validating with targeted tests
- if task-owned defaults such as base-branch preference remain duplicated in run models or application adapters, the boundary will keep feeling leaky; mitigate by making the task contract or runtime defaults the single source of truth and trimming duplicate fields afterward
- if temporary models and import rules added during the first extraction stay in place indefinitely, the final architecture will be harder to read than the one it replaced; mitigate by scheduling an explicit simplification pass before calling the refactor done

# Recommended Default Decision

Implement this as:

- two orchestrator subpackages: `developer.orchestrators.loop` and `developer.orchestrators.runs`;
- orchestrator-owned protocols in `src/developer/orchestrators/runs/protocols.py`;
- a new `ImplementationWorkspaceRunOrchestrator` in `src/developer/orchestrators/runs/implementation_workspace_run_orchestrator.py`;
- application-owned composition in `src/developer/application/implementation_run_runtime.py`;
- stronger import-boundary rules that enforce the dependency direction from infrastructure toward orchestrator-owned protocols;
- task-owned branch naming plus task-owned optional base-branch preference; and
- a final simplification pass that removes temporary rule and model scaffolding once the boundary is stable.

This keeps `developer.orchestrators` as the domain module while moving implementation-run orchestration to the layer that should own it.
