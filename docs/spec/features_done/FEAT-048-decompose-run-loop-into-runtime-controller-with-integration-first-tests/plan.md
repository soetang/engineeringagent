---
plan_id: FEAT-048
feature_id: FEAT-048
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Define runtime controller interface and delegation boundaries for run_loop
  status: done
  verification:
  - uv run pytest -q tests/test_loop_contracts.py::test_loop_facade_signatures_remain_stable
- id: ST-002
  title: Move run_loop orchestration sequencing into loop runtime controller
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py
- id: ST-003
  title: Preserve facade compatibility seams and line-budget constraints
  status: done
  verification:
  - uv run pytest -q tests/test_loop_contracts.py
  - uv run python harness/fitness-functions/check_loop_facade_line_budget.py
- id: ST-004
  title: Replace selected internal monkeypatch tests with integration-first controller
    tests
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py
  - uv run pytest -q tests/test_loop_opencode_integration.py
- id: ST-005
  title: Enforce boundary-only mocking policy in updated loop tests
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py tests/test_loop_opencode_integration.py
    tests/test_loop_contracts.py
- id: ST-006
  title: Run full loop-focused regression slice and loop-fast profile
  status: done
  verification:
  - uv run pytest -q tests/test_loop_ralph_mode.py tests/test_loop_opencode_integration.py
    tests/test_loop_contracts.py
  - uvx --from . engineeringagent gates run --profile loop_fast
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Define runtime controller interface and delegation boundaries for run_loop

Establish controller responsibilities and explicit handoff points from facade `run_loop` to runtime orchestration methods.

## ST-002 Move run_loop orchestration sequencing into loop runtime controller

Extract target resolution, dry-run/precondition gates, permission precheck, and iteration sequencing out of facade body while preserving behavior.

## ST-003 Preserve facade compatibility seams and line-budget constraints

Keep stable seams/signatures and ensure loop facade remains under enforced line budget after controller extraction.

## ST-004 Replace selected internal monkeypatch tests with integration-first controller tests

Convert a targeted subset of patch-heavy flow tests into tmp-repo integration tests that assert controller behavior through stable external boundaries.

## ST-005 Enforce boundary-only mocking policy in updated loop tests

Ensure updated tests mock only external/unstable boundaries and avoid introducing new internal control-flow patching.

## ST-006 Run full loop-focused regression slice and loop-fast profile

Validate controller refactor stability across loop behavior and architecture guardrails.
