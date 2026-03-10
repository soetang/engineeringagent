---
plan_id: FEAT-139
feature_id: FEAT-139
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Rename prompt and renderer terminology to canonical feedback
  status: done
  verification:
  - uv run pytest -q tests/loop/test_feedback_contracts.py tests/loop/test_loop_contracts.py
    tests/loop/test_loop_opencode_integration.py tests/loop/test_loop_ralph_mode.py
- id: ST-002
  title: Rename loop/checks/reviewer feedback contract fields
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_phases_coverage.py tests/loop/test_loop_contracts.py
    tests/checks/test_checks_reviewers_runtime.py tests/checks/test_run_checks_contract.py
- id: ST-003
  title: Align retry-envelope module and helper names to feedback terminology
  status: done
  verification:
  - uv run pytest -q tests/loop/test_feedback_contracts.py tests/loop/test_loop_phases_coverage.py
- id: ST-004
  title: Update docs and fitness assets to new naming
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_checks_own_prompt_feedback_rendering.py
    tests/fitness/test_fitness_rules_feedback_no_truncation.py
- id: ST-005
  title: Run final verification and spec validation
  status: done
  verification:
  - uv run pytest -q tests/loop/test_feedback_contracts.py tests/loop/test_loop_contracts.py
    tests/loop/test_loop_phases_coverage.py tests/loop/test_loop_opencode_integration.py
    tests/loop/test_loop_ralph_mode.py tests/checks/test_checks_reviewers_runtime.py
    tests/checks/test_run_checks_contract.py tests/fitness/test_fitness_rules_checks_own_prompt_feedback_rendering.py
    tests/fitness/test_fitness_rules_feedback_no_truncation.py
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Rename prompt and renderer terminology to canonical feedback

Update implementation/reviewer prompt prose and renderer helper naming to use `feedback` terminology. Remove retry-specific naming in touched prompt code.

## ST-002 Rename loop/checks/reviewer feedback contract fields

Replace `hook_feedback` and `prior_feedback` fields with canonical feedback field names through loop runtime, checks API, reviewer engine wiring, and telemetry interfaces.

## ST-003 Align retry-envelope module and helper names to feedback terminology

Rename retry-feedback model/function/type symbols to feedback naming while keeping envelope data semantics and deterministic serialization behavior.

## ST-004 Update docs and fitness assets to new naming

Update architecture/docs/fitness rule references and assertions that encode old retry-feedback wording or symbol names so policy remains consistent.

## ST-005 Run final verification and spec validation

Run targeted regressions and full spec validation to prove rename coherence.
