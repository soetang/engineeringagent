---
plan_id: FEAT-115
feature_id: FEAT-115
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add backend-agnostic helpers to engineeringagent.agents for loop usage
  status: done
  verification:
  - uv run pytest -q tests/agents
- id: ST-002
  title: Refactor loop permission precheck wiring to use agents.preflight
  status: done
  verification:
  - uv run pytest -q tests/loop
- id: ST-003
  title: Refactor selector step labeling to use agents helpers
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_selection.py
- id: ST-004
  title: Refactor implement step to remove backend-specific strings and gates
  status: done
  verification:
  - uv run pytest -q tests/loop
- id: ST-005
  title: Refactor iteration telemetry implement-step labeling
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_runtime_iteration.py
- id: ST-006
  title: Remove or internalize DEFAULT_OPENCODE_AGENT constant usage from core
  status: done
  verification:
  - uv run pytest -q
- id: ST-007
  title: Tighten backend-literal locality budget baseline to zero
  status: done
  verification:
  - uv run python harness/fitness_functions/check_backend_literal_locality_budget.py
  - uv run engineeringagent checks run --checks fitness --phase iteration_end
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add backend-agnostic helpers to engineeringagent.agents for loop usage

## ST-002 Refactor loop permission precheck wiring to use agents.preflight

## ST-003 Refactor selector step labeling to use agents helpers

## ST-004 Refactor implement step to remove backend-specific strings and gates

## ST-005 Refactor iteration telemetry implement-step labeling

## ST-006 Remove or internalize DEFAULT_OPENCODE_AGENT constant usage from core

## ST-007 Tighten backend-literal locality budget baseline to zero
