---
plan_id: FEAT-044
feature_id: FEAT-044
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Codify probe success as executable bash viability
  status: done
  verification:
  - uv run pytest -q tests/test_loop_opencode_integration.py::test_evaluate_permission_probe_detects_rejection_signal
- id: ST-002
  title: Make integration fixture permission-viable for default build agent
  status: done
  verification:
  - uv run pytest -q tests/test_loop_opencode_integration.py::test_loop_runs_opencode_integration
- id: ST-003
  title: Strengthen integration assertions around precheck and telemetry
  status: done
  verification:
  - uv run pytest -q tests/test_loop_opencode_integration.py::test_loop_reports_permission_rejection_in_run_telemetry
  - uv run pytest -q tests/test_loop_opencode_integration.py::test_run_loop_exits_before_selection_when_permission_precheck_fails
- id: ST-004
  title: Run full OpenCode integration regression slice
  status: done
  verification:
  - uv run pytest -q tests/test_loop_opencode_integration.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Codify probe success as executable bash viability

Ensure the precheck contract clearly requires that the probe command can be executed, and rejection markers remain first-class failure signals.

## ST-002 Make integration fixture permission-viable for default build agent

Update OpenCode integration test fixture/config generation so the local sandbox mirrors required allow-all behavior for the build agent.

## ST-003 Strengthen integration assertions around precheck and telemetry

Ensure tests assert explicit permission-contract outcomes and avoid indirect assertions that break when precheck exits early.

## ST-004 Run full OpenCode integration regression slice

Validate default, bypass, and remediation paths remain aligned after contract tightening.
