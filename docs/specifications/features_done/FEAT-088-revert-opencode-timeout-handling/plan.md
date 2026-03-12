---
plan_id: FEAT-088
feature_id: FEAT-088
status: done
source_spec: spec.yaml
planning_tier: planned
phases:
- id: ST-001
  title: Remove OpenCode timeout helper/env var and stop passing subprocess timeout
  status: done
  verification:
  - uv run pytest -q tests/test_loop_opencode_integration.py
- id: ST-002
  title: Remove timeout-specific implement messaging and failed_gate classification
  status: done
  verification:
  - uv run pytest -q tests/test_loop_opencode_integration.py
- id: ST-003
  title: Update tests and docs to remove timeout contract
  status: done
  verification:
  - uv run python -m engineeringagent.cli validate
  - uv run pytest -q
- id: ST-004
  title: Decide whether a fitness function is warranted
  status: done
  verification:
  - uv run python -m engineeringagent.cli fitness run --format json
---

# Archived Plan

Generated from the archived flat feature spec during the FEAT-183 bundled-only migration.

## ST-001 Remove OpenCode timeout helper/env var and stop passing subprocess timeout

Revert resolve_opencode_timeout_sec, DEFAULT_OPENCODE_TIMEOUT_SEC, and
OPENCODE_TIMEOUT_ENV from src/engineeringagent/opencode/client.py, and remove
passing timeout=... to subprocess.run.

## ST-002 Remove timeout-specific implement messaging and failed_gate classification

Remove timeout messaging and the TimeoutExpired catch in
src/engineeringagent/loop_runtime/implement.py so timeouts are not a distinct
failed_gate classification.

## ST-003 Update tests and docs to remove timeout contract

Remove or rewrite tests added for the timeout default and timeout telemetry,
and remove README references to ENGINEERINGAGENT_OPENCODE_TIMEOUT_SEC.

## ST-004 Decide whether a fitness function is warranted

Only add a new fitness rule if we want a permanent invariant that forbids
reintroducing OpenCode timeouts. Otherwise, rely on existing tests and review.
