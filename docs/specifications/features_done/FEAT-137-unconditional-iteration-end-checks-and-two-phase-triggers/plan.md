---
plan_id: FEAT-137
feature_id: FEAT-137
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove transition-dependent checks skipping in iteration pipeline
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_runtime_iteration.py
- id: ST-002
  title: Run iteration-end checks even when verification fails
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_phases_coverage.py tests/loop/test_loop_runtime_iteration.py
- id: ST-003
  title: Ensure loop iteration-end checks include validate coverage
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/loop/test_loop_phases_coverage.py
- id: ST-004
  title: Lock loop-triggered check phases to iteration-end and feature-done
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/cli/test_cli_checks.py
- id: ST-005
  title: Run focused regression and validation suite for FEAT-137
  status: done
  verification:
  - uv run engineeringagent validate
  - uv run pytest -q tests/loop/test_loop_runtime_iteration.py tests/loop/test_loop_phases_coverage.py
    tests/checks/test_run_checks_contract.py
- id: ST-006
  title: Delete legacy iteration checks-skip and fail-fast bypass branches
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_runtime_iteration.py tests/loop/test_loop_phases_coverage.py
    -k "verification or gate"
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove transition-dependent checks skipping in iteration pipeline

Refactor iteration sequencing so checks invocation does not depend on subtask transition-to-done heuristics.

## ST-002 Run iteration-end checks even when verification fails

Change fail-fast behavior so verification failure is recorded but does not block iteration-end checks execution in the same iteration.

## ST-003 Ensure loop iteration-end checks include validate coverage

Update loop check invocation to include validate under iteration-end runtime checks policy.

## ST-004 Lock loop-triggered check phases to iteration-end and feature-done

Keep automatic loop triggering constrained to `iteration_end` and `feature_done`, while preserving manual-only checks execution via CLI.

## ST-005 Run focused regression and validation suite for FEAT-137

Execute focused tests that assert unconditional iteration-end checks behavior and run full spec validation.

## ST-006 Delete legacy iteration checks-skip and fail-fast bypass branches

Remove transition-gated checks-skip branches and pre-check fail-fast shortcuts that suppress iteration-end checks execution.
