# Workspace Orchestration Plan

## Goal

Add a workspace abstraction around agent execution so the system can:

- provision an isolated workspace,
- start an implementation run inside that workspace,
- inspect active and past runs,
- keep the API generic enough for future remote/container execution.

This plan intentionally ignores cloud and Scaleway details for now. The first adapter is a local git worktree implementation.

The workspace layer must be agent-agnostic. `ImplementationAgent` is only the first consumer.

The orchestration logic for starting workspace-backed runs should live in `developer/orchestrators`, with dependency boundaries expressed as protocols so domain behavior can be tested with fakes and without adapter dependencies.

## Why Start Here

The current implementation loop is synchronous and intentionally small:

- `src/developer/orchestrators/implementation_agent.py` runs the implementation loop,
- `src/developer/orchestrators/protocols.py` already defines clean orchestration boundaries,
- agent adapters currently assume an optional local `path`, which is too narrow for future remote execution.

So the next step is not to make `ImplementationAgent` async. The next step is to add an outer orchestration layer that manages workspace sessions and run handles for any agent workflow.

## Target Architecture

Keep existing agent workflows as the inner workers.

For the first implementation, `ImplementationAgent` is the only workflow wired through this system, but the workspace contracts should not be shaped around implementation-specific behavior.

Add a new outer layer:

```python
workspace = workspace_provider.create(spec)
run = workspace_runner.start_run(
    workspace_id=workspace.id,
    request=RunRequest(agent_kind="implementation", context={}),
)
```

That outer layer is responsible for:

- creating and tracking workspaces,
- starting runs,
- exposing run status,
- persisting run metadata,
- adapting a workspace session into something an agent backend can execute against.

## Scope of the First Milestone

Implement only:

- a new `developer/workspaces` module,
- protocol interfaces and domain models,
- a local `git worktree` workspace provider,
- a local synchronous runner that still returns async-ready run handles,
- a simple file-backed registry for runs and workspaces.

Do not implement yet:

- remote/container execution,
- branch-diff reviewers,
- per-iteration commits,
- rich completion logic,
- queue workers or true background job execution.

## Module Layout

Planned files:

```text
src/developer/workspaces/__init__.py
src/developer/workspaces/models.py
src/developer/workspaces/settings.py
src/developer/workspaces/services/file_registry.py
src/developer/workspaces/adapters/git_worktree_provider.py
src/developer/workspaces/adapters/local_process_runner.py
src/developer/orchestrators/workspace_protocols.py
src/developer/orchestrators/workspace_run_orchestrator.py
```

Optional CLI wiring later:

```text
No dedicated workspace CLI needed for the first version.
```

## Domain Models

Start with small, explicit models.

Example:

```python
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    DESTROYED = "destroyed"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["local_path"]
    location: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    repo_path: str
    base_branch: str = "main"
    task_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    provider: str
    status: WorkspaceStatus
    execution_target: ExecutionTarget
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_kind: str
    context: dict[str, Any] = Field(default_factory=dict)


class RunHandle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    workspace_id: str
    status: RunStatus
    agent_kind: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    latest_message: str | None = None
    result_summary: str | None = None
```

Why this shape:

- `ExecutionTarget` avoids baking `path` into the core interface,
- the first adapter can still use `kind="local_path"`,
- later adapters can add other execution target kinds without changing orchestrator flow,
- `task_id` gives the provider enough context to create a unique branch/workspace per task run,
- `RunRequest.agent_kind` stays open so other agent workflows can run in workspaces later.

If stronger typing is needed later, `agent_kind` can evolve into a small enum without coupling the workspace module to one specific workflow.

## Orchestrator Protocols

The outer orchestration domain should depend on protocols, not adapters.

Example:

```python
from typing import Protocol

from developer.workspaces.models import RunHandle, RunRequest, WorkspaceSession, WorkspaceSpec


class WorkspaceProvider(Protocol):
    def create(self, spec: WorkspaceSpec) -> WorkspaceSession: ...

    def get(self, workspace_id: str) -> WorkspaceSession: ...

    def list(self) -> list[WorkspaceSession]: ...

    def destroy(self, workspace_id: str) -> None: ...


class WorkspaceRunRegistry(Protocol):
    def save_workspace(self, workspace: WorkspaceSession) -> None: ...

    def save_run(self, run: RunHandle) -> None: ...

    def get_workspace(self, workspace_id: str) -> WorkspaceSession: ...

    def get_run(self, run_id: str) -> RunHandle: ...

    def list_runs(self, workspace_id: str | None = None) -> list[RunHandle]: ...


class WorkspaceRunner(Protocol):
    def start_run(self, workspace_id: str, request: RunRequest) -> RunHandle: ...

    def get_run(self, run_id: str) -> RunHandle: ...

    def list_runs(self, workspace_id: str | None = None) -> list[RunHandle]: ...

    def cancel_run(self, run_id: str) -> None: ...
```

These protocols should live under `developer/orchestrators`, not `developer/workspaces`, because they define domain orchestration boundaries rather than provider-specific behavior.

## Outer Orchestration Service

Add one service that coordinates provider + runner + registry.

Example:

```python
from developer.orchestrators.workspace_protocols import WorkspaceProvider, WorkspaceRunner
from developer.workspaces.models import RunHandle, RunRequest, WorkspaceSession, WorkspaceSpec


class WorkspaceOrchestrator:
    def __init__(
        self,
        workspace_provider: WorkspaceProvider,
        workspace_runner: WorkspaceRunner,
    ) -> None:
        self._workspace_provider = workspace_provider
        self._workspace_runner = workspace_runner

    def run_in_workspace(
        self,
        workspace_spec: WorkspaceSpec,
        request: RunRequest,
    ) -> tuple[WorkspaceSession, RunHandle]:
        workspace = self._workspace_provider.create(workspace_spec)
        run = self._workspace_runner.start_run(workspace.id, request)
        return workspace, run
```

This service should stay small. It is a composition point, not a provider itself.

Important: this service should orchestrate generic agent runs in workspaces. It should not embed implementation-specific assumptions beyond delegating to a selected workflow runner.

This service should also live in `developer/orchestrators`, since it is pure domain orchestration and should be testable using protocol fakes only.

## Agent Workflow Boundary

To keep workspaces independent from any specific agent, introduce a small protocol for workspace-runnable agent workflows near the orchestration edge.

Example:

```python
from typing import Protocol


class WorkspaceRunnableAgent(Protocol):
    def run(self, request: RunRequest, workspace: WorkspaceSession) -> str:
        ...
```

And a resolver:

```python
class WorkspaceRunnableAgentResolver(Protocol):
    def resolve(self, agent_kind: str) -> WorkspaceRunnableAgent:
        ...
```

Then the local workspace runner can stay generic and delegate based on `request.agent_kind`.

For the first cut:

- `agent_kind="implementation"` resolves to a workspace-runnable implementation agent adapter,
- later agent kinds can reuse the same workspace machinery without changing the workspace module.

This protocol is intentionally higher-level than the existing inner orchestrator protocols in `src/developer/orchestrators/protocols.py`.

- the inner protocols model dependencies of a specific workflow such as `PromptBuilder` and `GateRunner`
- `WorkspaceRunnableAgent` models a complete workflow that can be executed inside a workspace

That separation keeps the workspace layer small while still letting individual agents have their own internal dependency graphs.

## Registry Design

Because the user wants to inspect active workspaces and progress later, add persistence early.

Recommendation:

- use a file-backed registry in a local state directory,
- store one JSON file per workspace and per run,
- keep it intentionally dumb for the first cut.

Example:

```python
import json
from pathlib import Path

from developer.workspaces.models import RunHandle, WorkspaceSession


class FileWorkspaceRegistry:
    def __init__(self, state_dir: Path) -> None:
        self._state_dir = state_dir
        self._workspaces_dir = state_dir / "workspaces"
        self._runs_dir = state_dir / "runs"
        self._workspaces_dir.mkdir(parents=True, exist_ok=True)
        self._runs_dir.mkdir(parents=True, exist_ok=True)

    def save_workspace(self, workspace: WorkspaceSession) -> None:
        path = self._workspaces_dir / f"{workspace.id}.json"
        path.write_text(workspace.model_dump_json(indent=2))

    def save_run(self, run: RunHandle) -> None:
        path = self._runs_dir / f"{run.id}.json"
        path.write_text(run.model_dump_json(indent=2))
```

Later this can move to sqlite without changing the protocol.

Note: the file registry implementation can still live in `developer/workspaces/services`, but it should implement an orchestrator-owned protocol.

## Local Git Worktree Provider

The first provider should manage a local worktree checkout and expose it as a generic execution target.

Responsibilities:

- generate workspace id,
- create a unique branch name for the task on the fly,
- create a git worktree under a configured directory,
- record metadata such as branch name and worktree path,
- return `WorkspaceSession(status=READY)`.

Example skeleton:

```python
from datetime import datetime, UTC
from pathlib import Path
from uuid import uuid4
import subprocess

from developer.workspaces.models import ExecutionTarget, WorkspaceSession, WorkspaceSpec, WorkspaceStatus


class GitWorktreeWorkspaceProvider:
    def __init__(self, workspaces_root: Path) -> None:
        self._workspaces_root = workspaces_root
        self._workspaces_root.mkdir(parents=True, exist_ok=True)

    def create(self, spec: WorkspaceSpec) -> WorkspaceSession:
        workspace_id = uuid4().hex
        branch_name = f"developer/{spec.task_id}/{workspace_id}"
        worktree_path = self._workspaces_root / workspace_id

        subprocess.run(
            [
                "git",
                "worktree",
                "add",
                "-b",
                branch_name,
                str(worktree_path),
                spec.base_branch,
            ],
            cwd=spec.repo_path,
            check=True,
            capture_output=True,
            text=True,
        )

        return WorkspaceSession(
            id=workspace_id,
            provider="git_worktree",
            status=WorkspaceStatus.READY,
            created_at=datetime.now(UTC),
            execution_target=ExecutionTarget(
                kind="local_path",
                location=str(worktree_path),
                metadata={"repo_path": spec.repo_path},
            ),
            metadata={
                "branch_name": branch_name,
                "base_branch": spec.base_branch,
                "worktree_path": str(worktree_path),
            },
        )
```

Destroy can come in the same adapter later:

```python
subprocess.run(
    ["git", "worktree", "remove", str(worktree_path)],
    cwd=repo_path,
    check=True,
    capture_output=True,
    text=True,
)
```

## Adapting Execution Targets into Agent Runners

Do not pass `path` around at the orchestration boundary. Translate from `ExecutionTarget` to the existing agent selection layer near the adapter edge.

Suggested helper:

```python
from developer.agents.select_agent_service import SelectAgentService
from developer.workspaces.models import ExecutionTarget


class AgentFactory:
    def __init__(self) -> None:
        self._agent_service = SelectAgentService()

    def for_execution_target(self, target: ExecutionTarget):
        if target.kind == "local_path":
            return self._agent_service.select_agent(path=target.location)
        raise ValueError(f"Unsupported execution target kind: {target.kind}")
```

This keeps the `path` assumption localized and easy to replace later.

## Local Process Runner

The first runner can be synchronous internally while still returning a persisted run handle.

Flow:

- load workspace from registry,
- mark run as `pending`, then `running`,
- resolve an agent workflow by `request.agent_kind`,
- run that workflow synchronously,
- save final run state.

Example:

```python
from datetime import UTC, datetime
from uuid import uuid4

from developer.workspaces.models import RunHandle, RunRequest, RunStatus


class LocalProcessWorkspaceRunner:
    def __init__(self, registry, agent_resolver) -> None:
        self._registry = registry
        self._agent_resolver = agent_resolver

    def start_run(self, workspace_id: str, request: RunRequest) -> RunHandle:
        workspace = self._registry.get_workspace(workspace_id)

        run = RunHandle(
            id=uuid4().hex,
            workspace_id=workspace_id,
            status=RunStatus.PENDING,
            agent_kind=request.agent_kind,
            latest_message="Run created",
        )
        self._registry.save_run(run)

        run.status = RunStatus.RUNNING
        run.started_at = datetime.now(UTC)
        run.latest_message = "Implementation run started"
        self._registry.save_run(run)

        try:
            agent = self._agent_resolver.resolve(request.agent_kind)
            result_summary = agent.run(request=request, workspace=workspace)

            run.status = RunStatus.SUCCEEDED
            run.finished_at = datetime.now(UTC)
            run.latest_message = f"Run finished with status={run.status.value}"
            run.result_summary = result_summary
            self._registry.save_run(run)
            return run
        except Exception as exc:
            run.status = RunStatus.FAILED
            run.finished_at = datetime.now(UTC)
            run.latest_message = str(exc)
            self._registry.save_run(run)
            raise
```

Example implementation adapter for the protocol:

```python
from developer.orchestrators.implementation_agent import ImplementationAgent
from developer.prompts.builder import OrchestratorPromptBuilder
from developer.quality.services import CheckGateRunner
from developer.tasks.implementation_judge import ImplementationJudge


class WorkspaceRunnableImplementationAgent:
    def __init__(self, agent_factory) -> None:
        self._agent_factory = agent_factory

    def run(self, request: RunRequest, workspace: WorkspaceSession) -> str:
        agent_runner = self._agent_factory.for_execution_target(
            workspace.execution_target
        )
        outcome = ImplementationAgent(
            prompt_builder=OrchestratorPromptBuilder(),
            agent_runner=agent_runner,
            gate_runner=CheckGateRunner(),
            completion_judge=ImplementationJudge(),
        ).run()
        if outcome.status != "success":
            raise RuntimeError(f"implementation failed after {outcome.iterations} iterations")
        return f"iterations={outcome.iterations}"
```

This is enough to validate the design before introducing threads, workers, or queues.

## Configuration

Use the existing config pattern: one settings model per section via `ConfigService`.

Suggested first config shape:

```toml
[workspaces]
default_provider = "git_worktree"
state_dir = ".developer/state"

[workspaces.git_worktree]
root_dir = ".developer/workspaces"
```

Suggested settings models:

```python
from pydantic import BaseModel, ConfigDict, Field


class GitWorktreeSettings(BaseModel):
    root_dir: str = Field(default=".developer/workspaces")

    model_config = ConfigDict(extra="forbid")


class WorkspaceSettings(BaseModel):
    default_provider: str = Field(default="git_worktree")
    state_dir: str = Field(default=".developer/state")
    git_worktree: GitWorktreeSettings = Field(default_factory=GitWorktreeSettings)

    model_config = ConfigDict(extra="forbid")
```

Note: `ConfigService` currently loads a single TOML section directly, so nested subsection parsing may require either:

1. flattening the first version of config, or
2. extending config loading slightly so `[workspaces.git_worktree]` becomes available to the `workspaces` settings model.

Recommendation: keep implementation simple and flatten the first version if needed:

```toml
[workspaces]
default_provider = "git_worktree"
state_dir = ".developer/state"
git_worktree_root_dir = ".developer/workspaces"
```

Branch names should not be configured globally. They should be derived per task/run by the provider so multiple tasks can run concurrently against the same repo without collisions.

Then normalize into nested models later.

## CLI Shape

The first cut should not add standalone workspace commands. Workspace behavior should be an implementation detail behind the existing command.

Only one end-to-end flow is required:

```text
developer implementation run
```

If workspaces are configured, that command should:

- create a workspace,
- start a run inside it,
- print workspace id and run id when useful,
- optionally wait for completion for now.

If workspaces are not configured, the command can keep the current direct execution path until the workspace path fully replaces it.

Example CLI wiring:

```python
@app.command()
def run() -> None:
    if workspace_mode_enabled():
        workspace, run = build_workspace_orchestrator().run_in_workspace(
            WorkspaceSpec(
                provider="git_worktree",
                repo_path=".",
                base_branch="main",
                task_id="task-123",
            ),
            RunRequest(agent_kind="implementation", context={}),
        )
        typer.echo(f"workspace={workspace.id} run={run.id} status={run.status.value}")
        return

    outcome = ImplementationAgent(
        prompt_builder=OrchestratorPromptBuilder(),
        agent_runner=SelectAgentService().select_agent(),
        gate_runner=CheckGateRunner(),
        completion_judge=ImplementationJudge(),
    ).run()
    typer.echo(f"status={outcome.status} iterations={outcome.iterations}")
```

## Tests

Focus on narrow, executable contracts.

Add tests for:

- orchestrator domain tests using fake `WorkspaceProvider`, `WorkspaceRunner`, and registry implementations,
- `WorkspaceSession` and `RunHandle` model validation,
- `GitWorktreeWorkspaceProvider.create()` creating a worktree and recording metadata,
- file registry save/load/list behavior,
- runner state transitions: `pending -> running -> succeeded|failed`,
- a real integration test that modifies multiple files inside an actual git worktree,
- orchestration service wiring,
- CLI smoke test for the new flow.

Example test skeleton:

```python
def test_runner_marks_run_succeeded(tmp_path):
    registry = FileWorkspaceRegistry(tmp_path)
    workspace = WorkspaceSession(...)
    registry.save_workspace(workspace)

    runner = LocalProcessWorkspaceRunner(
        registry=registry,
        agent_resolver=FakeAgentResolver(),
    )

    run = runner.start_run(
        workspace_id=workspace.id,
        request=RunRequest(agent_kind="implementation", context={}),
    )

    assert run.status == RunStatus.SUCCEEDED
    assert run.started_at is not None
    assert run.finished_at is not None
```

Add one higher-value integration test that uses a real git workspace and verifies real file changes inside it.

That test should:

- create a temporary git repo,
- create and commit a small starting file set,
- create a real git worktree workspace,
- run a fake workflow runner that writes or edits multiple files inside the worktree,
- assert the original repo working tree was not modified directly,
- assert the workspace checkout contains the expected file changes,
- assert git status inside the workspace shows the expected modifications.

Example skeleton:

```python
def test_workspace_run_modifies_files_in_isolated_worktree(tmp_path):
    repo = init_git_repo(tmp_path / "repo")
    commit_file(repo / "app.py", "print('before')\n")
    commit_file(repo / "README.md", "start\n")

    provider = GitWorktreeWorkspaceProvider(tmp_path / "workspaces")
    registry = FileWorkspaceRegistry(tmp_path / "state")

    workspace = provider.create(
        WorkspaceSpec(
            provider="git_worktree",
            repo_path=str(repo),
            base_branch="main",
            task_id="task-123",
        )
    )
    registry.save_workspace(workspace)

    class FakeWorkspaceRunnableAgent:
        def run(self, request, workspace):
            root = Path(workspace.execution_target.location)
            (root / "app.py").write_text("print('after')\n")
            (root / "new_file.txt").write_text("created\n")
            return "updated 2 files"

    runner = LocalProcessWorkspaceRunner(
        registry=registry,
        agent_resolver=StaticResolver(FakeWorkspaceRunnableAgent()),
    )

    run = runner.start_run(
        workspace_id=workspace.id,
        request=RunRequest(agent_kind="fake", context={}),
    )

    assert run.status == RunStatus.SUCCEEDED
    assert (repo / "new_file.txt").exists() is False
    assert (repo / "app.py").read_text() == "print('before')\n"

    workspace_root = Path(workspace.execution_target.location)
    assert (workspace_root / "app.py").read_text() == "print('after')\n"
    assert (workspace_root / "new_file.txt").read_text() == "created\n"
```

This test is important because it validates the main promise of the feature: agent work happens in an isolated workspace, not in the primary checkout.

The overall testing split should be:

- orchestrator domain tests: pure fakes, no git, no adapter dependencies,
- workspace adapter tests: concrete provider/runner behavior,
- one real integration test: end-to-end isolated worktree modification.

## Phased Execution Plan

### Phase 1: Models and Protocols

Create:

- `src/developer/workspaces/models.py`
- `src/developer/orchestrators/workspace_protocols.py`
- `src/developer/workspaces/__init__.py`

Definition of done:

- models are explicit and validated,
- protocols are provider-agnostic,
- no `path` requirement exists in the protocol layer.

### Phase 2: Registry and Settings

Create:

- `src/developer/workspaces/settings.py`
- `src/developer/workspaces/services/file_registry.py`

Definition of done:

- workspaces and runs can be persisted and listed,
- configuration can select `git_worktree` as default provider.

### Phase 3: Git Worktree Provider

Create:

- `src/developer/workspaces/adapters/git_worktree_provider.py`

Definition of done:

- provider creates an isolated worktree,
- session metadata records task-derived branch and checkout path,
- destroy path is defined even if CLI support comes later.

### Phase 4: Local Runner

Create:

- `src/developer/workspaces/adapters/local_process_runner.py`
- `src/developer/orchestrators/workspace_run_orchestrator.py`

Definition of done:

- generic workspace-runnable agents can run inside a workspace,
- `ImplementationAgent` is wired as the first adapter to that protocol,
- run handles are persisted with status transitions,
- agent selection is adapted from `ExecutionTarget`.

### Phase 5: CLI Integration

Update:

- `src/developer/presentation/commands/implementation.py`

Definition of done:

- `implementation run` uses workspace orchestration when workspaces are configured,
- no dedicated `workspace` command group is introduced,
- CLI still supports the current direct path until workspace mode becomes the default.

## Key Design Rules

- Keep `ImplementationAgent` unchanged as long as possible.
- Keep orchestration logic in `developer/orchestrators` and adapter logic in `developer/workspaces`.
- Do not make `path` part of workspace protocols.
- Translate `ExecutionTarget -> agent adapter configuration` at the edge.
- Keep workspace orchestration independent of any one agent workflow.
- Keep workspace lifecycle separate from run lifecycle.
- Add persistence before true async execution.
- Make the first adapter local and boring; optimize for correctness and inspectability.
- Generate branch names per task/run inside the provider; do not configure them globally.
- Add at least one real integration test that changes multiple files inside an actual worktree.

## Follow-Up After This Plan

Once the local git worktree flow works end-to-end, the next design step should be one of:

1. add detached/background execution with the same `RunHandle` API,
2. add VCS primitives for iteration commits and branch diff inspection,
3. enable reviewer flows using workspace-aware diff inputs.

That ordering keeps the architecture open for remote workspaces without forcing remote execution too early.
