---
schema_version: 1
task_id: add-background-workspace-implementation-launch
title: Add background launch mode for workspace implementation runs
status: ready
branch: feat/background-launch-strategy
base_branch: master
phases:
  - id: architecture
    title: Model launch mode as a strategy boundary
    status: todo
  - id: runtime
    title: Introduce shared run preparation, execution, and worker bootstrap
    status: todo
  - id: application
    title: Select launch strategy through config and result mapping
    status: todo
  - id: status-ux
    title: Surface run identity and inspection details
    status: todo
  - id: tests
    title: Cover handshake, persistence, and failure paths
    status: todo
---

# Goal

Add an opt-in background launch mode for workspace-backed `developer implement` so the CLI returns after startup succeeds while the long-running implementation workflow continues in a detached worker process.

After this change:

- workspace-backed `developer implement` remains foreground by default;
- `[workspaces].implementation_launch_mode = "background"` launches the implementation run in a detached subprocess after workspace creation succeeds;
- the CLI does not report success until the worker proves it has started the run;
- persisted workspace run state remains the source of truth for later inspection; and
- direct-mode `developer implement` continues to behave exactly as it does today.

# Scope Boundaries

Build this only for workspace-backed implementation runs in v1.

Reasons:

- the current workspace flow already persists `WorkspaceSession` and `RunHandle` state;
- workspace provisioning can stay synchronous while the expensive implementation loop moves to the background;
- direct mode still relies on process-global execution assumptions and should not be detached in this slice; and
- background execution needs follow-up inspection and cancellation semantics that are easier to add on top of workspace run identity than on top of the caller's live checkout.

Keep these boundaries in v1:

- workspace creation remains foreground;
- `implementation_launch_mode` defaults to `"foreground"`;
- do not introduce a daemon, queue, or `systemd` dependency in this slice;
- do not promise hard cancellation yet, but store enough process metadata to support it later; and
- do not make `developer.application.services.implementation_run_service` own new branch-planning or workspace-run policy.

State compatibility for this slice:

- do not preserve backward compatibility for old `.developer/state` data;
- treat the persisted workspace-run format as allowed to change in this refactor; and
- require clearing existing state before relying on the new background-launch behavior.

# Relationship To Existing Boundary Plans

This plan should align with `docs/plans/implementation-run-orchestration-boundary-plan.md`.

Recommended ownership after both plans land:

- `developer.orchestrators.runs` owns implementation-run planning and decides what workspace run should be launched;
- `developer.workspaces` owns generic run lifecycle, detached-process mechanics, persisted run state, and worker bootstrap contracts;
- `developer.application` owns composition, config resolution, and CLI-facing result mapping; and
- `developer.presentation` stays thin and should only echo the mapped result.

This means the background-launch work should not add new task-branch, publication-reuse, or workspace-request assembly helpers to `src/developer/application/services/implementation_run_service.py`.

This plan should also respect `docs/plans/workspace-execution-boundary-plan.md`.

Important implication:

- local workspace execution still depends on ambient `cwd` switching in `LocalPathWorkspaceExecutionAdapter`, so the background launch should use a separate OS process instead of an in-process thread or task.

If the orchestration-boundary refactor lands first, target the post-refactor file layout from the start.

If it has not landed yet, keep new launch mechanics in `developer.workspaces` and application composition helpers only, so the code can move cleanly once run orchestration shifts into `developer.orchestrators.runs`.

# Current State

Today the workspace-backed implementation path is still fully synchronous.

- `src/developer/presentation/commands/implement.py` calls `run_implementation(...)` and waits for a terminal result.
- `src/developer/application/services/implementation_run_service.py` selects workspace mode and waits for `WorkspaceRunOrchestrator.run_in_workspace(...)` to return a finished `RunHandle`.
- `src/developer/workspaces/services/workspace_run_orchestrator.py` creates the workspace and immediately calls the runner inline.
- `src/developer/workspaces/adapters/local_process_runner.py` persists a pending handle and then executes the full implementation workflow in the caller process.
- `src/developer/workspaces/adapters/local_path_execution_adapter.py` uses `os.chdir(...)`, which makes in-process background execution risky.
- there is no dedicated persisted request payload for replaying a run in a fresh worker process;
- there is no startup handshake state between the parent CLI process and a detached worker; and
- there is no CLI command yet for later run inspection, even though the registry already persists run state.

# Decision

Implement v1 background launch as a detached subprocess that starts only after foreground workspace creation succeeds.

Important architecture refinement after review:

- treat `implementation_launch_mode` as a first-class launch-strategy seam, not as an accumulating `if`/`elif` tree in application composition;
- do not keep adding one top-level `WorkspaceRunner` implementation per launch mode when those implementations need materially different dependency graphs;
- instead, keep one high-level workspace runner boundary and vary launch behavior through pluggable launch strategies or adapters selected by mode; and
- keep run preparation and run execution as shared responsibilities so foreground, background, and future modes do not drift.

## Config

Add a workspace setting:

```toml
[workspaces]
implementation_launch_mode = "foreground"
```

Recommended allowed values:

- `foreground` - current blocking behavior
- `background` - create the workspace in the foreground, then launch the implementation run in a detached worker and return after startup acknowledgment

Do not use a boolean flag.

Reasoning:

- `foreground` versus `background` expresses user-visible behavior instead of implementation detail;
- a string setting leaves room for a future third option such as `queued` or `remote`; and
- it keeps the config aligned with the implementation-domain naming already used elsewhere in the repo.

## Worker Model

Use a detached subprocess launched through Python, not a thread.

Recommended mechanism:

- parent process uses `subprocess.Popen(...)` with `start_new_session=True`;
- command uses `sys.executable -m ...` so the worker runs in the same Python environment as the parent;
- stdin is disconnected;
- stdout and stderr are redirected to a per-run log file; and
- the worker rehydrates all state from persisted workspace/run records instead of inheriting in-memory Python objects.

Do not treat `Popen(...)` success as run-start success.

Instead, require a startup handshake:

- parent writes the run in a non-terminal `starting` state;
- worker bootstraps, persists process metadata, validates that it can run, and then flips the run to `running`;
- parent waits on a direct startup-acknowledgment channel instead of polling persisted state;
- if the worker writes `failed` during bootstrap, surface that failure immediately; and
- if the timeout expires without acknowledgment, mark the run `failed` and return a launch failure instead of pretending the run started.

Recommended state-transition rule:

- only allow `STARTING -> RUNNING -> terminal` during successful startup and execution;
- allow `STARTING -> FAILED` when bootstrap fails or startup acknowledgment times out; and
- require the worker to re-check persisted run state before flipping to `RUNNING`, then exit without continuing if the parent has already marked the run terminal.

# Target Architecture

## Orchestrator Ownership

Once `docs/plans/implementation-run-orchestration-boundary-plan.md` lands, launch behavior should fit the new ownership model.

Recommended responsibility split:

- `developer.orchestrators.runs` decides that an implementation workspace run should start and produces the typed workspace run request and outcome;
- `developer.workspaces` decides how a workspace run is executed in `foreground` versus `background` launch mode;
- `developer.application` resolves `implementation_launch_mode`, builds the workspace runtime from shared services plus launch-strategy selection, and maps outcomes into `ImplementationRunResult`; and
- `developer.presentation` remains unchanged except for the message shown to the user.

Do not make orchestrators aware of `Popen(...)`, worker module paths, or file-backed process metadata.

## Workspace Runtime Shape

Recommended runtime additions:

- add `STARTING` to `RunStatus` so a detached launch has an explicit pre-acknowledgment state;
- persist launch input separately from mutable run result metadata so a fresh worker can replay the same `RunRequest` safely;
- persist a resolved launch snapshot for launch-critical runtime selection so the worker cannot drift if config changes after launch;
- add a shared run-preparation service that creates the run record and persists immutable launch input before any launch strategy starts executing;
- add a shared run-execution service that rehydrates one persisted run by `run_id` and executes it to completion;
- model foreground, background, and future launch modes as implementations of a common launch-strategy or launch-adapter protocol selected by mode;
- keep the worker entrypoint thin by delegating real execution to the shared run-execution service; and
- avoid growing mode selection as an inline `if`/`elif` chain in composition once additional launch modes such as `queued` or `remote` are introduced.

Recommended persistence split:

- `RunHandle` remains the mutable status record;
- `RunRequest` is persisted separately as immutable launch input for the shared executor;
- `LaunchSnapshot` or an equivalent model is persisted separately as immutable launch-time runtime/config input for the shared executor; and
- `RunHandle.metadata` is reserved for derived runtime and result metadata such as process identity, log path, commit SHAs, and publication details.

This is cleaner than storing launch input and output metadata in the same bag.

Recommended responsibility split inside `developer.workspaces`:

- `WorkspaceRunner` stays the outer contract used by `WorkspaceRunOrchestrator`;
- `WorkspaceRunPreparer` or similarly named service owns durable run creation and persistence of launch input;
- `WorkspaceRunExecutor` or similarly named service owns replaying one prepared run to a terminal state;
- `WorkspaceLaunchStrategy` or similarly named protocol owns how prepared work is started for one mode; and
- `BackgroundWorkspaceLauncher` remains a narrow subprocess-spawn concern beneath the background launch strategy rather than becoming the top-level runtime abstraction.

# Proposed Files

Targeting the post-boundary layout, recommended additions and updates are:

- `src/developer/workspaces/models.py`
- `src/developer/workspaces/protocols.py`
- `src/developer/workspaces/settings.py`
- `src/developer/workspaces/services/file_registry.py`
- `src/developer/workspaces/services/workspace_run_orchestrator.py`
- `src/developer/workspaces/services/workspace_run_preparer.py` or similarly named shared preparation service
- `src/developer/workspaces/services/workspace_run_executor.py` or similarly named shared execution service
- `src/developer/workspaces/services/workspace_launch_strategy_factory.py` or similarly named selector/registry
- `src/developer/workspaces/adapters/foreground_launch_strategy.py` or similarly named foreground strategy
- `src/developer/workspaces/adapters/background_process_launch_strategy.py` or similarly named subprocess strategy
- `src/developer/application/implementation_run_runtime.py` as the composition root described in `docs/plans/implementation-run-orchestration-boundary-plan.md`
- `src/developer/application/workspace_run_worker.py` or similarly named worker entrypoint
- `src/developer/application/services/implementation_run_service.py`
- `src/developer/presentation/commands/implement.py`
- `tests/workspaces/services/test_workspace_run_preparer.py`
- `tests/workspaces/services/test_workspace_run_executor.py`
- `tests/workspaces/adapters/test_background_process_launch_strategy.py`
- `tests/workspaces/adapters/test_foreground_launch_strategy.py`
- `tests/application/services/test_implementation_run_service.py`
- `tests/presentation/test_implementation_cli.py`

If `src/developer/application/implementation_run_runtime.py` does not exist yet when this work starts, use the current `src/developer/application/workspace_runtime.py` only as a temporary composition host and plan to move the wiring afterward.

# Proposed Model And Protocol Changes

## `src/developer/workspaces/models.py`

Recommended updates:

- add `RunStatus.STARTING`
- keep `RunStatus.RUNNING`, `SUCCEEDED`, `FAILED`, and `CANCELLED`
- keep `RunHandle` as the canonical status record
- do not make PID the durable identity; `run_id` stays the canonical handle

Recommended metadata persisted onto the run once the worker starts:

- `launch_mode = "background"`
- `pid`
- `process_start_time`
- `process_group_id`
- `log_path`
- `bootstrapped_at`

`pid` is useful for inspection and later cancellation, but it should be treated as launcher metadata rather than the primary run identity.

## `src/developer/workspaces/protocols.py`

Recommended updates:

- extend the registry protocol with methods for saving and loading one persisted `RunRequest` by `run_id`
- extend the registry protocol with methods for saving and loading one persisted launch snapshot by `run_id`
- keep `WorkspaceRunner.start_run(...) -> RunHandle` as the high-level contract
- add a small launch-strategy protocol with one stable input shape for all launch modes
- keep subprocess spawning behind a narrower background-launcher protocol used only by the subprocess strategy
- prefer a strategy registry or factory over inline mode branching in composition

Avoid making the workspace runner protocol implementation-specific by exposing raw `Popen` objects or shell commands.

## `src/developer/workspaces/settings.py`

Add `implementation_launch_mode` with a default of `"foreground"` and validation for the accepted values.

# Launch Flow

## Foreground Mode

Foreground mode should remain user-visible current behavior while using the same prepared-run contract as background mode.

Recommended flow:

1. create workspace;
2. prepare persisted run state, including `RunHandle`, `RunRequest`, and launch snapshot;
3. select the foreground launch strategy;
4. let the foreground strategy mark the run runnable and invoke the shared executor inline;
5. persist terminal outcome through the shared executor; and
6. return the terminal result.

## Background Mode

Background mode should keep workspace creation synchronous, then detach before the long-running implementation loop begins.

Recommended parent flow:

1. create the workspace in the foreground;
2. prepare persisted run state through the shared preparation service;
3. select the background launch strategy;
4. allocate the per-run log path;
5. create a one-shot startup-acknowledgment channel for the child;
6. spawn a detached worker subprocess;
7. wait briefly on the acknowledgment channel; and
8. return success only after the worker reports successful bootstrap and flips the run to `RUNNING`.

Recommended worker flow:

1. load the prepared run state by `run_id`;
2. open the configured log file and redirect uncaught bootstrap diagnostics there;
3. record `pid`, `process_start_time`, and `process_group_id` onto run metadata;
4. perform early validation needed to start safely;
5. re-check the persisted run state and stop if it is already terminal;
6. flip the run to `RUNNING` and send a success acknowledgment to the parent;
7. delegate real run execution to the shared executor; and
8. persist `SUCCEEDED` or `FAILED` with the final summary.

Important design constraint:

- the foreground path and the worker path should converge on the same execution service once launch-time setup is complete.

Recommended startup-time failure handling:

- if bootstrap fails before the worker marks the run `RUNNING`, persist `FAILED`, record the failure message, and send a failure acknowledgment when possible;
- if the parent times out before receiving acknowledgment, mark the run `FAILED`, report launch failure, and include the log path when possible; and
- do not leave a run stuck in `STARTING` without an explicit timeout or failure path.

# Application And CLI Behavior

## Application Composition

Application should resolve launch behavior from config and wire the workspace runtime accordingly.

Recommended application flow after the orchestration-boundary refactor:

1. resolve config;
2. ensure clean checkout;
3. resolve the task and normalize `max_iterations`;
4. resolve `implementation_launch_mode` from workspace settings;
5. delegate workspace-run planning to `developer.orchestrators.runs`;
6. build the workspace runtime from shared preparation and execution services plus a launch-strategy registry or factory;
7. delegate workspace execution to that launch-aware workspace runtime; and
8. map the returned run outcome into `ImplementationRunResult`.

Do not teach `implementation_run_service.py` how detached workers start.

That file should only select the composed use-case path and format the CLI-facing message.

## CLI Result Mapping

When `implementation_launch_mode = "background"` succeeds, the CLI should return a non-terminal message.

Recommended format:

- `workspace=<workspace-id>`
- `run=<run-id>`
- `task=<task-name>`
- `status=running`
- `branch=<task-branch>` when known
- `log=<path>` when available

Do not report `succeeded` merely because the worker launched.

# Status And Inspection UX

Background mode is much easier to use if the CLI can read persisted run state after launch.

Required support in this slice:

- add a read-only `developer runs get <run-id>` command that loads one persisted run by `run_id`.

Recommended v1 output fields:

- `run_id`
- `workspace_id`
- `status`
- `latest_message`
- `pid` when present
- `log_path` when present

The launch result should still print enough information for a user to locate the run in persisted state:

- `run_id`
- `workspace_id`
- `log_path`

Cancellation can remain a follow-up, but this slice should store enough process metadata that later cancellation can target the correct process group rather than only mutating metadata.

# Phase 1: Align launch ownership with orchestration boundaries

- [ ] Keep new launch mechanics out of `developer.orchestrators.runs`
- [ ] Keep subprocess and worker-bootstrap code out of `implementation_run_service.py`
- [ ] Model launch mode as a strategy or adapter seam instead of a growing `if`/`elif` tree in composition
- [ ] Keep one outer workspace-runner boundary while moving launch variation under a launch-strategy protocol
- [ ] Add launch-mode resolution only to application composition and workspace runtime wiring
- [ ] If `docs/plans/implementation-run-orchestration-boundary-plan.md` lands first, implement against `src/developer/application/implementation_run_runtime.py`
- [ ] If it has not landed yet, confine temporary composition changes to `src/developer/application/workspace_runtime.py`
- [ ] Avoid new branch-planning helpers in application while adding background launch support
- [ ] Avoid creating one top-level runner class per launch mode when those modes mainly differ in dispatch behavior

### Notes

This phase is about keeping the feature aligned with the target boundary and choosing an extension seam that will still read clearly if a third or fourth launch mode is added later.

# Phase 2: Add background launch lifecycle and worker bootstrap

- [ ] Add `RunStatus.STARTING`
- [ ] Persist `RunRequest` separately from `RunHandle` through a shared preparation path
- [ ] Persist a launch snapshot separately from `RunRequest` through that same preparation path
- [ ] Add a shared run-preparation service
- [ ] Add a shared run-execution service
- [ ] Add a launch-strategy protocol and selection mechanism
- [ ] Add a foreground launch strategy that delegates to the shared executor
- [ ] Add a subprocess background launch strategy
- [ ] Add a worker entrypoint that can execute one persisted run by `run_id`
- [ ] Launch the worker through `sys.executable -m ...` with detached-process settings
- [ ] Write per-run logs beneath the configured workspace state directory
- [ ] Persist `pid`, `process_start_time`, and `process_group_id` after bootstrap
- [ ] Require a direct startup-acknowledgment handshake that flips `STARTING` to `RUNNING`
- [ ] Fail fast when startup acknowledgment does not arrive within the timeout
- [ ] Keep the worker entrypoint thin and delegate actual replay to the shared executor

### Notes

The key runtime requirements are that the CLI returns only after the worker proves it started, not merely after `Popen(...)` returns, and that foreground and background execution share the same post-launch execution path.

# Phase 3: Gate launch mode through config and result mapping

- [ ] Add `implementation_launch_mode = "foreground"` to `WorkspaceSettings`
- [ ] Validate accepted values in config parsing
- [ ] Update checked-in config examples such as `engineeringagent.toml`
- [ ] Select launch strategy from config through a registry or factory rather than inline branching
- [ ] Keep direct mode unchanged
- [ ] Update `run_implementation(...)` result mapping so background launches return a non-terminal `running` message
- [ ] Keep `developer.presentation.commands.implement` thin and unchanged except for displayed output

### Notes

This phase keeps the feature opt-in and avoids surprising users who already rely on blocking behavior.

# Phase 4: Surface run identity and inspection details

- [ ] Include `workspace_id`, `run_id`, and `log_path` in successful background launch output
- [ ] Add `developer runs get <run-id>` as a small read-only inspection command
- [ ] Ensure persisted run state shows `starting`, `running`, and terminal statuses clearly
- [ ] Keep the source of truth in the registry rather than relying on process liveness alone

### Notes

The first background-launch slice is much easier to validate and debug when users can inspect run state without opening JSON files manually.

# Phase 5: Cover handshake, persistence, and failure paths

- [ ] Add launch-strategy tests for foreground versus background behavior
- [ ] Add shared-executor tests that foreground and worker replay use the same execution path
- [ ] Add strategy-selection tests for launch-mode resolution
- [ ] Add registry tests for persisted `RunRequest` storage and retrieval
- [ ] Add registry tests for persisted launch snapshot storage and retrieval
- [ ] Add worker-entrypoint tests for bootstrap success and bootstrap failure
- [ ] Add application-service tests for config gating and result mapping
- [ ] Add CLI tests for background launch output
- [ ] Add CLI tests for `developer runs get <run-id>`
- [ ] Add timeout tests for runs that never acknowledge `RUNNING`
- [ ] Add tests that confirm bootstrap failures become terminal `FAILED` runs
- [ ] Add tests that confirm background launch stores process metadata and log path
- [ ] Run the import-boundary fitness check aligned with `docs/plans/implementation-run-orchestration-boundary-plan.md`
- [ ] Add an integration-style mocked E2E test in a temp folder covering launch, startup acknowledgment, and `runs get`
- [ ] Run `uv run developer validate-plan docs/plans/background-workspace-implementation-launch-plan.md`

### Notes

The most important regression risk is claiming a run started when the worker never actually reached a valid running state.

# Migration Sequence

1. finish or at least preserve the ownership direction from `docs/plans/implementation-run-orchestration-boundary-plan.md`;
2. clear any existing local workspace-run state before relying on the new format;
3. add the launch-mode setting and explicit `STARTING` run state;
4. introduce the shared run-preparation and run-execution services;
5. add persisted `RunRequest`, launch-snapshot storage, and log-path allocation through the shared preparation path;
6. add the foreground launch strategy on top of the shared executor;
7. add the detached worker entrypoint, subprocess background strategy, and direct startup handshake;
8. wire launch-strategy selection through application composition;
9. update CLI-facing result mapping and add `developer runs get <run-id>`; and
10. add tests for strategy selection, handshake, timeout, bootstrap failure, mocked temp-folder E2E behavior, and boundary fitness.

# Risks And Mitigations

- if the worker is launched without a startup handshake, the CLI can claim success for runs that never really started; mitigate with `STARTING`, direct startup acknowledgment, and timeout-based failure
- if launch input is stored only in ad hoc metadata, worker replay will become brittle as the request shape evolves; mitigate by persisting `RunRequest` and a launch snapshot separately from mutable result metadata
- if launch modes are added through an accumulating `if`/`elif` tree in composition, the runtime wiring will become harder to extend and review; mitigate by introducing a launch-strategy protocol plus a selector or registry
- if foreground and background continue to use different execution paths after startup, behavior will drift and tests will duplicate; mitigate by introducing one shared executor reached by both inline and worker-based launch flows
- if subprocess launching is wired directly into application services, the ownership split from `docs/plans/implementation-run-orchestration-boundary-plan.md` will erode again; mitigate by keeping launch mechanics inside workspace runtime plus application composition
- if each launch mode becomes a separate top-level runner with a different constructor shape, the abstraction will grow more awkward as new modes are added; mitigate by keeping launch variation beneath a shared runner boundary and common prepared-run contract
- if PID is treated as the durable identity, later status and cancellation behavior can target the wrong process after PID reuse; mitigate by keeping `run_id` as the canonical identifier and storing PID only as launcher metadata together with process start time
- if background mode ships without any inspection surface, debugging failed launches will be unnecessarily painful; mitigate by printing `run_id` and `log_path` and adding a small read-only status command in the same slice
- if old local state files are read as if they matched the new persistence shape, debugging will become confusing; mitigate by treating this refactor as a local state-format break and requiring state cleanup before use

# Recommended Default Decision

Implement this as:

- a new workspace config setting `implementation_launch_mode = "foreground"`;
- workspace-only background launch in v1;
- one outer workspace-runner boundary backed by shared run preparation and shared run execution services;
- launch-mode-specific behavior modeled as pluggable launch strategies or adapters selected from config rather than a growing inline branch;
- a detached Python worker subprocess launched after foreground workspace creation;
- explicit `STARTING -> RUNNING -> terminal` run-state transitions with direct startup acknowledgment;
- persisted `RunRequest` storage, launch snapshots, and per-run log files;
- a required read-only `developer runs get <run-id>` command; and
- application-owned composition that stays aligned with the ownership model from `docs/plans/implementation-run-orchestration-boundary-plan.md`.

This keeps the feature opt-in, durable enough for real use, and compatible with the planned move of implementation-run orchestration out of `developer.application` and into `developer.orchestrators.runs`.
