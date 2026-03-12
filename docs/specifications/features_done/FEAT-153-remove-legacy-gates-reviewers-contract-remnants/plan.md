---
plan_id: FEAT-153
feature_id: FEAT-153
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove legacy specs contract models and issue helpers
  status: done
  verification:
  - uv run pytest -q tests/checks tests/reviewers
- id: ST-002
  title: Remove legacy compatibility branches from validate and CLI
  status: done
  verification:
  - uv run pytest -q tests/meta/test_validator.py tests/cli/test_cli.py
- id: ST-003
  title: Align tests with active checks-only contract surfaces
  status: done
  verification:
  - uv run pytest -q tests/checks tests/reviewers tests/meta/test_validator.py tests/cli/test_cli.py
- id: ST-004
  title: Update docs and references to remove legacy contract mention
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-005
  title: Run final regression and validation
  status: done
  verification:
  - uv run pytest -q tests/checks tests/reviewers tests/meta/test_validator.py tests/cli/test_cli.py
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove legacy specs contract models and issue helpers

Delete gate/reviewer legacy config models and issue-builder helpers that are not part of the active checks contract architecture.

## ST-002 Remove legacy compatibility branches from validate and CLI

Eliminate validate/CLI branches that exist only for gate/reviewer legacy contract handling, preserving deterministic active-surface behavior.

## ST-003 Align tests with active checks-only contract surfaces

Update or remove tests that directly import/assert removed legacy contract APIs and ensure remaining tests validate active contract ownership.

## ST-004 Update docs and references to remove legacy contract mention

Ensure contributor and user docs describe only checks-based harness contracts as maintained surfaces.

## ST-005 Run final regression and validation

Run targeted suites plus full validation to confirm legacy-remnant removal without regressions to active command/check behavior.
