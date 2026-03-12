---
plan_id: FEAT-057
feature_id: FEAT-057
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Inventory current CLI surface and lock parity expectations
  status: done
  verification:
  - uv run pytest -q tests/test_cli.py
- id: ST-002
  title: Introduce Typer app scaffold and root command wiring
  status: done
  verification:
  - uv run pytest -q tests/test_cli.py::test_main_runs_selected_handler
- id: ST-003
  title: Migrate gates and fitness command trees to Typer
  status: done
  verification:
  - uv run pytest -q tests/test_gates.py tests/test_fitness_catalog_generation.py
- id: ST-004
  title: Migrate run and init command options to Typer
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py tests/test_loop_ralph_mode.py
- id: ST-005
  title: Complete verification bar for parser migration
  status: done
  verification:
  - uv run pytest -q
  - uv run python -m engineeringagent.cli validate
  - uv run python -m engineeringagent.cli fitness run --format json
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Inventory current CLI surface and lock parity expectations

Capture existing commands/options/dispatch expectations from tests before migration to reduce behavior regressions.

## ST-002 Introduce Typer app scaffold and root command wiring

Add Typer app initialization and register current top-level command groups with equivalent option names.

## ST-003 Migrate gates and fitness command trees to Typer

Port nested subcommands and ensure plan/list/run/catalog options map cleanly to existing handlers.

## ST-004 Migrate run and init command options to Typer

Port positional and optional arguments for run and init commands, preserving default values and compatibility constraints.

## ST-005 Complete verification bar for parser migration

Ensure repository contract checks and fitness outputs remain stable after parser migration.
