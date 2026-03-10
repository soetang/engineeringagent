---
plan_id: FEAT-024
feature_id: FEAT-024
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add same-iteration archived-done adoption signal
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_selected_feature_moved_to_features_done_does_not_crash
- id: ST-002
  title: Continue gate and commit flow for adopted archived feature
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_all_selected_feature_moved_to_features_done_continues
- id: ST-003
  title: Restore active path on gate and commit failures after adoption
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_restores_archived_feature_when_gate_fails_after_prearchive
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_commit_failure_preserves_retryable_feature_path
- id: ST-004
  title: Preserve strict archived-at-start failure contract
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_archived_done_without_completion_commit_fails
- id: ST-005
  title: Run targeted loop regressions and schema validation
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uvx --from . engineeringagent validate --schema-only
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add same-iteration archived-done adoption signal

Track whether selected feature was active at iteration start and became archived+done after implement, and use that signal to continue iteration flow rather than failing feature-missing.

## ST-002 Continue gate and commit flow for adopted archived feature

Ensure adopted same-iteration archived features execute gate profile and completion commit flow with stable summary and telemetry behavior.

## ST-003 Restore active path on gate and commit failures after adoption

Reuse restore helpers so adopted archive state rolls back to active path on failure and retries remain deterministic.

## ST-004 Preserve strict archived-at-start failure contract

Keep deterministic failure behavior for cases where selected feature is already archived before iteration start and not eligible for same- iteration adoption.

## ST-005 Run targeted loop regressions and schema validation

Execute focused loop tests for adoption and rollback behavior plus schema validation before marking feature ready.
