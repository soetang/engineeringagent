---
plan_id: FEAT-135
feature_id: FEAT-135
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Extract init command orchestration into a dedicated service module
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli.py
- id: ST-002
  title: Centralize engineeringagent.toml mutation and writing helpers
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli.py tests/cli/test_cli_checks.py
- id: ST-003
  title: Split Typer app wiring from command handlers
  status: done
  verification:
  - uv run pytest -q tests/cli
- id: ST-004
  title: Deduplicate shared terminal and path/output helper utilities
  status: done
  verification:
  - uv run pytest -q tests/cli tests/loop/test_loop_output.py
- id: ST-005
  title: Apply minor CLI UX cleanup while preserving behavior
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli.py
- id: ST-006
  title: Run final targeted regression suite and validate specs
  status: done
  verification:
  - uv run pytest -q tests/cli
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Extract init command orchestration into a dedicated service module

Move non-CLI I/O business logic from `cmd_init` into a typed service boundary while preserving command semantics.

## ST-002 Centralize engineeringagent.toml mutation and writing helpers

Move config write/upsert responsibilities out of CLI and unify with config-domain precedence/normalization behavior.

## ST-003 Split Typer app wiring from command handlers

Separate command registration/app bootstrap from command implementation functions to simplify navigation and reduce module coupling.

## ST-004 Deduplicate shared terminal and path/output helper utilities

Replace duplicated helper implementations in CLI/runtime modules with shared utility functions and consistent behavior.

## ST-005 Apply minor CLI UX cleanup while preserving behavior

Improve readability of selected command output/help wording where it does not alter workflow semantics.

## ST-006 Run final targeted regression suite and validate specs

Confirm modularization is complete and behavior remains stable.
