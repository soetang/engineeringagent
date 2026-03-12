---
plan_id: FEAT-018
feature_id: FEAT-018
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add regression tests for selected feature moved to features_done
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_selected_feature_moved_to_features_done_does_not_crash
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_all_selected_feature_moved_to_features_done_continues
- id: ST-002
  title: Add regression test for missing selected feature without archive counterpart
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_missing_selected_feature_without_archive_fails_cleanly
- id: ST-003
  title: Implement archive-aware missing selected-feature handling in loop runtime
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_selected_feature_moved_to_features_done_does_not_crash
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_missing_selected_feature_without_archive_fails_cleanly
- id: ST-004
  title: Ensure loop bookkeeping and messaging remain deterministic in both modes
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_all_selected_feature_moved_to_features_done_continues
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_missing_selected_feature_without_archive_fails_cleanly
- id: ST-005
  title: Run focused loop regression and spec validation checks
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uvx --from . engineeringagent validate --schema-only
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add regression tests for selected feature moved to features_done

Reproduce the reported failure by simulating an implementation step that moves the selected feature file to `docs/spec/features_done/` before the second feature load path executes.

## ST-002 Add regression test for missing selected feature without archive counterpart

Capture the failure-mode requirement by validating the loop fails cleanly and emits actionable messaging when selected feature path disappears and cannot be resolved in `docs/spec/features_done/`.

## ST-003 Implement archive-aware missing selected-feature handling in loop runtime

Update loop iteration flow to guard all post-implementation reload points against missing selected feature paths and branch behavior based on archive counterpart presence.

## ST-004 Ensure loop bookkeeping and messaging remain deterministic in both modes

Confirm selected-path removal, next-action semantics, and summary output stay stable in explicit path and `--all` startup snapshot workflows after the new missing-path handling is introduced.

## ST-005 Run focused loop regression and spec validation checks

Execute focused tests plus repository spec validation to ensure the change is covered and the new feature spec remains valid.
