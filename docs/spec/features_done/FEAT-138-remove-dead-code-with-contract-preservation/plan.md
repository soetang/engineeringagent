---
plan_id: FEAT-138
feature_id: FEAT-138
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove confirmed-dead source helpers with explicit symbol list
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/meta/test_validator.py
    tests/fitness/test_fitness_catalog_generation.py
- id: ST-002
  title: Remove likely-dead facade signature constants with rollback guard
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_contracts.py tests/fitness/test_fitness_no_facade_varargs_shims.py
- id: ST-003
  title: Remove dead test-only artifacts with explicit symbol list
  status: done
  verification:
  - uv run pytest -q tests/config/test_repo_engineeringagent_toml.py tests/harness/test_checks_runtime.py
    tests/meta/test_validator.py
- id: ST-004
  title: Re-verify CLI and checks/spec-definition behavior parity
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli_checks_catalog.py tests/checks/test_checks_exports.py
    tests/checks/test_run_checks_contract.py tests/meta/test_validator.py
- id: ST-005
  title: Run full validation and full suite for final regression proof
  status: done
  verification:
  - uv run engineeringagent validate
  - uv run pytest
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove confirmed-dead source helpers with explicit symbol list

Remove exactly these symbols unless new usage is found: `engineeringagent.checks.fitness.catalog.write_rule_catalog_markdown` in `src/engineeringagent/checks/fitness/catalog.py`, `engineeringagent.checks.validate.validator._append_gate_config_issues` and `engineeringagent.checks.validate.validator._append_reviewer_config_issues` in `src/engineeringagent/checks/validate/validator.py`, and `engineeringagent.specs.find_subtask` in `src/engineeringagent/specs.py`. Preserve behavior and rollback any symbol if usage is discovered.

## ST-002 Remove likely-dead facade signature constants with rollback guard

Remove exactly these constants if behavior stays unchanged: `engineeringagent.loop_runtime.facade_signatures.RUN_IMPLEMENT_STEP_SIGNATURE` and `engineeringagent.loop_runtime.facade_signatures.RUN_FEATURE_ITERATION_SIGNATURE` in `src/engineeringagent/loop_runtime/facade_signatures.py`. If usage/regression is found, restore and defer.

## ST-003 Remove dead test-only artifacts with explicit symbol list

Remove exactly these dead test artifacts: import `resolve_agents_backend_id` from `tests/config/test_repo_engineeringagent_toml.py`, import `SimpleNamespace` from `tests/harness/test_checks_runtime.py`, and helper `_read_repo_text` from `tests/meta/test_validator.py`. Keep behavior-oriented assertions unchanged.

## ST-004 Re-verify CLI and checks/spec-definition behavior parity

Run focused regressions that assert unchanged CLI output, checks execution semantics, and spec-validation contracts after cleanup.

## ST-005 Run full validation and full suite for final regression proof

Execute repository-wide validation and tests to confirm no behavior regressions for user-facing surfaces and harness workflow.
