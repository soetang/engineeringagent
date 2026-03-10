---
plan_id: FEAT-149
feature_id: FEAT-149
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove CLI-side duplicate reviewer feature-path precondition
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli_checks.py
- id: ST-002
  title: Make checks command rendering handle normalization input errors
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli_checks.py tests/checks/test_run_checks_contract.py
- id: ST-003
  title: Run targeted regression and spec validation
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli_checks.py tests/checks/test_run_checks_contract.py
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove CLI-side duplicate reviewer feature-path precondition

Delete the CLI checks-wiring guard that duplicates reviewer feature-path policy owned by request normalization.

## ST-002 Make checks command rendering handle normalization input errors

Ensure CLI command handler renders normalization validation failures cleanly and exits non-zero without stack-trace behavior.

## ST-003 Run targeted regression and spec validation

Confirm boundary ownership and deterministic behavior remain intact after deduplication.
