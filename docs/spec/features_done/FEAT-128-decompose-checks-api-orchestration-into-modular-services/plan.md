---
plan_id: FEAT-128
feature_id: FEAT-128
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Extract checks request normalization from api module
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py -k "phase or groups
    or unexpected"
- id: ST-002
  title: Extract shared checks config and check-id selection orchestration
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/cli/test_cli_checks.py
- id: ST-003
  title: Extract group dispatch and aggregation orchestration
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/checks/test_commands_group_port.py
    tests/checks/test_fitness_group_port.py
- id: ST-004
  title: Apply broader internal checks cleanup for readability
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/checks/test_checks_reviewers_runtime.py
- id: ST-005
  title: Re-lock CLI checks command parity through shared API surface
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli_checks.py tests/cli/test_cli.py
- id: ST-006
  title: Run final validation for FEAT-128 integration
  status: done
  verification:
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Extract checks request normalization from api module

Move phase/group/kwargs normalization and request construction into a dedicated internal module with focused tests.

## ST-002 Extract shared checks config and check-id selection orchestration

Move checks-doc load + check-id selection flow behind one internal orchestration boundary consumed by the API facade.

## ST-003 Extract group dispatch and aggregation orchestration

Move validate/commands/fitness/reviewers group dispatch and final aggregation into dedicated internal helpers or modules while preserving group-order behavior.

## ST-004 Apply broader internal checks cleanup for readability

Remove obsolete duplicate helpers and simplify call graph in checks internals without changing externally visible behavior.

## ST-005 Re-lock CLI checks command parity through shared API surface

Ensure CLI checks flows still map to equivalent run_checks outcomes and actionable messages after orchestration split.

## ST-006 Run final validation for FEAT-128 integration

Confirm the modularization integrates cleanly with repository spec contracts.
