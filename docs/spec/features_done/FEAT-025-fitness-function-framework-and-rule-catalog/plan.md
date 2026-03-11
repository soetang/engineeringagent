---
plan_id: FEAT-025
feature_id: FEAT-025
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define fitness-function domain model and result contract
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_contract.py
  - uv run pytest -q tests/test_fitness_manifest_contract.py
- id: ST-002
  title: Implement registry and rule discovery entrypoints
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_registry.py
  - uv run pytest -q tests/test_fitness_manifest.py
  - uv run pytest -q tests/test_fitness_rule_id_collisions.py
- id: ST-003
  title: Implement command adapter contract for custom polyglot rules
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_adapters.py
  - uv run pytest -q tests/test_fitness_side_effect_contract.py
- id: ST-004
  title: Add initial built-in rules for architecture and loop boundaries
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_rules_directionality.py
  - uv run pytest -q tests/test_fitness_rules_loop_subprocess_boundary.py
- id: ST-005
  title: Integrate fitness execution into CLI and gate profile
  status: done
  verification:
  - uv run pytest -q tests/test_cli.py::test_fitness_subcommands
  - uv run pytest -q tests/test_gates.py::test_fitness_gate_integration
  - uv run pytest -q tests/test_fitness_parallel_runner.py
- id: ST-006
  title: Publish auto-generated rule catalog docs with diagrams
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness catalog --format markdown --output
    docs/fitness-functions/rules.md
  - uv run pytest -q tests/test_fitness_catalog_generation.py
  - uv run mdformat --check README.md AGENTS.md docs/references/docs-architecture.md
- id: ST-007
  title: Run full validation and regression suite for feature readiness
  status: done
  verification:
  - uvx --from . engineeringagent validate
  - uvx --from . engineeringagent gates run --profile precommit
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define fitness-function domain model and result contract

Specify rule identity, severity, scope/target, and pass/fail payload shape so rule output is deterministic for both human and gate consumers. Define and document the versioned custom rule manifest and result envelope contract.

## ST-002 Implement registry and rule discovery entrypoints

Add a centralized registry that enumerates built-in fitness rules and merges user-defined rules loaded from harness/fitness_functions/rules.yaml so listing and selection behavior reflects the active combined catalog. Reject duplicate rule IDs deterministically with clear diagnostics.

## ST-003 Implement command adapter contract for custom polyglot rules

Implement the external command adapter contract used by user-defined rules so language-native tools can run while preserving a common result envelope. Built-in Python rules may keep internal adapter paths but custom rule extension must rely on command execution from the harness manifest. Contract metadata must include side-effect-free declaration for all rules.

## ST-004 Add initial built-in rules for architecture and loop boundaries

Implement directionality checks for key dependency boundaries and enforce that loop orchestration code does not invoke subprocess directly outside approved adapters.

## ST-005 Integrate fitness execution into CLI and gate profile

Add command surface to list and run fitness rules and wire a gate entry so violations fail consistently in automated checks. Include configurable parallel execution (for example --jobs) while keeping final result output deterministic.

## ST-006 Publish auto-generated rule catalog docs with diagrams

Create a dedicated docs section that lists active rules, scope, rationale, and remediation guidance from generated output, plus architecture diagrams for execution flow. Canonical rule inventory should be generated from the implemented registry rather than maintained manually.

## ST-007 Run full validation and regression suite for feature readiness

Ensure schema, typing, lint, and targeted tests pass with the new framework and no regression in existing loop behavior.
