---
plan_id: FEAT-172
feature_id: FEAT-172
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add checks config path resolver in config boundary
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py
- id: ST-002
  title: Replace hardcoded checks path usage in checks CLI and loop runtime
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli_checks.py tests/loop/test_loop_phases_coverage.py
- id: ST-003
  title: Add regression tests for default and configured path behavior
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/cli/test_cli.py
- id: ST-004
  title: Simplify checks path-label and config selection plumbing
  status: done
  verification:
  - uv run pytest -q tests/checks/test_config_selection.py tests/config/test_config_harness_checks_path.py
- id: ST-005
  title: Address reviewer feedback on brittle FEAT-172 tests
  status: done
  verification:
  - uv run pytest -q tests/checks/test_config_selection.py tests/cli/test_cli.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add checks config path resolver in config boundary

Introduce a shared resolver for checks config path with precedence
`engineeringagent.toml` -> `pyproject.toml` -> default path.

## ST-002 Replace hardcoded checks path usage in checks CLI and loop runtime

Update checks loader and run-all/gate-phase path checks to use the shared
resolver so behavior is consistent across surfaces.

## ST-003 Add regression tests for default and configured path behavior

Add/adjust tests for default path fallback, configured path success,
and invalid-path error handling.

## ST-004 Simplify checks path-label and config selection plumbing

Remove duplicated path-label helpers and redundant selection fallback
path resolution while preserving behavior.

## ST-005 Address reviewer feedback on brittle FEAT-172 tests

Replace implementation-coupled test coverage with filesystem-driven behavior
coverage and remove brittle help-text assertions.
