# Workspace Execution Boundary Plan

## Goal

Move execution-context setup out of the application layer and into the workspace module so that:

- execution behavior follows `ExecutionTarget.kind`;
- workspace provisioning stays separate from workflow execution; and
- future targets such as containers can replace local `cwd` switching without changing application orchestration.

## Checklist

### Package Structure

- [ ] Make `src/engineeringagent/workspaces/models.py` the canonical workspace models module
- [ ] Make `src/engineeringagent/workspaces/protocols.py` the canonical workspace protocols module
- [ ] Move `WorkspaceRunOrchestrator` to `src/engineeringagent/workspaces/services/workspace_run_orchestrator.py`
- [ ] Keep temporary compatibility shims in old orchestrator paths during migration

### Workspace Runtime

- [ ] Add `src/engineeringagent/workspaces/adapters/local_path_execution_adapter.py`
- [ ] Add `src/engineeringagent/workspaces/adapters/default_execution_adapter_resolver.py`
- [ ] Update `LocalProcessWorkspaceRunner` to resolve execution adapters from `ExecutionTarget`
- [ ] Move local `cwd` ownership out of application and into the local execution adapter

### Application Bridges

- [ ] Add `src/engineeringagent/application/workspace_bridges.py`
- [ ] Move `LocalExecutionAgentFactory` into `engineeringagent.application.workspace_bridges`
- [ ] Move `WorkspaceRunnableImplementationAgent` into `engineeringagent.application.workspace_bridges`
- [ ] Move `DefaultWorkspaceRunnableAgentResolver` into `engineeringagent.application.workspace_bridges`
- [ ] Reduce `src/engineeringagent/application/workspace_runtime.py` to composition-only logic

### Import Boundaries

- [ ] Update `harness/policy/import_rules.yaml` to enforce that `engineeringagent.workspaces` does not import from `engineeringagent.orchestrators`
- [ ] Update `harness/policy/import_rules.yaml` to enforce that `engineeringagent.workspaces` does not import from `engineeringagent.application`
- [ ] Update `harness/policy/import_rules.yaml` to enforce that `engineeringagent.orchestrators` does not import from `engineeringagent.workspaces`
- [ ] Update `harness/policy/import_rules.yaml` to enforce that `engineeringagent.orchestrators` does not import from `engineeringagent.application`
- [ ] Verify the import-boundary fitness check covers the new rules
- [ ] Remove temporary compatibility shims after imports are fully migrated

### Tests

- [ ] Add `tests/workspaces/adapters/test_local_path_execution_adapter.py`
- [ ] Update `tests/workspaces/adapters/test_local_process_runner.py`
- [ ] Update `tests/application/test_workspace_runtime.py`
- [ ] Add `tests/application/test_workspace_bridges.py`
- [ ] Update `tests/workspaces/adapters/test_git_worktree_provider.py`
- [ ] Update `tests/workspaces/test_real_integration.py`
- [ ] Run the relevant test suite after each migration phase
- [ ] Run the import-boundary fitness check after package-boundary changes

## Problem In The Current Design

Today `WorkspaceRunnableImplementationAgent` in `src/engineeringagent/application/workspace_runtime.py` changes the process working directory before calling the implementation workflow.

That creates two problems:

- the application layer owns local execution mechanics; and
- the execution behavior is coupled to one workflow wrapper instead of to the workspace runtime itself.

The current `GitWorktreeWorkspaceProvider` is only a provisioning adapter. It creates a worktree and returns `ExecutionTarget(kind="local_path")`. The `os.chdir(...)` behavior is therefore not really `git_worktree` behavior; it is `local_path` execution behavior.

## Package Ownership And Import Rules

This plan should follow a stricter package structure.

### `engineeringagent.orchestrators`

Owns domain workflow logic for the implementation loop.

Examples:

- `ImplementationAgent`
- prompt, gate, and completion protocols
- orchestrator outcome and iteration models

Import rule:

- `engineeringagent.orchestrators` must not import from `engineeringagent.workspaces` or `engineeringagent.application`.

### `engineeringagent.workspaces`

Owns the workspace subsystem and execution environment.

Examples:

- workspace lifecycle models and protocols
- execution targets
- providers, runners, registries, and execution adapters
- workspace-backed run orchestration

Import rule:

- `engineeringagent.workspaces` must not import from `engineeringagent.orchestrators` or `engineeringagent.application`.

### `engineeringagent.application`

Owns use-case composition and bridge adapters between subsystems.

Examples:

- wiring the implementation workflow into the workspace runtime
- selecting the concrete agent backend for a workspace-backed implementation run
- composing config, workspaces, and orchestrators into the CLI use case

Import rule:

- `engineeringagent.application` may import from both `engineeringagent.orchestrators` and `engineeringagent.workspaces`.

This means the application layer should be the place that adapts the implementation-domain workflow into a workspace-runnable shape.

## Recommendation

Keep provisioning and execution as separate concerns inside `engineeringagent.workspaces`, and let `engineeringagent.application` bridge the implementation workflow into that runtime.

Recommended rule:

- `WorkspaceProvider` decides what workspace exists and what `ExecutionTarget` it exposes.
- `WorkspaceExecutionAdapter` decides how code runs for that target.
- `engineeringagent.application` decides which domain workflow is exposed as a `WorkspaceRunnableAgent`.

Under this design, a git-worktree workspace is not the same object as local execution, but it naturally resolves to local execution because it returns `ExecutionTarget(kind="local_path")`.

This is a better fit than putting two methods on one provider object, and it preserves the rule that `engineeringagent.workspaces` does not need to know anything about the implementation orchestrator domain.

## Why Not Use One Object For Both

Combining provisioning and execution into the same adapter looks attractive at first, but it creates avoidable coupling.

### Drawbacks Of A Single Combined Object

- different providers can share the same execution strategy;
- one provider may evolve to support a different execution target later;
- runner logic becomes harder to test independently from provisioning; and
- the provider interface stops meaning "provision a workspace" and becomes a mixed lifecycle object.

Examples:

- `git_worktree -> local_path` is the current pairing;
- a future `local_copy -> local_path` would want the same execution adapter;
- a future `git_worktree -> container` should be possible without redefining the provider contract; and
- a future `remote_repo_clone -> container` could reuse the same container execution adapter.

## Better Approach: Paired By Data, Not By Class

The clean boundary is:

1. provider creates `WorkspaceSession`;
2. provider sets `workspace.execution_target`;
3. runner resolves an execution adapter from `execution_target.kind`; and
4. the execution adapter runs the workflow inside that target.

This still gives you the coupling you want, but via explicit data instead of a hard-wired combined class.

If configuration convenience is important, add a higher-level "workspace backend" composition layer that wires a provider plus its expected execution target defaults. That can be a factory concern without merging the runtime responsibilities into one protocol.

## Proposed Architecture

### 1. Add Execution Adapter Protocol In The Workspace Module

Add a workspace-owned protocol for target-specific execution.

Suggested shape:

```python
class WorkspaceExecutionAdapter(Protocol):
    def run(
        self,
        workspace: WorkspaceSession,
        request: RunRequest,
        agent: WorkspaceRunnableAgent,
    ) -> WorkspaceRunnableResult:
        ...
```

And a resolver:

```python
class WorkspaceExecutionAdapterResolver(Protocol):
    def resolve(self, target: ExecutionTarget) -> WorkspaceExecutionAdapter:
        ...
```

This keeps the abstraction at the right level: the adapter owns how execution happens for the target, not just how a context manager is entered.

### 2. Move Local `cwd` Handling Into A Local Execution Adapter

Create a local adapter in the workspace package, for example:

- `src/engineeringagent/workspaces/adapters/local_path_execution_adapter.py`

Responsibilities:

- validate that `ExecutionTarget.kind == "local_path"`;
- temporarily switch into `workspace.execution_target.location`; and
- call `agent.run(request=request, workspace=workspace)` inside that context.

The existing `_working_directory()` helper should move beside this adapter, because it is local execution machinery.

### 3. Update `LocalProcessWorkspaceRunner`

`LocalProcessWorkspaceRunner` should stop calling the workflow directly.

New flow:

1. load workspace;
2. resolve `WorkspaceRunnableAgent` from `agent_kind`;
3. resolve `WorkspaceExecutionAdapter` from `workspace.execution_target`; and
4. delegate execution to that adapter.

This makes the runner the composition point for:

- what workflow to run; and
- how to run it in the target.

### 4. Keep `GitWorktreeWorkspaceProvider` Focused On Provisioning

Do not move `cwd` logic into `GitWorktreeWorkspaceProvider`.

Its responsibilities should remain:

- create worktree;
- record branch and repo metadata;
- return `ExecutionTarget(kind="local_path")`; and
- destroy the worktree later.

This preserves a clean meaning for `WorkspaceProvider`.

### 5. Simplify `WorkspaceRunnableImplementationAgent`

After the change, `WorkspaceRunnableImplementationAgent` should not know about local process execution details.

It should only:

- build the implementation agent for the resolved execution target if needed; and
- return `WorkspaceRunnableResult` based on the workflow outcome.

It should no longer call `os.chdir(...)` directly.

## Near-Term Scope

For this change, keep ambient `cwd` switching as the actual mechanism for local execution.

Do not try to make every dependency path-explicit yet.

Reason:

- config loading, prompts, and some command execution still rely on the process working directory today.

So the first refactor should only move ownership of `cwd` switching into the workspace runtime layer.

## Follow-Up Direction

Later, if you want a cleaner non-global runtime model, you can incrementally move from ambient `cwd` to explicit path-aware dependencies.

That would include:

- passing workspace path into agent adapters;
- making config loading explicitly path-scoped;
- making quality command execution explicitly path-scoped; and
- reducing reliance on process-global `os.chdir(...)`.

That is a useful second phase, but it should not block this boundary cleanup.

## Suggested File Moves And New Files

### Move Existing Files

- move `src/engineeringagent/orchestrators/workspace_models.py` to `src/engineeringagent/workspaces/models.py`
- move `src/engineeringagent/orchestrators/workspace_protocols.py` to `src/engineeringagent/workspaces/protocols.py`
- move `src/engineeringagent/orchestrators/workspace_run_orchestrator.py` to `src/engineeringagent/workspaces/services/workspace_run_orchestrator.py`

### Add New Files

- `src/engineeringagent/workspaces/adapters/local_path_execution_adapter.py`
- `src/engineeringagent/workspaces/adapters/default_execution_adapter_resolver.py`
- `src/engineeringagent/application/workspace_bridges.py`
- `tests/workspaces/adapters/test_local_path_execution_adapter.py`
- `harness/policy/import_rules.yaml`

### Update Existing Files

- `src/engineeringagent/workspaces/adapters/local_process_runner.py`
- `src/engineeringagent/workspaces/adapters/git_worktree_provider.py`
- `src/engineeringagent/workspaces/adapters/__init__.py`
- `src/engineeringagent/workspaces/services/file_registry.py`
- `src/engineeringagent/application/workspace_runtime.py`
- `src/engineeringagent/application/services/implementation_run_service.py`
- `tests/application/test_workspace_runtime.py`
- `tests/workspaces/adapters/test_local_process_runner.py`
- `tests/workspaces/adapters/test_git_worktree_provider.py`
- `tests/workspaces/test_real_integration.py`
- `harness/fitness/tests/test_import_rules.py` when the generic fitness behavior needs coverage for the new rule shape

After this refactor, `src/engineeringagent/workspaces/models.py` and `src/engineeringagent/workspaces/protocols.py` become the source of truth rather than re-export shims.

## Concrete Code Changes

### `src/engineeringagent/workspaces/models.py`

Replace the current re-export file with the concrete workspace models moved from `src/engineeringagent/orchestrators/workspace_models.py`.

This file should directly define:

- `WorkspaceStatus`
- `RunStatus`
- `ExecutionTarget`
- `WorkspaceSpec`
- `WorkspaceSession`
- `RunRequest`
- `RunHandle`
- `WorkspaceRunnableResult`

After the move, update imports across the repo to use `engineeringagent.workspaces.models` as the canonical module.

### `src/engineeringagent/workspaces/protocols.py`

Replace the current split by moving the contents of `src/engineeringagent/orchestrators/workspace_protocols.py` here and extending it with the new execution adapter boundary.

This file should own:

- `WorkspaceProvider`
- `WorkspaceRunRegistry`
- `WorkspaceRunnableAgent`
- `WorkspaceRunnableAgentResolver`
- `WorkspaceRunner`
- `WorkspaceExecutionAdapter`
- `WorkspaceExecutionAdapterResolver`

Suggested addition:

```python
from typing import Protocol

class WorkspaceExecutionAdapter(Protocol):
    def run(
        self,
        workspace: WorkspaceSession,
        request: RunRequest,
        agent: WorkspaceRunnableAgent,
    ) -> WorkspaceRunnableResult:
        ...


class WorkspaceExecutionAdapterResolver(Protocol):
    def resolve(self, target: ExecutionTarget) -> WorkspaceExecutionAdapter:
        ...
```

This lets `engineeringagent.workspaces` fully own the workspace subsystem without importing the implementation-domain package.

### `src/engineeringagent/workspaces/services/workspace_run_orchestrator.py`

Move `WorkspaceRunOrchestrator` here unchanged except for import paths.

Why move it now:

- it coordinates workspace provider plus workspace runner only;
- it has no dependency on implementation-domain concepts; and
- it fits the same subsystem as the other workspace runtime services.

### `src/engineeringagent/workspaces/adapters/local_path_execution_adapter.py`

Move the current `_working_directory()` helper here and wrap the runnable agent call.

Suggested shape:

```python
import os
from contextlib import contextmanager
from pathlib import Path

from engineeringagent.workspaces.protocols import (
    WorkspaceExecutionAdapter,
    WorkspaceRunnableAgent,
)
from engineeringagent.workspaces.models import (
    RunRequest,
    WorkspaceRunnableResult,
    WorkspaceSession,
)


class LocalPathWorkspaceExecutionAdapter(WorkspaceExecutionAdapter):
    def run(
        self,
        workspace: WorkspaceSession,
        request: RunRequest,
        agent: WorkspaceRunnableAgent,
    ) -> WorkspaceRunnableResult:
        workspace_root = Path(workspace.execution_target.location)
        if workspace.execution_target.kind != "local_path":
            raise ValueError(
                "LocalPathWorkspaceExecutionAdapter requires local_path target"
            )
        with _working_directory(workspace_root):
            return agent.run(request=request, workspace=workspace)


@contextmanager
def _working_directory(path: Path):
    previous_cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous_cwd)
```

This is the smallest move that places local process behavior in the workspace layer.

### `src/engineeringagent/workspaces/adapters/default_execution_adapter_resolver.py`

Add the default mapping from `ExecutionTarget.kind` to adapter.

Suggested shape:

```python
from engineeringagent.workspaces.protocols import (
    WorkspaceExecutionAdapter,
    WorkspaceExecutionAdapterResolver,
)
from engineeringagent.workspaces.models import ExecutionTarget

from .local_path_execution_adapter import LocalPathWorkspaceExecutionAdapter


class DefaultWorkspaceExecutionAdapterResolver(
    WorkspaceExecutionAdapterResolver
):
    def resolve(self, target: ExecutionTarget) -> WorkspaceExecutionAdapter:
        if target.kind == "local_path":
            return LocalPathWorkspaceExecutionAdapter()
        raise ValueError(f"Unsupported execution target kind: {target.kind}")
```

This is where future container support would plug in.

### `src/engineeringagent/workspaces/adapters/local_process_runner.py`

Change the runner constructor so it accepts an execution-adapter resolver.

Suggested update:

```python
from engineeringagent.workspaces.protocols import (
    WorkspaceExecutionAdapterResolver,
)


class LocalProcessWorkspaceRunner:
    def __init__(
        self,
        registry: WorkspaceRunRegistry,
        agent_resolver: WorkspaceRunnableAgentResolver,
        execution_adapter_resolver: WorkspaceExecutionAdapterResolver,
    ) -> None:
        self._registry = registry
        self._agent_resolver = agent_resolver
        self._execution_adapter_resolver = execution_adapter_resolver
```

And in `start_run()` replace the direct agent call:

```python
agent = self._agent_resolver.resolve(request.agent_kind)
execution_adapter = self._execution_adapter_resolver.resolve(
    workspace.execution_target
)
result = execution_adapter.run(
    workspace=workspace,
    request=request,
    agent=agent,
)
```

This is the core runtime change.

Also update this file so it imports workspace protocols only from `engineeringagent.workspaces.protocols`, not from `engineeringagent.orchestrators.workspace_protocols`.

### `src/engineeringagent/workspaces/adapters/git_worktree_provider.py`

Update imports so the provider depends only on `engineeringagent.workspaces.models` and `engineeringagent.workspaces.protocols`.

No behavior change is needed beyond import cleanup and keeping `ExecutionTarget(kind="local_path")` as the provider output.

### `src/engineeringagent/workspaces/services/file_registry.py`

This file is already in the right package.

Only update imports if needed so the registry depends on the moved canonical workspace models and protocols.

### `src/engineeringagent/application/workspace_bridges.py`

Add an application-owned bridge module.

This is where the implementation-domain workflow should be adapted into the workspace runtime, because `engineeringagent.workspaces` must not import from `engineeringagent.orchestrators`.

Move or place these classes here:

- `LocalExecutionAgentFactory`
- `WorkspaceRunnableImplementationAgent`
- `DefaultWorkspaceRunnableAgentResolver`

These classes should implement workspace-owned protocols but remain application-owned code.

Suggested imports:

```python
from engineeringagent.agents.protocol import AgentProtocol
from engineeringagent.agents.select_agent_service import SelectAgentService
from engineeringagent.orchestrators.implementation_agent import ImplementationAgent
from engineeringagent.workspaces.models import (
    ExecutionTarget,
    RunRequest,
    WorkspaceRunnableResult,
    WorkspaceSession,
)
from engineeringagent.workspaces.protocols import (
    WorkspaceRunnableAgent,
    WorkspaceRunnableAgentResolver,
)
```

Under the import rules in this plan:

- this file may import from both `engineeringagent.orchestrators` and `engineeringagent.workspaces`;
- `engineeringagent.workspaces` must not import this file.

### `src/engineeringagent/application/workspace_runtime.py`

Make this file composition-only again.

Concrete edits:

- remove `LocalExecutionAgentFactory`
- remove `WorkspaceRunnableImplementationAgent`
- remove `DefaultWorkspaceRunnableAgentResolver`
- remove `import os`
- remove `from contextlib import contextmanager`
- remove the `_working_directory()` helper
- construct `DefaultWorkspaceExecutionAdapterResolver()` and pass it into `LocalProcessWorkspaceRunner`
- import the application bridge resolver from `src/engineeringagent/application/workspace_bridges.py`
- import `WorkspaceRunOrchestrator` from `src/engineeringagent/workspaces/services/workspace_run_orchestrator.py`

Suggested runner wiring:

```python
from engineeringagent.application.workspace_bridges import (
    DefaultWorkspaceRunnableAgentResolver,
)
from engineeringagent.workspaces.adapters.default_execution_adapter_resolver import (
    DefaultWorkspaceExecutionAdapterResolver,
)
from engineeringagent.workspaces.services.workspace_run_orchestrator import (
    WorkspaceRunOrchestrator,
)

runner = LocalProcessWorkspaceRunner(
    registry=registry,
    agent_resolver=DefaultWorkspaceRunnableAgentResolver(),
    execution_adapter_resolver=DefaultWorkspaceExecutionAdapterResolver(),
)
```

No workflow adaptation or `chdir` should remain in this file.

### `src/engineeringagent/workspaces/adapters/__init__.py`

Export the new runtime pieces:

```python
from engineeringagent.workspaces.adapters.default_execution_adapter_resolver import (
    DefaultWorkspaceExecutionAdapterResolver,
)
from engineeringagent.workspaces.adapters.local_path_execution_adapter import (
    LocalPathWorkspaceExecutionAdapter,
)
```

If you move `WorkspaceRunOrchestrator` into `engineeringagent.workspaces.services`, consider exporting it from a package `__init__.py` there as well.

### `src/engineeringagent/application/services/implementation_run_service.py`

Keep this file application-owned, but update imports so it depends on the moved workspace modules.

Possible follow-up improvement in the same change:

- extract workspace-spec construction into a helper such as `build_workspace_spec_for_current_repo()` under `engineeringagent.application.workspace_runtime`.

That keeps the CLI entrypoint thin while still respecting package boundaries.

### `tests/application/test_workspace_runtime.py`

Change the test intent.

Current test proves that `LocalExecutionAgentFactory` does not pass a path because workspace mode relies on application-owned `cwd`.

After this refactor the better assertion is narrower:

- `workspace_runtime` composes `WorkspaceRunOrchestrator` from workspace-owned runtime pieces; and
- `workspace_runtime` wires the runner with:
  - `DefaultWorkspaceRunnableAgentResolver` from `engineeringagent.application.workspace_bridges`; and
  - `DefaultWorkspaceExecutionAdapterResolver` from `engineeringagent.workspaces.adapters`.

That removes the outdated architectural assumption from the test.

### `tests/application/test_workspace_bridges.py`

Add or move tests here for:

- `LocalExecutionAgentFactory`
- `WorkspaceRunnableImplementationAgent`
- `DefaultWorkspaceRunnableAgentResolver`

These are application-bridge concerns, not workspace-runtime concerns.

### `tests/workspaces/adapters/test_local_process_runner.py`

Update the runner tests to use a fake execution-adapter resolver.

Add two fakes:

```python
class _RecordingExecutionAdapter:
    def __init__(self, result: WorkspaceRunnableResult) -> None:
        self.calls = []
        self._result = result

    def run(self, workspace, request, agent):
        self.calls.append((workspace, request, agent))
        return self._result


class _StaticExecutionAdapterResolver:
    def __init__(self, adapter):
        self.adapter = adapter
        self.targets = []

    def resolve(self, target):
        self.targets.append(target)
        return self.adapter
```

Then assert:

- the runner resolves the adapter from `workspace.execution_target`;
- the adapter receives `workspace`, `request`, and the resolved agent; and
- run state persistence still behaves the same.

### `tests/workspaces/adapters/test_local_path_execution_adapter.py`

Add a new focused test file.

Recommended tests:

- `test_local_path_adapter_runs_agent_inside_workspace_directory`
- `test_local_path_adapter_restores_previous_directory_after_success`
- `test_local_path_adapter_restores_previous_directory_after_failure`
- `test_local_path_adapter_rejects_non_local_target`

The simplest agent test double can assert `Path.cwd()` while running.

### `tests/workspaces/adapters/test_git_worktree_provider.py`

Keep the existing provider behavior checks and add an explicit assertion that the provisioned workspace still returns:

```python
assert workspace.execution_target.kind == "local_path"
```

That documents the provider-to-execution pairing at the data boundary.

### `tests/workspaces/test_real_integration.py`

No architectural rewrite is needed here, but keep this file as the proof that:

- the worktree is created;
- edits happen in the isolated checkout; and
- the source repo is untouched.

If helpful, add one assertion that the implementation ran from the workspace path by checking the modified files remain rooted in `workspace.execution_target.location`.

### `harness/policy/import_rules.yaml`

Add architectural guards for the new import rules in policy rather than in unit tests.

Recommended assertions:

- files under `src/engineeringagent/workspaces/` must not import from `engineeringagent.orchestrators`;
- files under `src/engineeringagent/workspaces/` must not import from `engineeringagent.application`;
- files under `src/engineeringagent/orchestrators/` must not import from `engineeringagent.workspaces`;
- files under `src/engineeringagent/orchestrators/` must not import from `engineeringagent.application`.

Recommended policy additions:

- add a `workspaces-only-import-workspaces` rule for `src/engineeringagent/workspaces/**/*.py`
- keep or tighten the existing `orchestrators-only-import-orchestrators` rule for `src/engineeringagent/orchestrators/**/*.py`

The existing fitness script already evaluates this policy, so the boundary should live there.

### `harness/fitness/tests/test_import_rules.py`

Only update this file if the new policy shape requires additional coverage of the generic fitness tooling.

Do not add repository architecture assertions under `tests/`; keep those concerns in the harness fitness layer.

## Optional Cleanup Not Required In This Change

Once the package split is in place, a later cleanup could separate application composition even further, for example by splitting:

- `engineeringagent.application.workspace_runtime` for builders/factories only; and
- `engineeringagent.application.workspace_bridges` for adapters from application use cases into the workspace runtime.

That split is helpful but not required to complete the boundary correction.

## Test Plan

### Update Existing Tests

- replace the application-layer expectation in `tests/application/test_workspace_runtime.py` that local runs rely on application-owned `cwd` handling;
- move `LocalExecutionAgentFactory` tests into application bridge coverage and keep them focused on agent selection, not execution context; and
- update runner tests to assert the runner delegates through the execution adapter.

### Add New Tests

- local execution adapter restores the previous working directory on success;
- local execution adapter restores the previous working directory on failure;
- local execution adapter runs the workflow with the workspace as the active cwd;
- runner resolves execution adapter from `ExecutionTarget.kind`;
- git worktree provider still returns `local_path` execution targets; and
- integration coverage still proves changes occur inside the worktree, not the source repo.

## Implementation Order

### Phase 1: Protocols

- move `workspace_models` into `engineeringagent.workspaces.models` and make that file canonical;
- move `workspace_protocols` into `engineeringagent.workspaces.protocols` and make that file canonical; and
- add `WorkspaceExecutionAdapter` and `WorkspaceExecutionAdapterResolver` there.

### Phase 2: Workspace Runtime Move

- move `WorkspaceRunOrchestrator` into `engineeringagent.workspaces.services`; and
- update existing workspace adapters and services to import only from `engineeringagent.workspaces`.

### Phase 3: Local Adapter

- move `_working_directory()` into the new local execution adapter;
- implement local-path execution there.

### Phase 4: Runner Wiring

- inject execution-adapter resolution into `LocalProcessWorkspaceRunner`;
- delegate target-specific execution through that adapter.

### Phase 5: Application Bridge Cleanup

- move `LocalExecutionAgentFactory`, `WorkspaceRunnableImplementationAgent`, and `DefaultWorkspaceRunnableAgentResolver` into `engineeringagent.application.workspace_bridges`; and
- keep `engineeringagent.application.workspace_runtime` responsible only for assembling workspace and orchestrator components.

### Phase 6: Import Boundary Enforcement

- update `harness/policy/import_rules.yaml`; and
- ensure the harness fitness check enforces that `engineeringagent.workspaces` does not import `engineeringagent.orchestrators` or `engineeringagent.application`.

### Phase 7: Tests

- update unit tests for the new boundary;
- run integration coverage for workspace-backed execution; and
- run the import-boundary fitness check after package-boundary changes.

## Migration Sequence To Minimize Breakage

Use a staged migration so imports keep working while code moves.

### Step 1: Make `engineeringagent.workspaces` Canonical First

- copy the contents of `src/engineeringagent/orchestrators/workspace_models.py` into `src/engineeringagent/workspaces/models.py`;
- copy the contents of `src/engineeringagent/orchestrators/workspace_protocols.py` into `src/engineeringagent/workspaces/protocols.py`;
- update workspace-owned files to import from the new canonical modules; and
- leave temporary compatibility shims in the old orchestrator paths.

Temporary shim pattern:

```python
# src/engineeringagent/orchestrators/workspace_models.py
from engineeringagent.workspaces.models import *
```

```python
# src/engineeringagent/orchestrators/workspace_protocols.py
from engineeringagent.workspaces.protocols import *
```

This keeps the tree green while imports are migrated incrementally.

### Step 2: Move `WorkspaceRunOrchestrator` With A Compatibility Shim

- add `src/engineeringagent/workspaces/services/workspace_run_orchestrator.py`;
- update application composition to import the new path; and
- keep `src/engineeringagent/orchestrators/workspace_run_orchestrator.py` as a temporary re-export.

Shim pattern:

```python
from engineeringagent.workspaces.services.workspace_run_orchestrator import (
    WorkspaceRunOrchestrator,
)
```

This avoids a large cross-repo import flip in one commit.

### Step 3: Add The New Local Execution Adapter Without Deleting Old Logic Yet

- add `LocalPathWorkspaceExecutionAdapter`;
- add `DefaultWorkspaceExecutionAdapterResolver`; and
- add focused tests for those new pieces.

At this step, the existing application-layer `_working_directory()` can still exist temporarily.

That keeps the new execution path testable before changing the main runtime wiring.

### Step 4: Switch `LocalProcessWorkspaceRunner` To Execution Adapter Resolution

- extend the runner constructor to take `execution_adapter_resolver`;
- update only the composition points that instantiate the runner; and
- update `tests/workspaces/adapters/test_local_process_runner.py` in the same commit.

After this step, target-specific execution belongs to the workspace runtime even if the application bridge classes have not moved yet.

### Step 5: Move Application Bridge Classes Out Of `workspace_runtime`

- create `src/engineeringagent/application/workspace_bridges.py`;
- move `LocalExecutionAgentFactory`, `WorkspaceRunnableImplementationAgent`, and `DefaultWorkspaceRunnableAgentResolver` there; and
- update `src/engineeringagent/application/workspace_runtime.py` to import those bridge classes instead of defining them.

At this point `workspace_runtime.py` becomes a pure composition module.

### Step 6: Remove The Old `cwd` Logic From Application

- delete `_working_directory()` from `src/engineeringagent/application/workspace_runtime.py`;
- remove the old `os.chdir(...)` flow from `WorkspaceRunnableImplementationAgent`; and
- rely only on `LocalPathWorkspaceExecutionAdapter` for local execution context.

This is the moment where the architectural ownership actually changes.

### Step 7: Add Import Boundary Tests Before Deleting Shims

- update `harness/policy/import_rules.yaml`;
- verify the fitness check enforces the new package rules; and
- run the full test suite plus the fitness check while the compatibility shims are still present.

This gives you a safety net before removing migration helpers.

### Step 8: Remove Compatibility Shims

- delete the temporary re-export contents from:
  - `src/engineeringagent/orchestrators/workspace_models.py`
  - `src/engineeringagent/orchestrators/workspace_protocols.py`
  - `src/engineeringagent/orchestrators/workspace_run_orchestrator.py`
- update any final imports still pointing at the old paths; and
- rerun tests plus boundary checks.

Only remove shims after all imports are updated and the architecture test passes.

## Suggested Commit Breakdown

If you want this refactor to stay reviewable, split it into small commits.

1. add canonical `engineeringagent.workspaces.models` and `engineeringagent.workspaces.protocols` with temporary re-exports from `engineeringagent.orchestrators`
2. move `WorkspaceRunOrchestrator` into `engineeringagent.workspaces.services` with temporary re-export
3. add local execution adapter and resolver plus tests
4. wire `LocalProcessWorkspaceRunner` through execution adapters
5. move application bridge classes into `engineeringagent.application.workspace_bridges`
6. remove old application-owned `cwd` logic
7. update import-boundary policy and verify the fitness check
8. remove temporary orchestrator compatibility shims

## Recommended Default Decision

Use this package structure:

- `engineeringagent.orchestrators` owns implementation workflow domain logic;
- `engineeringagent.workspaces` owns workspace models, protocols, adapters, and runtime;
- `engineeringagent.application` owns composition plus bridge adapters between those packages.

Within that structure:

- use separate provider and execution-adapter protocols, connected by `ExecutionTarget`; and
- enforce an import rule that `engineeringagent.workspaces` must not import from the implementation domain.

That gives you the coupling you want in practice, while keeping the architecture extensible enough for future container targets and preserving clean package ownership.
