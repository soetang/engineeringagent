---
plan_id: FEAT-019
feature_id: FEAT-019
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add run CLI flag and loop plumbing for output verbosity
  status: done
  verification:
  - uvx --from . engineeringagent run --help
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_cli_run_help_includes_verbose_output_flag
- id: ST-002
  title: Add per-feature detailed progress log writer and ignore rule
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_writes_per_feature_progress_log
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_progress_logs_are_gitignored
- id: ST-003
  title: Capture implement and gate output in concise mode with verbose override
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_concise_mode_hides_raw_implement_and_gate_output
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_verbose_output_streams_raw_implement_and_gate_output
  - uv run pytest -q tests/test_gates.py::test_cmd_gates_run_output_unchanged_when_loop_concise_mode_exists
- id: ST-004
  title: Include log path in telemetry and failure messaging
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_telemetry_includes_log_path
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_failure_prints_detailed_log_pointer
- id: ST-005
  title: Document concise default and verbose-output usage
  status: done
  verification:
  - python3 -c "from pathlib import Path; t=Path('README.md').read_text(encoding='utf-8').lower();
    assert 'verbose-output' in t and 'progress/run-feature-' in t and 'concise' in
    t; print('ok')"
- id: ST-006
  title: Run focused regression and schema checks
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uv run pytest -q tests/test_gates.py
  - uvx --from . engineeringagent validate --schema-only
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add run CLI flag and loop plumbing for output verbosity

Add `--verbose-output` to `engineeringagent run` and thread the setting into loop iteration execution.

## ST-002 Add per-feature detailed progress log writer and ignore rule

Add deterministic log-path resolution for `progress/run-feature-<FEATURE_ID>.txt`, append per-attempt details, and update ignore rules so logs do not appear in commit status.

## ST-003 Capture implement and gate output in concise mode with verbose override

In default mode, suppress raw implement/gate output from terminal and write it to detailed logs. In verbose mode, preserve terminal streaming. Keep gate command behavior unchanged for direct `gates run`.

## ST-004 Include log path in telemetry and failure messaging

Add `log_path` to each runs telemetry record and ensure concise failure output points operators to the detailed file.

## ST-005 Document concise default and verbose-output usage

Update README loop behavior and CLI details to describe concise terminal output, detailed per-feature logs, and `--verbose-output` behavior.

## ST-006 Run focused regression and schema checks

Validate loop output behavior, telemetry changes, and spec schema compatibility after implementing concise output and detailed logs.
