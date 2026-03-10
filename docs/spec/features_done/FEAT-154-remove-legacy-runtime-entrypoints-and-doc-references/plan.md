---
plan_id: FEAT-154
feature_id: FEAT-154
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove fitness compatibility CLI app and handler
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli.py tests/cli/test_cli_reviewers.py
- id: ST-002
  title: Remove reviewer legacy kwargs invocation path
  status: done
  verification:
  - uv run pytest -q tests/reviewers/test_reviewers_runtime.py tests/reviewers/test_reviewers_additional_coverage.py
- id: ST-003
  title: Remove include_reviewers scaffold compatibility no-op
  status: done
  verification:
  - uv run pytest -q tests/cli/test_init_command.py tests/cli/test_init_scaffold.py
- id: ST-004
  title: Align docs to active command and import surfaces
  status: done
  verification:
  - uv run engineeringagent validate
- id: ST-005
  title: Run final regression and spec validation
  status: done
  verification:
  - uv run pytest -q tests/cli/test_cli.py tests/cli/test_cli_reviewers.py tests/reviewers/test_reviewers_runtime.py
    tests/reviewers/test_reviewers_additional_coverage.py tests/cli/test_init_command.py
    tests/cli/test_init_scaffold.py
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove fitness compatibility CLI app and handler

Delete Typer `fitness` subapp registration and runtime handler paths that exist only as compatibility entrypoints, delete associated CLI-compat-only tests/helpers, and preserve supported checks-run behavior.

## ST-002 Remove reviewer legacy kwargs invocation path

Refactor `run_reviewer` contract to typed request-only invocation and update runtime call sites/tests that currently pass kwargs; delete kwargs coercion helpers/tests that only existed for legacy compatibility.

## ST-003 Remove include_reviewers scaffold compatibility no-op

Delete `include_reviewers` from scaffold manifest function signatures and options containers, then delete compatibility-only tests and align remaining tests to supported init inputs only.

## ST-004 Align docs to active command and import surfaces

Update active docs that reference removed legacy command/import surfaces so contributor guidance matches runtime reality.

## ST-005 Run final regression and spec validation

Execute targeted regression tests plus full validation to confirm the compatibility-seam removals.
