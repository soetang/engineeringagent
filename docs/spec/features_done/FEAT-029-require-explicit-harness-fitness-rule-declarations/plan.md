---
plan_id: FEAT-029
feature_id: FEAT-029
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Extend fitness manifest contract for explicit builtin references
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_manifest_contract.py
  - uv run pytest -q tests/test_fitness_manifest.py
- id: ST-002
  title: Remove implicit builtin activation from catalog construction
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_registry.py
  - uv run pytest -q tests/test_fitness_rule_id_collisions.py
- id: ST-003
  title: Enforce declaration-only behavior across list run and catalog commands
  status: done
  verification:
  - uv run pytest -q tests/test_cli.py
  - uv run pytest -q tests/test_fitness_catalog_generation.py
  - uv run pytest -q tests/test_cli.py::test_fitness_run_executes_shell_command_rule
  - uv run pytest -q tests/test_cli.py::test_fitness_list_shows_declared_shell_rule_only
- id: ST-004
  title: Add validator checks for manifest builtin reference integrity
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py
  - uvx --from . engineeringagent validate
- id: ST-005
  title: Seed explicit builtin declarations in repo and init scaffolding
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py
  - uv run pytest -q tests/test_gates.py
- id: ST-006
  title: Run focused regressions and validate gate behavior
  status: done
  verification:
  - uvx --from . engineeringagent validate --schema-only
  - uv run pytest -q tests/test_cli.py
  - uv run pytest -q tests/test_fitness_registry.py
  - uv run pytest -q tests/test_fitness_catalog_generation.py
  - uvx --from . engineeringagent gates run --profile loop_fast
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Extend fitness manifest contract for explicit builtin references

Add contract support for builtin reference entries in harness/fitness-functions/rules.yaml while preserving existing command-rule support.

## ST-002 Remove implicit builtin activation from catalog construction

Refactor registry and runner so active catalogs are declaration-driven and no longer append built-ins by default.

## ST-003 Enforce declaration-only behavior across list run and catalog commands

Ensure CLI surfaces share one active catalog source and cannot include undeclared rules. Include regression coverage for shell-command custom rules to confirm non-Python declaration and execution paths remain valid. Prefer tmp_path temporary project roots for these tests to keep setup lightweight and deterministic.

## ST-004 Add validator checks for manifest builtin reference integrity

Make validation fail with deterministic diagnostics when builtin manifest references are invalid or unresolved.

## ST-005 Seed explicit builtin declarations in repo and init scaffolding

Populate harness defaults and init-generated manifests with explicit references for the current built-in architecture rules.

## ST-006 Run focused regressions and validate gate behavior

Confirm declaration-driven behavior holds in gate execution and repo-level validation flows.
