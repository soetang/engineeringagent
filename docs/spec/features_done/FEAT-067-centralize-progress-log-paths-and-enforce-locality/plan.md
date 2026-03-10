---
plan_id: FEAT-067
feature_id: FEAT-067
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Introduce canonical progress-path and logging-sink helper API
  status: done
  verification:
  - uv run pytest -q tests/test_loop_contracts.py tests/test_reviewers_state.py
- id: ST-002
  title: Migrate loop telemetry/progress log writing to logging package handlers
  status: done
  verification:
  - uv run pytest -q tests/test_loop_output.py tests/test_loop_ralph_mode.py tests/test_reviewers_state.py
- id: ST-003
  title: Add logging-path and loop-log-write locality fitness enforcement
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
  - uv run pytest -q tests/test_loop_contracts.py
- id: ST-004
  title: Add dedicated rule tests for pass and fail locality scenarios
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_rules_logging_path_locality.py
- id: ST-005
  title: Regenerate fitness rule catalog and validate feature spec contracts
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness catalog --format markdown --output
    docs/fitness-functions/rules.md
  - uv run python -m engineeringagent.cli validate
- id: ST-006
  title: Simplify post-migration telemetry/reviewer helpers
  status: done
  verification:
  - uv run pytest -q tests/test_loop_output.py tests/test_reviewers_state.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Introduce canonical progress-path and logging-sink helper API

Define helper function(s) for runs log path, per-feature progress log path, reviewer state path, and logger/handler construction for loop log sinks.

## ST-002 Migrate loop telemetry/progress log writing to logging package handlers

Replace direct file append writes for `runs.jsonl` and per-feature progress logs with logging helper calls while preserving payload/text content; keep reviewer-state path usage centralized.

## ST-003 Add logging-path and loop-log-write locality fitness enforcement

Implement checker under harness fitness scripts to detect path-locality and direct write violations for centralized loop log sinks; register in harness fitness manifest with deterministic envelope output.

## ST-004 Add dedicated rule tests for pass and fail locality scenarios

Add focused tests that assert violations for inline path literals and pass behavior for centralized helper usage.

## ST-005 Regenerate fitness rule catalog and validate feature spec contracts

Ensure docs and schema-facing validation reflect the new architecture rule contract.

## ST-006 Simplify post-migration telemetry/reviewer helpers

Reduce redundant ANSI stripping and minor reviewer state parsing duplication without changing loop output contracts.
