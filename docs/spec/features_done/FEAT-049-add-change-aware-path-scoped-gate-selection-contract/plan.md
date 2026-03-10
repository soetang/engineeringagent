---
plan_id: FEAT-049
feature_id: FEAT-049
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Extend gate contract for path-scoped selectors and normalized runner metadata
  status: done
  verification:
  - uv run pytest -q tests/test_gates.py::test_load_gate_config_accepts_on_change_selectors
  - uv run pytest -q tests/test_gates.py::test_load_gate_config_accepts_legacy_run_and_structured_command_runner
  - uv run pytest -q tests/test_gates.py::test_load_gate_config_rejects_gate_with_both_run_and_runner
  - uv run pytest -q tests/test_gates.py::test_load_gate_config_rejects_gate_with_neither_run_nor_runner
  - uv run pytest -q tests/test_gates.py::test_load_gate_config_rejects_unknown_gate_fields
  - uv run pytest -q tests/test_gates.py::test_load_gate_config_defaults_missing_contract_version_to_v1
  - uv run pytest -q tests/test_gates.py::test_normalize_gate_runner_maps_legacy_run_to_command_runner
  - uv run pytest -q tests/test_gates.py::test_load_gate_config_rejects_invalid_on_change_selectors
- id: ST-002
  title: Implement deterministic changed-file discovery for base and head inputs
  status: done
  verification:
  - uv run pytest -q tests/test_gates.py::test_collect_changed_paths_supports_base_and_head
  - uv run pytest -q tests/test_gates.py::test_collect_changed_paths_includes_rename_old_and_new
  - uv run pytest -q tests/test_gates.py::test_collect_changed_paths_falls_back_to_run_all_when_diff_fails
- id: ST-003
  title: Add gate planning layer that emits deterministic run or skip decisions
  status: done
  verification:
  - uv run pytest -q tests/test_gates.py::test_plan_profile_emits_gate_decision_reason_envelope
  - uv run pytest -q tests/test_gates.py::test_plan_profile_runs_when_on_change_matches_any_path
  - uv run pytest -q tests/test_gates.py::test_plan_profile_skips_when_on_change_does_not_match
  - uv run pytest -q tests/test_gates.py::test_plan_profile_runs_when_on_change_is_omitted
  - uv run pytest -q tests/test_gates.py::test_plan_profile_reason_always_run_no_on_change
  - uv run pytest -q tests/test_gates.py::test_plan_profile_reason_matched_on_change
  - uv run pytest -q tests/test_gates.py::test_plan_profile_reason_no_on_change_match
  - uv run pytest -q tests/test_gates.py::test_plan_profile_reason_fallback_run_all_change_discovery_failed
- id: ST-004
  title: Wire planner into gates run execution without changing selected gate semantics
  status: done
  verification:
  - uv run pytest -q tests/test_gates.py::test_run_profile_executes_only_planned_run_gates
  - uv run pytest -q tests/test_gates.py::test_run_profile_preserves_fail_fast_for_selected_gates
- id: ST-005
  title: Expose decision interface in CLI for planning and explainability
  status: done
  verification:
  - uv run pytest -q tests/test_gates.py::test_cmd_gates_plan_supports_base_and_head_inputs
  - uv run pytest -q tests/test_gates.py::test_cmd_gates_plan_outputs_deterministic_decisions
  - uv run pytest -q tests/test_gates.py::test_cmd_gates_plan_outputs_decision_reason_enums
  - uv run pytest -q tests/test_gates.py::test_cmd_gates_run_supports_base_head_and_explain_output
  - uv run pytest -q tests/test_gates.py::test_cmd_gates_run_explain_prints_planner_decisions_before_execution
- id: ST-006
  title: Update default gate examples and regressions for spec-only versus code-change
    behavior
  status: done
  verification:
  - uv run pytest -q tests/test_gates.py
  - uv run pytest -q tests/test_cli.py
  - uvx --from . engineeringagent validate
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Extend gate contract for path-scoped selectors and normalized runner metadata

Add strict contract fields for optional `on_change` selectors and runner metadata while preserving legacy `run` compatibility and clear validation errors.

## ST-002 Implement deterministic changed-file discovery for base and head inputs

Add change-set collection that supports explicit `--base` and `--head`, includes rename old and new paths, and supports safe fallback when diff resolution fails.

## ST-003 Add gate planning layer that emits deterministic run or skip decisions

Evaluate profile gates against changed paths before execution and produce concise machine-parse-friendly decision and reason entries.

## ST-004 Wire planner into gates run execution without changing selected gate semantics

Ensure `gates run` executes only `run` decisions, preserves order, and keeps fail-fast behavior and output contracts for executed gates.

## ST-005 Expose decision interface in CLI for planning and explainability

Add CLI inputs for explicit change-set boundaries and a deterministic way to inspect run or skip decisions before execution.

## ST-006 Update default gate examples and regressions for spec-only versus code-change behavior

Demonstrate path-scoped gate intent in `harness/gates.yaml` and add regression coverage proving spec-only change sets skip unrelated heavyweight gates.
