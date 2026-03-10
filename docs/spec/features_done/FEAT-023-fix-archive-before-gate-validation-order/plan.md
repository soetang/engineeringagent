---
plan_id: FEAT-023
feature_id: FEAT-023
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Reorder done-state archive to run before gate execution
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_archives_done_feature_before_gate_execution
- id: ST-002
  title: Add gate-failure rollback for pre-gate archive path
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_restores_archived_feature_when_gate_fails_after_prearchive
- id: ST-003
  title: Preserve completion and telemetry semantics with new ordering
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_gate_failure_feedback_is_injected_into_next_prompt
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_completion_commit_includes_archive_move
- id: ST-004
  title: Add regression for spec-validate ordering interaction
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_spec_validate_no_longer_blocks_done_archive_ordering
- id: ST-005
  title: Run targeted loop regressions and schema validation
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uvx --from . engineeringagent validate --schema-only
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Reorder done-state archive to run before gate execution

Update iteration sequencing so selected-feature done-state archive happens before gate profile execution while preserving existing selection and post-implement load behavior.

## ST-002 Add gate-failure rollback for pre-gate archive path

Ensure archived feature specs are restored to active path when a gate fails after archive in the same iteration so retry behavior remains deterministic.

## ST-003 Preserve completion and telemetry semantics with new ordering

Keep completion commit gating, failed_gate reporting, next_action values, and retry feedback plumbing stable with the reordered archive flow.

## ST-004 Add regression for spec-validate ordering interaction

Add a focused regression test that runs with `loop_fast` gate semantics and asserts selected done features no longer fail due to done-in-active validation before archive.

## ST-005 Run targeted loop regressions and schema validation

Execute targeted tests for sequencing and rollback behavior, plus spec schema validation, before implementation completion.
