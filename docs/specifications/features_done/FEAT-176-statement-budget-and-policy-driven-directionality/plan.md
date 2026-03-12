---
plan_id: FEAT-176
feature_id: FEAT-176
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add policy-driven AST statement budget checker and config schema
  status: done
  verification:
  - uv run pytest -q tests/fitness -k statement_budget
- id: ST-002
  title: Register statement budget rule and refresh fitness catalog docs
  status: done
  verification:
  - uv run engineeringagent checks catalog --format markdown --output docs/fitness-functions/rules.md
  - uv run pytest -q tests/fitness/test_fitness_catalog_generation.py
- id: ST-003
  title: Migrate dependency directionality checker to policy-configured boundaries
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_directionality.py tests/fitness/test_fitness_adapters.py
- id: ST-004
  title: Centralize module-size policy by disabling pylint C0302
  status: done
  verification:
  - uv run pylint --score=n --reports=n src/engineeringagent tests harness
- id: ST-005
  title: Refactor oversized modules to satisfy initial statement caps
  status: done
  verification:
  - uv run engineeringagent checks run --checks fitness --phase iteration_end
  - uv run pytest -q tests/cli/test_cli.py tests/cli/test_init_command_surface.py
    tests/cli/test_init_command_backend.py tests/cli/test_init_command_conflicts.py
    tests/cli/test_init_command_scaffold.py tests/loop/test_loop_feature_iteration_support.py
    tests/loop/test_loop_feature_iteration_verification.py tests/loop/test_loop_feature_iteration_execution.py
    tests/loop/test_loop_feature_iteration_lifecycle.py tests/loop/test_loop_feature_iteration_feedback.py
    tests/checks/test_run_checks_contract_core.py tests/checks/test_run_checks_contract_commands.py
    tests/checks/test_run_checks_contract_loader.py tests/checks/test_run_checks_contract_reviewers.py
- id: ST-006
  title: Run end-to-end validation for FEAT-176 policy and remediation changes
  status: done
  verification:
  - uv run engineeringagent validate --schema-only
  - uv run engineeringagent checks run --phase iteration_end
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add policy-driven AST statement budget checker and config schema

Implement a new checker under `harness/fitness_functions/` that counts non-doc AST statements per Python file and enforces threshold policies by path scope. Add a policy file under `harness/fitness_functions/policies/` with initial caps for `src/engineeringagent`, `tests`, and `harness`. Rule tests must use only synthetic fixture repos for checker execution.

## ST-002 Register statement budget rule and refresh fitness catalog docs

Add the new rule to `harness/fitness_functions/rules.yaml`, ensure rule metadata includes canonical remediation guidance once, and regenerate docs catalog output.

## ST-003 Migrate dependency directionality checker to policy-configured boundaries

Replace hardcoded blocked import maps in `check_dependency_directionality.py` with policy-configured boundaries while keeping the existing rule id and baseline blocked imports behaviorally equivalent.

## ST-004 Centralize module-size policy by disabling pylint C0302

Update lint configuration so pylint no longer emits `too-many-lines` diagnostics, leaving module-size governance to the statement-budget fitness rule.

## ST-005 Refactor oversized modules to satisfy initial statement caps

Reduce duplication and extract cohesive concerns into existing package folders first (or new domain subpackages when justified) for current offenders. When introducing new internal seams, update directionality policy boundaries so extracted internals remain owned and cannot be imported from unauthorized modules. Do not introduce stricter repo-wide ratchets or additional offender targets beyond this spec without a separate follow-on spec.

## ST-006 Run end-to-end validation for FEAT-176 policy and remediation changes

Validate schema, fitness checks, and targeted regressions after policy migration and module decomposition work lands.
