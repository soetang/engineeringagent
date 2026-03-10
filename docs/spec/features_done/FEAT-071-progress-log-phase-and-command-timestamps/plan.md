---
plan_id: FEAT-071
feature_id: FEAT-071
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add per-phase timestamp capture and render into feature progress log
  status: done
  verification:
  - uv run pytest -q tests/test_loop_output.py tests/test_loop_runtime_iteration.py
- id: ST-002
  title: Add per-command timestamps for gate execution
  status: done
  verification:
  - uv run pytest -q tests/test_gates.py tests/test_loop_ralph_mode.py
- id: ST-003
  title: Add per-command timestamps for verification execution
  status: done
  verification:
  - uv run pytest -q tests/test_loop_output.py
- id: ST-004
  title: Add per-reviewer timestamps for reviewer execution
  status: done
  verification:
  - uv run pytest -q tests/test_loop_reviewers.py
- id: ST-005
  title: Add slowest summary line and deterministic tests
  status: done
  verification:
  - uv run pytest -q tests/test_loop_output.py
- id: ST-006
  title: Improve precondition hint when not in a git repo
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_requires_git_repo_before_allow_dirty_hint
- id: ST-007
  title: README onboarding fixes from review feedback
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
- id: ST-008
  title: Refactor loop facade to satisfy line budget fitness rule
  status: done
  verification:
  - uv run pytest -q tests/test_loop_contracts.py::test_loop_facade_line_budget_enforced
  - uv run python -m engineeringagent.cli fitness run --format json
- id: ST-009
  title: Add per-command timestamps for implement execution
  status: done
  verification:
  - uv run pytest -q tests/test_loop_runtime_iteration.py::test_iteration_pipeline_records_phase_timings
- id: ST-010
  title: Centralize UTC timestamp formatting helper
  status: done
  verification:
  - uv run pytest -q tests/test_loop_runtime_time_format.py
  - uv run pytest -q tests/test_loop_output.py tests/test_loop_runtime_iteration.py
- id: ST-011
  title: Refactor telemetry timing formatters to avoid duplication
  status: done
  verification:
  - uv run pytest -q tests/test_loop_output.py
- id: ST-012
  title: Simplify gate timing_hook plumbing
  status: done
  verification:
  - uv run pytest -q tests/test_gates.py
- id: ST-013
  title: Improve timing model ordering for readability
  status: done
  verification:
  - uv run pytest -q tests/test_loop_output.py
- id: ST-014
  title: Fix reviewer prompt typos (readme_process)
  status: done
  verification:
  - uv run pytest -q tests/test_repo_readme_process_reviewer_activation.py
- id: ST-015
  title: Clamp timing end timestamps to avoid negative wall-clock ranges
  status: done
  verification:
  - uv run pytest -q tests/test_loop_runtime_iteration.py::test_timed_phase_clamps_ended_at_when_clock_skews_backwards
    tests/test_loop_output.py::test_verification_command_timing_clamps_ended_at_when_clock_skews_backwards
    tests/test_loop_reviewers.py::test_reviewer_command_timing_clamps_ended_at_when_clock_skews_backwards
- id: ST-016
  title: Remove duplicate git status invocation in loop preconditions
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py::test_run_loop_requires_git_repo_before_allow_dirty_hint
    tests/test_loop_ralph_mode.py::test_enforce_worktree_precondition_reads_git_status_once
- id: ST-017
  title: Tighten telemetry formatter typing and simplify slowest selection
  status: done
  verification:
  - uv run pytest -q tests/test_loop_output.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add per-phase timestamp capture and render into feature progress log

Extend the iteration pipeline + telemetry writer to capture major phase
boundaries with `started_at`/`ended_at` and computed `duration_sec`, and render
them into the feature progress log (additive to existing markers).

## ST-002 Add per-command timestamps for gate execution

Instrument gate execution so each executed gate command records
`started_at`/`ended_at`/`duration_sec` and is included in the gate output that
is persisted into the feature progress log.

## ST-003 Add per-command timestamps for verification execution

Instrument verification command execution so each verification command record
includes `started_at`/`ended_at`/`duration_sec` in the verification output that
is persisted into the feature progress log.

## ST-004 Add per-reviewer timestamps for reviewer execution

Instrument reviewer runs so each reviewer execution record includes
`started_at`/`ended_at`/`duration_sec` for the reviewer id, and ensure this
timing is included in the reviewer output persisted to the feature progress log.

## ST-005 Add slowest summary line and deterministic tests

Compute the longest single duration among phase and per-command timings and
render the `slowest=...` summary line. Add tests that stub time sources so the
output is deterministic.

## ST-006 Improve precondition hint when not in a git repo

When `engineeringagent run ...` is executed outside a git repository, the loop
currently emits a misleading hint to re-run with `--allow-dirty`. Improve the
precondition hint so it points the user to `git init` (and ensure the
allow-dirty hint is only used for the dirty-worktree case).

## ST-007 README onboarding fixes from review feedback

Address reviewer feedback for README-driven first-run onboarding:
- include a minimal example feature YAML that passes the feature schema
- document that non-dry `run` requires a git repo and (by default) a clean worktree
- document the default OpenCode implement dependency + first-run alternatives
- clarify what `init` scaffolds vs the recommended `uvx ...` invocation

## ST-008 Refactor loop facade to satisfy line budget fitness rule

The loop facade module must remain <= 650 lines (fitness rule
architecture.loop-facade-line-budget). Reduce non-essential facade surface
text/formatting so feature timing additions do not regress the budget.

## ST-009 Add per-command timestamps for implement execution

Ensure the implement phase records a `command_timing` entry when the
implement command runs (default OpenCode mode and custom `--implement-command`).

## ST-010 Centralize UTC timestamp formatting helper

Deduplicate UTC ISO-8601 formatting so iteration/phases render timing
timestamps from one helper (avoid drift across modules).

## ST-011 Refactor telemetry timing formatters to avoid duplication

Extract shared formatting helpers for phase_timing/command_timing lines
so slowest summary rendering and log line rendering cannot drift.

## ST-012 Simplify gate timing_hook plumbing

Tighten timing_hook control flow and typing in gate execution while
preserving current behavior and output.

## ST-013 Improve timing model ordering for readability

Move PhaseTiming/CommandTiming definitions above their first use in
loop_runtime models.

## ST-014 Fix reviewer prompt typos (readme_process)

Clean up obvious typos/grammar in the readme_process reviewer prompt
(no behavioral change).

## ST-015 Clamp timing end timestamps to avoid negative wall-clock ranges

Ensure phase/command timing records never emit ended_at earlier than
started_at when wall-clock time skews backwards (keep duration_sec computed
from clamped boundaries).

## ST-016 Remove duplicate git status invocation in loop preconditions

Avoid redundant `git status` calls when validating repo/worktree
preconditions; preserve user-facing hints for repo vs dirty-worktree cases.

## ST-017 Tighten telemetry formatter typing and simplify slowest selection

Replace `Any` timing parameters with concrete PhaseTiming/CommandTiming
and simplify slowest summary selection without changing output.
