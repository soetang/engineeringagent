# Specification Model

## Purpose

Define the canonical specification package that drives selection, prompting, verification, and completion.

## Design Goal

The specification package must be sufficient for a fresh implementation agent to make progress without hidden operator memory.
If a repository contains only specifications, plans, research notes, and harness policy, the system should still be able to execute a reliable delivery loop.

## Canonical Package Layout

Default layout under `paths.specifications_root`:

```text
docs/specifications/features/
  FEAT-001-short-name/
    specification.yaml
    plan.md            # required for planned/researched work
    research.md        # required for researched work only
    supporting/
```

Completed work moves to:

```text
docs/specifications/features_done/
  FEAT-001-short-name/
```

## Core Objects

### FeatureSpecification

The top-level source of truth for one change outcome.

Required fields:

- `id`
- `title`
- `kind`
- `status`
- `priority`
- `objective`
- `problem`
- `scope.in`
- `scope.out`
- `constraints`
- `acceptance`
- `planning_mode`
- `artifacts`
- `quality_profile`

Recommended fields:

- `contract_changes`
- `verification_expectations`
- `dependencies`
- `expected_commit_subject`
- `updated_at`

### ImplementationPlan

An ordered sequence of phases used only when the change needs explicit decomposition.

Each phase owns:

- `phase_id`
- `title`
- `goal`
- `status`
- `depends_on`
- `verification_commands`
- `completion_signals`

### ResearchNote

Optional context used when discovery is needed before planning or implementation.
Research informs the specification, but it does not override it.

## Status Model

Recommended specification statuses:

- `draft`
- `ready`
- `active`
- `blocked`
- `done`
- `archived`

Recommended phase statuses:

- `pending`
- `active`
- `done`
- `blocked`

Only the application layer may confirm the transition from `active` to `done`.
An implementation agent may complete phases and update evidence, but final completion is recorded only after the required quality gates pass.
All specification and phase status changes are provisional inside the feature workspace until the accepted-iteration commit succeeds.

## Planning Modes

- `direct`: no plan required; the whole specification is the active work unit
- `planned`: `plan.md` required; the active work unit is the first incomplete phase
- `researched`: `research.md` and `plan.md` required before execution begins

Planning mode controls how the harness selects the next unit of work.

Priority order is canonical and descending:

- `critical`
- `high`
- `medium`
- `low`

## Selection Rules

1. consider only `active` or `ready` feature specifications
2. prefer `active` over `ready`
3. within the same status bucket, sort by priority descending, then by feature identifier ascending
4. for `direct`, select the specification itself
5. for `planned` or `researched`, select the first non-done phase whose dependencies are complete
6. never select a blocked specification or blocked phase
7. treat missing phase dependencies or dependency cycles as validation failures
8. when a `ready` feature specification is selected for an iteration, the harness transitions it to `active` before prompt rendering
9. if a candidate has no executable phase because prerequisites are not yet satisfied, skip it with reason code `NO_EXECUTABLE_PHASE`
10. if all candidates are skipped for that reason, end selection with stable blocked result `NO_EXECUTABLE_FEATURE`

## Completion Rules

A feature specification becomes eligible for `done` when:

- all required phases are done
- acceptance criteria are satisfied
- any declared contract changes are reflected in the specification artifacts

It becomes confirmed `done` only when the application layer also verifies that:

- required validations have passed
- required checks have passed
- required reviewer decisions are approved

It becomes `archived` only after the system records confirmed completion and moves the package to done storage.

## Quality Profile

Every feature specification carries a quality profile that tells the harness how much enforcement is required.

The profile should answer:

- which validation families are mandatory
- which check groups run at iteration end
- which check groups run at feature completion
- whether reviewer approval is required
- whether contract-change evidence is mandatory

This allows the specification itself to declare the level of rigor needed for delivery.

The quality profile binds a feature specification to named check groups defined in `harness/checks.yaml`.

## Canonical `specification.yaml` Shape

```yaml
id: FEAT-001
title: Run a repository harness from feature specifications
kind: feature
status: ready
priority: high
objective: Let operators describe work once and let the harness drive execution.
problem: Repository automation is inconsistent and depends on hidden operator memory.
scope:
  in:
    - feature specification packages
    - deterministic quality gates
    - agent-driven implementation loop
  out:
    - hosted orchestration service
constraints:
  - Keep domain and application policy separate from adapters.
  - Prefer deterministic checks before reviewer agents.
acceptance:
  - The harness selects a feature specification and active phase deterministically.
  - The implementation agent receives enough context from specification artifacts alone.
planning_mode: planned
artifacts:
  plan: required
  research: optional
quality_profile:
  validation: required
  iteration_end_groups: [style, typecheck, tests]
  feature_done_groups: [style, typecheck, tests, reviewer]
  reviewer_policy: required_on_completion
contract_changes: []
verification_expectations:
  - uv run ruff check .
  - uv run pyright
  - uv run pytest
expected_commit_subject: feature: implement harness-driven specification loop
```

## Canonical `plan.md` Shape

`plan.md` should begin with structured frontmatter that the harness can parse.
The markdown body then gives human-readable detail per phase.

Required frontmatter fields per phase:

- `phase_id`
- `title`
- `status`
- `goal`
- `depends_on`
- `verification_commands`
- `completion_signals`

`verification_commands` are normalized into generated command checks for the `iteration_end` phase.
They are not executed as a second independent verification mechanism outside the checks system.
Their canonical v1 representation is argv vectors (`list[list[str]]`), not shell strings.
They run once, in the iteration where the phase first transitions to `done` in a committed accepted iteration.

For Python repositories, `verification_commands` should use `uv` as the command root.
Canonical forms are `[uv, run, pytest, ...]`, `[uv, run, ruff, ...]`, and `[uv, run, pyright, ...]`.
Ad hoc `pip`, `venv`, `poetry`, or shell-activated virtualenv flows are non-canonical in this architecture.

Each phase that changes runtime behavior should include at least one targeted unit or integration test command proving that behavior.
Docs-only or config-only phases may omit that only when the phase's `completion_signals` make the exception explicit.

Canonical frontmatter shape:

```yaml
---
phases:
  - phase_id: P1
    title: Establish specification repository and selection
    status: pending
    goal: Make the harness select one active specification deterministically.
    depends_on: []
    verification_commands:
      - [uv, run, pytest]
    completion_signals:
      - selection works from specification artifacts alone
---
```

The body should expand on decisions, tradeoffs, and implementation notes without becoming the source of truth for status.

## Status Transition Rules

Allowed specification transitions:

- `draft -> ready`
- `ready -> active`
- `active -> blocked`
- `blocked -> active`
- `active -> done`
- `done -> archived`

Forbidden transitions:

- `draft -> done`
- `ready -> archived`
- `blocked -> done` without returning to `active`

Allowed phase transitions:

- `pending -> active`
- `active -> done`
- `active -> blocked`
- `blocked -> active`

## Prompt Contract for the Implementation Agent

When the harness invokes the implementation agent, it must provide at least:

- the selected feature identifier
- the path to `specification.yaml`
- the path to `plan.md`, when present
- the path to `research.md`, when present
- the path to the latest persisted `handoff.md`, when continuing the same feature
- latest retry feedback
- any additional repository artifact paths the prompt definition explicitly requires

The prompt should not require the agent to infer missing product intent from repository archaeology.
Referenced files should be passed as paths by default.
Their contents should be interpolated only when the active prompt definition explicitly requests excerpts or full content.

## Minimum Buildable Rule

If a new repository contains:

- one valid feature specification package
- one valid harness configuration
- one configured agent adapter

then the system should be able to:

1. validate the repository
2. select the next work unit
3. run one implementation iteration
4. execute the relevant quality checks
5. produce an iteration report and progress records, plus handoff when the feature remains unarchived

That is the minimum standard for the specification model.
