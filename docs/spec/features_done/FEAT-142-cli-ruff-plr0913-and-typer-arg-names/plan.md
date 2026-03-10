---
plan_id: FEAT-142
feature_id: FEAT-142
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Scope Ruff PLR0913 ignore to cli.py
  status: done
  verification:
  - uv run ruff check src/engineeringagent/cli.py
  - uv run ruff check src/engineeringagent
- id: ST-002
  title: Align handler arg names for fitness commands
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli.py tests/cli/test_cli_typer_parity_helpers.py
  - uv run ruff check src/engineeringagent
- id: ST-003
  title: Align handler arg names for run command
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli.py
  - uv run python -m engineeringagent.cli run --help
- id: ST-004
  title: Update tests that construct handler args directly
  status: done
  verification:
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Scope Ruff PLR0913 ignore to cli.py

Update `pyproject.toml` Ruff config to add a `per-file-ignores` entry for
`src/engineeringagent/cli.py` targeting only `PLR0913`.

Notes:
- Already present in pyproject.toml under tool.ruff.lint.per-file-ignores.

## ST-002 Align handler arg names for fitness commands

Rename internal handler attributes so fitness handlers read `args.output_format`
instead of `args.format`, and ensure Typer wrappers pass `output_format=...`.

## ST-003 Align handler arg names for run command

Rename internal handler attributes so `cmd_run` reads `args.run_all` instead of
`args.all`, and ensure the Typer wrapper passes `run_all=...` (still wired to `--all`).

## ST-004 Update tests that construct handler args directly

Update tests that call `cmd_*` functions with fake args namespaces so they provide
`output_format` and `run_all` (and no longer rely on `format` / `all`).
