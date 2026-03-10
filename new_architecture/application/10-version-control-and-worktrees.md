# Version Control and Worktrees

## Purpose

Define how the harness uses version control to isolate iteration work, keep the integration branch clean, and make review depend on a clear diff.

## Recommended Default

Use an isolated feature workspace for every active feature specification.

That means:

- one dedicated git worktree per active feature specification
- one feature branch per active feature specification
- one commit per successful iteration
- review and completion checks based on the diff to a configured integration branch

The integration branch should default to `main` and remain configurable.

## Why This Model

- the integration checkout stays clean
- each feature specification has an isolated execution context
- iteration commits produce a readable progress history
- reviewers and completion checks can use a stable diff base

## Authoritative Workspace Rule

The feature worktree and feature branch are the authoritative repository state for an active feature specification.
If execution happens somewhere else, that other location is a derived execution target and must reconcile back into the authoritative workspace.

## Workspace Layout

Recommended local layout:

```text
.engineeringagent/
  worktrees/
    FEAT-001/
      repo/
```

Recommended branch naming:

```text
ea/FEAT-001
```

## Iteration Flow

1. select the next feature specification
2. acquire or create its worktree from the integration branch or latest accepted feature branch state
3. optionally publish that worktree to a remote execution target
4. run the implementation step in the selected execution environment
5. reconcile the resulting changes back into the authoritative worktree when needed
6. run validation and checks against the authoritative feature state
7. compute diff against the configured integration branch
8. run `feature_done` checks, including reviewer checks when configured, against that diff
9. if the iteration succeeds, create one commit on the feature branch

## Review Baseline Rule

Reviewer and phase-end checks should reason about:

- the current branch diff against the integration branch
- the list of changed paths
- bounded summaries or excerpts only when explicitly required

They should not require the full repository history or unrelated file contents.

## Commit Policy

- at most one harness-created commit per successful iteration
- no commit when the iteration fails before acceptance
- commit subject uses `expected_commit_subject` when present; otherwise fallback to `feature(<feature-id>): accepted iteration`
- commit creation happens only after required quality gates pass
- the harness requires a clean isolated feature workspace before an iteration starts
- the accepted-iteration commit stages all changes produced in that workspace, including any specification status or archive updates
- if the staged diff is empty, the harness creates no commit and must not persist `done` or `archived` state transitions
- all specification and phase status writes remain provisional until the accepted-iteration commit succeeds
- after a failed iteration, the preserved dirty workspace blocks further iteration work until an explicit clean or reset action occurs

This means a feature branch will usually accumulate multiple accepted-iteration commits before the final iteration marks the feature `done` and archives it.

## Branch and Merge Policy

Recommended default:

- the feature branch accumulates accepted iteration commits
- the integration branch is never modified directly by the harness during iteration work
- final integration is a separate explicit action outside the iteration loop

This keeps iteration execution separate from promotion to the integration branch.

## Remote Execution Option

The harness may support remote execution targets such as cloud containers.

Recommended rule:

- the run starts in the orchestration process
- the orchestration process acquires the authoritative feature worktree
- the worktree or branch state is published to the remote target
- implementation and optional smoke checks may run remotely when configured
- resulting commits or file changes reconcile back into the authoritative feature branch

Authoritative validation, `feature_done` checks, and reviewer checks run only after reconciliation back into the authoritative feature workspace.

This lets the product scale to remote execution without changing its specification or quality model.

## Failure Policy

- failed iterations keep their worktree for inspection unless cleanup policy says otherwise
- a failed review does not discard repository changes automatically
- archive rollback affects managed specification state only, not arbitrary edited files
- worktree cleanup is safe only after the operator or automation no longer needs inspection state
- remote execution cleanup is safe only after reconciliation and evidence capture are complete

V1 retry policy is `block until clean/reset`.
The harness does not silently continue from a dirty failed workspace.

If a phase was marked `done` in a failed or uncommitted iteration, its generated verification checks must run again after the workspace is reset and the `done` transition is committed successfully.

## Workspace Recovery

V1 recovery action is `hard_reset_to_last_accepted_commit`.
The CLI should expose this through `workspace reset <feature-id>` backed by `WorkspaceRecoveryService`.

## Required Ports and Adapters

### Port

- `FeatureWorkspaceManager`

Responsibilities:

- create or refresh the feature worktree
- ensure the correct feature branch is checked out
- expose the workspace path for execution
- clean up or preserve the workspace according to policy

### Adapters

- `GitWorktreeManager`
- `GitCliGateway`

The worktree manager owns branch and worktree lifecycle.
The git gateway owns status, diff, and commit operations inside the workspace.

## Validation and Fitness Rules

Version-control policy should be enforced by validation and fitness functions:

- worktree root exists or can be created
- configured integration branch exists
- branch naming is deterministic
- implementation and reviewer execution happen inside the feature workspace
- review diff is computed against the integration branch, not against arbitrary local state
- remote execution reconciles into the feature workspace before review diff calculation

## Optional Stricter Mode

If stronger isolation is needed, the harness may support ephemeral iteration worktrees layered on top of the feature branch.
That is an optimization of the same design, not a different model.

## Design Outcome

This approach makes iteration state easier to inspect, review, and reason about.
It also gives the harness a stable artifact for quality checks: the current feature branch diff against the integration branch.
