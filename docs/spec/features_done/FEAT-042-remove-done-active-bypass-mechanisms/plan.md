---
plan_id: FEAT-042
feature_id: FEAT-042
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove schema-only validation mode from CLI and validator interfaces
  status: done
  verification:
  - uv run pytest -q tests/test_cli.py::test_validate_fails_on_agents_docs_map_errors
  - uv run pytest -q tests/test_validator.py::test_validate_reports_done_feature_left_in_active_directory
- id: ST-002
  title: Replace allowlist transition handling with explicit unsupported-file validation
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py::test_validate_transitional_policy_for_preexisting_done_features
  - uv run pytest -q tests/test_validator.py::test_validate_uses_configured_docs_root
- id: ST-003
  title: Update validator tests for hard enforcement and no-bypass messaging
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py
- id: ST-004
  title: Remove transition artifact and align current docs with new command contract
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py
  - uvx --from . engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove schema-only validation mode from CLI and validator interfaces

Remove `--schema-only` argument wiring and simplify validator invocation so archival policy checks are always enforced.

## ST-002 Replace allowlist transition handling with explicit unsupported-file validation

Delete allowlist loading logic and add deterministic validation failure when `.allow-done-active.txt` is present in active features.

## ST-003 Update validator tests for hard enforcement and no-bypass messaging

Replace transitional allowlist expectations with hard-fail assertions, add coverage for unsupported transition file presence, and keep done-archive invariants explicit.

## ST-004 Remove transition artifact and align current docs with new command contract

Remove `docs/spec/features/.allow-done-active.txt` and update active reference docs that currently instruct `validate --schema-only`.
