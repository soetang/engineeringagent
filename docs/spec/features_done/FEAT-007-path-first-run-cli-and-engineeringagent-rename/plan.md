---
plan_id: FEAT-007
feature_id: FEAT-007
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define and implement top-level run CLI contract
  status: done
  verification:
  - uv run engineeringagent --help
  - uv run engineeringagent run --help
- id: ST-002
  title: Switch loop selection from feature ID to explicit file path
  status: done
  verification:
  - uv run engineeringagent run docs/spec/features/FEAT-003-back-pressure-and-verification-pipeline.yaml
    --dry-run --skip-implement
  - uv run engineeringagent run docs/spec/features/FEAT-003-back-pressure-and-verification-pipeline.yaml
    docs/spec/features/FEAT-004-ralph-loop-opencode-mode.yaml --dry-run --skip-implement
  - uv run engineeringagent validate
- id: ST-003
  title: Perform full package and module rename to engineeringagent
  status: done
  verification:
  - uv run python -c "import engineeringagent.cli; print('ok')"
  - uv run pytest -q
- id: ST-004
  title: Update scripts and docs to hard-cutover command examples
  status: done
  verification:
  - uv run python scripts/validate_specs.py
  - uv run engineeringagent run docs/spec/features/FEAT-003-back-pressure-and-verification-pipeline.yaml
    --dry-run --skip-implement
- id: ST-005
  title: Add CLI contract tests for path-first run behavior
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define and implement top-level run CLI contract

Flatten run ergonomics so users call `engineeringagent run <feature-spec-path> [feature-spec-path ...]` without loop nesting and without feature-id flags.

Attempts: 0

## ST-002 Switch loop selection from feature ID to explicit file path

Update run execution to resolve provided spec file path(s), load those features, and use feature `id` values only for telemetry/reporting.

Attempts: 0

## ST-003 Perform full package and module rename to engineeringagent

Rename pyproject package metadata, script entrypoint, source package directory, and import references from `agent_harness` to `engineeringagent`.

Attempts: 0

## ST-004 Update scripts and docs to hard-cutover command examples

Replace old command references and examples so quickstart, wrappers, and references consistently use the new run contract.

Attempts: 0

## ST-005 Add CLI contract tests for path-first run behavior

Cover parser behavior and loop selection using one or many feature file paths, including invalid path handling and removal of legacy id-based invocation.

Attempts: 0
