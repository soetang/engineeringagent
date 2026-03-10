# Execution Targets and Remote Runs

## Purpose

Define how a run starts in the orchestration process and can then execute locally or on another instance such as a cloud container.

## Core Idea

The harness separates three concerns:

1. orchestration
2. authoritative repository state
3. execution location

The run always starts in orchestration.
Orchestration selects the feature specification, resolves the authoritative feature workspace, and then chooses where execution should happen.

For the initial product, execution should stay local by default.
Remote container execution is a future optional extension point, not a first-version requirement.

## Roles

### Orchestration process

Owns:

- specification selection
- prompt construction
- quality policy decisions
- progress recording
- commit policy

### Authoritative workspace

Owns:

- the feature branch
- the authoritative diff against the integration branch
- the source documents that determine feature state

### Execution target

Owns:

- running the implementation agent
- running optional remote smoke checks when configured there
- returning changes, commits, and execution evidence

## Execution Modes

### Local execution target

The execution target is the authoritative feature worktree itself.
This is the simplest and default mode.

### Remote execution target

The execution target is a synchronized remote environment, such as a cloud container.
The authoritative workspace stays local unless a stricter remote-first design is chosen explicitly.

`engineeringagent run` still starts in the local orchestration process in this mode.

## Remote Run Sequence

1. orchestration starts locally
2. the harness acquires the authoritative feature worktree and branch
3. the harness publishes repository state to the remote target
4. prompt rendering happens from local authoritative state
5. implementation and optional smoke checks run remotely
6. the harness retrieves resulting commits, patches, or file updates
7. the harness reconciles those results into the authoritative feature workspace
8. authoritative validation, `feature_done` checks, and reviewer checks use the reconciled authoritative diff against the integration branch

## Publish Strategies

Supported strategies may include:

- worktree snapshot upload
- branch push to a remote temporary repository
- archive sync to a container volume

The chosen strategy is an adapter concern.
Application services should only know that publish and reconcile succeeded or failed.

For Python repositories, local and remote targets should provision dependencies from `pyproject.toml` and `uv.lock`.
Python tool execution should stay `uv`-based on both sides so remote runs do not drift from local iteration behavior.

## Reconciliation Strategies

Supported strategies may include:

- fast-forward feature branch to a returned commit
- apply a returned patch
- copy back changed files and create the iteration commit locally

Reconciliation must be deterministic and auditable.

## Invariants

- orchestration remains the control plane
- specification and quality policy remain local product truth
- the integration branch is never the active mutation surface during an iteration
- reviewer decisions are made against the authoritative diff, not remote-only state
- remote execution does not weaken prompt, validation, or fitness-function discipline

For v1, all validation and checks stay local because remote execution is not enabled yet.

## Future Extension Ports

- `FeatureWorkspaceManager`
- `ExecutionTarget`
- `VersionControlGateway`
- `ProgressJournal`

## Required Adapters for V1

- `GitWorktreeManager`
- `GitCliGateway`
- `SubprocessShellRunner`
- one local `AgentRunner` adapter such as `CodexConnector` or `OpenCodeConnector`

## Optional Remote Adapters

- `RemoteContainerExecutionTarget`
- one or more publish and reconcile helpers owned by the execution adapter

## Validation Rules

The harness should reject a remote-execution configuration when:

- no authoritative workspace policy is defined
- no publish strategy is configured
- no reconcile strategy is configured
- remote target identity is missing
- required credentials or connectivity settings are absent

## Design Outcome

This model lets a run start in one place and execute in another without changing the fundamental architecture.
The product still behaves like a specification-driven harness with explicit quality gates and a clear diff-based review model.
