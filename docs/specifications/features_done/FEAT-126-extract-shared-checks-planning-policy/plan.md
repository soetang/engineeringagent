---
plan_id: FEAT-126
feature_id: FEAT-126
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add shared checks planning policy module
  status: done
  verification:
  - uv run pytest -q tests/checks/test_commands_runtime.py tests/checks/test_fitness_runtime.py
- id: ST-002
  title: Migrate command planner to shared policy
  status: done
  verification:
  - uv run pytest -q tests/checks/test_commands_runtime.py tests/checks/test_commands_group_port.py
- id: ST-003
  title: Migrate fitness planner to shared policy
  status: done
  verification:
  - uv run pytest -q tests/checks/test_fitness_runtime.py tests/checks/test_fitness_group_port.py
- id: ST-004
  title: Migrate reviewer planner to shared policy
  status: done
  verification:
  - uv run pytest -q tests/checks/test_checks_reviewers_runtime.py tests/reviewers/test_reviewers_runtime.py
- id: ST-005
  title: Add parity regressions and remove duplicate planner helpers
  status: done
  verification:
  - uv run pytest -q tests/checks/test_commands_runtime.py tests/checks/test_fitness_runtime.py
    tests/checks/test_checks_reviewers_runtime.py
- id: ST-006
  title: Run integration verification for checks surface
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/harness/test_checks_runtime.py
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add shared checks planning policy module

Introduce reusable helpers for effective phase resolution and on_change run/skip decisions with deterministic reason output.

## ST-002 Migrate command planner to shared policy

Refactor command planner to delegate policy decisions while preserving output and invocation behavior.

## ST-003 Migrate fitness planner to shared policy

Refactor fitness planner to use shared policy without changing selection behavior or failure payload semantics.

## ST-004 Migrate reviewer planner to shared policy

Refactor reviewer runtime planner to use shared policy and keep reviewer state/cache execution semantics unchanged.

## ST-005 Add parity regressions and remove duplicate planner helpers

Lock decision equivalence with focused parity tests, then remove obsolete duplicated helper code paths.

## ST-006 Run integration verification for checks surface

Confirm consolidated planner policy does not change checks API outcomes in combined group runs.
