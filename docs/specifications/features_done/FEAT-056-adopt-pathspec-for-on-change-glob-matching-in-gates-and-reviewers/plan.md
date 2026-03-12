---
plan_id: FEAT-056
feature_id: FEAT-056
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add shared pathspec matcher utility
  status: done
  verification:
  - uv run pytest -q tests/test_gates.py
- id: ST-002
  title: Migrate gate planner matching to shared matcher
  status: done
  verification:
  - uv run pytest -q tests/test_gates.py
- id: ST-003
  title: Migrate reviewer planner matching to shared matcher
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_runtime.py tests/test_reviewers_state.py
- id: ST-004
  title: Add edge-case regression tests for pathspec semantics
  status: done
  verification:
  - uv run pytest -q tests/test_gates.py tests/test_reviewers_runtime.py
- id: ST-005
  title: Run full verification bar for dependency adoption
  status: done
  verification:
  - uv run pytest -q tests/test_gates.py tests/test_reviewers_runtime.py tests/test_reviewers_state.py
  - uv run python -m engineeringagent.cli validate
  - uv run python -m engineeringagent.cli fitness run --format json
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add shared pathspec matcher utility

Create a reusable matcher API and wire dependency usage behind deterministic helper functions.

## ST-002 Migrate gate planner matching to shared matcher

Replace gate-local `Path.match` logic with pathspec-backed matching while preserving reason envelopes.

## ST-003 Migrate reviewer planner matching to shared matcher

Replace reviewer-local `Path.match` logic and preserve phase and approval-cache behavior.

## ST-004 Add edge-case regression tests for pathspec semantics

Cover nested globs, renamed paths, empty-changes paths, and separator normalization behavior.

## ST-005 Run full verification bar for dependency adoption

Confirm the migration meets repository quality gates.
