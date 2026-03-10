# Handoff and Resumption

## Purpose

Define how the system hands work off between iterations or future execution environments without making chat history the source of truth.

## Core Rule

Handoff is an operational summary, not product truth.
The source of truth remains:

- feature specifications
- plans and research artifacts
- accepted iteration commits
- append-only progress events

Handoff artifacts summarize what the next iteration model needs to know.
They are internal runtime artifacts, not part of the CLI surface.
They are persisted precisely so the next model can read the handoff file by path during prompt assembly.

## When Handoff Is Emitted

- an accepted iteration commits work but the feature remains unarchived
- an iteration fails during implementation, validation, checks, or review
- the accepted-iteration commit cannot be created and the feature remains unarchived
- the workspace is blocked pending reset
- a future remote execution flow needs carryover context between environments

A successful iteration that archives the feature does not emit a new handoff.

## Canonical Handoff Artifacts

Store handoff artifacts under the effective `paths.progress_root`.
With default configuration that is `.engineeringagent/progress/`:

```text
.engineeringagent/progress/
  FEAT-001/
    iteration-report.json
    handoff.md
```

- `iteration-report.json` is the machine-readable record
- `handoff.md` is an internal model-facing carryover artifact

`iteration-report.json` is written for every finalized iteration outcome.
`handoff.md` is written only when the feature remains unarchived after finalization.

`ProgressJournal` owns persistence of both artifacts.

## Required Handoff Content

Every handoff should include:

- feature identifier
- current branch and workspace path
- execution mode (`local_worktree` or future remote mode)
- specification, plan, and research paths
- latest accepted commit, if any
- carryover summary for the next iteration
- current failure or stop reason, when relevant
- current workspace state (`clean`, `dirty`, `blocked`)
- pending quality gates, if any

## Canonical `handoff.md` Shape

```md
# Handoff

- Feature: `FEAT-001`
- Workspace: `.engineeringagent/worktrees/FEAT-001/repo`
- Branch: `ea/FEAT-001`
- Execution mode: `local_worktree`
- Specification: `docs/specifications/features/FEAT-001/specification.yaml`
- Plan: `docs/specifications/features/FEAT-001/plan.md`
- Research: `docs/specifications/features/FEAT-001/research.md`
- Latest accepted commit: `abc1234`
- Carryover summary: continue from phase `P1` and address the failing generated verification check
- State: `blocked`
- Reason: `pytest` failed in generated verification check `verify::FEAT-001::P1::0`
- Pending gates: `iteration_end/tests`
```

## Resumption Rule

The next iteration starts from repository artifacts plus the latest handoff artifact.
It must not require prior chat context.

When continuing the same feature, the run loop asks `ProgressJournal.latest_handoff_path(feature_id)` for the persisted file and passes that path through prompt assembly as the optional `handoff_path` interpolation.
`engineeringagent run` consumes handoff internally through that prompt-building flow rather than exposing handoff as a separate CLI resume surface.
Recovery actions such as workspace reset are separate operational concerns, not part of the handoff contract itself.

## Relationship to Progress Journal

- progress journal: append-only event stream
- iteration report: machine-readable result snapshot
- handoff: concise internal carryover summary for the next iteration

These are related, but not interchangeable.

## Design Goal

The next iteration should be able to consume `handoff.md` and continue with the right context without relying on prior chat history.
