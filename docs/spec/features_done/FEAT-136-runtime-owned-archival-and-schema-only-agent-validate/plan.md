---
plan_id: FEAT-136
feature_id: FEAT-136
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Update implement prompt validation instruction to schema-only
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_ralph_mode.py -k prompt
- id: ST-002
  title: Simplify runtime archive/load flow to remove agent-move fallback branches
  status: done
  verification:
  - uv run pytest -q tests/loop/test_selected_feature_load_without_archive_fallback.py
    tests/loop/test_feature_archive_subtasks_done.py tests/loop/test_loop_runtime_iteration.py
- id: ST-003
  title: Preserve deterministic rollback and completion semantics after simplification
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_ralph_mode.py -k "archive or completion"
- id: ST-004
  title: Update loop integration tests that relied on agent-triggered archive fallback
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_ralph_mode.py tests/loop/test_loop_opencode_integration.py
- id: ST-005
  title: Run focused validation suite for FEAT-136
  status: done
  verification:
  - uv run engineeringagent validate
  - uv run pytest -q tests/loop/test_loop_runtime_iteration.py tests/loop/test_loop_phases_coverage.py
- id: ST-006
  title: Add explicit prompt contract regression for schema-only validate command
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_ralph_mode.py -k prompt
- id: ST-007
  title: Delete legacy archival fallback branches and keep one runtime archival path
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_runtime_iteration.py tests/loop/test_feature_archive_subtasks_done.py
    tests/loop/test_loop_ralph_mode.py -k archive
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Update implement prompt validation instruction to schema-only

Switch the implementation prompt command to `uv run engineeringagent validate --schema-only` and update prompt contract tests accordingly.

## ST-002 Simplify runtime archive/load flow to remove agent-move fallback branches

Remove or narrow selected-feature archive fallback paths that only serve agent-triggered full-validate moves, while preserving deterministic runtime-owned archival state transitions.

## ST-003 Preserve deterministic rollback and completion semantics after simplification

Ensure gate/reviewer/commit failure paths still restore selected feature state deterministically when required.

## ST-004 Update loop integration tests that relied on agent-triggered archive fallback

Replace legacy fallback-specific assertions with runtime-owned archival behavior assertions.

## ST-005 Run focused validation suite for FEAT-136

Run schema validation and focused loop regressions for archive behavior and prompt contract updates.

## ST-006 Add explicit prompt contract regression for schema-only validate command

Add/adjust prompt contract coverage so implementation guidance is asserted to use `uv run engineeringagent validate --schema-only` as the validation command.

## ST-007 Delete legacy archival fallback branches and keep one runtime archival path

Remove compatibility helper branches and fallback paths tied to agent-triggered archival, and keep only the runtime-owned archival flow.
