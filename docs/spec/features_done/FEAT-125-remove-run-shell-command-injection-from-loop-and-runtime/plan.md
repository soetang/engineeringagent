---
plan_id: FEAT-125
feature_id: FEAT-125
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove loop verification runner dependency model and wiring
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_runtime_iteration.py tests/loop/test_loop_output.py
    tests/loop/test_loop_phases_coverage.py
- id: ST-002
  title: Make verification phase own execution wiring internally
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_phases_coverage.py tests/loop/test_loop_ralph_mode.py
- id: ST-003
  title: Remove command-runner argument from checks command runtime
  status: done
  verification:
  - uv run pytest -q tests/checks/test_commands_runtime.py tests/checks/test_commands_group_port.py
    tests/checks/test_run_checks_contract.py tests/harness/test_checks_runtime.py
- id: ST-004
  title: Update tests for module-owned execution seams
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_ralph_mode.py tests/checks/test_commands_runtime.py
- id: ST-005
  title: Run full regression and repository validation
  status: done
  verification:
  - uv run pytest -q
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove loop verification runner dependency model and wiring

Delete loop-owned `run_shell_command` import/wiring and remove verification dependency threading from iteration pipeline contracts.

## ST-002 Make verification phase own execution wiring internally

Refactor verification phase to execute commands through internal module-owned wiring and keep orchestration contracts free of execution callables.

## ST-003 Remove command-runner argument from checks command runtime

Update `run_planned_command_checks(...)` and checks API call sites so command runtime owns shell execution internally.

## ST-004 Update tests for module-owned execution seams

Replace argument-injection/loop-module patch patterns with module-level monkeypatch seams that match the new ownership boundary.

## ST-005 Run full regression and repository validation

Confirm no behavior drift after boundary simplification and contract cleanup.
