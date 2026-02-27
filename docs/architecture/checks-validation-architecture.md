# Checks Validation Architecture (To-Be)

## Purpose

Define a validation architecture where repository-level policy and check-type-specific policy are owned by separate modules while preserving one deterministic `engineeringagent validate` entrypoint.

## Non-goals

- Define migration sequencing.
- Change check execution semantics in `checks run`.
- Replace the existing checks orchestration strategy model.

## Core Outcome

Validation ownership is explicit:

- Repo-level validation owns cross-cutting repository contracts (spec/docs/process invariants).
- Each check strategy may optionally own static validation for its own config/artifacts.
- `engineeringagent validate` composes both via a registry and emits deterministic results.

## Public API

`run_validate(project_root, *, schema_only=False) -> list[str]`

Behavior:

- Runs repo validators in deterministic order.
- Runs registered strategy validators in deterministic order.
- Returns deterministic, user-facing messages.
- Performs static checks only (no command execution, no reviewer agent execution).

## Contracts

### ValidationContext

Static validation context shared across validators.

Required fields:

- `project_root`
- `docs_root`
- `schema_only`

Optional fields:

- `selected_groups` (future filter support)
- `docs_map_config` (future resolved docs mapping)

### ValidationIssue

Canonical internal issue model before rendering.

Fields:

- `validator_id`
- `scope` (`repo` or `strategy`)
- `path` (logical source path)
- `message`
- `code` (stable rule id)

### RepoValidator

Protocol for repository-level validators.

- `validator_id`
- `validate(context) -> tuple[ValidationIssue, ...]`

### StrategyValidator (Optional Capability)

Optional protocol implemented by check strategies (or strategy-owned validator modules).

- `strategy_type`
- `validator_id`
- `validate(context) -> tuple[ValidationIssue, ...]`

Note: strategy validation is a capability, not a required no-op method on every strategy.

### ValidationRegistry

Registry that composes:

- Repo validators
- Strategy validators discovered from registered strategies (or explicit strategy-validator registration)

The registry enforces deterministic ordering and rejects duplicate `validator_id` registrations.

## Ownership Rules

### Repo-level validation owns

- feature schema sync
- feature id and file invariants
- active/done archival policy
- AGENTS docs-map references
- purge invariants and other cross-cutting repository policies

### Strategy-owned validation owns

- reviewer prompt static hygiene and reviewer-owned prompt policy
- fitness catalog and manifest integrity checks
- command-check static config linting (if not already guaranteed by contract schema)

## Execution Model

1. Build `ValidationContext`.
2. Resolve registry (repo validators plus strategy validators).
3. Run validators in deterministic order.
4. Aggregate `ValidationIssue` values.
5. Render deterministic message strings for CLI output.

## Boundary Rules

- Repo validators must not encode strategy-specific policy.
- Strategy validators must not encode repo-global policy.
- Runtime preconditions (for example, reviewer `feature_path` requirements for execution) stay in request normalization and execution paths, not static repo validation.
- Validators are side-effect free and deterministic.

## Integration with Checks Orchestration

This architecture complements checks orchestration:

- `checks run` continues to use check strategies for planning and execution.
- `validate` uses validator ownership aligned to those same strategy boundaries.
- A strategy can evolve execution and static validation independently behind stable contracts.

## Extensibility Rules

Adding a new check type requires:

1. Strategy implementation and registration.
2. Optional strategy validator implementation and registration.
3. Tests for deterministic validation output (when a validator exists).

No repo-level validator changes are required for strategy-local rules.

## Invariants

- One stable `engineeringagent validate` entrypoint.
- Deterministic validator order and message order.
- Single ownership per validation rule.
- No duplication of strategy policy inside repo validator.
- Static validation remains side-effect free.
