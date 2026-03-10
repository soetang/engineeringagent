---
plan_id: FEAT-123
feature_id: FEAT-123
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove legacy progress shim modules
  status: done
  verification:
  - uv run pytest -q tests/meta/test_progress_import_paths.py
- id: ST-002
  title: Add progress package convenience re-exports (only if they are currently used
    in production code - else delete them)
  status: done
  verification:
  - uv run pytest -q tests/meta
- id: ST-003
  title: Update contract tests for hard-fail legacy imports
  status: done
  verification:
  - uv run pytest -q tests/meta/test_legacy_shim_imports.py tests/meta/test_progress_import_paths.py
- id: ST-004
  title: Run full validation for breaking import-surface change
  status: done
  verification:
  - uv run pytest -q
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove legacy progress shim modules

Delete the two top-level shim files and any remaining production references under `src/engineeringagent/**`.

## ST-002 Add progress package convenience re-exports (only if they are currently used in production code - else delete them)

Update `engineeringagent.progress.__init__` to expose commonly used paths/logging helpers while keeping canonical submodules intact.

## ST-003 Update contract tests for hard-fail legacy imports

Replace shim-importability assertions with explicit checks that legacy modules are absent and canonical imports work.

Notes:
- Replaced token-based scanning with AST import-statement validation across production Python modules under `src/engineeringagent/**`.

## ST-004 Run full validation for breaking import-surface change

Validate no regressions in loop/reviewer progress behavior and spec/runtime contracts.
