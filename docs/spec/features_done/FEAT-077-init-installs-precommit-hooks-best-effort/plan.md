---
plan_id: FEAT-077
feature_id: FEAT-077
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add pre-commit install logic and skip flag to init
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py
- id: ST-002
  title: Add tests for git-present or missing and pre-commit-present or missing behavior
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py
- id: ST-003
  title: Delegate pre-commit install subprocess calls to git client
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py
  - uv run python -m engineeringagent.cli fitness run --format json
- id: ST-004
  title: Harden non-fatal hook install and simplify tests
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py
  - uv run pytest -q tests/test_git_client.py
- id: ST-005
  title: Treat .git files as repos and tighten init tests
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add pre-commit install logic and skip flag to init

Implement best-effort hook installation and ensure it is non-fatal and non-interactive.

## ST-002 Add tests for git-present or missing and pre-commit-present or missing behavior

Stub subprocess calls to validate init behavior and output messages deterministically.

## ST-003 Delegate pre-commit install subprocess calls to git client

Fix architecture.loop-subprocess-boundary by moving pre-commit subprocess calls
out of `engineeringagent.cli` and into `engineeringagent.git.client`.

## ST-004 Harden non-fatal hook install and simplify tests

Make hook installation resilient to unexpected subprocess errors and reduce test coupling by asserting init delegates to git_client while git_client unit tests own subprocess kwargs validation.

## ST-005 Treat .git files as repos and tighten init tests

Git worktrees represent .git as a file rather than a directory. Init should still attempt best-effort pre-commit hook installation in that case. Also tighten monkeypatch usage and remove redundant delegation tests.
