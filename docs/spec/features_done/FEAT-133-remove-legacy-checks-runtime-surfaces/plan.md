---
plan_id: FEAT-133
feature_id: FEAT-133
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove duplicated command and fitness runtime execution compatibility paths
  status: done
  verification:
  - uv run pytest -q tests/checks/test_commands_runtime.py tests/checks/test_fitness_runtime.py
    tests/checks/test_run_checks_contract.py
- id: ST-002
  title: Remove reviewer legacy planning and parsing helper surfaces
  status: done
  verification:
  - uv run pytest -q tests/reviewers tests/checks/test_checks_reviewers_runtime.py
- id: ST-003
  title: Collapse duplicated checks planning-to-execution mapping helpers
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/harness/test_checks_runtime.py
- id: ST-004
  title: Update checks exports and integration tests for removed legacy surfaces
  status: done
  verification:
  - uv run pytest -q tests/checks/test_checks_exports.py tests/fitness/test_fitness_rules_checks_import_surface.py
- id: ST-005
  title: Run final targeted regression suite and validate specs
  status: done
  verification:
  - uv run pytest -q tests/checks tests/reviewers tests/harness/test_checks_runtime.py
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove duplicated command and fitness runtime execution compatibility paths

Delete compatibility-only runtime executors/wrappers that duplicate strategy-owned command and fitness execution, and migrate tests to the canonical path.

## ST-002 Remove reviewer legacy planning and parsing helper surfaces

Remove `load_reviewer_config`, `plan_reviewers`, and `parse_reviewer_decision` from reviewer engine and align tests to current strategy/runtime contracts.

## ST-003 Collapse duplicated checks planning-to-execution mapping helpers

Consolidate repeated planner/decision/execution shaping helpers into one checks-owned implementation to reduce drift.

## ST-004 Update checks exports and integration tests for removed legacy surfaces

Ensure top-level checks surface remains explicit and tests assert removed legacy helpers are no longer part of supported imports/contracts. Delete tests that only covered removed legacy paths.

## ST-005 Run final targeted regression suite and validate specs

Confirm no behavior drift after legacy removals and simplification.
