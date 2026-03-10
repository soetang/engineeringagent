# Loop-Driven Build Plan

## Purpose

Define a phased implementation sequence that an iterative agent loop can build safely.

## Build Strategy

Build thin vertical slices.
For Python repositories, environment setup, dependency changes, and tool execution should use `uv`.
Each slice must end with one executable path, one stable acceptance condition, and a small verification set that includes focused unit or integration tests for changed behavior unless the slice is explicitly docs-only or config-only.

## Slice 1: Core Contracts and Protocol Ports

Deliver:

- domain models for specifications, plans, checks, and progress events
- ports defined as Python `Protocol` contracts
- repository configuration model

Exit criteria:

- domain objects can be loaded into memory
- Protocol-based test doubles compile under `pyright`
- architecture validation can detect forbidden imports

Verification:

- `uv run ruff check .`
- `uv run pyright`
- `uv run pytest tests/domain tests/ports`

## Slice 2: Specification Repository and Validation

Deliver:

- filesystem-backed specification repository
- validation command for `specification.yaml`, `research.md`, `plan.md`, and harness contracts
- conditional authoring rules for `direct`, `planned`, and `researched` work
- initial CLI surface for `validate`

Exit criteria:

- one valid feature specification package passes validation
- `direct` work can become `ready` without `plan.md`
- `planned` work requires `plan.md` before `ready`
- `researched` work requires both `research.md` and `plan.md` before `ready`
- malformed specification packages produce stable issues

Verification:

- `uv run ruff check .`
- `uv run pyright`
- `uv run pytest tests/validation tests/specifications`

## Slice 3: Local Workspace and Selection

Deliver:

- worktree manager
- feature selection policy
- iteration context assembly

Exit criteria:

- the system can select the next feature specification deterministically
- the system can create or refresh an isolated feature worktree

Verification:

- `uv run ruff check .`
- `uv run pyright`
- `uv run pytest tests/selection tests/worktrees`

## Slice 4: Prompt Builder and Agent Execution

Deliver:

- prompt definition repository
- prompt inspection view
- prompt builder with minimal-context rendering
- agent-runner integration
- shell-runner integration for local command execution

Exit criteria:

- blocking startup validation runs before any `AgentRunner` call
- the system can render a deterministic implementation prompt
- file-derived prompt values default to path-only rendering
- one implementation-agent request can run in a local feature workspace

Manual verify:

- inspect one prompt definition without running the agent
- run one local agent-execution smoke test against a dummy feature specification

Verification:

- `uv run ruff check .`
- `uv run pyright`
- `uv run pytest tests/prompts tests/agents tests/execution`

## Slice 5: Deterministic Quality Engine

Deliver:

- checks catalog loader
- command-check strategies
- generated command checks normalized from phase `verification_commands`
- default quality groups for `ruff`, `pyright`, and `pytest`

Exit criteria:

- the system can execute iteration-end checks from `harness/checks.yaml`
- the system can normalize phase `verification_commands` into generated checks in the same quality pipeline
- generated verification checks run only for phase `done` transitions being committed by the accepted iteration
- failures produce structured results and retry feedback

Verification:

- `uv run ruff check .`
- `uv run pyright`
- `uv run pytest tests/checks`

## Slice 6: Completion Flow and Reviewers

Deliver:

- completion confirmation rules
- diff-based reviewer checks
- iteration commit creation
- feature archival flow

Exit criteria:

- a completed feature specification can move to `done` only after quality gates pass
- reviewer checks operate on the diff against the integration branch
- one accepted iteration creates one commit

Verification:

- `uv run ruff check .`
- `uv run pyright`
- `uv run pytest tests/reviewers tests/completion`

## Slice 7: Progress Journal and Observability

Deliver:

- append-only progress journal
- iteration report model
- handoff artifact generation plus latest-handoff path lookup for internal iteration carryover
- `workspace reset` flow for blocked work
- human-readable presenter outputs

Exit criteria:

- each iteration emits a machine-readable report
- any non-archived iteration emits a handoff artifact for internal carryover
- continuing the same feature injects the latest persisted `handoff.md` path into the next implementation prompt
- blocked work can continue only after reset
- failed iterations are explainable from reports plus journal entries

Verification:

- `uv run ruff check .`
- `uv run pyright`
- `uv run pytest tests/progress tests/presentation tests/workflow`

## Slice 8: Optional Remote Execution Foundation

Deliver:

- remote-target adapter and publish/reconcile helpers
- remote-target contracts for publish and reconcile flows

Exit criteria:

- local execution remains the default path
- remote execution can be configured without changing specification or quality contracts

Manual verify:

- keep the same local execution path working unchanged
- validate that a configured remote target is recognized but still optional

Slices 1-7 define the v1 product line.
Slice 8 is explicitly post-v1 optional work.

Verification:

- `uv run ruff check .`
- `uv run pyright`
- `uv run pytest tests/execution_targets`

## Rules for the Loop

- do not start a later slice until the current slice has an executable path
- keep each slice shippable behind the CLI surface
- prefer end-to-end behavior over internal abstraction completeness
- preserve deterministic validation and diff-based review from the first slice that can support them
- do not treat a behavior-changing slice as complete until it adds or updates focused unit or integration tests

## Definition of Ready for Implementation

This architecture package is ready for a loop-driven build when:

- the loop can read a single slice and its exit criteria without consulting hidden context
- every slice names concrete verification commands
- later slices extend earlier contracts instead of rewriting them

That is the intended use of this build plan.
