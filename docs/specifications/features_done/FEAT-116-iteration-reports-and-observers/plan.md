---
plan_id: FEAT-116
feature_id: FEAT-116
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define IterationReport model
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_runtime_iteration.py
- id: ST-002
  title: Refactor iteration pipeline to return report instead of side effects
  status: done
  verification:
  - uv run pytest -q tests/loop
- id: ST-003
  title: Implement observers for telemetry and console output
  status: done
  verification:
  - uv run pytest -q tests/loop
- id: ST-004
  title: Update loop wiring to use observers
  status: done
  verification:
  - uv run pytest -q
- id: ST-005
  title: Add fitness rule to prevent iteration pipeline side effects
  status: done
  verification:
  - uv run engineeringagent checks run --checks fitness --phase iteration_end
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define IterationReport model

## ST-002 Refactor iteration pipeline to return report instead of side effects

## ST-003 Implement observers for telemetry and console output

## ST-004 Update loop wiring to use observers

## ST-005 Add fitness rule to prevent iteration pipeline side effects

Add fitness rule `architecture.iteration-pipeline-observer-decoupling`.
It should fail if the iteration pipeline performs telemetry writes or terminal
output, and pass only when those side effects are routed through observers.
