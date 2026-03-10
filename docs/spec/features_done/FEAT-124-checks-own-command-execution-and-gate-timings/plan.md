---
plan_id: FEAT-124
feature_id: FEAT-124
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add structured command invocation records to checks results
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/checks/test_commands_runtime.py
- id: ST-002
  title: Remove run_shell_command override from run_checks API
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/checks/test_commands_group_port.py
- id: ST-003
  title: Refactor gate timing correlation to structured checks data
  status: done
  verification:
  - uv run pytest -q tests/harness/test_checks_runtime.py tests/loop/test_loop_output.py
    tests/loop/test_loop_ralph_mode.py
- id: ST-004
  title: Update boundary/regression tests for the API break
  status: done
  verification:
  - uv run pytest -q tests/checks tests/loop/test_loop_phases_coverage.py
- id: ST-005
  title: Run full repository verification after breaking change
  status: done
  verification:
  - uv run pytest -q
  - uv run engineeringagent validate
- id: ST-006
  title: Deduplicate changed-path resolution in checks API groups
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py -k resolve_changed_paths
  - uv run engineeringagent validate
- id: ST-007
  title: Re-run FEAT-124 regression verification after simplification
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/checks/test_commands_group_port.py
    tests/checks/test_commands_runtime.py tests/harness/test_checks_runtime.py tests/loop/test_loop_output.py
    tests/loop/test_loop_ralph_mode.py
- id: ST-008
  title: Address reviewer simplification follow-ups
  status: done
  verification:
  - uv run pytest -q tests/checks/test_commands_runtime.py tests/checks/test_run_checks_contract.py
    tests/harness/test_checks_runtime.py tests/loop/test_loop_output.py tests/loop/test_loop_ralph_mode.py
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add structured command invocation records to checks results

Add typed command invocation metadata in checks command runtime and thread it through command-group execution into `ChecksRunResult`.

## ST-002 Remove run_shell_command override from run_checks API

Delete `run_shell_command` from supported `run_checks` kwargs and remove related checks API plumbing.

## ST-003 Refactor gate timing correlation to structured checks data

Update loop gate-phase wiring/dependencies so command timings are derived from structured checks result metadata instead of parsed output lines.

## ST-004 Update boundary/regression tests for the API break

Adjust tests that used `run_checks(..., run_shell_command=...)` and add regressions for checks-owned execution boundary.

## ST-005 Run full repository verification after breaking change

Run full validation/test suite to confirm stable behavior after checks API break.

## ST-006 Deduplicate changed-path resolution in checks API groups

Factor repeated changed-path collector resolution from command/fitness/reviewer groups into a single helper to reduce maintenance risk without changing behavior.

## ST-007 Re-run FEAT-124 regression verification after simplification

Execute the broader FEAT-124 targeted regression commands to confirm no behavior drift after helper extraction.

## ST-008 Address reviewer simplification follow-ups

Apply reviewer-requested maintainability simplifications across loop gate timing materialization and checks command/runtime helpers without changing FEAT-124 behavior.
