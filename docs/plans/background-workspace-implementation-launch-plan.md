---
schema_version: 1
task_id: add-background-workspace-implementation-launch
title: Add background launch mode for workspace implementation runs
status: ready
branch: feat/add-background-workspace-implementation-launch
base_branch: main
phases:
  - id: architecture
    title: Align launch ownership with orchestration boundaries
    status: todo
  - id: runtime
    title: Add background launch lifecycle and worker bootstrap
    status: todo
  - id: application
    title: Gate launch mode through config and result mapping
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
- `developer.application` resolves `implementation_launch_mode`, builds the workspace runtime with the correct runner or launcher, and maps outcomes into `ImplementationRunResult`; and
- `developer.presentation` remains unchanged except for the message shown to the user.

Do not make orchestrators aware of `Popen(...)`, worker module paths, or file-backed process metadata.

## Workspace Runtime Shape

Recommended runtime additions:

- add `STARTING` to `RunStatus` so a detached launch has an explicit pre-acknowledgment state;
- persist launch input separately from mutable run result metadata so a fresh worker can replay the same `RunRequest` safely;
- persist a resolved launch snapshot for launch-critical runtime selection so the worker cannot drift if config changes after launch;
- add a background-capable workspace runner or launcher collaborator instead of overloading the current synchronous runner with opaque branches;
- keep the foreground runner path available for `implementation_launch_mode = "foreground"`; and
- add a small worker entrypoint that rehydrates one persisted run and executes it to completion.

Recommended persistence split:

- `RunHandle` remains the mutable status record;
- `RunRequest` is persisted separately as immutable launch input for the worker; and
- `LaunchSnapshot` or an equivalent model is persisted separately as immutable launch-time runtime/config input for the worker; and
- `RunHandle.metadata` is reserved for derived runtime and result metadata such as process identity, log path, commit SHAs, and publication details.

This is cleaner than storing launch input and output metadata in the same bag.

# Proposed Files

Targeting the post-boundary layout, recommended additions and updates are:

- `src/developer/workspaces/models.py`
- `src/developer/workspaces/protocols.py`
- `src/developer/workspaces/settings.py`
- `src/developer/workspaces/services/file_registry.py`
- `src/developer/workspaces/services/workspace_run_orchestrator.py`
- `src/developer/workspaces/adapters/local_process_runner.py` for the existing foreground path
- `src/developer/workspaces/adapters/background_process_runner.py` or similarly named background runner
- `src/developer/application/implementation_run_runtime.py` as the composition root described in `docs/plans/implementation-run-orchestration-boundary-plan.md`
- `src/developer/application/workspace_run_worker.py` or similarly named worker entrypoint
- `src/developer/application/services/implementation_run_service.py`
- `src/developer/presentation/commands/implement.py`
- `tests/workspaces/adapters/test_background_process_runner.py`
- `tests/workspaces/adapters/test_local_process_runner.py`
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
- add a small launch-focused protocol only if it meaningfully separates subprocess spawning from run-state coordination

Avoid making the workspace runner protocol implementation-specific by exposing raw `Popen` objects or shell commands.

## `src/developer/workspaces/settings.py`

Add `implementation_launch_mode` with a default of `"foreground"` and validation for the accepted values.

# Launch Flow

## Foreground Mode

Foreground mode should remain the current behavior.

Recommended flow:

1. create workspace;
2. create run handle;
3. execute inline;
4. persist terminal outcome; and
5. return the terminal result.

## Background Mode

Background mode should keep workspace creation synchronous, then detach before the long-running implementation loop begins.

Recommended parent flow:

1. create the workspace in the foreground;
2. persist a `RunHandle(status=STARTING, ...)`;
3. persist the immutable `RunRequest` for replay;
4. persist the immutable launch snapshot used for runtime/config replay;
5. allocate the per-run log path;
6. create a one-shot startup-acknowledgment channel for the child;
7. spawn a detached worker subprocess;
8. wait briefly on the acknowledgment channel; and
9. return success only after the worker reports successful bootstrap and flips the run to `RUNNING`.

Recommended worker flow:

1. load the `WorkspaceSession`, `RunHandle`, persisted `RunRequest`, and persisted launch snapshot;
2. open the configured log file and redirect uncaught bootstrap diagnostics there;
3. record `pid`, `process_start_time`, and `process_group_id` onto run metadata;
4. resolve the same runnable agent and execution adapter using the persisted launch snapshot rather than current config;
5. perform early validation needed to start safely;
6. re-check the persisted run state and stop if it is already terminal;
7. flip the run to `RUNNING` and send a success acknowledgment to the parent;
8. execute the existing implementation flow to completion; and
9. persist `SUCCEEDED` or `FAILED` with the final summary.

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
6. delegate workspace execution to a launch-aware workspace runtime; and
7. map the returned run outcome into `ImplementationRunResult`.

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
- [ ] Add launch-mode resolution only to application composition and workspace runtime wiring
- [ ] If `docs/plans/implementation-run-orchestration-boundary-plan.md` lands first, implement against `src/developer/application/implementation_run_runtime.py`
- [ ] If it has not landed yet, confine temporary composition changes to `src/developer/application/workspace_runtime.py`
- [ ] Avoid new branch-planning helpers in application while adding background launch support

### Notes

This phase is about keeping the feature aligned with the target boundary so the later orchestrator refactor does not need to undo the launch design.

# Phase 2: Add background launch lifecycle and worker bootstrap

- [ ] Add `RunStatus.STARTING`
- [ ] Persist `RunRequest` separately from `RunHandle`
- [ ] Persist a launch snapshot separately from `RunRequest`
- [ ] Add a background-capable workspace runner or launcher collaborator
- [ ] Add a worker entrypoint that can execute one persisted run by `run_id`
- [ ] Launch the worker through `sys.executable -m ...` with detached-process settings
- [ ] Write per-run logs beneath the configured workspace state directory
- [ ] Persist `pid`, `process_start_time`, and `process_group_id` after bootstrap
- [ ] Require a direct startup-acknowledgment handshake that flips `STARTING` to `RUNNING`
- [ ] Fail fast when startup acknowledgment does not arrive within the timeout

### Notes

The key runtime requirement is that the CLI returns only after the worker proves it started, not merely after `Popen(...)` returns.

# Phase 3: Gate launch mode through config and result mapping

- [ ] Add `implementation_launch_mode = "foreground"` to `WorkspaceSettings`
- [ ] Validate accepted values in config parsing
- [ ] Update checked-in config examples such as `engineeringagent.toml`
- [ ] Select foreground versus background workspace execution in application composition
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

- [ ] Add workspace-runner tests for foreground versus background launch behavior
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
4. add persisted `RunRequest`, launch-snapshot storage, and log-path allocation;
5. add the detached worker entrypoint and direct startup handshake;
6. wire foreground versus background selection through application composition;
7. update CLI-facing result mapping and add `developer runs get <run-id>`; and
8. add tests for handshake, timeout, bootstrap failure, mocked temp-folder E2E behavior, and boundary fitness.

# Risks And Mitigations

- if the worker is launched without a startup handshake, the CLI can claim success for runs that never really started; mitigate with `STARTING`, direct startup acknowledgment, and timeout-based failure
- if launch input is stored only in ad hoc metadata, worker replay will become brittle as the request shape evolves; mitigate by persisting `RunRequest` and a launch snapshot separately from mutable result metadata
- if subprocess launching is wired directly into application services, the ownership split from `docs/plans/implementation-run-orchestration-boundary-plan.md` will erode again; mitigate by keeping launch mechanics inside workspace runtime plus application composition
- if PID is treated as the durable identity, later status and cancellation behavior can target the wrong process after PID reuse; mitigate by keeping `run_id` as the canonical identifier and storing PID only as launcher metadata together with process start time
- if background mode ships without any inspection surface, debugging failed launches will be unnecessarily painful; mitigate by printing `run_id` and `log_path` and adding a small read-only status command in the same slice
- if old local state files are read as if they matched the new persistence shape, debugging will become confusing; mitigate by treating this refactor as a local state-format break and requiring state cleanup before use

# Recommended Default Decision

Implement this as:

- a new workspace config setting `implementation_launch_mode = "foreground"`;
- workspace-only background launch in v1;
- a detached Python worker subprocess launched after foreground workspace creation;
- explicit `STARTING -> RUNNING -> terminal` run-state transitions with direct startup acknowledgment;
- persisted `RunRequest` storage, launch snapshots, and per-run log files;
- a required read-only `developer runs get <run-id>` command; and
- application-owned composition that stays aligned with the ownership model from `docs/plans/implementation-run-orchestration-boundary-plan.md`.

This keeps the feature opt-in, durable enough for real use, and compatible with the planned move of implementation-run orchestration out of `developer.application` and into `developer.orchestrators.runs`.
