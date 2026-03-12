---
plan_id: FEAT-150
feature_id: FEAT-150
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define canonical PlannedCheck in strategy contracts
  status: done
  verification:
  - uv run pytest -q tests/checks/test_commands_runtime.py tests/checks/test_fitness_runtime.py
- id: ST-002
  title: Update check planners to return shared PlannedCheck
  status: done
  verification:
  - uv run pytest -q tests/checks/test_commands_runtime.py tests/checks/test_fitness_runtime.py
    tests/checks/test_checks_reviewers_runtime.py
- id: ST-003
  title: Align tests and imports to canonical planning contract
  status: done
  verification:
  - uv run pytest -q tests/checks/test_checks_reviewers_runtime.py tests/checks/test_run_checks_contract.py
- id: ST-004
  title: Run final validation for planning parity
  status: done
  verification:
  - uv run pytest -q tests/checks/test_commands_runtime.py tests/checks/test_fitness_runtime.py
    tests/checks/test_checks_reviewers_runtime.py tests/checks/test_run_checks_contract.py
  - uv run engineeringagent validate
- id: ST-005
  title: Reviewer feedback cleanup for planner constructors and import ordering
  status: done
  verification:
  - UV_CACHE_DIR=/tmp/uv-cache uv run ruff check --select I --fix src/engineeringagent/checks/commands/runtime.py
    src/engineeringagent/checks/fitness/runtime.py src/engineeringagent/checks/reviewers/runtime.py
    src/engineeringagent/checks/strategy_contracts.py
  - UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q tests/checks/test_commands_runtime.py
    tests/checks/test_fitness_runtime.py tests/checks/test_checks_reviewers_runtime.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define canonical PlannedCheck in strategy contracts

Add one shared planning-record type in `strategy_contracts.py` with fields `check_id`, `decision`, and `reason`.

## ST-002 Update check planners to return shared PlannedCheck

Update command/fitness/reviewer planning functions to construct and return the shared type and remove local duplicate model declarations.

## ST-003 Align tests and imports to canonical planning contract

Update tests/imports to use the shared strategy-contract planning record and keep runtime-module import ergonomics stable where needed.

## ST-004 Run final validation for planning parity

Validate that deduplication does not change deterministic planner outcomes and repository validation contracts.

## ST-005 Reviewer feedback cleanup for planner constructors and import ordering

Address post-review maintainability feedback by centralizing planned-check constructor wiring and restoring repo-standard import ordering in touched modules.
