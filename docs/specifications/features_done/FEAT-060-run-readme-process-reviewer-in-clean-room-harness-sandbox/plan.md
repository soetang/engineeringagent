---
plan_id: FEAT-060
feature_id: FEAT-060
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add harness-owned clean-room sandbox builder for reviewer execution
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_sandbox.py::test_readme_process_clean_room_sandbox_contains_expected_assets_only
- id: ST-002
  title: Wire reviewer runtime to use harness sandbox builder for readme_process
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_sandbox.py::test_readme_process_uses_harness_clean_room_sandbox
- id: ST-003
  title: Ensure CLI availability contract inside clean-room sandbox
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_sandbox.py::test_readme_process_clean_room_can_execute_engineeringagent_cli
- id: ST-004
  title: Preserve blocking policy behavior and parser-failure handling after sandbox
    migration
  status: done
  verification:
  - uv run pytest -q tests/test_loop_reviewers.py::test_readme_process_request_changes_blocks_until_retry_or_exhaustion
  - uv run pytest -q tests/test_reviewers_sandbox.py::test_run_reviewer_returns_request_changes_when_sandbox_setup_fails
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add harness-owned clean-room sandbox builder for reviewer execution

Implement deterministic sandbox creation utility for readme_process with explicit allowed artifacts.

## ST-002 Wire reviewer runtime to use harness sandbox builder for readme_process

Replace full snapshot copy path with clean-room builder wiring while preserving reviewer flow contracts.

## ST-003 Ensure CLI availability contract inside clean-room sandbox

Provide deterministic access path for engineeringagent CLI from sandbox without requiring full repo mirror.

## ST-004 Preserve blocking policy behavior and parser-failure handling after sandbox migration

Confirm retry, exhaustion, and failure semantics are unchanged by sandbox implementation shift.
