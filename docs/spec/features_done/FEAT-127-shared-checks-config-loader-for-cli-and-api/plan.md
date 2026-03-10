---
plan_id: FEAT-127
feature_id: FEAT-127
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add shared checks config loader/helper module
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py
- id: ST-002
  title: Migrate checks API to shared loader helper
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/cli/test_cli_checks.py
- id: ST-003
  title: Migrate CLI run-all checks-config preflight to shared helper
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli.py
- id: ST-004
  title: Add/adjust parity regressions for loader outcomes
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/cli/test_cli.py
    tests/cli/test_cli_checks.py
- id: ST-005
  title: Run final validation for feature integration
  status: done
  verification:
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add shared checks config loader/helper module

Create a shared loader that resolves `harness/checks.yaml` and returns deterministic success/error outcomes for parse, contract, and model-validation paths.

## ST-002 Migrate checks API to shared loader helper

Replace `_load_harness_checks_doc(...)` plumbing with the shared helper while preserving checks API group failure semantics.

## ST-003 Migrate CLI run-all checks-config preflight to shared helper

Replace duplicated checks-config load/contract-validation logic in `cmd_run` with the shared helper and keep legacy-file checks separate.

## ST-004 Add/adjust parity regressions for loader outcomes

Lock missing/invalid checks-config outcomes across both call sites to prevent future drift.

## ST-005 Run final validation for feature integration

Confirm spec and targeted runtime behavior remain stable after dedupe refactor.
