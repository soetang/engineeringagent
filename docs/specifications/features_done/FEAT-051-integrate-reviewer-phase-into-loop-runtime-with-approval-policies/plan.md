---
plan_id: FEAT-051
feature_id: FEAT-051
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add reviewer phase outcome models and iteration state fields
  status: done
  verification:
  - uv run pytest -q tests/test_loop_contracts.py
- id: ST-002
  title: Add reviewer phase execution to iteration sequencing
  status: done
  verification:
  - uv run pytest -q tests/test_loop_reviewers.py::test_reviewer_phase_runs_after_gates_before_commit
- id: ST-003
  title: Enforce advisory follow-up implement latch semantics
  status: done
  verification:
  - uv run pytest -q tests/test_loop_reviewers.py::test_advisory_feedback_requires_one_followup_implement_pass
- id: ST-004
  title: Implement blocking retry and exhausted-policy handling
  status: done
  verification:
  - uv run pytest -q tests/test_loop_reviewers.py::test_blocking_reviewer_requests_retry_and_sets_feedback
  - uv run pytest -q tests/test_loop_reviewers.py::test_blocking_reviewer_exhausted_continues_with_warning_by_default
  - uv run pytest -q tests/test_loop_reviewers.py::test_blocking_reviewer_exhausted_can_be_configured_to_fail
- id: ST-005
  title: Persist reviewer state and approval reuse invalidation
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_state.py
- id: ST-006
  title: Extend telemetry and summary outputs with reviewer fields
  status: done
  verification:
  - uv run pytest -q tests/test_loop_output.py
  - uv run pytest -q tests/test_loop_contracts.py::test_retry_feedback_contract_accepts_verification_failure
- id: ST-007
  title: Run reviewer and loop regression slice
  status: done
  verification:
  - uv run pytest -q tests/test_loop_reviewers.py tests/test_loop_ralph_mode.py tests/test_loop_contracts.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add reviewer phase outcome models and iteration state fields

Extend loop runtime model contracts to carry reviewer status, decision, failed reviewer id, and reviewer feedback.

## ST-002 Add reviewer phase execution to iteration sequencing

Invoke reviewer phase after gate pass and before completion commit while preserving existing phase-gating behavior.

## ST-003 Enforce advisory follow-up implement latch semantics

Implement and test required one-pass follow-up behavior after advisory advice.

## ST-004 Implement blocking retry and exhausted-policy handling

Apply max retry policy and continue-on-exhausted behavior with deterministic feedback and next-action mapping.

## ST-005 Persist reviewer state and approval reuse invalidation

Save and load reviewer approval/retry metadata in `progress/reviewers-state.json` and invalidate cache when scoped changes occur.

## ST-006 Extend telemetry and summary outputs with reviewer fields

Add deterministic reviewer output fields to per-iteration telemetry and human summary lines.

## ST-007 Run reviewer and loop regression slice

Validate reviewer-loop integration and ensure no regressions in existing loop behavior.
