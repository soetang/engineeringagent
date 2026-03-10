---
plan_id: FEAT-098
feature_id: FEAT-098
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Extend checks CLI with group selection and single-check mode
  status: done
  verification:
  - uv run python -m engineeringagent.cli checks run --phase iteration_end
  - uv run pytest -q
- id: ST-002
  title: Migrate cmd_checks_run to call engineeringagent.checks.run_checks
  status: done
  verification:
  - uv run pytest -q
- id: ST-003
  title: Migrate loop runtime gates + reviewers orchestration to checks.run_checks
  status: done
  verification:
  - uv run pytest -q
- id: ST-004
  title: Remove legacy harness policing from engineeringagent validate
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q
- id: ST-005
  title: Remove production imports of legacy checks entrypoints
  status: done
  verification:
  - uv run pytest -q
- id: ST-006
  title: Fix ruff lint in legacy compatibility wrappers
  status: done
  verification:
  - uv run ruff check src/engineeringagent harness
- id: ST-007
  title: Fix pyright typing for legacy compatibility wrappers
  status: done
  verification:
  - uv run pyright src/engineeringagent tests harness
- id: ST-008
  title: Address checks migration reviewer feedback
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Extend checks CLI with group selection and single-check mode

Update Typer wiring for `engineeringagent checks run` to accept repeatable `--checks`, plus optional `--check-id` and `--feature-path` (required when reviewers group selected). Keep default behavior unchanged when `--checks` is omitted.

## ST-002 Migrate cmd_checks_run to call engineeringagent.checks.run_checks

Replace `cmd_checks_run` internals with a call to `engineeringagent.checks.run_checks(...)`, wiring `run_shell_command` and `start_agent` from `engineeringagent.opencode.client`. Preserve output + exit-code semantics.

## ST-003 Migrate loop runtime gates + reviewers orchestration to checks.run_checks

Update `engineeringagent.loop_runtime.phases` to call `engineeringagent.checks.run_checks(...)` for: - gate phase: groups ['commands','fitness'] at iteration_end (and feature_done when archived) - reviewer phase: group ['reviewers'] at feature_done Preserve retry-feedback behavior and deterministic status fields.

## ST-004 Remove legacy harness policing from engineeringagent validate

Remove the validator failure that triggers when `harness/gates.yaml` or `harness/reviewers.yaml` exist. Validation should remain strict for specs and active contracts, but legacy harness files are not a setup/validate concern after this change.

## ST-005 Remove production imports of legacy checks entrypoints

Ensure production code under `src/engineeringagent/**` no longer imports any of: `engineeringagent.harness_checks_runtime`, `engineeringagent.validator`, or `engineeringagent.reviewers`. Add a pytest guard to prevent regressions.

## ST-006 Fix ruff lint in legacy compatibility wrappers

Address ruff E402 caused by misplaced __future__ imports in legacy wrapper modules. Keep behavior unchanged; wrappers still re-export canonical checks surfaces.

## ST-007 Fix pyright typing for legacy compatibility wrappers

Update legacy wrapper modules to provide explicit re-exports so static type checking passes when tests import legacy symbols. Keep runtime behavior unchanged.

## ST-008 Address checks migration reviewer feedback

Tighten changed-path collector fallback, simplify ChecksRunResult plumbing, normalize CLI --feature-path forwarding, and replace globals().update shims with PEP-562 delegation.
