---
plan_id: FEAT-159
feature_id: FEAT-159
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define argv execution contract for string commands
  status: done
  verification:
  - uv run pytest -q tests/checks/test_commands_group_port.py
- id: ST-002
  title: Implement shell-false command runner with deterministic errors
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py
- id: ST-003
  title: Preserve checks and verification output contracts
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_phases_coverage.py tests/loop/test_loop_runtime_iteration.py
- id: ST-004
  title: Add regression coverage for rejected shell syntax
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_feature_iteration.py tests/checks/test_run_checks_contract.py
- id: ST-005
  title: Validate docs and spec contract updates
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-006
  title: Apply reviewer maintainability simplifications in process runner
  status: done
  verification:
  - uv run pytest -q tests/checks/test_commands_group_port.py tests/checks/test_run_checks_contract.py
- id: ST-007
  title: Harden embedded shell-syntax rejection and add bypass regressions
  status: done
  verification:
  - uv run pytest -q tests/checks/test_commands_group_port.py tests/checks/test_run_checks_contract.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define argv execution contract for string commands

Specify normalization, parsing, and invalid-token handling for command strings so command runner behavior is deterministic and testable.

## ST-002 Implement shell-false command runner with deterministic errors

Update process command runner to parse string commands to argv and execute via subprocess without shell, including parse and executable error handling.

## ST-003 Preserve checks and verification output contracts

Ensure checks and verification phases keep stable output framing and failure handling when runner returns parse/missing-executable failures.

## ST-004 Add regression coverage for rejected shell syntax

Add tests for command strings containing shell operators and confirm deterministic rejection behavior across checks and verification paths.

## ST-005 Validate docs and spec contract updates

Update relevant docs to reflect argv-based execution semantics and run repository validation checks.

## ST-006 Apply reviewer maintainability simplifications in process runner

Apply non-behavioral readability cleanups requested by reviewer feedback in the argv runner implementation.

## ST-007 Harden embedded shell-syntax rejection and add bypass regressions

Address reviewer-reported bypasses where backticks and variable expansion syntax embedded inside tokens were accepted; reject deterministically and cover with targeted tests.
