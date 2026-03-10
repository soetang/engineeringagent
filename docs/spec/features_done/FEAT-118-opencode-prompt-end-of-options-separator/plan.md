---
plan_id: FEAT-118
feature_id: FEAT-118
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add end-of-options separator in OpenCode client command construction
  status: done
  verification:
  - uv run pytest -q tests/opencode/test_opencode_client.py
- id: ST-002
  title: Add explicit non-regression test for hyphen-leading prompt payload handling
  status: done
  verification:
  - uv run pytest -q tests/opencode/test_opencode_client.py tests/agents/test_opencode_backend.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add end-of-options separator in OpenCode client command construction

Update OpenCode client argv building so prompt payload is appended only after
`--`, preserving existing option handling.

## ST-002 Add explicit non-regression test for hyphen-leading prompt payload handling

Extend OpenCode client/backend tests to assert command argv includes the
separator and remains stable for normal and hyphen-leading prompts.

Add a dedicated client test focused on `---`-prefixed prompt input so future
argv regressions are caught even if other prompt tests still pass.
