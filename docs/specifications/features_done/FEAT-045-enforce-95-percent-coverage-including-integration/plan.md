---
plan_id: FEAT-045
feature_id: FEAT-045
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Configure direct pytest coverage enforcement at 95 percent
  status: done
  verification:
  - uv run pytest -q
- id: ST-002
  title: Include integration tests in default pytest execution path
  status: done
  verification:
  - uv run pytest -q --no-cov tests/test_loop_opencode_integration.py
- id: ST-003
  title: Add regression coverage test for configuration contract
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py
- id: ST-004
  title: Raise suite coverage to meet 95 percent threshold
  status: done
  verification:
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Configure direct pytest coverage enforcement at 95 percent

Add or update pytest/coverage config so default test execution fails below 95 percent without gate mediation.

## ST-002 Include integration tests in default pytest execution path

Remove marker-based default exclusion and ensure integration tests are part of normal run behavior.

## ST-003 Add regression coverage test for configuration contract

Add a focused test that asserts the configured minimum-coverage policy and default inclusion behavior remain intact.

## ST-004 Raise suite coverage to meet 95 percent threshold

Add focused tests for currently under-covered modules so the enforced threshold passes consistently.
