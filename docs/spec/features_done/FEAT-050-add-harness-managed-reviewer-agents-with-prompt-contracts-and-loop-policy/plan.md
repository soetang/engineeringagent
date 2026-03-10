---
plan_id: FEAT-050
feature_id: FEAT-050
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Add strict reviewer contract models and validator wiring
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_contract.py
  - uv run pytest -q tests/test_validator.py
- id: ST-002
  title: Add reviewer config loader and planner with phase and on-change matching
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_runtime.py::test_plan_reviewers_by_phase_and_change_selectors
  - uv run pytest -q tests/test_reviewers_runtime.py::test_plan_reviewers_reports_deterministic_skip_reasons
- id: ST-003
  title: Implement harness prompt loading and shared OpenCode reviewer runner
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_runtime.py::test_run_reviewer_loads_harness_prompt_and_parses_decision
  - uv run pytest -q tests/test_reviewers_runtime.py::test_run_reviewer_parse_failure_returns_request_changes
- id: ST-004
  title: Add approval-state persistence and first-approval reuse invalidation logic
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_state.py
- id: ST-005
  title: Integrate reviewer phase into loop iteration with blocking and advisory policy
  status: done
  verification:
  - uv run pytest -q tests/test_loop_reviewers.py::test_blocking_reviewer_requests_retry_and_sets_feedback
  - uv run pytest -q tests/test_loop_reviewers.py::test_advisory_reviewer_records_warning_without_blocking
  - uv run pytest -q tests/test_loop_reviewers.py::test_advisory_feedback_requires_one_followup_implement_pass
- id: ST-006
  title: Implement retry and exhausted-policy behavior for blocking reviewers
  status: done
  verification:
  - uv run pytest -q tests/test_loop_reviewers.py::test_blocking_reviewer_exhausted_continues_with_warning_by_default
  - uv run pytest -q tests/test_loop_reviewers.py::test_blocking_reviewer_exhausted_can_be_configured_to_fail
- id: ST-007
  title: Add temp worktree snapshot sandbox mode for README process reviewers
  status: done
  verification:
  - uv run pytest -q tests/test_reviewers_sandbox.py
- id: ST-008
  title: Add reviewer CLI tooling and scaffold support for custom harness setup
  status: done
  verification:
  - uv run pytest -q tests/test_cli_reviewers.py
  - uv run pytest -q tests/test_init_scaffold.py
- id: ST-009
  title: Add reviewer docs sections and run final contract and loop-fast checks
  status: done
  verification:
  - uv run pytest -q tests/test_validator.py::test_agents_docs_map_extraction_scoped_to_docs_layout_section
  - uvx --from . engineeringagent validate
  - uvx --from . engineeringagent gates run --profile loop_fast
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Add strict reviewer contract models and validator wiring

Define `harness/reviewers.yaml` contract models and surface deterministic validation failures through `engineeringagent validate`.

## ST-002 Add reviewer config loader and planner with phase and on-change matching

Implement runtime loading and deterministic planning decisions using phase trigger, changed paths, and explicit run or skip reasons.

## ST-003 Implement harness prompt loading and shared OpenCode reviewer runner

Load reviewer prompts from harness prompt files, compose execution context, run via shared OpenCode agent, and parse strict decision envelopes.

## ST-004 Add approval-state persistence and first-approval reuse invalidation logic

Persist reviewer approval metadata and invalidate cached approval when scoped changes require re-review.

## ST-005 Integrate reviewer phase into loop iteration with blocking and advisory policy

Execute reviewer phase after gates and before completion commit, map blocking/advisory outcomes into retry flow and hook feedback semantics, and enforce one required implement follow-up pass after advisory advice.

## ST-006 Implement retry and exhausted-policy behavior for blocking reviewers

Enforce max retry handling and continue-on-exhausted warning behavior with deterministic telemetry and next-action semantics.

## ST-007 Add temp worktree snapshot sandbox mode for README process reviewers

Support isolated reviewer execution in temporary snapshot/worktree when configured, scoped for README process checks.

## ST-008 Add reviewer CLI tooling and scaffold support for custom harness setup

Add `reviewers` CLI subcommands (init/list/plan/run) and scaffolded starter config plus prompt examples for easy repository adoption.

## ST-009 Add reviewer docs sections and run final contract and loop-fast checks

Document reviewer contract and workflow in README and agent references in plain English, include explicit policy semantics and examples for advisory and blocking modes, update AGENTS docs map, then run repository validation and loop-fast checks.
