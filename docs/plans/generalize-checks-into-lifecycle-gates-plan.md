---
schema_version: 1
task_id: generalize-checks-into-lifecycle-gates
title: Generalize checks into lifecycle gates
status: ready
branch: feat/generalize-checks-into-lifecycle-gates
base_branch: main
phases:
  - id: rename
    title: Rename quality and checks concepts to gates
    status: todo
  - id: orchestrator
    title: Add BeforeImplementation gate phase to the orchestrator
    status: todo
  - id: cli-and-scaffolding
    title: Rename CLI, schema, config, and scaffolding surfaces to gates
    status: todo
  - id: tests-and-docs
    title: Update tests and docs for gates
    status: todo
---

# Generalize Checks into Lifecycle Gates

## Goal

Keep the change simple.

Rename the current quality/checks subsystem to **gates**, add a new orchestrator-owned `BeforeImplementation` phase, and run configured gates at that phase before the first agent iteration starts.

After this change:

- repositories declare `gates` instead of `checks`;
- gates can run at `BeforeImplementation`, `IterationComplete`, and `ImplementationComplete`;
- gates still execute in YAML declaration order;
- `BeforeImplementation` failure aborts the run before any agent prompt or iteration starts; and
- iteration and completion failures still become loop feedback.

## Scope

Include only:

- an internal rename from `quality` / `checks` to `gates`;
- a new orchestrator-owned `BeforeImplementation` phase;
- gate execution at that phase before the loop starts;
- gate config renamed to `gates`, `gate_type`, and `gates.root_path`; and
- CLI, schema, scaffolding, and harness updates to match.

Do not include:

- stage buckets such as transform vs check;
- numeric ordering fields;
- publication flow changes;
- a new `engineeringagent.lifecycle` package; or
- compatibility aliases for old names.

## Implementation Progress Checklist

Use these checkboxes during implementation.

- [ ] Rename `engineeringagent.quality` to `engineeringagent.gates` and update imports.
- [ ] Rename config and schema terms from `checks` to `gates`.
- [ ] Keep `GatePhase` orchestrator-owned and add `BeforeImplementation`.
- [ ] Keep `GateRunner` orchestrator-owned and wire the concrete implementation from `engineeringagent.application`.
- [ ] Run `BeforeImplementation` once before any agent prompt.
- [ ] Abort immediately if a `BeforeImplementation` gate fails.
- [ ] Rename CLI and scaffolding surfaces to `gates`.
- [ ] Add `uv sync` as the repository's default `BeforeImplementation` gate.
- [ ] Update tests and docs.

## Current State

Today:

- the config root is `checks.yaml` via `quality.checks_path`;
- manifests use `checks:` and `check_type`;
- `GatePhase` only supports `IterationComplete` and `ImplementationComplete`;
- `ImplementationAgent` runs configured checks only after an iteration or after completion;
- generated scaffolds still create `checks.yaml` and quality files; and
- docs still teach `quality` / `checks` terminology.

This means deterministic setup work has no first-class phase before the loop starts.

## Decision

Adopt **gates** as the primary abstraction.

Keep the architecture simple:

- keep phases owned by `engineeringagent.orchestrators.loop`;
- keep the orchestrator dependency direction unchanged;
- rename the concrete subsystem from `engineeringagent.quality` to `engineeringagent.gates`; and
- extend the existing gate model rather than introducing a second abstraction layer.

## Target Architecture

### Orchestrator ownership

- `GatePhase` stays in `engineeringagent.orchestrators.loop.models`.
- Add `BeforeImplementation` to `GatePhase`.
- `GateRunner` stays in `engineeringagent.orchestrators.loop.protocols`.
- `engineeringagent.orchestrators` must not import concrete modules from `engineeringagent.gates`, `engineeringagent.application`, or `engineeringagent.workspaces`.
- `engineeringagent.application` composes the concrete gate runner and injects it into the orchestrator.

### Gates subsystem

Rename the existing subsystem in place:

- `engineeringagent.quality` → `engineeringagent.gates`

Keep the same overall responsibilities, just with gate-oriented names:

- models
- settings
- protocol
- collection service
- validation service
- runner
- schema service
- adapters

### Config model

Rename the public config shape to:

- `gates.yaml`
- `gates:`
- `gate_type`
- `gates.root_path`

Example root manifest:

```yaml
gates:
  - name: Local commands
    filepath: gates/commands.yaml
```

Example referenced file:

```yaml
name: commands
filepath: ""
gates:
  - gate_type: command
    phases: ["BeforeImplementation"]
    command: ["uv", "sync"]
  - gate_type: command
    phases: ["IterationComplete", "ImplementationComplete"]
    command: ["ruff", "format"]
  - gate_type: command
    phases: ["ImplementationComplete"]
    command: ["pytest"]
```

### Runtime behavior

`ImplementationAgent` should run gates in this order:

1. observer validation
2. `BeforeImplementation` gates
3. first prompt + first agent iteration
4. `IterationComplete` gates after each iteration
5. `ImplementationComplete` gates after task completion

Failure behavior:

- if `BeforeImplementation` fails, abort immediately before any prompt build or agent run;
- if `IterationComplete` fails, return feedback into the next iteration;
- if `ImplementationComplete` fails, return feedback into the next iteration.

## Repository Defaults

This repository should adopt the new naming and default setup gate in the same change.

Required repository updates:

- rename `harness/checks.yaml` to `harness/gates.yaml`;
- rename the TOML key from `quality.checks_path` to `gates.root_path`;
- add a `BeforeImplementation` command gate that runs `uv sync`; and
- keep existing deterministic validation commands under the renamed gate manifests.

Recommended default gate entry:

```yaml
gates:
  - gate_type: command
    phases: ["BeforeImplementation"]
    command: ["uv", "sync"]
```

## Required Implementation Work

### Phase 1: Rename the subsystem

- [ ] Rename `engineeringagent.quality` package paths to `engineeringagent.gates`.
- [ ] Rename check-oriented models, protocols, services, adapters, and imports to gate-oriented names.
- [ ] Rename the top-level config keys from `checks` to `gates`.
- [ ] Rename direct-entry typing from `check_type` to `gate_type`.
- [ ] Rename TOML-backed settings from `quality.checks_path` to `gates.root_path`.
- [ ] Rename schema generation from quality/check wording to gates wording.

### Phase 2: Add the new orchestrator phase

- [ ] Add `BeforeImplementation` to `GatePhase`.
- [ ] Update the concrete gate runner to filter and execute `BeforeImplementation` gates.
- [ ] Update `ImplementationAgent` to run `BeforeImplementation` before the first prompt is built.
- [ ] Ensure `BeforeImplementation` failure aborts before any agent iteration starts.
- [ ] Keep `IterationComplete` and `ImplementationComplete` behavior unchanged apart from the renamed gate terminology.
- [ ] Preserve short-circuit-on-first-failure behavior for orchestrator usage.

### Phase 3: Rename public surfaces

- [ ] Rename the CLI group from `check` to `gates`.
- [ ] Rename schema output from `engineeringagent schema quality` to `engineeringagent schema gates`.
- [ ] Update `init` scaffolding to generate `gates.yaml` and referenced gate files.
- [ ] Update generated `engineeringagent.toml` defaults to point at `gates.root_path`.
- [ ] Update AGENTS scaffolding text to teach `engineeringagent gates run`, `engineeringagent gates validate`, and `engineeringagent schema gates`.
- [ ] Update this repository's checked-in harness files to include the `uv sync` setup gate.

### Phase 4: Tests and docs

- [ ] Update unit tests for config parsing, validation, schema export, collection, and runner behavior.
- [ ] Update orchestrator tests to cover `BeforeImplementation` execution.
- [ ] Add tests proving setup failure aborts before any prompt build or agent run.
- [ ] Update CLI tests for the renamed `gates` command group.
- [ ] Add tests proving removed old surfaces fail clearly, including `engineeringagent check ...` and `engineeringagent schema quality`.
- [ ] Update onboarding and reference docs from quality/check wording to gates wording.

## Impacted Existing Files

- `src/engineeringagent/orchestrators/loop/models.py`
- `src/engineeringagent/orchestrators/loop/protocols.py`
- `src/engineeringagent/orchestrators/loop/implementation_agent.py`
- `src/engineeringagent/application/workspace_bridges.py`
- `src/engineeringagent/application/services/check_service.py`
- `src/engineeringagent/application/services/schema_service.py`
- `src/engineeringagent/presentation/cli.py`
- `src/engineeringagent/presentation/commands/check.py`
- `src/engineeringagent/presentation/commands/schema.py`
- `src/engineeringagent/scaffolding/paths.py`
- `src/engineeringagent/scaffolding/service.py`
- `src/engineeringagent/scaffolding/templates.py`
- `src/engineeringagent/quality/`
- `engineeringagent.toml`
- `docs/getting-started.md`
- `docs/reference.md`
- `harness/checks.yaml`
- `harness/fitness_functions.yaml`

## Testing Strategy

Minimum coverage for this slice:

- gate collection preserves YAML order and referenced-file traversal order;
- phase filtering works for single and multi-phase gates;
- `BeforeImplementation` executes once before the first prompt;
- `BeforeImplementation` failure aborts before any prompt build or agent execution;
- iteration and completion failures still become loop feedback;
- CLI output still renders one line per executed gate; and
- scaffolded repositories validate and run with the new gate-oriented paths, including the default `uv sync` setup gate.

## Risks and Mitigations

### Risk: rename blast radius becomes too large

Mitigation:

- keep the change focused on the internal rename, the new phase, and the renamed surfaces; and
- avoid introducing extra abstraction layers.

### Risk: before-implementation semantics become confusing

Mitigation:

- keep v1 behavior strict and simple: run once before the agent starts, and abort immediately if setup fails.

### Risk: orchestrator boundary gets weakened

Mitigation:

- keep phase names and the runner port owned by `engineeringagent.orchestrators.loop`; and
- continue composing concrete gate implementations only from `engineeringagent.application`.

## Recommended Delivery Order

1. rename `quality` / `checks` concepts to `gates`;
2. add `BeforeImplementation` to the orchestrator and execute it before the loop; and
3. update CLI, schema, scaffolding, harness files, tests, and docs.
