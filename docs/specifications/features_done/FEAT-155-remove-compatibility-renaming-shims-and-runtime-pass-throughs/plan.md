---
plan_id: FEAT-155
feature_id: FEAT-155
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove planning-policy constant mirror exports from checks runtimes
  status: done
  verification:
  - uv run pytest -q tests/checks
- id: ST-002
  title: Remove validate runtime pass-through and standardize canonical naming
  status: done
  verification:
  - uv run pytest -q tests/checks/test_validate_group.py
- id: ST-003
  title: Update tests and import-surface assertions for removed shim paths
  status: done
  verification:
  - uv run pytest -q tests/fitness/test_fitness_rules_checks_import_surface.py tests/checks/test_validate_group.py
- id: ST-004
  title: Remove compatibility-only test aliases and legacy wrappers
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_feature_iteration.py tests/loop/test_loop_opencode_integration.py
    tests/harness/test_checks_runtime.py
- id: ST-005
  title: Run final contract validation
  status: done
  verification:
  - uv run engineeringagent validate --schema-only
  - uv run pytest -q tests/checks/test_validate_group.py tests/fitness/test_fitness_rules_checks_import_surface.py
    tests/loop/test_loop_feature_iteration.py tests/loop/test_loop_opencode_integration.py
    tests/harness/test_checks_runtime.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove planning-policy constant mirror exports from checks runtimes

Delete alias-import plus assignment re-export patterns from command/fitness/reviewer runtime modules and switch to canonical constant usage/imports.

## ST-002 Remove validate runtime pass-through and standardize canonical naming

Remove `checks.validate.runtime` alias wrapper and route validate execution through the canonical validate symbol/module, including package exports if still needed.

## ST-003 Update tests and import-surface assertions for removed shim paths

Update tests that monkeypatch/import removed shim paths so they assert canonical imports only, including checks import-surface fitness tests.

## ST-004 Remove compatibility-only test aliases and legacy wrappers

Replace or remove compatibility wrappers that keep legacy test call shapes and migration-era alias pass-throughs, while preserving readability aliases that improve local test clarity.

## ST-005 Run final contract validation

Run final schema validation and targeted regression checks to confirm removed shim surfaces are not referenced.
