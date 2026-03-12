---
plan_id: FEAT-059
feature_id: FEAT-059
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add repository-owned reviewers.yaml profile entry for code_simplifier
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_runtime.py::test_code_simplifier_plans_only_for_code_scoped_changes
- id: ST-002
  title: Align reviewer runtime agent invocation with default OpenCode agent contract
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_sandbox.py tests/test_reviewers_runtime.py
- id: ST-003
  title: Harden code_simplifier prompt for strict decision-envelope output
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_runtime.py::test_run_reviewer_loads_harness_prompt_and_parses_decision
- id: ST-004
  title: Prove code_simplifier executes in-loop with deterministic status reporting
  status: done
  verification:
  - uv run pytest -q tests/test_loop_reviewers.py::test_code_simplifier_advisory_requires_one_followup_implement_pass
  - uv run pytest -q tests/test_loop_output.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add repository-owned reviewers.yaml profile entry for code_simplifier

Create active reviewer config for this repo so loop_fast can plan and run code_simplifier.

## ST-002 Align reviewer runtime agent invocation with default OpenCode agent contract

Remove hard-coded build-agent reviewer invocation and use shared default agent contract.

## ST-003 Harden code_simplifier prompt for strict decision-envelope output

Lightly edit prompt wording so parser-facing JSON requirements and non-approval semantics are explicit.

## ST-004 Prove code_simplifier executes in-loop with deterministic status reporting

Add or update loop integration tests to verify reviewer phase activation and telemetry fields for code_simplifier.
