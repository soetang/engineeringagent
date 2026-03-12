---
plan_id: FEAT-062
feature_id: FEAT-062
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Port builtin rule implementations to harness command scripts
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_adapters.py
- id: ST-002
  title: Replace builtin manifest references with command entries
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_manifest_contract.py tests/test_fitness_registry.py
- id: ST-003
  title: Remove builtin loader and manifest contract support from runtime
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_manifest.py tests/test_fitness_rule_id_collisions.py
- id: ST-004
  title: Migrate and reorganize rule-specific tests to harness-oriented structure
  status: done
  verification:
  - uv run pytest -q tests/test_fitness_rules_directionality.py tests/test_fitness_rules_loop_subprocess_boundary.py
    tests/test_fitness_rules_prompt_locality.py tests/test_fitness_rules_scaffold_template_locality.py
- id: ST-005
  title: Run full validation and loop-fast gates after migration
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run python -m engineeringagent.cli gates run --profile loop_fast
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Port builtin rule implementations to harness command scripts

Create one command script per migrated rule with deterministic envelope output.

## ST-002 Replace builtin manifest references with command entries

Update harness fitness manifest so active rule catalog is fully command-backed.

## ST-003 Remove builtin loader and manifest contract support from runtime

Delete BuiltinRuleManifestReference usage and builtin resolution branches from fitness registry/contracts.

## ST-004 Migrate and reorganize rule-specific tests to harness-oriented structure

Move builtin-function tests to harness-command behavior tests while maintaining deterministic assertions.

## ST-005 Run full validation and loop-fast gates after migration

Confirm migrated harness-only fitness stack blocks or passes exactly through existing gate profiles.
