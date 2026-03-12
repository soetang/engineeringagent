---
plan_id: FEAT-021
feature_id: FEAT-021
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add same-iteration completion commit signal to loop flow
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_completion_commit_includes_archive_move
- id: ST-002
  title: Tighten archive-fallback completion handling
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_selected_feature_moved_to_features_done_does_not_crash
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_missing_selected_feature_without_archive_fails_cleanly
- id: ST-003
  title: Align loop terminal messaging with commit guarantees
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_all_selected_feature_moved_to_features_done_continues
- id: ST-004
  title: Add regression tests for archived-done without completion commit
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_archived_done_without_completion_commit_fails
- id: ST-005
  title: Add integration test for per-feature commit enforcement
  status: done
  verification:
  - uv run pytest -q tests/test_loop_opencode_integration.py::test_loop_archived_done_requires_same_iteration_completion_commit
- id: ST-006
  title: Run targeted regression and schema validation
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uv run pytest -q tests/test_loop_opencode_integration.py
  - uvx --from . engineeringagent validate --schema-only
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add same-iteration completion commit signal to loop flow

Track completion-commit success explicitly and gate completion transitions on that signal instead of archive-fallback status alone.

## ST-002 Tighten archive-fallback completion handling

Fail cleanly when selected feature is archived/done without same-iteration completion commit, with stable failed-gate and actionable feedback.

## ST-003 Align loop terminal messaging with commit guarantees

Ensure summary/no-work messaging does not imply completion commits occurred when they did not.

## ST-004 Add regression tests for archived-done without completion commit

Add focused tests that assert deterministic failure behavior and no `select_next_feature` transition for the archived-done/no-commit path.

## ST-005 Add integration test for per-feature commit enforcement

Add an integration-style test that creates an isolated temp project, initializes a git repository, seeds feature specs and working files, runs loop execution through the archived-done edge case, and asserts the loop does not advance without a same-iteration completion commit.

## ST-006 Run targeted regression and schema validation

Verify loop behavior and spec validity after implementing the fix.
