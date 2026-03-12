---
plan_id: FEAT-079
feature_id: FEAT-079
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Extend reviewer contract model with feedback_context
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_contract.py
  - uv run python -m engineeringagent.cli validate
- id: ST-002
  title: Forward feedback_context in reviewer-phase hook feedback
  status: done
  verification:
  - uv run pytest -q tests/test_loop_reviewers.py tests/test_loop_runtime_iteration.py
- id: ST-003
  title: Document feedback_context in reviewer reference and authoring guide
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
- id: ST-004
  title: Configure readme_process feedback_context in this repo
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
- id: ST-005
  title: Run full regression and confirm reviewer feedback remains detectable
  status: done
  verification:
  - uv run pytest -q
- id: ST-006
  title: Refactor feedback_context formatting helpers
  status: done
  verification:
  - uv run pytest -q tests/test_loop_output.py tests/test_loop_reviewers.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Extend reviewer contract model with feedback_context

Update the strict Pydantic contract so `harness/reviewers.yaml` can include
`reviewers.<id>.feedback_context` without validation errors.

## ST-002 Forward feedback_context in reviewer-phase hook feedback

Update reviewer forwarding formatting so `feedback_context` is included in the
text that becomes the next-iteration `hook_feedback`, while preserving the
`reviewer '` prefix used by telemetry extraction.

## ST-003 Document feedback_context in reviewer reference and authoring guide

Update the reviewer reference doc and authoring guide to list `feedback_context`
as an optional reviewer field and describe its forwarding semantics.

## ST-004 Configure readme_process feedback_context in this repo

Update `harness/reviewers.yaml` so `readme_process` provides implement-facing
context that it runs in a constrained clean-room sandbox and may not have full
repo/spec visibility; implement should still address failures but choose fixes
consistent with the full codebase and feature specs.

## ST-005 Run full regression and confirm reviewer feedback remains detectable

Run the full test suite and ensure progress telemetry still records reviewer
feedback presence/summary correctly.

## ST-006 Refactor feedback_context formatting helpers

De-duplicate feedback_context appending in reviewer forwarding and make
feedback_context stripping intent explicit, without changing behavior.
