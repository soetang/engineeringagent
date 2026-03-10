---
plan_id: FEAT-037
feature_id: FEAT-037
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define TOML docs-root configuration contract and resolver precedence
  status: done
  verification:
  - uv run pytest -q tests/test_cli.py::test_docs_root_resolver_defaults_to_docs
  - uv run pytest -q tests/test_cli.py::test_docs_root_resolver_prefers_engineeringagent_toml
  - uv run pytest -q tests/test_cli.py::test_docs_root_resolver_reads_pyproject_tool_engineeringagent
- id: ST-002
  title: Wire validator path resolution to configured docs root
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py::test_validate_uses_configured_docs_root
  - uvx --from . engineeringagent validate
- id: ST-003
  title: Wire run all discovery and archive flow to configured docs root
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_all_uses_configured_docs_root
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_archive_path_uses_configured_docs_root
- id: ST-004
  title: Integrate init separate docs mode with TOML docs-root config
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py::test_init_separate_docs_writes_engineeringagent_toml_docs_root
  - uv run pytest -q tests/test_init_command.py::test_validate_and_run_all_use_separate_docs_root
- id: ST-005
  title: Run compatibility regressions for default docs root repositories
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py::test_validate_defaults_to_docs_without_toml_config
  - uv run pytest -q
  - uvx --from . engineeringagent validate
  - uvx --from . engineeringagent gates run --profile loop_fast
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define TOML docs-root configuration contract and resolver precedence

Add one deterministic resolver for docs root using `engineeringagent.toml` first, then `pyproject.toml:[tool.engineeringagent]`, with fallback behavior and clear error messages for invalid values.

## ST-002 Wire validator path resolution to configured docs root

Replace hardcoded validator paths with docs-root derived paths for feature specs, done specs, schema artifact, and potential features.

## ST-003 Wire run all discovery and archive flow to configured docs root

Update loop discovery and completion archive path logic to use docs-root aware directories while preserving current behavior under default root.

## ST-004 Integrate init separate docs mode with TOML docs-root config

Ensure init writes docs-root TOML configuration when separate docs mode is selected and verify runtime commands consume it without extra flags.

## ST-005 Run compatibility regressions for default docs root repositories

Confirm repositories that rely on default `docs/` continue to pass validation, loop-fast checks, and loop behavior unchanged when no TOML docs-root config is present.
