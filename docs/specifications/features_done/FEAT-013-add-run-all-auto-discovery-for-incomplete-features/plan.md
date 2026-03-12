---
plan_id: FEAT-013
feature_id: FEAT-013
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add run CLI input modes for --all and explicit paths
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_cli_run_all_dry_run_skip_implement
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_cli_run_rejects_combined_all_and_paths
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_cli_run_requires_paths_or_all
  - uvx --from . engineeringagent run --help
- id: ST-002
  title: Implement deterministic startup snapshot for --all discovery
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_all_discovers_backlog_and_in_progress_only
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_all_excludes_blocked_and_done_from_startup_snapshot
- id: ST-003
  title: Integrate --all snapshot behavior into dry-run and non-dry loop flow
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_all_exits_zero_when_no_runnable_features
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_all_does_not_include_specs_created_after_startup
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_all_dry_run_reports_snapshot_selection
- id: ST-004
  title: Guard explicit-path mode from regressions
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_cli_run_dry_run_skip_implement_path_first
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_reports_invalid_feature_path
- id: ST-005
  title: Document run --all behavior and deterministic snapshot semantics
  status: done
  verification:
  - python3 -c "from pathlib import Path; t=Path('README.md').read_text(encoding='utf-8').lower();
    assert '--all' in t and 'snapshot' in t and 'blocked' in t; print('ok')"
  - python3 -c "from pathlib import Path; t=Path('docs/references/uv-workflow.md').read_text(encoding='utf-8').lower();
    assert '--all' in t and 'run' in t; print('ok')"
- id: ST-006
  title: Run targeted regression suite for new run mode
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uvx --from . engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add run CLI input modes for --all and explicit paths

Update parser and run command wiring so users can invoke auto-discovery with `--all`, while preserving explicit path mode and providing clear validation errors for invalid input combinations.

## ST-002 Implement deterministic startup snapshot for --all discovery

Add startup resolution for `--all` that discovers active feature files, filters by runnable statuses (`backlog`, `in_progress`), and produces a deterministic fixed candidate set used for the rest of the run.

## ST-003 Integrate --all snapshot behavior into dry-run and non-dry loop flow

Ensure dry-run selection, non-dry iteration, and terminal messaging correctly reflect startup snapshot behavior, including no-work success exits and no mid-run candidate expansion from newly created specs.

## ST-004 Guard explicit-path mode from regressions

Confirm path-first execution still behaves exactly as before so `--all` is purely an additive mode and does not break existing caller workflows.

## ST-005 Document run --all behavior and deterministic snapshot semantics

Update contributor docs to show canonical `run --all` usage, mutual exclusivity rules, blocked-feature exclusion at startup, and one-time snapshot semantics.

## ST-006 Run targeted regression suite for new run mode

Execute focused tests for parser and loop behavior so the new mode is validated with the agreed targeted test depth.
