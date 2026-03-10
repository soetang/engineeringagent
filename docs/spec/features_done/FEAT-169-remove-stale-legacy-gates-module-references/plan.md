---
plan_id: FEAT-169
feature_id: FEAT-169
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove legacy gates path from subprocess boundary policy assets
  status: done
  verification:
  - uv run python harness/fitness-functions/check_loop_subprocess_boundary.py
- id: ST-002
  title: Update fitness fixtures and assertions to stop modeling gates module allowlisting
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_loop_subprocess_boundary.py
  - uv run pytest -q tests/fitness/test_fitness_adapters.py
  - uv run pytest -q tests/fitness/test_fitness_rules_directionality.py
- id: ST-003
  title: Remove legacy module import-deletion assertion from harness tests
  status: done
  verification:
  - uv run engineeringagent validate --schema-only
  - uv run pytest -q tests/fitness/test_fitness_rules_loop_subprocess_boundary.py
    tests/fitness/test_fitness_adapters.py tests/fitness/test_fitness_rules_directionality.py
    tests/harness/test_gates.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove legacy gates path from subprocess boundary policy assets

Remove `src/engineeringagent/gates.py` from native and semgrep parity policy
files so active allowlists only contain current modules.

## ST-002 Update fitness fixtures and assertions to stop modeling gates module allowlisting

Update tests that currently create `src/engineeringagent/gates.py` fixtures or
assert non-violation behavior for that path, replacing with active module paths
where needed.

## ST-003 Remove legacy module import-deletion assertion from harness tests

Confirm the new cleanup spec validates and targeted suites pass with no remaining
active legacy gates module references.
