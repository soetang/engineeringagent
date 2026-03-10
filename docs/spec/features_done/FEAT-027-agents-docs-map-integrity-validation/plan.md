---
plan_id: FEAT-027
feature_id: FEAT-027
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define AGENTS docs-map extraction and validation rules
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py::test_agents_docs_map_extraction_scoped_to_docs_layout_section
  - uv run pytest -q tests/test_validator.py::test_agents_docs_map_extraction_is_deterministic
- id: ST-002
  title: Integrate docs-map integrity checks into validate command flow
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py::test_validate_reports_missing_agents_docs_map_path
  - uv run pytest -q tests/test_validator.py::test_validate_reports_empty_agents_docs_map_glob
  - uv run pytest -q tests/test_cli.py::test_validate_fails_on_agents_docs_map_errors
- id: ST-003
  title: Align AGENTS documentation map to existing repository structure
  status: done
  verification:
  - uvx --from . engineeringagent validate
- id: ST-004
  title: Run targeted regressions and loop-fast gate verification
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py
  - uvx --from . engineeringagent validate
  - uvx --from . engineeringagent gates run --profile loop_fast
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define AGENTS docs-map extraction and validation rules

Implement parser logic that reads AGENTS docs-map section only and extracts references for literal/glob validation with deterministic ordering.

## ST-002 Integrate docs-map integrity checks into validate command flow

Add missing-path and empty-glob checks to validator output and fail engineeringagent validate with actionable diagnostics.

## ST-003 Align AGENTS documentation map to existing repository structure

Update AGENTS docs-map references so all listed files/directories/globs exist and reflect current repository organization.

## ST-004 Run targeted regressions and loop-fast gate verification

Confirm validator behavior and default gate integration remain stable after docs-map enforcement.
