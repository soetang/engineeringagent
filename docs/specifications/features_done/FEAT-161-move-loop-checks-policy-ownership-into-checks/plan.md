---
plan_id: FEAT-161
feature_id: FEAT-161
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Lock loop to checks delegation behavior with tests
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_phases_coverage.py
- id: ST-002
  title: Remove loop-owned checks policy constants and explicit groups
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_phases_coverage.py
- id: ST-003
  title: Add loop checks policy ownership fitness rule
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_loop_checks_policy_ownership.py
- id: ST-004
  title: Boundary regression and runtime verification
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_loop_checks_result_boundary.py
  - uv run engineeringagent checks run --phase iteration_end
- id: ST-005
  title: Final validation and docs sync
  status: done
  verification:
  - uv run engineeringagent validate
  - uv run engineeringagent checks catalog --format markdown --output docs/fitness-functions/rules.md
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Lock loop to checks delegation behavior with tests

Update and add loop phase coverage tests to assert loop delegates policy ownership and preserves deterministic outcomes.

## ST-002 Remove loop-owned checks policy constants and explicit groups

Refactor loop phase orchestration to stop encoding checks group and timing policy and rely on checks-owned selection decisions.

## ST-003 Add loop checks policy ownership fitness rule

Add focused fitness enforcement that detects loop-side checks policy ownership regressions (group maps/literals and explicit list selection patterns).

## ST-004 Boundary regression and runtime verification

Validate compatibility with existing loop and checks boundary rules and runtime checks command flows.

## ST-005 Final validation and docs sync

Run repository validation and regenerate fitness catalog docs after adding the new rule.
