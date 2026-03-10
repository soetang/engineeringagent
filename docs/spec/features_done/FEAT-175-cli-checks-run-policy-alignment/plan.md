---
plan_id: FEAT-175
feature_id: FEAT-175
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Lock direct CLI checks defaults and on_change-ignore behavior with tests
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli_checks.py tests/checks/test_run_checks_contract.py
- id: ST-002
  title: Implement CLI-scoped planning policy signal in checks normalization/orchestration
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/checks/test_commands_runtime.py
    tests/checks/test_fitness_runtime.py
- id: ST-003
  title: Add checks run all-phases CLI option with deterministic fan-out
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli_checks.py tests/checks/test_run_checks_contract.py
- id: ST-004
  title: Preserve reviewer CLI preconditions while aligning policy semantics
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli_checks.py tests/checks/test_checks_reviewers_runtime.py
- id: ST-005
  title: Update docs and run full validation for FEAT-175
  status: done
  verification:
  - uv run engineeringagent validate
  - uv run pytest -q tests/cli/test_cli_checks.py tests/checks/test_run_checks_contract.py
    tests/checks/test_commands_runtime.py tests/checks/test_fitness_runtime.py tests/checks/test_checks_reviewers_runtime.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Lock direct CLI checks defaults and on_change-ignore behavior with tests

Add focused coverage for default-group selection and direct CLI execution rules that ignore `when.on_change` across command, fitness, and reviewer planning paths.

## ST-002 Implement CLI-scoped planning policy signal in checks normalization/orchestration

Extend request normalization and shared planning policy so direct CLI checks runs use phase-only eligibility (ignore `on_change`) while preserving existing loop runtime behavior.

## ST-003 Add checks run all-phases CLI option with deterministic fan-out

Add CLI support to run `iteration_end`, `feature_done`, and `manual` in one invocation with stable ordering and consistent first-failure reporting.

## ST-004 Preserve reviewer CLI preconditions while aligning policy semantics

Keep reviewer requirements deterministic (`--feature-path` required when reviewers are selected) and ensure policy updates do not relax this precondition.

## ST-005 Update docs and run full validation for FEAT-175

Update guidance/examples for direct checks runs and execute validation plus targeted regressions.
