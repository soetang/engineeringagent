---
plan_id: FEAT-134
feature_id: FEAT-134
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove facade-signature compatibility module and dependent tests/seams
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_contracts.py tests/loop/test_loop_runtime_iteration.py
- id: ST-002
  title: Remove loop alias and unused compatibility parameters
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_contracts.py tests/loop/test_loop_ralph_mode.py
- id: ST-003
  title: Replace private runtime imports with explicit public service seams
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_runtime_iteration.py tests/loop/test_loop_phases_coverage.py
- id: ST-004
  title: Remove dead compatibility code paths and simplify wiring
  status: done
  verification:
  - uv run pytest -q tests/loop tests/harness/test_checks_runtime.py
- id: ST-005
  title: Run final targeted regression suite and validate specs
  status: done
  verification:
  - uv run pytest -q tests/loop tests/cli/test_cli.py
  - uv run engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove facade-signature compatibility module and dependent tests/seams

Delete `loop_runtime/facade_signatures.py`, remove references that only protect shim behavior, delete shim-only tests, and align remaining tests with explicit LoopRun contracts.

## ST-002 Remove loop alias and unused compatibility parameters

Remove `_require_clean_worktree` alias and remove unused compatibility parameters from loop feature-iteration entrypoints.

## ST-003 Replace private runtime imports with explicit public service seams

Export explicit helper/service functions from runtime modules and migrate loop imports to those public seams.

## ST-004 Remove dead compatibility code paths and simplify wiring

Delete dead compatibility-only branches introduced for seam preservation and keep only architecture-aligned runtime wiring.

## ST-005 Run final targeted regression suite and validate specs

Confirm loop cleanup keeps behavior while removing legacy seams.
