---
plan_id: FEAT-156
feature_id: FEAT-156
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove changed-path collector signature shim from checks API
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py
- id: ST-002
  title: Remove implement runtime run-agent signature shim
  status: done
  verification:
  - uv run pytest -q tests/loop/test_loop_contracts.py
- id: ST-003
  title: Remove dependent callers and compatibility-only tests
  status: done
  verification:
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/loop/test_loop_contracts.py
- id: ST-004
  title: Run final schema and targeted regressions
  status: done
  verification:
  - uv run engineeringagent validate --schema-only
  - uv run pytest -q tests/checks/test_run_checks_contract.py tests/loop/test_loop_contracts.py
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove changed-path collector signature shim from checks API

Delete helper logic that probes collector signatures and silently falls back to one-arg calls; keep canonical invocation only.

## ST-002 Remove implement runtime run-agent signature shim

Delete run-agent signature probing and legacy fallback invocation; require canonical structured-output call shape.

## ST-003 Remove dependent callers and compatibility-only tests

Update or delete production callsites, fixtures, and tests that depended on removed fallback signatures so only canonical contracts remain.

## ST-004 Run final schema and targeted regressions

Run final targeted regression checks and schema validation to confirm removed compatibility seams are not reintroduced.
