---
plan_id: FEAT-022
feature_id: FEAT-022
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add Pyright tooling and baseline config
  status: done
  verification:
  - uv sync
  - uv run pyright --version
- id: ST-002
  title: Add precommit Pyright gate wiring
  status: done
  verification:
  - uvx --from . engineeringagent gates list
  - uvx --from . engineeringagent gates run --profile precommit
- id: ST-003
  title: Align type annotations for configured scope
  status: done
  verification:
  - uv run pyright src/engineeringagent tests harness
- id: ST-004
  title: Extend gate and scaffold regression tests
  status: done
  verification:
  - uv run pytest -q tests/test_gates.py
  - uv run pytest -q tests/test_init_command.py
- id: ST-005
  title: Update contributor workflow documentation
  status: done
  verification:
  - uv run pytest -q tests/test_gates.py::test_scaffolded_gates_config_has_expected_commands
  - uvx --from . engineeringagent gates run --profile precommit
- id: ST-006
  title: Run focused validation for spec and harness gates
  status: done
  verification:
  - uvx --from . engineeringagent validate
  - uv run pytest -q tests/test_gates.py tests/test_init_command.py
  - uv run pyright src/engineeringagent tests harness
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add Pyright tooling and baseline config

Introduce Pyright dependency and repository config with basic mode and explicit include scope for package, tests, and harness paths.

## ST-002 Add precommit Pyright gate wiring

Register `pyright_validate` command and include it in precommit profile in both checked-in gate config and scaffolded default gate configuration.

## ST-003 Align type annotations for configured scope

Resolve or constrain baseline type issues so Pyright passes in configured coverage scope without introducing strict-mode requirements.

## ST-004 Extend gate and scaffold regression tests

Update and add tests that verify pyright gate registration, scaffolded defaults, and profile behavior remain stable.

## ST-005 Update contributor workflow documentation

Update docs that describe local quality checks so Pyright is part of the standard precommit workflow narrative and command references.

## ST-006 Run focused validation for spec and harness gates

Run targeted validation and test commands to confirm contract compliance and gate behavior before marking the feature ready for execution loops.
