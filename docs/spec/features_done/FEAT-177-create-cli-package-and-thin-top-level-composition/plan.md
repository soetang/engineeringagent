---
plan_id: FEAT-177
feature_id: FEAT-177
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Introduce CLI package bootstrap and top-level composition seam
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli.py tests/cli/test_cli_typer_parity_helpers.py
- id: ST-002
  title: Move command-family handlers into focused CLI package modules
  status: done
  verification:
  - uv run pytest -q tests/cli
  - uv run pytest -q tests/meta/test_agent_boundary_migration_smoke.py tests/fitness/test_fitness_rules_statement_budget.py
- id: ST-003
  title: Replace touched CLI global injection seams with explicit package-local adapters
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_service.py tests/cli/test_init_command_surface.py
    tests/cli/test_init_command_backend.py tests/cli/test_init_command_conflicts.py
- id: ST-004
  title: Run final CLI regression validation for package refactor
  status: done
  verification:
  - uv run pytest -q tests/cli
  - uv run engineeringagent validate --schema-only
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Introduce CLI package bootstrap and top-level composition seam

Create `src/engineeringagent/cli/` with `__init__.py`, `__main__.py`, and one bootstrap module (`app.py` or `typer.py`) while preserving the published CLI entrypoint and current module-execution behavior.

## ST-002 Move command-family handlers into focused CLI package modules

Split command implementation by ownership so `run`, `validate`, `schema`, `approach`, `checks`, `init`, and `progress` each live in package-owned modules. Update path-sensitive tests that currently reference `src/engineeringagent/cli.py` directly.

## ST-003 Replace touched CLI global injection seams with explicit package-local adapters

Where this refactor currently depends on module-global mutation or hidden indirection, move to explicit dependency builders or adapter functions owned by the CLI package.

## ST-004 Run final CLI regression validation for package refactor

Confirm the CLI package split preserves behavior and that spec validation still passes after the reorganization.
