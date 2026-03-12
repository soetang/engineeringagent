---
plan_id: FEAT-074
feature_id: FEAT-074
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Update python_uv pre-commit template entry to uvx engineeringagent
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py::test_init_python_uv_profile_available
- id: ST-002
  title: Add ruff isolated gate to python_uv scaffolded gates.yaml
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py
- id: ST-003
  title: Scaffold commit-msg validator for python_uv pre-commit hook
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py::test_init_python_uv_profile_available
- id: ST-004
  title: Update README python_uv section and run guidance
  status: done
  verification:
  - uv run pytest -q
- id: ST-006
  title: Remove subprocess usage from scaffolded commit-msg validator
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
- id: ST-005
  title: Align uv-llms reference with scaffolded precommit gates
  status: done
  verification:
  - uv run pytest -q
- id: ST-007
  title: Simplify python_uv scaffold implementation
  status: done
  verification:
  - uv run pytest -q tests/test_init_command.py
  - uv run pytest -q tests/test_loop_contracts.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Update python_uv pre-commit template entry to uvx engineeringagent

Change the python_uv scaffold template so it can work in adopters' repos without
a local engineeringagent package.

## ST-002 Add ruff isolated gate to python_uv scaffolded gates.yaml

Ensure the python_uv scaffolded precommit profile runs ruff base checks without
requiring repo configuration by using `--isolated`.

## ST-003 Scaffold commit-msg validator for python_uv pre-commit hook

The python_uv scaffold includes a commit-msg hook. Ensure the referenced
 validator script is actually scaffolded and does not require importing
 engineeringagent from the target repo's environment.

## ST-004 Update README python_uv section and run guidance

Bring README statements in sync with current python_uv scaffold behavior
 (ruff gate + precommit profile wiring) and clarify non-dry `engineeringagent run`
 guidance when OpenCode is not configured.

## ST-006 Remove subprocess usage from scaffolded commit-msg validator

The scaffolded commit-msg validator is shipped as a Python file under src/engineeringagent/scaffold_templates and is scanned by the repository's subprocess-boundary fitness rule. Keep the validator subprocess-free while preserving commit-msg hook behavior.

## ST-005 Align uv-llms reference with scaffolded precommit gates

Update docs/references/uv-workflow.md so precommit profile descriptions
 match init slim outputs (core: spec gate only; python_uv: spec + ruff; no pyright).

## ST-007 Simplify python_uv scaffold implementation

Refactor-only cleanup suggested by code_simplifier: remove duplicate python_uv checks, keep the loop monkeypatch seam lightweight, and build the commit-msg regex from ALLOWED_COMMIT_TYPES.
