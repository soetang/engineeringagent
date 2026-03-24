---
schema_version: 1
task_id: generalize-checks-into-lifecycle-steps
title: Generalize checks into lifecycle steps
status: ready
branch: feat/generalize-checks-into-lifecycle-steps
base_branch: main
phases:
  - id: contract
    title: Define the steps contract and rename the domain boundary
    status: todo
  - id: runtime
    title: Replace check-gate execution with lifecycle-step execution
    status: todo
  - id: cli-and-scaffolding
    title: Rename CLI, schema, and scaffolding surfaces to steps
    status: todo
  - id: tests-and-docs
    title: Update tests, schemas, and documentation for lifecycle steps
    status: todo
---

# Generalize Checks into Lifecycle Steps

## Goal

Replace the current check-centric quality gate model with a simpler lifecycle-step model that can run deterministic commands at multiple implementation phases.

After this change:

- repositories can declare ordered `steps` instead of `checks`;
- a step can run in one or more lifecycle phases;
- steps execute in YAML declaration order;
- the first blocking step failure becomes the feedback returned to the implementation loop; and
- scaffolding and docs stop teaching checks as the primary abstraction.

## Scope

Keep v1 intentionally small.

Include only:

- three phases: `BeforeImplementation`, `IterationComplete`, and `ImplementationComplete`;
- ordered execution based on YAML declaration order only;
- step failure feedback shared through the existing implementation loop;
- current deterministic command execution and existing adapter-backed step kinds; and
- a direct in-place rename from `quality` / `checks` to `steps`.

Do not include in this slice:

- explicit stage buckets such as `transform` vs `check`;
- numeric ordering fields;
- commit, push, or pull-request publication as lifecycle steps;
- non-blocking reporting hooks; or
- a broad rewrite of observer-based publication behavior.

## Current State

The current system is split across two concepts:

1. a phase-aware quality check runner; and
2. an implementation loop that only knows about gate pass/fail.

Today:

- the config root is `checks.yaml` via `QualitySettings.checks_path`;
- the root and referenced YAML files both use `checks:` entries;
- direct entries are typed by `check_type` and can declare one `phase`;
- `GatePhase` only supports `IterationComplete` and `ImplementationComplete`;
- `ImplementationAgent` calls `CheckGateRunner.check(...)` after each iteration and after completion;
- `CommandAdapter` already provides deterministic subprocess execution;
- generated scaffolds still create `checks.yaml` and `quality/commands.yaml`; and
- docs and schema surfaces still describe the feature as `quality` / `checks`.

This makes setup-style deterministic work awkward to express and keeps the implementation loop coupled to the narrower idea of “checks”.

## Decision

Adopt **lifecycle steps** as the new primary abstraction.

### v1 execution model

A lifecycle step is a deterministic executable entry that declares:

- `name`
- `step_type`
- `phases`
- step-type-specific payload such as `command`

Execution rules for v1:

1. select steps matching the requested lifecycle phase;
2. preserve YAML declaration order;
3. execute sequentially;
4. stop on the first failure for implementation-loop gate usage; and
5. return the failed step message as feedback.

### v1 simplifications

Do **not** model semantic differences such as transform vs check in runtime behavior yet.

For the implementation loop, the important behavior is simply:

- run configured lifecycle steps;
- if one fails, return the reason as agent feedback.

### Rename rule

Do the rename directly instead of carrying legacy translation layers.

For this slice:

- prefer `steps.yaml`, `steps:`, `step_type`, and step-oriented CLI/schema names only;
- rename the existing `engineeringagent.quality` package in place to `engineeringagent.steps`; and
- avoid introducing a second package such as `engineeringagent.lifecycle` alongside the renamed subsystem.

## Implementation Progress Checklist

Use this checklist during implementation and update the checkboxes as work lands.

- [ ] Rename the `engineeringagent.quality` package to `engineeringagent.steps` and update imports.
- [ ] Rename check-oriented models, protocols, services, and adapters to step-oriented names.
- [ ] Replace `GatePhase` with orchestrator-owned `LifecyclePhase`, including `BeforeImplementation`.
- [ ] Add step config models using `steps`, `step_type`, and `phases`.
- [ ] Rename TOML config ownership from `quality.checks_path` to `steps.root_path`.
- [ ] Keep orchestrator dependency direction intact by wiring concrete step runners only from `engineeringagent.application`.
- [ ] Run `BeforeImplementation` once before any agent prompt and abort immediately on failure.
- [ ] Replace iteration/final gate execution with lifecycle-step execution.
- [ ] Rename CLI and schema surfaces to `engineeringagent step ...` and `engineeringagent schema steps`.
- [ ] Update scaffolding, docs, and harness files to the new step-oriented names.
- [ ] Add and pass the required rename, loop, and failure-behavior tests.

## Target Architecture

### Domain model

Replace check-specific loop terms with lifecycle-step terms:

- `GatePhase` → `LifecyclePhase`
- `GateRunner` → `LifecycleStepRunner`
- `CheckGateRunner` → `LifecycleStepRunner` implementation

Architectural ownership rule:

- `LifecyclePhase` remains owned by `engineeringagent.orchestrators.loop` because phases describe orchestrator timing, not step configuration;
- `engineeringagent.steps` consumes the orchestrator-owned phase contract when filtering and executing steps; and
- `engineeringagent.orchestrators` must continue to define ports and domain models without importing from `engineeringagent.steps`, `engineeringagent.application`, `engineeringagent.workspaces`, or other infrastructure-facing modules.

Recommended phase enum for v1:

- `BeforeImplementation`
- `IterationComplete`
- `ImplementationComplete`

### Configuration model

Introduce a step-oriented config model that mirrors the current file-reference pattern.

Recommended public shape:

```yaml
steps:
  - name: Local commands
    filepath: steps/commands.yaml
```

Referenced file example:

```yaml
name: commands
filepath: ""
steps:
  - step_type: command
    phases: ["BeforeImplementation"]
    command: ["uv", "sync"]
  - step_type: command
    phases: ["IterationComplete", "ImplementationComplete"]
    command: ["ruff", "format"]
  - step_type: command
    phases: ["ImplementationComplete"]
    command: ["pytest"]
```

### Runtime model

The implementation loop should run lifecycle steps in three places:

1. once before the first implementation iteration for `BeforeImplementation`;
2. after each agent iteration for `IterationComplete`; and
3. after task completion for `ImplementationComplete`.

Recommended behavior:

- keep `observer.validate(...)` as the infrastructure preflight hook;
- run `BeforeImplementation` lifecycle steps after observer validation and before the first prompt;
- if `IterationComplete` or `ImplementationComplete` step execution fails, return feedback to the agent loop as today; and
- if `BeforeImplementation` fails, abort the run immediately before any agent prompt or agent iteration is started.

That keeps v1 simple while still creating the extensibility point for setup commands.

### Repository-default manifest updates

This repository should adopt the new step model in its own checked-in harness/config as part of the same change.

Required repository updates:

- rename `harness/checks.yaml` to `harness/steps.yaml`;
- add a `BeforeImplementation` command step that runs `uv sync`;
- keep the existing deterministic validation commands under the renamed step manifests; and
- rename the TOML config path to `steps.root_path` so the repository points at the new root step manifest.

Recommended repository-owned setup entry:

```yaml
steps:
  - step_type: command
    phases: ["BeforeImplementation"]
    command: ["uv", "sync"]
```

## Proposed File Ownership

Rename the existing `engineeringagent.quality` subsystem in place to `engineeringagent.steps`.

Recommended target files:

- `src/engineeringagent/steps/models.py`
- `src/engineeringagent/steps/protocol.py`
- `src/engineeringagent/steps/settings.py`
- `src/engineeringagent/steps/services/collection_service.py`
- `src/engineeringagent/steps/services/validation_service.py`
- `src/engineeringagent/steps/services/runner.py`
- `src/engineeringagent/steps/services/schema_service.py`
- `src/engineeringagent/steps/adapters/...`

Architectural rule for this slice:

- do not keep `engineeringagent.quality` as a parallel package;
- do not introduce a separate `engineeringagent.lifecycle` package; and
- finish the rename with application wiring, CLI, schema, docs, and scaffolding all pointing at `engineeringagent.steps`.

Dependency rule for this slice:

- `engineeringagent.orchestrators.loop` remains the domain owner of lifecycle timing and phase names;
- `engineeringagent.orchestrators` must not import concrete execution/config modules from `engineeringagent.steps`;
- `engineeringagent.steps` may import orchestrator-owned phase models or protocols when needed; and
- `engineeringagent.application` continues to compose concrete `engineeringagent.steps` implementations into orchestrator-owned ports.

## Required Implementation Work

### Phase 1: Define the contract and rename the subsystem

- [ ] Add `LifecyclePhase` with `BeforeImplementation`, `IterationComplete`, and `ImplementationComplete`.
- [ ] Define a step-root model replacing the top-level `checks` terminology with `steps`.
- [ ] Rename direct-entry typing from `check_type` to `step_type`.
- [ ] Allow one step entry to target multiple phases through `phases`.
- [ ] Rename `engineeringagent.quality` modules, imports, and service names to `engineeringagent.steps`.
- [ ] Rename TOML-backed settings from `quality.checks_path` to `steps.root_path`.
- [ ] Update schema generation to emit only the step-oriented public schema.

### Phase 2: Replace gate execution with lifecycle-step execution

- [ ] Replace `CheckCollectionService` with a step-oriented collection service that preserves declaration order across file references.
- [ ] Replace `CheckGateRunner` with a lifecycle-step runner that filters by `LifecyclePhase` and returns loop-ready feedback.
- [ ] Keep adapter-backed execution so existing command and agentic-review behavior still works.
- [ ] Define an orchestrator-owned runner protocol and ensure `ImplementationAgent` depends on that protocol rather than importing `engineeringagent.steps` directly.
- [ ] Update `ImplementationAgent` to run `BeforeImplementation` once before entering the loop.
- [ ] Ensure `BeforeImplementation` failure aborts before any prompt is built or any agent iteration starts.
- [ ] Update `ImplementationAgent` to call the lifecycle-step runner instead of the check gate runner for iteration and completion phases.
- [ ] Keep short-circuit-on-first-failure behavior for implementation-loop usage.

### Phase 3: Rename public surfaces and scaffold defaults

- [ ] Add the lifecycle-step CLI group as `engineeringagent step validate` and `engineeringagent step run`.
- [ ] Remove the old `engineeringagent check ...` CLI surface rather than carrying both names.
- [ ] Rename the schema command surface from `engineeringagent schema quality` to `engineeringagent schema steps` and remove the old name.
- [ ] Update `init` scaffolding to generate `steps.yaml` and referenced step files instead of `checks.yaml` and quality files.
- [ ] Update generated `engineeringagent.toml` defaults to point at `steps.root_path`.
- [ ] Update AGENTS scaffolding text to teach `engineeringagent step ...` and `engineeringagent schema steps` as the preferred workflow.
- [ ] Update the repository's checked-in harness files to include a `BeforeImplementation` `uv sync` step in `harness/steps.yaml`.

### Phase 4: Tests, docs, and rename coverage

- [ ] Update unit tests for config parsing, schema export, collection, validation, and runner behavior.
- [ ] Update loop tests to cover `BeforeImplementation` execution and failure handling.
- [ ] Update CLI tests for the renamed `step` command group.
- [ ] Add tests proving setup failure aborts before any prompt build or agent execution.
- [ ] Add tests proving removed legacy surfaces fail clearly, including `checks.yaml`-shaped config, `engineeringagent check ...`, and `engineeringagent schema quality`.
- [ ] Update onboarding/reference docs and relevant plan docs away from quality/check wording where they describe the current product surface.
- [ ] Update harness fixtures to use the new preferred step naming.

## Impacted Existing Files

Expected primary touch points:

- `src/engineeringagent/orchestrators/loop/models.py`
- `src/engineeringagent/orchestrators/loop/protocols.py`
- `src/engineeringagent/orchestrators/loop/implementation_agent.py`
- `src/engineeringagent/application/workspace_bridges.py`
- `src/engineeringagent/application/services/check_service.py` (rename to step service)
- `src/engineeringagent/application/services/schema_service.py`
- `src/engineeringagent/presentation/cli.py`
- `src/engineeringagent/presentation/commands/check.py` (rename to step command)
- `src/engineeringagent/presentation/commands/schema.py`
- `src/engineeringagent/scaffolding/paths.py`
- `src/engineeringagent/scaffolding/service.py`
- `src/engineeringagent/scaffolding/templates.py`
- `src/engineeringagent/quality/` (rename package to `src/engineeringagent/steps/`)
- `engineeringagent.toml`
- `docs/getting-started.md`
- `docs/reference.md`
- `harness/checks.yaml`
- `harness/fitness_functions.yaml`

## Testing Strategy

Minimum test coverage for this slice:

- collection service preserves YAML order and referenced-file traversal order;
- phase filtering works for single and multi-phase steps;
- `BeforeImplementation` executes once before the first agent prompt;
- `BeforeImplementation` failure aborts before any prompt build or agent execution;
- iteration and final failures still become loop feedback;
- CLI output still renders one line per executed step;
- removed legacy surfaces fail clearly; and
- scaffolded repositories validate and run with the new step-oriented paths, including the default `uv sync` setup step.

## Risks and Mitigations

### Risk: rename blast radius becomes too large

Mitigation:

- rename the subsystem in one coherent slice instead of mixing old and new vocabulary;
- keep the architecture simple by avoiding bridge layers and duplicate packages; and
- update scaffolding, docs, and CLI together so new usage is consistent immediately.

### Risk: before-implementation semantics become confusing

Mitigation:

- keep v1 behavior strict and simple: run once before the agent starts, and abort immediately if setup fails; and
- revisit agent-retry semantics only after step execution is established.

### Risk: adapter migration breaks non-command checks

Mitigation:

- keep the existing adapter registration pattern;
- rename interfaces at the boundary but preserve adapter-backed execution behavior; and
- add tests for both `command` and `agentic_review` step shapes.

## Recommended Delivery Order

Implement this in three reviewable commits or PR-sized slices if possible:

1. domain/runtime rename from quality/checks to steps;
2. loop integration with `BeforeImplementation`; and
3. CLI, scaffolding, schema, and docs migration with rename coverage.
