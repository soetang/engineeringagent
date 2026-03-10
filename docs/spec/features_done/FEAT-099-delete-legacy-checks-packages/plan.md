---
plan_id: FEAT-099
feature_id: FEAT-099
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Relocate fitness framework under checks and update callsites
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
  - uv run pytest -q
- id: ST-002
  title: Relocate retry-feedback under checks and update loop_runtime imports
  status: done
  verification:
  - uv run pytest -q
- id: ST-003
  title: Update harness fitness import allowlist and migrate harness imports
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
  - uv run pytest -q
- id: ST-004
  title: Enforce unused-by-production invariant (imports)
  status: done
  verification:
  - uv run pytest -q
  - uv run python -m engineeringagent.cli validate
- id: ST-005
  title: Add checks import surface enforcement fitness rule
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
  - uv run pytest -q
- id: ST-006
  title: Delete legacy harness_checks_runtime module
  status: done
  verification:
  - uv run pytest -q
- id: ST-007
  title: Delete legacy validator module
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q
- id: ST-008
  title: Delete legacy reviewers module
  status: done
  verification:
  - uv run pytest -q
- id: ST-009
  title: Delete legacy fitness package
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
  - uv run pytest -q
- id: ST-010
  title: Delete legacy retry_feedback package
  status: done
  verification:
  - uv run pytest -q
- id: ST-011
  title: Cleanup checks migration follow-ups
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run python -m engineeringagent.cli fitness run --format json
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Relocate fitness framework under checks and update callsites

Move fitness contracts/registry/runner/catalog/adapters/envelope behind `src/engineeringagent/checks/fitness/**` (or equivalent) and update all production imports to use `engineeringagent.checks.*`. Ensure deterministic behavior and preserve the FitnessRuleResult contract.

## ST-002 Relocate retry-feedback under checks and update loop_runtime imports

Move retry-feedback contracts/builders behind `src/engineeringagent/checks/**` and update loop runtime to import from `engineeringagent.checks.*`. Preserve serialization shape and determinism of retry-feedback payloads.

## ST-003 Update harness fitness import allowlist and migrate harness imports

Update the harness allowlist fitness rule to permit the new checks surface and keep the allowlist narrow. Migrate harness fitness scripts to import the supported helper from `engineeringagent.checks` as needed.

## ST-004 Enforce unused-by-production invariant (imports)

Add an automated check (pytest) that scans `src/engineeringagent/**` imports and fails on forbidden legacy imports: - engineeringagent.harness_checks_runtime - engineeringagent.validator - engineeringagent.reviewers - engineeringagent.fitness - engineeringagent.retry_feedback

## ST-005 Add checks import surface enforcement fitness rule

Add a harness fitness function that scans Python imports under `src/engineeringagent/**`. Enforce that any module outside `src/engineeringagent/checks/**`: - does not import `engineeringagent.checks.<submodule>` (no submodule imports) - only imports allowed names from `engineeringagent.checks` (e.g. `run_checks`,
  `emit_fitness_result`, `emit_result_envelope`)
Register the rule in `harness/fitness-functions/rules.yaml`.

## ST-006 Delete legacy harness_checks_runtime module

Remove `src/engineeringagent/harness_checks_runtime.py` after verifying it has zero production callsites and all functionality is available under `src/engineeringagent/checks/**`.

## ST-007 Delete legacy validator module

Remove `src/engineeringagent/validator.py` after verifying it has zero production callsites and validation execution is available under `src/engineeringagent/checks/**`.

## ST-008 Delete legacy reviewers module

Remove `src/engineeringagent/reviewers.py` after verifying it has zero production callsites and reviewer execution is available under `src/engineeringagent/checks/**`.

## ST-009 Delete legacy fitness package

Remove the `src/engineeringagent/fitness/` package after relocating its functionality under checks and updating all production and harness imports.

## ST-010 Delete legacy retry_feedback package

Remove the `src/engineeringagent/retry_feedback/` package after relocating its functionality under checks and updating loop runtime imports.

## ST-011 Cleanup checks migration follow-ups

Simplify checks import-surface enforcement, reduce import coupling in validation, and avoid repeated catalog loads in fitness runtime.
