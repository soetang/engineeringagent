---
plan_id: FEAT-151
feature_id: FEAT-151
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Relocate fitness emitter implementation under checks/fitness
  status: done
  verification:
  - uv run pytest -q tests/checks/test_checks_exports.py
- id: ST-002
  title: Remove emit_result_envelope alias from checks surface
  status: done
  verification:
  - uv run pytest -q tests/checks/test_checks_exports.py
- id: ST-003
  title: Migrate harness fitness scripts to emit_fitness_result
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_harness_envelope_helper_surface.py
    tests/fitness/test_fitness_rules_harness_src_import_allowlist.py
- id: ST-004
  title: Correct fitness README and architecture documentation
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-005
  title: Run targeted regression and repository validation
  status: done
  verification:
  - uv run pytest -q tests/checks/test_checks_exports.py tests/fitness/test_fitness_harness_envelope_helper_surface.py
    tests/fitness/test_fitness_rules_harness_src_import_allowlist.py tests/fitness/test_fitness_rules_checks_import_surface.py
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Relocate fitness emitter implementation under checks/fitness

Move the canonical deterministic JSON emitter implementation from `checks/fitness_api.py` into a fitness-owned module and keep import ownership explicit via top-level checks exports.

## ST-002 Remove emit_result_envelope alias from checks surface

Remove alias export and all alias wiring from `engineeringagent.checks`. Update dependent tests to assert alias removal and canonical helper usage.

## ST-003 Migrate harness fitness scripts to emit_fitness_result

Update all harness fitness-function scripts to import and call `emit_fitness_result` from `engineeringagent.checks`.

## ST-004 Correct fitness README and architecture documentation

Update fitness docs so helper import examples and architecture flow describe the current checks-owned contract and CLI surface.

## ST-005 Run targeted regression and repository validation

Run focused tests for checks export surface and harness fitness script contracts, then run full spec/doc validation to ensure no contract drift.
