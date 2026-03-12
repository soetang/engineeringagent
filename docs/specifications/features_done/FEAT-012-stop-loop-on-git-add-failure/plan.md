---
plan_id: FEAT-012
feature_id: FEAT-012
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add terminal loop stop path for git_add failures
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_git_add_failure_exits_immediately
- id: ST-002
  title: Validate telemetry behavior for terminal git_add failure
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_git_add_failure_exits_immediately
- id: ST-003
  title: Preserve retry semantics for git_commit hook failures
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_commit_failure_retries_same_feature
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add terminal loop stop path for git_add failures

Adjust loop orchestration so `failed_gate=git_add` exits the current run immediately instead of continuing retry cycles.

## ST-002 Validate telemetry behavior for terminal git_add failure

Ensure telemetry output remains consistent and includes a single failed iteration record for `git_add` terminal stop conditions.

## ST-003 Preserve retry semantics for git_commit hook failures

Confirm existing commit-hook recovery loop remains active so retriable `git_commit` failures continue to work with subsequent attempts.
