---
plan_id: FEAT-020
feature_id: FEAT-020
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Extend gate execution API to expose failed gate output for loop mode
  status: done
  verification:
  - uv run pytest -q tests/test_gates.py::test_run_profile_returns_failed_gate_output_for_loop_mode
  - uv run pytest -q tests/test_gates.py::test_cmd_gates_run_output_behavior_unchanged
- id: ST-002
  title: Plumb failed-gate feedback into loop retry state
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_gate_failure_feedback_is_injected_into_next_prompt
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_gate_failure_feedback_replaces_previous_feedback
- id: ST-003
  title: Keep retry prompt formatting and truncation deterministic
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_gate_failure_feedback_is_truncated_before_prompt_injection
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_commit_failure_feedback_still_injected_into_next_prompt
- id: ST-004
  title: Cover spec-validate and non-spec gate failure paths
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_spec_validate_failure_feedback_round_trips_to_retry_prompt
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_non_validation_gate_failure_feedback_round_trips_to_retry_prompt
- id: ST-005
  title: Run focused validation and loop regression checks
  status: done
  verification:
  - uvx --from . engineeringagent validate --schema-only
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uv run pytest -q tests/test_gates.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Extend gate execution API to expose failed gate output for loop mode

Refactor gate execution so loop runtime can capture failed gate command output without changing normal direct gate command UX.

## ST-002 Plumb failed-gate feedback into loop retry state

Update loop iteration failure handling so gate failures set retry feedback for the same selected feature path using latest-only semantics.

## ST-003 Keep retry prompt formatting and truncation deterministic

Ensure failed-gate output uses existing truncation limits and clear prompt labeling so implement retries target the reported blocker.

## ST-004 Cover spec-validate and non-spec gate failure paths

Add focused loop regression tests that exercise at least one failing validation gate and one failing non-validation gate.

## ST-005 Run focused validation and loop regression checks

Confirm schema validity and targeted retry-flow coverage after the feature is implemented.
