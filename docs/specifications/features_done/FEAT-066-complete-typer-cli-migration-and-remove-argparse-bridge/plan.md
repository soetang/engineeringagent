---
plan_id: FEAT-066
feature_id: FEAT-066
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Replace argparse-forwarded commands with Typer-native command wiring
  status: done
  verification:
  - uv run pytest -q tests/test_cli.py tests/test_cli_reviewers.py
- id: ST-002
  title: Remove argparse parser construction and legacy forwarding helpers from cli.py
  status: done
  verification:
  - uv run pytest -q tests/test_cli.py tests/test_cli_typer_parity_helpers.py
- id: ST-003
  title: Refactor command handlers away from argparse Namespace coupling
  status: done
  verification:
  - uv run pytest -q tests/test_cli.py tests/test_init_command.py tests/test_loop_ralph_mode.py
- id: ST-004
  title: Rewrite parser-introspection tests to Typer-native contract assertions
  status: done
  verification:
  - uv run pytest -q tests/test_cli.py tests/test_fitness_catalog_generation.py tests/test_gates.py
- id: ST-005
  title: Run full regression and validation for Typer-only CLI contract
  status: done
  verification:
  - uv run pytest -q
  - uv run python -m engineeringagent.cli validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Replace argparse-forwarded commands with Typer-native command wiring

Migrate remaining forwarded command paths (for example validate/reviewers) to direct Typer handlers and typed option declarations.

## ST-002 Remove argparse parser construction and legacy forwarding helpers from cli.py

Delete `build_parser` and related legacy dispatch helpers, ensuring command routing remains deterministic under Typer.

## ST-003 Refactor command handlers away from argparse Namespace coupling

Update handler signatures/call patterns so command execution uses explicit typed values or Typer context payloads instead of argparse Namespace objects.

## ST-004 Rewrite parser-introspection tests to Typer-native contract assertions

Replace tests that inspect argparse parser trees/options with behavior-based Typer invocation coverage including command/flag parity.

## ST-005 Run full regression and validation for Typer-only CLI contract

Confirm full repository tests and spec validation pass with argparse removed from main CLI module.
