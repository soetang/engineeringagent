---
plan_id: FEAT-146
feature_id: FEAT-146
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Enforce two-state reviewer decision contract in engine and runtime normalization
  status: done
  verification:
  - uv run pytest -q tests/reviewers/test_reviewers_runtime.py tests/checks/test_checks_reviewers_runtime.py
- id: ST-002
  title: Add deterministic verbose reviewer payload rendering in checks runtime output
  status: done
  verification:
  - uv run pytest -q tests/checks/test_checks_reviewers_runtime.py tests/checks/test_run_checks_contract.py
- id: ST-003
  title: Add fallback remediation guidance when required_actions is empty
  status: done
  verification:
  - uv run pytest -q tests/checks/test_checks_reviewers_runtime.py tests/checks/test_run_checks_contract.py
- id: ST-004
  title: Align retry-feedback reviewer decision typing and messaging with two-state
    policy
  status: done
  verification:
  - uv run pytest -q tests/loop/test_retry_feedback_contracts.py tests/loop/test_loop_output.py
- id: ST-005
  title: Update docs and run final targeted verification
  status: done
  verification:
  - uv run pytest -q tests/reviewers/test_reviewers_runtime.py tests/checks/test_checks_reviewers_runtime.py
    tests/checks/test_run_checks_contract.py tests/loop/test_retry_feedback_contracts.py
    tests/loop/test_loop_runtime_iteration.py tests/loop/test_loop_output.py
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Enforce two-state reviewer decision contract in engine and runtime normalization

Remove `warning` from reviewer decision literals and enforce binary reviewer decision behavior in checks reviewer execution/normalization paths.

## ST-002 Add deterministic verbose reviewer payload rendering in checks runtime output

Keep default concise output, but in verbose mode render all normalized reviewer decision payload keys in deterministic order and structure.

## ST-003 Add fallback remediation guidance when required_actions is empty

Ensure non-approve reviewer outcomes include actionable fallback guidance when `required_actions` is absent or empty so users can proceed from terminal output.

## ST-004 Align retry-feedback reviewer decision typing and messaging with two-state policy

Update reviewer retry-feedback model/builders/tests so reviewer decision values and default messaging align with approve/request_changes-only semantics.

## ST-005 Update docs and run final targeted verification

Update reviewer documentation for two-state decision policy and verbose reviewer detail surfacing, then run final targeted tests and spec validation.
