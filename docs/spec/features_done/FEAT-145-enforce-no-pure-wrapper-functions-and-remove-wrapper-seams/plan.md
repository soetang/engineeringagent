---
plan_id: FEAT-145
feature_id: FEAT-145
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define and register no-pure-wrapper fitness rule contract
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_manifest.py tests/fitness/test_fitness_rule_id_collisions.py
- id: ST-002
  title: Implement deterministic pure-wrapper detection with exception support
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_no_pure_wrapper_functions.py
- id: ST-003
  title: Remove or refactor existing wrapper seams in runtime/checks/helpers modules
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_contracts.py tests/loop/test_loop_runtime_iteration.py
    tests/checks/test_fitness_runtime.py tests/checks/test_validate_group.py tests/agents/test_agents_helpers.py
    tests/config/test_config_harness_toggles.py
- id: ST-004
  title: Enforce remediation-first exception policy and document any unavoidable exceptions
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_no_pure_wrapper_functions.py
    tests/fitness/test_fitness_rules_catalog_docs_sync.py
- id: ST-005
  title: Run final validation, checks, and targeted regressions
  status: done
  verification:
  - uv run engineeringagent validate
  - uv run engineeringagent checks run --phase iteration_end
  - uv run pytest -q tests/fitness/test_fitness_rules_no_pure_wrapper_functions.py
    tests/fitness/test_fitness_manifest.py tests/checks/test_fitness_runtime.py tests/loop/test_loop_contracts.py
    tests/agents/test_agents_helpers.py tests/config/test_config_harness_toggles.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define and register no-pure-wrapper fitness rule contract

Add rule metadata, script wiring, and any policy config file structure needed for scanning both src and harness fitness-function modules.

## ST-002 Implement deterministic pure-wrapper detection with exception support

Build AST-based detection for one-line pass-through wrappers, produce deterministic sorted diagnostics, and support policy-backed explicit exceptions.

## ST-003 Remove or refactor existing wrapper seams in runtime/checks/helpers modules

Replace current pure wrappers with direct canonical APIs and update dependent imports/calls. Prioritize `loop_runtime/feature_state.py`, `loop_runtime/implement.py`, `loop.py`, `agents/helpers.py`, `prompt_feedback.py`, and checks config/registry/runtime wrapper sites.

## ST-004 Enforce remediation-first exception policy and document any unavoidable exceptions

Keep allowlist empty if feasible; if any exception remains, require explicit rationale and deterministic remediation notes following the ordered decision tree.

## ST-005 Run final validation, checks, and targeted regressions

Confirm architecture policy enforcement, wrapper cleanup, and docs/manifest consistency.
