---
plan_id: FEAT-178
feature_id: FEAT-178
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Identify and extract clearly checks-owned contracts
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/cli/test_cli_checks.py
- id: ST-002
  title: Update CLI and loop imports to use narrow domain-owned contracts
  status: done
  verification:
  - uv run pytest -q tests/cli tests/loop
- id: ST-003
  title: Lock contract ownership with targeted regression tests
  status: done
  verification:
  - uv run pytest -q tests/checks tests/cli tests/loop
- id: ST-004
  title: Run final validation for domain-owned contract cleanup
  status: done
  verification:
  - uv run pytest -q tests/checks tests/cli tests/loop
  - uv run engineeringagent validate --schema-only
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Identify and extract clearly checks-owned contracts

Start with `HarnessCheckPhase` and any adjacent narrow contracts whose semantics are driven by checks execution/selection behavior rather than by spec persistence. Keep the first move intentionally small to avoid a premature shared-contract bucket.

## ST-002 Update CLI and loop imports to use narrow domain-owned contracts

Replace imports from broad modules like `engineeringagent.specs` where the caller only needs checks-owned contracts. Expected first call sites include current CLI helpers and loop/checks modules that import `HarnessCheckPhase` only.

## ST-003 Lock contract ownership with targeted regression tests

Add or update focused tests so moved contract ownership remains explicit and behaviorally stable during future refactors.

## ST-004 Run final validation for domain-owned contract cleanup

Confirm contract values, schema behavior, and targeted regressions remain stable after import and ownership cleanup.
