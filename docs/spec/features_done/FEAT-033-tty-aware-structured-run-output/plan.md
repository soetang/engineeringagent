---
plan_id: FEAT-033
feature_id: FEAT-033
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add run-output presentation helper with TTY and no-color detection
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_plain_output_when_not_tty
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_styled_output_when_tty
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_no_color_env_disables_styling
- id: ST-002
  title: Apply structured lifecycle formatting to run loop terminal messages
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_failure_prints_detailed_log_pointer
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_all_selected_feature_moved_to_features_done_continues
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_iteration_output_uses_emoji_contract
- id: ST-003
  title: Preserve ANSI-free file logs and telemetry
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_writes_per_feature_progress_log
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_telemetry_includes_log_path
- id: ST-004
  title: Update run documentation for readability behavior and color fallbacks
  status: done
  verification:
  - python3 -c "from pathlib import Path; t=Path('README.md').read_text(encoding='utf-8').lower();
    assert 'verbose-output' in t and 'no_color' in t; print('ok')"
- id: ST-005
  title: Run focused loop regressions and final loop_fast gate profile
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uv run pytest -q tests/test_loop_opencode_integration.py
  - uvx --from . engineeringagent gates run --profile loop_fast
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add run-output presentation helper with TTY and no-color detection

Implement reusable formatting helpers for lifecycle labels and status tokens, with explicit checks for terminal capability and no-color environment overrides.

## ST-002 Apply structured lifecycle formatting to run loop terminal messages

Route `run` lifecycle prints (precheck, selection, implement step, summary, failure detail, completion) through the new formatter while preserving message intent, and render iteration lines using the canonical emoji-forward contract.

## ST-003 Preserve ANSI-free file logs and telemetry

Ensure styled terminal rendering does not leak into progress log files or runs telemetry payloads.

## ST-004 Update run documentation for readability behavior and color fallbacks

Document the structured output behavior, TTY-aware styling, and how to force plain output.

## ST-005 Run focused loop regressions and final loop_fast gate profile

Validate new output formatting behavior with focused tests and final gate profile used by the run loop workflow.
