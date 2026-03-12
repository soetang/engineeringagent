---
plan_id: FEAT-040
feature_id: FEAT-040
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add loop-runtime verification phase contract and telemetry fields
  status: done
  verification:
  - uv run pytest -q tests/test_loop_contracts.py::test_iteration_outcome_includes_verification_status
  - uv run pytest -q tests/test_loop_contracts.py::test_retry_feedback_contract_accepts_verification_failure
- id: ST-002
  title: Execute selected subtask verification commands in harness runtime
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_selected_subtask_verification_runs_in_iteration
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_verification_failure_marks_iteration_non_pass
- id: ST-003
  title: Inject verification failure output into next retry prompt
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_verification_failure_feedback_is_injected_into_next_prompt
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_verification_failure_feedback_replaces_previous_feedback
- id: ST-004
  title: Update presentation and progress logging for verification outcomes
  status: done
  verification:
  - uv run pytest -q tests/test_loop_output.py::test_progress_log_records_verification_status
  - uv run pytest -q tests/test_loop_output.py::test_non_verbose_terminal_output_shows_verification_summary
- id: ST-005
  title: Run regression checks for retry and gate compatibility
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uv run pytest -q tests/test_gates.py
  - uvx --from . engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add loop-runtime verification phase contract and telemetry fields

Define data contracts for per-iteration verification execution and outcomes, including status strings, failed verification command identity, and prompt-feedback payload.

## ST-002 Execute selected subtask verification commands in harness runtime

Implement the verification phase so loop runtime executes selected subtask `verification` commands and captures deterministic pass/fail outcomes.

## ST-003 Inject verification failure output into next retry prompt

Reuse retry-feedback plumbing so failed verification output is truncated and injected into the next implement prompt for the same selected feature.

## ST-004 Update presentation and progress logging for verification outcomes

Add concise terminal status and structured progress log sections so humans can see verification outcomes without confusing them with gate results. Create a new test module `tests/test_loop_output.py` in this subtask and add focused output assertions there.

## ST-005 Run regression checks for retry and gate compatibility

Confirm verification feedback does not regress gate-failure and commit-failure retry flows while resolving repeated verification-failure loops.
