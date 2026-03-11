---
plan_id: FEAT-082
feature_id: FEAT-082
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Create engineeringagent.progress package and move helper modules
  status: done
  verification:
  - uv run ruff check src/engineeringagent
  - uv run pyright src/engineeringagent tests harness
- id: ST-002
  title: Update imports in loop runtime and reviewers
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_output.py tests/reviewers/test_reviewers_state.py
    tests/meta/test_progress_import_paths.py
- id: ST-003
  title: Update harness progress locality rule for new canonical module path
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
  - uv run pytest -q tests/fitness/test_fitness_rules_logging_path_locality.py
- id: ST-004
  title: Update any remaining references and regressions
  status: done
  verification:
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Create engineeringagent.progress package and move helper modules

Introduce `src/engineeringagent/progress/__init__.py`, move path helpers to
`paths.py` and write helpers to `logging.py`.

## ST-002 Update imports in loop runtime and reviewers

Update `engineeringagent.loop_runtime.telemetry` and `engineeringagent.reviewers`
to import progress helpers from the new subpackage.

## ST-003 Update harness progress locality rule for new canonical module path

Update `harness/fitness_functions/check_progress_log_locality.py` to allowlist
`src/engineeringagent/progress/paths.py` and update remediation text to refer to
`engineeringagent.progress.paths` and `engineeringagent.progress.logging`.

## ST-004 Update any remaining references and regressions

Update any tests or docs that reference the old progress helper module names,
and confirm no regressions in progress path literal enforcement.
