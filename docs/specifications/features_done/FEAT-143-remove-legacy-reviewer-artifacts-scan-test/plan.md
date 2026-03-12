---
plan_id: FEAT-143
feature_id: FEAT-143
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove the legacy reviewer artifact scan test
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove the legacy reviewer artifact scan test

Delete `tests/test_no_legacy_reviewer_artifacts.py` (or remove the single test
it contains) and ensure no other tests rely on it.
