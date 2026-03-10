---
plan_id: FEAT-097
feature_id: FEAT-097
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Create checks package skeleton and supported exports
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q
- id: ST-002
  title: Move canonical fitness envelope emitter under checks (with shim)
  status: done
  verification:
  - uv run pytest -q
- id: ST-003
  title: Implement run_checks group orchestration contract
  status: done
  verification:
  - uv run pytest -q
- id: ST-007
  title: Remove forbidden dataclasses usage and ruff suppressions in checks API
  status: done
  verification:
  - uv run pytest -q
  - uv run python -m engineeringagent.cli fitness run --format json
- id: ST-006
  title: Implement validate group execution under checks
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q
- id: ST-004
  title: Implement commands+fitness execution under checks (parity with current behavior)
  status: done
  verification:
  - uv run pytest -q
- id: ST-005
  title: Implement reviewers execution under checks without OpenCode logic
  status: done
  verification:
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Create checks package skeleton and supported exports

Add `src/engineeringagent/checks/` with `validate/`, `commands/`, `fitness/`, `reviewers/`, and define the narrow export surface in `src/engineeringagent/checks/__init__.py`.

## ST-002 Move canonical fitness envelope emitter under checks (with shim)

Implement `emit_fitness_result` under `checks/` and provide `emit_result_envelope` alias. Keep `engineeringagent.fitness.envelope.emit_result_envelope` working by delegating to checks. Add tests for deterministic JSON emission and contract_version behavior.

## ST-003 Implement run_checks group orchestration contract

Implement `engineeringagent.checks.run_checks(...)` with `checks=[...]` group selection, deterministic group order, default groups ["commands", "fitness"], and optional `check_id` single-check mode. Return a deterministic structured result (ChecksRunResult).

## ST-007 Remove forbidden dataclasses usage and ruff suppressions in checks API

Refactor `engineeringagent.checks.api.run_checks` internals to comply with architecture gates: remove stdlib dataclasses usage and remove non-ignorable ruff suppression for PLR0913 while keeping CLI behavior unchanged.

## ST-006 Implement validate group execution under checks

Port spec/setup validation execution into `checks/validate/**` so that `engineeringagent.checks.run_checks(..., checks=["validate"])` is functional. Preserve existing validation outputs and exit semantics.

## ST-004 Implement commands+fitness execution under checks (parity with current behavior)

Port command/fitness planning and execution (currently in harness_checks_runtime) into `checks/commands/**` and `checks/fitness/**`, preserving deterministic output and failure signaling. Add parity tests against known harness/checks.yaml fixtures.

Notes:
- Port fitness check execution to `engineeringagent.checks.fitness.runtime` and stop dispatching to `engineeringagent.harness_checks_runtime.run_planned_fitness_checks`.

## ST-005 Implement reviewers execution under checks without OpenCode logic

Port reviewer check planning/execution glue into `checks/reviewers/**`. Ensure reviewer execution calls an injected `start_agent_fn` (or wiring import from `engineeringagent.opencode.*`) and requires explicit `feature_path` when reviewers are selected.
