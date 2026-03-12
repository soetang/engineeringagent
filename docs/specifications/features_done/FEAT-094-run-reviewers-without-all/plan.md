---
plan_id: FEAT-094
feature_id: FEAT-094
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Enable reviewer planning/execution when checks.yaml exists (independent of
    run_all)
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_reviewers.py
- id: ST-002
  title: Update tests to cover reviewer enablement without --all
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_reviewers.py
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Enable reviewer planning/execution when checks.yaml exists (independent of run_all)

Update run_reviewer_phase to load harness/checks.yaml and plan reviewer checks
whenever checks.yaml exists, not only when iteration_inputs.run_all is true.

## ST-002 Update tests to cover reviewer enablement without --all

Update or replace the existing unit test that asserts reviewers are not_configured
when run_all is false. Add a test that creates a minimal harness/checks.yaml
with a reviewer check and asserts reviewer_status is not_configured only when
checks.yaml is missing.
