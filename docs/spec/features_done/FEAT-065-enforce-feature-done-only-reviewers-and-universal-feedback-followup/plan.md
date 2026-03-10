---
plan_id: FEAT-065
feature_id: FEAT-065
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Normalize reviewer phase planning/runtime to feature_done-only execution
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_runtime.py tests/test_loop_reviewers.py::test_reviewer_phase_runs_after_gates_before_commit
- id: ST-002
  title: Expand reviewer feedback formatting and forwarding to all decision types
  status: done
  verification:
  - uv run pytest -q tests/test_loop_reviewers.py tests/test_loop_runtime_iteration.py
- id: ST-003
  title: Generalize follow-up latch policy to require one post-review implement pass
    for any feedback
  status: done
  verification:
  - uv run pytest -q tests/test_loop_reviewers.py
- id: ST-004
  title: Preserve blocking reviewer retry semantics under feature_done-only policy
  status: done
  verification:
  - uv run pytest -q tests/test_loop_reviewers.py::test_blocking_reviewer_exhausted_continues_with_warning_by_default
  - uv run pytest -q tests/test_loop_reviewers.py::test_blocking_reviewer_exhaustion_stops_when_continue_disabled
- id: ST-005
  title: Update reviewer reference docs and validate contract narrative
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
- id: ST-006
  title: Add explicit human-visible reviewer feedback summary logging
  status: done
  verification:
  - uv run pytest -q tests/test_loop_output.py tests/test_loop_reviewers.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Normalize reviewer phase planning/runtime to feature_done-only execution

Implement deterministic mapping so configured iteration_end reviewers run at feature_done and no reviewer executes during intermediate iteration_end passes.

## ST-002 Expand reviewer feedback formatting and forwarding to all decision types

Ensure approve/warning/request_changes outcomes all contribute retry feedback payloads that are injected into next implement prompt.

## ST-003 Generalize follow-up latch policy to require one post-review implement pass for any feedback

Rework follow-up gating so completion is deferred exactly once when reviewer feedback exists, including approve feedback, while preserving retry stability.

## ST-004 Preserve blocking reviewer retry semantics under feature_done-only policy

Confirm max_retries and continue_on_exhausted behavior are unaffected by phase and feedback policy changes.

## ST-005 Update reviewer reference docs and validate contract narrative

Align reviewer docs with feature_done-only execution, legacy phase alias behavior, and universal feedback forwarding/follow-up policy.

## ST-006 Add explicit human-visible reviewer feedback summary logging

Extend loop telemetry/progress logging so reviewer feedback forwarded to implement is also exposed as deterministic reviewer-feedback summaries for humans in `progress/runs.jsonl` and `progress/run-feature-<feature-id>.txt`.
